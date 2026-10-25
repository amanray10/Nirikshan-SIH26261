"""Faculty norms: FSR, cadre ratio, qualifications (APH Appendix 7; AICTE 2019 qualification regulations)."""
import math

from ..extractor import normalise_qualification
from ..types import Evidence, S_FAIL, S_NOT_CHECKED, S_PASS, S_REVIEW
from .engine import CaseFacts, Norms, Outcome, rule

TEACHING = {"Professor", "Associate Professor", "Assistant Professor"}


def required_faculty(f: CaseFacts, n: Norms) -> tuple[int, dict]:
    ratio = n.get("faculty_student_ratio", f.program)
    years = n.get("course_duration_years", f.program)
    s_total = f.requested_intake * years
    required = math.ceil(s_total / ratio)
    info = {"S": int(s_total), "ratio": int(ratio), "base_required": required, "reduced": False}
    adm = f.declared.get("avg_admission_ratio")
    if adm is not None and adm <= n.get("faculty_reduction_admission_threshold"):
        required = math.ceil(required * n.get("faculty_reduction_factor"))
        info["reduced"] = True
        info["avg_admission_ratio"] = adm
    info["required"] = required
    return required, info


def _teaching(f: CaseFacts) -> list[dict]:
    return [r for r in f.faculty if r.get("designation") in TEACHING]


def _row_evidence(r: dict, note: str = "") -> Evidence:
    return Evidence(r.get("document_id"), "faculty_list", r.get("page", 1), r.get("bbox"), "faculty_row",
                    r.get("name"), f"{r.get('name')} · {r.get('designation')} · {r.get('qualification')}", note)


@rule("APH-FSR-01", "Faculty strength at faculty-student ratio 1:20", "A7.2", "faculty")
def faculty_ratio(f: CaseFacts, n: Norms) -> Outcome:
    """Number of teaching faculty >= ceil(S / ratio), with the 25% reduction for low admissions."""
    if not f.has("faculty_list"):
        return Outcome(S_NOT_CHECKED, "Faculty list not uploaded.")
    teaching = _teaching(f)
    required, info = required_faculty(f, n)
    params = {**info, "actual": len(teaching)}
    note = " (25% reduction applied for admissions at or below 50%)" if info["reduced"] else ""
    if not teaching:
        return Outcome(S_REVIEW, "No faculty rows could be read from the faculty list.", params=params)
    if len(teaching) >= required:
        return Outcome(S_PASS, f"{len(teaching)} teaching faculty meet the {required} required for S = {info['S']} "
                       f"at 1:{info['ratio']}{note}.", params=params)
    params["shortfall"] = required - len(teaching)
    if f.ocr_sourced("faculty_list") and params["shortfall"] <= 2:
        return Outcome(S_REVIEW, f"{len(teaching)} faculty read from a scanned list against {required} required; the gap of "
                       f"{params['shortfall']} may be an OCR miss. Check the list.", params=params)
    return Outcome(S_FAIL, f"{len(teaching)} teaching faculty against {required} required for S = {info['S']} "
                   f"at 1:{info['ratio']}{note}; shortfall of {required - len(teaching)}.", params=params)


@rule("APH-FSR-02", "Declared faculty count vs faculty list", "C2.6b", "faculty", severity="medium")
def declared_faculty(f: CaseFacts, n: Norms) -> Outcome:
    """Faculty count declared on the portal equals the rows in the uploaded faculty list."""
    declared = f.declared.get("faculty_count")
    if declared is None or not f.has("faculty_list"):
        return Outcome(S_NOT_CHECKED, "Declared faculty count or faculty list not available.")
    actual = len(_teaching(f))
    params = {"declared": declared, "actual": actual}
    if actual >= declared:
        return Outcome(S_PASS, f"Faculty list has {actual} teaching faculty; {declared} declared.", params=params)
    if f.ocr_sourced("faculty_list") and declared - actual <= 2:
        return Outcome(S_REVIEW, f"{declared} declared; {actual} rows read from a scanned list. The difference may be an "
                       "OCR miss; check the list before raising a deficiency.", params=params)
    return Outcome(S_FAIL, f"{declared} faculty declared on the portal but only {actual} appear in the faculty list.", params=params)


@rule("APH-CADRE-01", "Cadre ratio 1:2:6 (Professor : Associate : Assistant)", "A7.C", "faculty", severity="medium")
def cadre_ratio(f: CaseFacts, n: Norms) -> Outcome:
    """Professors >= T/9 and Associates >= 2T/9; Associates may stand in for Professors (officer confirms)."""
    if not f.has("faculty_list"):
        return Outcome(S_NOT_CHECKED, "Faculty list not uploaded.")
    teaching = _teaching(f)
    if not teaching:
        return Outcome(S_REVIEW, "No faculty rows could be read from the faculty list.")
    total, _ = required_faculty(f, n)
    r = n.get("cadre_ratio_R", f.program)
    req_p, req_a = max(1, math.floor(total / r)), math.floor(2 * total / r)
    p = sum(1 for x in teaching if x["designation"] == "Professor")
    a = sum(1 for x in teaching if x["designation"] == "Associate Professor")
    params = {"req_prof": req_p, "req_assoc": req_a, "prof": p, "assoc": a}
    if p >= req_p and a >= req_a:
        return Outcome(S_PASS, f"{p} Professors (need {req_p}) and {a} Associate Professors (need {req_a}).", params=params)
    if p + a >= req_p + req_a:
        return Outcome(S_REVIEW, f"Only {p} Professors against {req_p}; Associate Professors ({a}) cover the gap, which "
                       "Appendix 7 allows when a qualified Professor is unavailable. Officer to confirm.", params=params)
    return Outcome(S_FAIL, f"{p} Professors and {a} Associate Professors against {req_p} and {req_a} required "
                   f"(cadre 1:2:6 on {total} faculty).", params=params)


@rule("APH-FQ-01", "Faculty qualifications by cadre", "FQ.2019", "faculty", severity="medium")
def qualifications(f: CaseFacts, n: Norms) -> Outcome:
    """Assistant Professor: Master's; Associate Professor / Professor: Ph.D."""
    if not f.has("faculty_list"):
        return Outcome(S_NOT_CHECKED, "Faculty list not uploaded.")
    bad = []
    for r in _teaching(f):
        q = normalise_qualification(r.get("qualification", ""))
        need = "PHD" if r["designation"] in ("Professor", "Associate Professor") else "MASTERS"
        ok = q == "PHD" or (need == "MASTERS" and q == "MASTERS")
        if not ok:
            bad.append(r)
    if not bad:
        return Outcome(S_PASS, f"All {len(_teaching(f))} teaching faculty meet the qualification for their cadre.")
    names = ", ".join(f"{r['name']} ({r['designation']}, {r['qualification'] or 'not stated'})" for r in bad[:5])
    more = f" and {len(bad) - 5} more" if len(bad) > 5 else ""
    return Outcome(S_FAIL, f"{len(bad)} faculty below the minimum qualification: {names}{more}.",
                   [_row_evidence(r, "qualification below cadre minimum") for r in bad[:10]],
                   {"count": len(bad), "names": [r["name"] for r in bad]})
