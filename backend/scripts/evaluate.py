"""Measure the system against the synthetic ground truth. Only numbers produced here go in the pitch.

    python scripts/evaluate.py      (after scripts/seed.py)

Writes data/evaluation/latest.json (shown in the app's Evaluation page) and prints a summary.
"""
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Application, Document, ExtractedField, FacultyRecord, Finding, Institution, VerificationRun  # noqa: E402
from app.services import retrieval  # noqa: E402

FLAG_KINDS = ("FRAUD_SIGNAL", "DEFICIENCY", "REVIEW_ITEM")
FRAUD_PROBLEMS = {"ghost_faculty", "photo_reuse", "identical_file", "declared_overstated", "tamper_scan", "sig_tamper", "qr_mismatch"}


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return str(v).strip().upper()


def main():
    truth = json.loads((settings.data_dir / "synthetic" / "ground_truth.json").read_text(encoding="utf-8"))
    db = SessionLocal()
    by_aicte = {i.aicte_id: i for i in db.scalars(select(Institution))}

    per_problem = defaultdict(lambda: {"planted": 0, "detected": 0, "kind_ok": 0})
    tp_codes = fp_codes = 0
    false_positives, clean_alarms, missed = [], [], []
    field_total = field_ok = 0
    field_errors = []
    per_field = defaultdict(lambda: [0, 0])
    durations, tool_ms = [], defaultdict(list)
    app_rows = []

    for key, t in truth["applications"].items():
        inst = by_aicte[t["aicte_id"]]
        app = db.scalars(select(Application).where(Application.institution_id == inst.id,
                                                   Application.academic_year == key.split("_")[1])).first()
        fs = db.scalars(select(Finding).where(Finding.application_id == app.id)).all()
        flagged = {f.code: f for f in fs if f.kind in FLAG_KINDS}
        expected, allowed = set(t["expected"]), set(t["allowed"])
        for prob in t["problems"]:
            codes = truth["problems"][prob][0]
            per_problem[prob]["planted"] += 1
            if all(c in flagged for c in codes):
                per_problem[prob]["detected"] += 1
                want = "FRAUD_SIGNAL" if prob in FRAUD_PROBLEMS else None
                if want is None or all(flagged[c].kind == want for c in codes):
                    per_problem[prob]["kind_ok"] += 1
            else:
                missed.append({"application": key, "problem": prob, "expected": codes})
        for code, f in flagged.items():
            if code in expected:
                tp_codes += 1
            elif code not in allowed:
                fp_codes += 1
                false_positives.append({"application": key, "code": code, "kind": f.kind, "summary": f.summary[:160]})
                if t["clean"]:
                    clean_alarms.append({"application": key, "code": code, "summary": f.summary[:160]})
        # field extraction accuracy
        docs = {d.category: d for d in db.scalars(select(Document).where(Document.application_id == app.id))}
        for cat, fields in t["fields"].items():
            d = docs.get(cat)
            if not d:
                continue
            if cat == "faculty_list":
                n = len(db.scalars(select(FacultyRecord).where(FacultyRecord.document_id == d.id)).all())
                ok = n == fields["rows"]
                field_total += 1
                field_ok += ok
                per_field["faculty_list.rows"][0] += ok
                per_field["faculty_list.rows"][1] += 1
                if not ok:
                    field_errors.append({"application": key, "field": "faculty rows", "expected": fields["rows"], "got": n})
                continue
            got = {r.field_name: r.value for r in db.scalars(select(ExtractedField).where(ExtractedField.document_id == d.id))}
            for name, want in fields.items():
                g = got.get(name)
                ok = g is not None and _num(g) == _num(want)
                field_total += 1
                field_ok += ok
                per_field[f"{cat}.{name}"][0] += ok
                per_field[f"{cat}.{name}"][1] += 1
                if not ok:
                    field_errors.append({"application": key, "field": f"{cat}.{name}", "expected": want, "got": g,
                                         "source": d.text_source})
        run = db.scalars(select(VerificationRun).where(VerificationRun.application_id == app.id, VerificationRun.status == "DONE")
                         .order_by(VerificationRun.id.desc())).first()
        if run:
            durations.append(run.duration_ms)
            for tl in run.tool_log:
                tool_ms[tl["tool"]].append(tl["ms"])
        app_rows.append({"application": key, "institution": t["institution"], "clean": t["clean"], "problems": t["problems"],
                         "flagged": sorted(flagged), "risk": app.risk_score, "band": app.risk_band})

    planted = sum(v["planted"] for v in per_problem.values())
    detected = sum(v["detected"] for v in per_problem.values())
    kind_ok = sum(v["kind_ok"] for v in per_problem.values())
    clean_apps = [r for r in app_rows if r["clean"]]

    ext_file = settings.data_dir / "evaluation" / "extraction_times.json"
    ext_times = json.loads(ext_file.read_text()) if ext_file.exists() else {}
    end_to_end = []
    for r, d in zip(app_rows, durations):
        if r["application"] in ext_times:
            end_to_end.append(ext_times[r["application"]] + d)

    # retrieval
    qs = json.loads((settings.data_dir / "aph" / "eval_questions.json").read_text(encoding="utf-8"))["questions"]
    hits1 = hits5 = 0
    rmiss = []
    for q in qs:
        ids = [h["clause_id"] for h in retrieval.search(q["q"], 5)]
        hits1 += ids[:1] == [q["clause"]]
        hits5 += q["clause"] in ids
        if q["clause"] not in ids:
            rmiss.append({"q": q["q"], "want": q["clause"], "got": ids})

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {"applications_scored": len(app_rows), "clean_applications": len(clean_apps),
                    "planted_problems": planted, "problem_types": len(per_problem),
                    "note": "Synthetic dossiers from scripts/generate_synthetic.py; fictional institutions."},
        "detection": {"recall": round(detected / planted, 3) if planted else None,
                      "precision": round(tp_codes / (tp_codes + fp_codes), 3) if tp_codes + fp_codes else None,
                      "detected": detected, "planted": planted, "true_positive_codes": tp_codes, "false_positive_codes": fp_codes,
                      "fraud_vs_deficiency_correct": round(kind_ok / detected, 3) if detected else None},
        "clean_applications": {"count": len(clean_apps), "with_any_flag": len({a["application"] for a in clean_alarms}),
                               "false_alarms": clean_alarms},
        "per_problem": {k: v for k, v in sorted(per_problem.items())},
        "missed": missed, "false_positives": false_positives,
        "extraction": {"accuracy": round(field_ok / field_total, 3) if field_total else None, "correct": field_ok,
                       "total": field_total, "per_field": {k: {"correct": v[0], "total": v[1]} for k, v in sorted(per_field.items())},
                       "errors": field_errors[:40]},
        "retrieval": {"engine": retrieval.engine_name(), "questions": len(qs), "recall_at_1": round(hits1 / len(qs), 3),
                      "recall_at_5": round(hits5 / len(qs), 3), "misses": rmiss,
                      "note": "Team-authored question set; optimistic until tested with officers' real questions."},
        "timing": {"end_to_end_median_s": round(statistics.median(end_to_end) / 1000, 2) if end_to_end else None,
                   "end_to_end_max_s": round(max(end_to_end) / 1000, 2) if end_to_end else None,
                   "median_s": round(statistics.median(durations) / 1000, 2) if durations else None,
                   "mean_s": round(statistics.mean(durations) / 1000, 2) if durations else None,
                   "max_s": round(max(durations) / 1000, 2) if durations else None,
                   "per_tool_mean_ms": {k: round(statistics.mean(v)) for k, v in tool_ms.items()},
                   "note": "End-to-end = reading/OCR of every document plus all checks, single process, on the 2-vCPU cloud machine that ran the seed. Scanned dossiers take longest (OCR)."},
        "officer_minutes_saved": {"status": "not measured",
                                  "protocol": "Time 3 people reviewing 4 dossiers manually vs with Nirikshan (2 each way, swapped); report median minutes per dossier."},
        "applications": app_rows,
    }
    out = settings.data_dir / "evaluation"
    out.mkdir(exist_ok=True)
    (out / "latest.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")

    write_markdown(result)
    print(f"Detection recall    {detected}/{planted} = {result['detection']['recall']}")
    print(f"Precision (codes)   {tp_codes}/{tp_codes + fp_codes} = {result['detection']['precision']}")
    print(f"Fraud-vs-deficiency {result['detection']['fraud_vs_deficiency_correct']}")
    print(f"Clean apps flagged  {result['clean_applications']['with_any_flag']}/{len(clean_apps)}")
    print(f"Field extraction    {field_ok}/{field_total} = {result['extraction']['accuracy']}")
    print(f"Retrieval R@1 {result['retrieval']['recall_at_1']}  R@5 {result['retrieval']['recall_at_5']} ({retrieval.engine_name()})")
    print(f"Timing end-to-end median {result['timing']['end_to_end_median_s']} s, max {result['timing']['end_to_end_max_s']} s; checks only median {result['timing']['median_s']} s")
    if missed:
        print("\nMISSED:")
        for m in missed:
            print("  ", m)
    if false_positives:
        print("\nFALSE POSITIVES:")
        for f in false_positives:
            print("  ", f)
    if field_errors:
        print("\nFIELD ERRORS:")
        for e in field_errors[:40]:
            print("  ", e)
    if rmiss:
        print("\nRETRIEVAL MISSES:")
        for m in rmiss:
            print("  ", m)


def write_markdown(r: dict):
    d, t = r["detection"], r["timing"]
    lines = [
        "# Evaluation", "",
        f"Generated by `scripts/evaluate.py` on {r['generated_at']}. {r['dataset']['note']}", "",
        f"Dataset: {r['dataset']['applications_scored']} current-year applications ({r['dataset']['clean_applications']} clean), "
        f"{r['dataset']['planted_problems']} planted problems of {r['dataset']['problem_types']} types; three institutions' dossiers are fully scanned (OCR path).", "",
        "| Metric | Result |", "| --- | --- |",
        f"| Planted problems caught (recall) | {d['detected']}/{d['planted']} ({d['recall']:.1%}) |",
        f"| Flags that were correct (precision) | {d['true_positive_codes']}/{d['true_positive_codes'] + d['false_positive_codes']} ({d['precision']:.1%}) |",
        f"| Fraud signal vs deficiency classified correctly | {d['fraud_vs_deficiency_correct']:.1%} |",
        f"| Clean applications with any flag | {r['clean_applications']['with_any_flag']}/{r['clean_applications']['count']} |",
        f"| Fields extracted correctly | {r['extraction']['correct']}/{r['extraction']['total']} ({r['extraction']['accuracy']:.1%}) |",
        f"| APH clause retrieval, top-1 / top-5 ({r['retrieval']['questions']} questions, {r['retrieval']['engine']}) | {r['retrieval']['recall_at_1']:.1%} / {r['retrieval']['recall_at_5']:.1%} |",
        f"| Time per dossier, end to end (median / max) | {t.get('end_to_end_median_s')} s / {t.get('end_to_end_max_s')} s |",
        f"| Officer minutes saved | not measured yet |", "",
        "## Caveats", "",
        "- The same team wrote the generator, the extractor and the question set, so these numbers are optimistic. Real dossiers have more varied layouts.",
        f"- Officer time saved: {r['officer_minutes_saved']['protocol']}",
        f"- Timing: {t['note']}", "",
        "## Misses and false flags", "",
    ]
    lines += [f"- Missed: {m['application']} {m['problem']}" for m in r["missed"]] or ["- No planted problem was missed."]
    lines += [f"- False flag: {f['application']} {f['code']} ({f['kind']}): {f['summary']}" for f in r["false_positives"]]
    lines += [f"- Extraction error: {e['application']} {e['field']}: expected {e['expected']}, read {e['got']}" for e in r["extraction"]["errors"]]
    lines += ["", "## Per problem type", "", "| Problem | Caught | Right kind |", "| --- | --- | --- |"]
    lines += [f"| {k} | {v['detected']}/{v['planted']} | {v['kind_ok']}/{v['detected']} |" for k, v in r["per_problem"].items()]
    out = ROOT.parent / "docs" / "EVALUATION.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
