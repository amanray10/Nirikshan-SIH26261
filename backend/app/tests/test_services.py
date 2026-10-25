from datetime import date

from app.services import risk
from app.services.authenticity import haversine_km, noise_inconsistency
from app.services.consistency import run as consistency_run
from app.services.extractor import extract_fields, normalise_qualification, parse_date, parse_number
from app.services.rules import CaseFacts
from app.services.types import FRAUD, REVIEW, FieldValue, FindingData, Line, PageText


def test_parse_date_formats_and_ambiguity():
    assert parse_date("31-03-2027") == ("2027-03-31", 1.0)
    assert parse_date("12 March 2025") == ("2025-03-12", 1.0)
    iso, conf = parse_date("04/05/2026")  # 4 May or 5 April: flagged, not guessed silently
    assert iso == "2026-05-04" and conf < 1


def test_devanagari_digits():
    assert parse_number("४,२००.५० वर्ग मीटर") == 4200.5


def test_label_value_extraction_with_bbox():
    page = PageText(1, 595, 842, [Line("Survey No.: 189 / 6B", [50, 100, 300, 112]),
                                  Line("Total Built-up Area: 10,850.00 Sq.m", [50, 130, 400, 142])], "digital")
    got = {f.field: f for f in extract_fields([page], "building_plan", 7)}
    assert got["survey_number"].value == "189/6B"
    assert got["total_built_up_area_sqm"].value == 10850.0 and got["total_built_up_area_sqm"].bbox == [50, 130, 400, 142]


def test_declaration_spanning_lines():
    page = PageText(1, 595, 842, [Line("I declare that no inquiry by any central or state agency is", [50, 100, 500, 112]),
                                  Line("pending against the institution.", [50, 114, 300, 126])], "digital")
    got = {f.field for f in extract_fields([page], "affidavit", 1)}
    assert "no_inquiry_pending" in got and "inquiry_pending" not in got


def test_qualification_buckets():
    assert normalise_qualification("Ph.D") == "PHD"
    assert normalise_qualification("M.Tech") == "MASTERS"
    assert normalise_qualification("B.Tech") == "BACHELORS"


def _facts(fields):
    f = CaseFacts("EOA", "UG Engineering & Technology", 240, "2026-27", {}, date(2026, 1, 20))
    for x in fields:
        f.fields.setdefault(x.field, []).append(x)
    return f


def test_survey_mismatch_detected():
    f = _facts([FieldValue("survey_number", "189/6B", "189/6B", 1, "land_deed", 1, None, 1),
                FieldValue("survey_number", "189/9", "189/9", 2, "building_plan", 1, None, 1)])
    out = {x.code: x for x in consistency_run(f, "", "")}
    assert out["CON-SURVEY"].kind == REVIEW and out["CON-SURVEY"].severity == "high"


def test_trust_name_probable_match_not_mismatch():
    f = _facts([FieldValue("owner_name", "Sahyadri Education Trust", "", 1, "land_deed", 1, None, 1),
                FieldValue("trust_name", "Sahyadri Educational Trust (Regd.)", "", 2, "affidavit", 1, None, 1)])
    out = {x.code: x for x in consistency_run(f, "", "")}
    assert out["CON-TRUST"].kind != REVIEW or out["CON-TRUST"].severity == "low"


def test_risk_score_is_explained():
    fs = [FindingData("XIN-FACULTY", FRAUD, "t", "s", "high"), FindingData("CON-SURVEY", REVIEW, "t", "s", "high")]
    score, band, parts = risk.score(fs)
    assert score == 36 and band == "HIGH" and parts[0]["code"] == "XIN-FACULTY"


def test_haversine():
    assert 140 < haversine_km(18.52, 73.86, 19.99, 73.79) < 170  # Pune -> Nashik


def test_noise_inconsistency_finds_clean_patch():
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(1)
    arr = np.clip(235 + rng.normal(0, 7, (600, 600)), 0, 255)
    arr[200:260, 200:400] = 246  # pasted, noise-free patch
    regions = noise_inconsistency(Image.fromarray(arr.astype("uint8")))
    assert regions and regions[0][0] <= 216 and regions[0][2] >= 384
    clean = np.clip(235 + rng.normal(0, 7, (600, 600)), 0, 255)
    assert noise_inconsistency(Image.fromarray(clean.astype("uint8"))) == []
