"""Every APH rule has unit tests (brief: 'Every rule gets a unit test before it is merged')."""
from datetime import date

import pytest

from app.services.rules import REGISTRY, CaseFacts, Norms, evaluate
from app.services.types import DEFICIENCY, FRAUD, FieldValue, S_FAIL, S_NA, S_NOT_CHECKED, S_PASS, S_REVIEW


def fv(field, value, cat, conf=1.0, doc=1):
    return FieldValue(field, value, str(value), doc, cat, 1, [0, 0, 10, 10], conf)


def facts(app_type="INTAKE_INCREASE", intake=300, declared=None, fields=(), cats=(), faculty=None, sources=None):
    f = CaseFacts(app_type=app_type, program="UG Engineering & Technology", requested_intake=intake,
                  academic_year="2026-27", declared=declared or {}, application_date=date(2026, 1, 20))
    for x in fields:
        f.fields.setdefault(x.field, []).append(x)
        f.categories.setdefault(x.category, [x.document_id])
    for c in cats:
        f.categories.setdefault(c, [99])
    f.faculty = faculty or []
    f.sources = sources or {}
    return f


N = Norms.from_file()


def run(code, f):
    return REGISTRY[code].fn(f, N)


def teaching(p, a, s, qual_ok=True):
    rows = [{"designation": "Professor", "qualification": "Ph.D" if qual_ok else "M.Tech", "name": f"P{i}"} for i in range(p)]
    rows += [{"designation": "Associate Professor", "qualification": "Ph.D", "name": f"A{i}"} for i in range(a)]
    rows += [{"designation": "Assistant Professor", "qualification": "M.Tech", "name": f"S{i}"} for i in range(s)]
    return rows


# ---- documents
def test_required_documents_missing():
    out = run("APH-DOC-01", facts(cats=["land_deed", "building_plan"]))
    assert out.status == S_FAIL and out.params["count"] == 6


def test_required_documents_complete():
    cats = ["land_deed", "occupancy_certificate", "fire_noc", "affidavit", "faculty_list"]
    assert run("APH-DOC-01", facts(app_type="EOA", cats=cats)).status == S_PASS


# ---- built-up area (required = 3000 + 30 * intake with demo norms)
def test_bua_pass():
    assert run("APH-BUA-01", facts(fields=[fv("total_built_up_area_sqm", 12500, "building_plan")])).status == S_PASS


def test_bua_fail_reports_shortfall():
    out = run("APH-BUA-01", facts(fields=[fv("total_built_up_area_sqm", 10850, "building_plan")]))
    assert out.status == S_FAIL and out.params["shortfall"] == 1150 and out.evidence


def test_bua_missing_is_review_not_fail():
    assert run("APH-BUA-01", facts()).status == S_REVIEW


def test_declared_area_small_overstatement_is_deficiency():
    out = run("APH-BUA-02", facts(declared={"built_up_area_sqm": 10500}, fields=[fv("total_built_up_area_sqm", 10000, "building_plan")]))
    assert out.status == S_FAIL and out.kind is None


def test_declared_area_gross_overstatement_is_fraud_signal():
    out = run("APH-BUA-02", facts(declared={"built_up_area_sqm": 12000}, fields=[fv("total_built_up_area_sqm", 10000, "building_plan")]))
    assert out.status == S_FAIL and out.kind == FRAUD


def test_declared_area_within_tolerance():
    out = run("APH-BUA-02", facts(declared={"built_up_area_sqm": 10150}, fields=[fv("total_built_up_area_sqm", 10000, "building_plan")]))
    assert out.status == S_PASS


def test_oc_covers_plan():
    f = facts(fields=[fv("built_up_area_sqm", 8000, "occupancy_certificate"), fv("total_built_up_area_sqm", 10000, "building_plan")])
    assert run("APH-OC-01", f).status == S_FAIL
    f = facts(fields=[fv("built_up_area_sqm", 10000, "occupancy_certificate"), fv("total_built_up_area_sqm", 10000, "building_plan")])
    assert run("APH-OC-01", f).status == S_PASS


def test_architect_registration():
    assert run("APH-PLAN-01", facts(fields=[fv("architect_reg_no", "CA/2004/28588", "building_plan")])).status == S_PASS
    assert run("APH-PLAN-01", facts(cats=["building_plan"])).status == S_FAIL
    assert run("APH-PLAN-01", facts()).status == S_NOT_CHECKED


# ---- fire
def test_fire_valid_and_expired():
    assert run("APH-FIRE-01", facts(fields=[fv("valid_until", "2027-03-31", "fire_noc")])).status == S_PASS
    out = run("APH-FIRE-01", facts(fields=[fv("valid_until", "2025-11-30", "fire_noc")]))
    assert out.status == S_FAIL and out.params["valid_until"] == "30-11-2025"


def test_fire_ambiguous_date_needs_review():
    assert run("APH-FIRE-01", facts(fields=[fv("valid_until", "2027-03-04", "fire_noc", conf=0.7)])).status == S_REVIEW


# ---- faculty (intake 300 -> S = 1200 -> 60 faculty; cadre 6 Prof / 13 Assoc)
def test_fsr_pass_and_fail():
    assert run("APH-FSR-01", facts(cats=["faculty_list"], faculty=teaching(7, 14, 40))).status == S_PASS
    out = run("APH-FSR-01", facts(cats=["faculty_list"], faculty=teaching(7, 14, 30)))
    assert out.status == S_FAIL and out.params["shortfall"] == 9


def test_fsr_reduction_for_low_admissions():
    f = facts(cats=["faculty_list"], faculty=teaching(6, 12, 28), declared={"avg_admission_ratio": 0.45})
    out = run("APH-FSR-01", f)
    assert out.status == S_PASS and out.params["required"] == 45 and out.params["reduced"]


def test_fsr_small_gap_on_scanned_list_is_review():
    f = facts(cats=["faculty_list"], faculty=teaching(7, 14, 38), sources={99: "ocr:tesseract"})
    assert run("APH-FSR-01", f).status == S_REVIEW


def test_declared_faculty_count():
    assert run("APH-FSR-02", facts(cats=["faculty_list"], faculty=teaching(7, 14, 40), declared={"faculty_count": 61})).status == S_PASS
    assert run("APH-FSR-02", facts(cats=["faculty_list"], faculty=teaching(7, 14, 40), declared={"faculty_count": 69})).status == S_FAIL


def test_cadre_ratio_pass_substitution_and_fail():
    assert run("APH-CADRE-01", facts(cats=["faculty_list"], faculty=teaching(6, 13, 41))).status == S_PASS
    assert run("APH-CADRE-01", facts(cats=["faculty_list"], faculty=teaching(3, 16, 41))).status == S_REVIEW
    assert run("APH-CADRE-01", facts(cats=["faculty_list"], faculty=teaching(2, 3, 55))).status == S_FAIL


def test_qualifications():
    assert run("APH-FQ-01", facts(cats=["faculty_list"], faculty=teaching(2, 2, 2))).status == S_PASS
    out = run("APH-FQ-01", facts(cats=["faculty_list"], faculty=teaching(2, 2, 2, qual_ok=False)))
    assert out.status == S_FAIL and out.params["count"] == 2


# ---- land and legal
def test_land_owned():
    assert run("APH-LAND-01", facts(fields=[fv("deed_type", "sale", "land_deed")])).status == S_PASS


def test_land_lease_short():
    f = facts(fields=[fv("deed_type", "lease", "land_deed"), fv("lease_term_years", 30, "land_deed"),
                      fv("lease_start_date", "2003-06-01", "land_deed")])
    out = run("APH-LAND-01", f)
    assert out.status == S_FAIL and out.params["left"] < 25


def test_land_lease_ok():
    f = facts(fields=[fv("deed_type", "lease", "land_deed"), fv("lease_term_years", 99, "land_deed"),
                      fv("lease_start_date", "2011-04-01", "land_deed")])
    assert run("APH-LAND-01", f).status == S_PASS


def test_affidavit_checks():
    ok = facts(fields=[fv("notarised", True, "affidavit"), fv("requested_intake", 300, "affidavit")])
    assert run("APH-AFF-01", ok).status == S_PASS
    bad = facts(fields=[fv("requested_intake", 360, "affidavit")])
    out = run("APH-AFF-01", bad)
    assert out.status == S_FAIL and len(out.params["problems"]) == 2


def test_core_branches():
    courses = [{"name": n, "core": True, "existing_intake": 60} for n in ("CSE", "ME", "CE")]
    assert run("APH-EXP-01", facts(declared={"courses": courses})).status == S_PASS
    assert run("APH-EXP-01", facts(declared={"courses": courses[:2]})).status == S_FAIL


def test_pending_inquiry():
    assert run("APH-EXP-02", facts(fields=[fv("no_inquiry_pending", True, "affidavit")])).status == S_PASS
    assert run("APH-EXP-02", facts(fields=[fv("inquiry_pending", True, "affidavit")])).status == S_FAIL
    assert run("APH-EXP-02", facts()).status == S_REVIEW


# ---- engine
def test_engine_marks_not_applicable_and_maps_kinds():
    evals, findings = evaluate(facts(app_type="EOA", fields=[fv("total_built_up_area_sqm", 5000, "building_plan")]), N)
    by = {e["rule_code"]: e["status"] for e in evals}
    assert by["APH-EXP-01"] == S_NA and by["APH-PLAN-01"] == S_NA
    bua = next(f for f in findings if f.code == "APH-BUA-01")
    assert bua.kind == DEFICIENCY and bua.clause_ref.startswith("APH 2024-27")


@pytest.mark.parametrize("code", list(REGISTRY))
def test_every_rule_cites_a_clause_and_has_docstring(code):
    r = REGISTRY[code]
    assert r.clause_id and r.description, code
