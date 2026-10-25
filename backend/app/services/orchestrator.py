"""Controlled orchestrator: one planner, a FIXED list of typed tools, a logged trace. No free-form agent loops.

extract_document_fields -> run_aph_rules -> compare_document_fields -> check_history ->
check_cross_institution -> screen_authenticity -> retrieve_aph_clause -> generate_report
"""
import time
import traceback
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (Application, AphNorm, AphRule, Document, ExtractedField, FacultyRecord, Finding, Institution,
                      MediaHash, Notice, RuleEvaluation, VerificationRun)
from ..security import hash_identifier
from . import authenticity, consistency, cross_institution, history, llm, notices, ocr, retrieval, risk
from .extractor import extract_faculty, extract_fields
from .parser import extract_pages, page_count
from .rules.engine import CaseFacts, Norms, clause_ref, clauses, evaluate
from .types import DEFICIENCY, FRAUD, PASS, REVIEW, VERIFIED, FieldValue, FindingData

NUMBER_FIELDS = {"total_built_up_area_sqm", "plot_area_sqm", "built_up_area_sqm", "land_area_acres", "lease_term_years",
                 "requested_intake", "latitude", "longitude"}
BOOL_FIELDS = {"notarised", "no_inquiry_pending", "inquiry_pending", "architect_certified"}

# Related APH clause for findings that are not rule evaluations (shown as "related", not "violated").
RELATED_CLAUSE = {"XIN-FACULTY": "A7.F", "XIN-LOOKALIKE": "A7.F", "XIN-PHOTO": "PEN.F", "XIN-FILE": "PEN.F",
                  "AUT-VISUAL": "PEN.F", "AUT-SIG": "PEN.F", "AUT-QR": "PEN.F", "AUT-META": "PEN.F",
                  "CON-SURVEY": "C2.6b", "CON-ADDRESS": "C2.6b", "CON-TRUST": "C2.6b", "CON-INSTNAME": "C2.6b",
                  "CON-LANDAREA": "LAND.U", "HIS-BUA": "C2.6a", "HIS-SURVEY": "EVC", "HIS-FACULTY": "A7.F",
                  "HIS-LAND": "LAND.U", "GEO-PHOTO": "EVC"}


# ---------------------------------------------------------------- tool 1
def extract_document(db: Session, doc: Document) -> dict:
    """Structured fields from one file, with page, bbox and confidence for every value."""
    path = Path(doc.file_path)
    db.execute(delete(ExtractedField).where(ExtractedField.document_id == doc.id))
    db.execute(delete(FacultyRecord).where(FacultyRecord.document_id == doc.id))
    db.execute(delete(MediaHash).where(MediaHash.document_id == doc.id))
    doc.page_count = page_count(path)
    n_fields = 0
    if doc.category == "campus_photo":
        ph, lat, lon = authenticity.photo_info(path)
        if ph:
            db.add(MediaHash(document_id=doc.id, page=1, phash=ph, gps_lat=lat, gps_lon=lon))
        doc.text_source = "image"
    else:
        pages = extract_pages(path)
        doc.text_source = ",".join(sorted({p.source for p in pages}))
        for fv in extract_fields(pages, doc.category, doc.id):
            db.add(ExtractedField(document_id=doc.id, field_name=fv.field, value=str(fv.value),
                                  original_text=fv.original_text, page=fv.page, bbox=fv.bbox, confidence=fv.confidence))
            n_fields += 1
        if doc.category == "faculty_list":
            for r in extract_faculty(str(path), doc.id):
                raw = r.pop("raw_id")
                db.add(FacultyRecord(application_id=doc.application_id, document_id=doc.id, name=r["name"], dob=r["dob"],
                                     id_hash=hash_identifier(raw) if raw else "", id_last4=raw[-4:] if raw else "",
                                     qualification=r["qualification"], designation=r["designation"],
                                     date_of_joining=r["date_of_joining"], page=r["page"], bbox=r["bbox"]))
                n_fields += 1
    doc.status = "EXTRACTED"
    db.flush()
    return {"document_id": doc.id, "category": doc.category, "fields": n_fields, "text_source": doc.text_source}


def ensure_extracted(db: Session, app: Application, force: bool = False) -> list[dict]:
    out = []
    for doc in app.documents:
        if force or doc.status != "EXTRACTED":
            out.append(extract_document(db, doc))
    return out


# ---------------------------------------------------------------- facts
def build_facts(db: Session, app: Application) -> CaseFacts:
    app_date = app.declared.get("application_date")
    facts = CaseFacts(
        app_type=app.type, program=app.program, requested_intake=app.requested_intake,
        academic_year=app.academic_year, declared=app.declared or {},
        application_date=date.fromisoformat(app_date) if app_date else (app.submitted_at or datetime.now()).date(),
    )
    for doc in app.documents:
        facts.categories.setdefault(doc.category, []).append(doc.id)
        facts.sources[doc.id] = doc.text_source or ""
        rows = db.scalars(select(ExtractedField).where(ExtractedField.document_id == doc.id)).all()
        for r in rows:
            raw = r.corrected_value if r.corrected_value is not None else r.value
            if r.field_name in NUMBER_FIELDS:
                try:
                    val = float(raw)
                except ValueError:
                    continue
            elif r.field_name in BOOL_FIELDS:
                val = raw in ("True", "true", "1", "yes")
                if not val:
                    continue
            else:
                val = raw
            facts.fields.setdefault(r.field_name, []).append(FieldValue(
                r.field_name, val, r.original_text, doc.id, doc.category, r.page, r.bbox,
                1.0 if r.corrected_value is not None else r.confidence, r.id,
                "corrected by officer" if r.corrected_value is not None else ""))
    for fr in db.scalars(select(FacultyRecord).where(FacultyRecord.application_id == app.id)).all():
        facts.faculty.append({"name": fr.name, "dob": fr.dob, "designation": fr.designation,
                              "qualification": fr.qualification, "date_of_joining": fr.date_of_joining,
                              "page": fr.page, "bbox": fr.bbox, "document_id": fr.document_id, "id_hash": fr.id_hash})
    return facts


def load_norms(db: Session) -> Norms:
    rows = db.scalars(select(AphNorm)).all()
    if not rows:
        return Norms.from_file()
    return Norms([{"program": r.program, "norm_name": r.norm_name, "value": r.value, "clause_ref": r.clause_ref} for r in rows])


def previous_application(db: Session, app: Application) -> Application | None:
    return db.scalars(select(Application).where(
        Application.institution_id == app.institution_id, Application.academic_year < app.academic_year,
        Application.status.notin_(["DRAFT"])).order_by(Application.academic_year.desc())).first()


# ---------------------------------------------------------------- explanation
def explain(f: FindingData) -> str:
    if f.kind == FRAUD:
        return (f"{f.summary} This is a fraud signal, not a deficiency: it is escalated for committee review "
                f"rather than sent to the institution as a fix-it item.")
    if f.kind == DEFICIENCY:
        return (f"{f.summary} This is a deficiency under {f.clause_ref}. The institution can rectify it, so it is "
                f"included in the draft rectification notice.")
    if f.kind == REVIEW:
        return f"{f.summary} The system cannot settle this automatically; an officer should look at the evidence and decide."
    if f.kind == VERIFIED:
        return f.summary
    return f.summary


# ---------------------------------------------------------------- main
def run_verification(db: Session, app_id: int, mode: str = "scrutiny", force_extract: bool = False) -> int:
    app = db.get(Application, app_id)
    inst = db.get(Institution, app.institution_id)
    run = VerificationRun(application_id=app.id, mode=mode, status="RUNNING", tool_log=[],
                          engines={"ocr": ocr.available_engine(), "retrieval": retrieval.engine_name(),
                                   "llm": llm.name(), "aph_edition": settings.aph_edition})
    db.add(run)
    if mode == "scrutiny":
        app.status = "PROCESSING"
    db.commit()
    t_start = time.perf_counter()
    log: list[dict] = []

    def tool(name, purpose, fn):
        t0 = time.perf_counter()
        result = fn()
        log.append({"tool": name, "purpose": purpose, "ms": round((time.perf_counter() - t0) * 1000),
                    "output": _summarise(result)})
        return result

    try:
        tool("extract_document_fields", "Structured fields from each file (text layer or OCR)",
             lambda: ensure_extracted(db, app, force_extract))
        facts = build_facts(db, app)
        norms = load_norms(db)
        enabled = {r.rule_code for r in db.scalars(select(AphRule).where(AphRule.enabled.is_(True)))} or None
        evaluations, findings = tool("run_aph_rules", "Execute applicable, versioned APH rules (incl. required documents)",
                                     lambda: evaluate(facts, norms, enabled))
        findings += tool("compare_document_fields", "Cross-document mismatches",
                         lambda: consistency.run(facts, inst.name, inst.trust_name))

        prev = previous_application(db, app)
        def _hist():
            if not prev:
                return []
            ensure_extracted(db, prev)
            pf = build_facts(db, prev)
            return history.run(facts, pf, prev.ref_no, {f["id_hash"] for f in facts.faculty},
                               {f["id_hash"] for f in pf.faculty})
        findings += tool("check_history", "Changes vs the institution's previous application", _hist)
        findings += tool("check_cross_institution", "Shared faculty, reused photos, identical files across institutions",
                         lambda: cross_institution.run(db, app))
        findings += tool("screen_authenticity", "Authenticity levels 1-4 (metadata, visual, signature/QR, issuer mock)",
                         lambda: _authenticity(db, app, facts, norms, inst))
        tool("retrieve_aph_clause", "Attach the supporting APH clause to every finding", lambda: _attach_clauses(findings))
        score, band, parts = tool("generate_report", "Risk score, explanations, bilingual notice draft",
                                  lambda: _report(db, app, inst, run, evaluations, findings))
        app.risk_score, app.risk_band = score, band
        if mode == "scrutiny":
            app.status = "UNDER_REVIEW"
        run.status = "DONE"
    except Exception as exc:
        db.rollback()
        run = db.get(VerificationRun, run.id)
        app = db.get(Application, app_id)
        run.status, run.error = "FAILED", f"{exc}\n{traceback.format_exc()[-1500:]}"
        if mode == "scrutiny":
            app.status = "SUBMITTED"
    run.duration_ms = round((time.perf_counter() - t_start) * 1000)
    run.tool_log = log
    db.commit()
    return run.id


def _summarise(result) -> str:
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], list):
        return f"{len(result[0])} rules evaluated, {len(result[1])} findings"
    if isinstance(result, tuple) and len(result) == 3:
        return f"risk {result[0]:.0f} ({result[1]})"
    if isinstance(result, list):
        kinds = {}
        for r in result:
            k = getattr(r, "kind", None) or ("extracted" if isinstance(r, dict) else "item")
            kinds[k] = kinds.get(k, 0) + 1
        return ", ".join(f"{v} {k}" for k, v in kinds.items()) or "nothing found"
    return str(result)[:120] if result is not None else "ok"


def _authenticity(db: Session, app: Application, facts: CaseFacts, norms: Norms, inst: Institution) -> list[FindingData]:
    out: list[FindingData] = []
    photos = []
    for doc in app.documents:
        path = Path(doc.file_path)
        labels = []
        if doc.category == "campus_photo":
            mh = db.scalars(select(MediaHash).where(MediaHash.document_id == doc.id)).first()
            if mh:
                photos.append((doc.id, doc.filename, mh.gps_lat, mh.gps_lon))
            doc.authenticity = {"label": "Photo: reuse and GPS screened", "level": 2}
            continue
        f_meta = authenticity.metadata_check(path, doc.id, doc.category)
        f_vis = authenticity.visual_check(path, doc.id, doc.category)
        f_sig, sig_label = authenticity.signature_check(path, doc.id, doc.category)
        fields = [fv for vs in facts.fields.values() for fv in vs if fv.document_id == doc.id]
        f_qr, qr_label = authenticity.qr_check(path, doc.id, doc.category, fields)
        out += f_meta + f_vis + f_sig + f_qr
        bad = [f for f in f_vis + f_sig + f_qr if f.kind == FRAUD]
        if bad:
            label = {"label": "Suspicious: " + bad[0].title.lower(), "level": 3 if f_sig or f_qr else 2}
        elif sig_label and "Verified" in sig_label["label"]:
            label = sig_label
        elif qr_label and "Verified" in qr_label["label"]:
            label = qr_label
        elif f_meta:
            label = {"label": "Signs of editing in metadata; not independently verified", "level": 1}
        else:
            label = {"label": "No anomaly detected; not independently verified", "level": 1}
        doc.authenticity = label
    campus = None
    lat, lon = facts.first("latitude", "land_deed"), facts.first("longitude", "land_deed")
    if lat and lon:
        campus = (lat.value, lon.value)
    elif inst.latitude is not None:
        campus = (inst.latitude, inst.longitude)
    out += authenticity.gps_check(photos, campus, norms.get("photo_gps_max_distance_km"))
    return out


def _attach_clauses(findings: list[FindingData]) -> int:
    cl = clauses()
    for f in findings:
        if not f.clause_id:
            cid = RELATED_CLAUSE.get(f.code)
            if cid:
                f.clause_id = cid
                f.clause_ref = "Related: " + clause_ref(cid)
        if f.clause_id in cl:
            f.related = {**f.related, "clause_text": cl[f.clause_id]["text"], "clause_title": cl[f.clause_id]["title"],
                         "clause_status": cl[f.clause_id]["source_status"]}
    return len(findings)


def _report(db: Session, app: Application, inst: Institution, run: VerificationRun, evaluations, findings):
    db.execute(delete(Finding).where(Finding.application_id == app.id))
    db.execute(delete(Notice).where(Notice.application_id == app.id, Notice.status == "DRAFT"))
    for ev in evaluations:
        db.add(RuleEvaluation(application_id=app.id, run_id=run.id, rule_code=ev["rule_code"],
                              rule_version=ev["rule_version"], status=ev["status"], detail=ev["detail"],
                              evidence_json=ev["evidence"]))
    rows = []
    for f in findings:
        row = Finding(application_id=app.id, run_id=run.id, code=f.code, kind=f.kind, severity=f.severity,
                      category=f.category, source=f.source, status=f.status, title=f.title, summary=f.summary,
                      explanation=explain(f), clause_ref=f.clause_ref, clause_id=f.clause_id,
                      establishes=f.establishes, evidence_json=[e.dict() for e in f.evidence],
                      related={**f.related, "params": f.params})
        db.add(row)
        rows.append({"code": f.code, "kind": f.kind, "title": f.title, "summary": f.summary,
                     "clause_ref": f.clause_ref, "params": f.params})
    score, band, parts = risk.score(findings)
    run.engines = {**run.engines, "risk_breakdown": parts}
    drafts = notices.build(app, inst, rows, settings.aph_edition)
    for lang, body in drafts.items():
        db.add(Notice(application_id=app.id, language=lang, body=body, status="DRAFT"))
    db.flush()
    return score, band, parts
