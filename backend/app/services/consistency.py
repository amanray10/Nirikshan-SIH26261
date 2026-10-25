"""Cross-document consistency: the same fact compared across documents with structured data, not LLM guesses.

Three levels: exact match, probable match (both values shown), mismatch. Uncertain cases go to the officer.
"""
import re

from rapidfuzz import fuzz

from .rules.engine import CaseFacts
from .types import PASS, REVIEW, FieldValue, FindingData

ESTABLISHES = "Compares extracted values across documents. A mismatch needs explanation; it is not by itself proof of fraud."

ENTITY_NOISE = r"\b(the|of|and|educational|education|charitable|public|trust|society|foundation|registered|regd|pvt|private|ltd|limited)\b"


def _norm_entity(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(ENTITY_NOISE, " ", re.sub(r"[^\w\s]", " ", str(s).lower()))).strip()


def _norm_addr(s: str) -> str:
    s = str(s).lower()
    for a, b in (("road", "rd"), ("street", "st"), ("district", "dist"), ("taluka", "tal"), ("near", "nr")):
        s = re.sub(rf"\b{a}\b", b, s)
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def _compare(values: list[FieldValue], kind: str) -> tuple[str, float]:
    """Return (level, worst score) across all pairs."""
    worst = 100.0
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            a, b = values[i].value, values[j].value
            if kind == "exact":
                score = 100.0 if str(a) == str(b) else 0.0
            elif kind == "entity":
                score = fuzz.token_set_ratio(_norm_entity(a), _norm_entity(b))
            else:
                score = fuzz.token_set_ratio(_norm_addr(a), _norm_addr(b))
            worst = min(worst, score)
    if worst >= 95:
        return "exact", worst
    if worst >= 82:
        return "probable", worst
    return "mismatch", worst


CHECKS = [
    # code, label, field, categories, comparison, severity on mismatch
    ("CON-SURVEY", "Survey number", "survey_number", ["land_deed", "building_plan", "occupancy_certificate"], "exact", "high"),
    ("CON-ADDRESS", "Campus address", "address", ["land_deed", "building_plan", "occupancy_certificate", "fire_noc"], "address", "medium"),
    ("CON-TRUST", "Trust / society name", None, None, "entity", "high"),
    ("CON-INSTNAME", "Institution name", "institution_name", ["building_plan", "fire_noc", "affidavit"], "entity", "medium"),
]


def run(facts: CaseFacts, institution_name: str, trust_name: str) -> list[FindingData]:
    findings = []
    for code, label, field, cats, kind, sev in CHECKS:
        if code == "CON-TRUST":
            values = [v for v in (facts.first("owner_name", "land_deed"), facts.first("trust_name", "affidavit"),
                                  facts.first("trust_name", "trust_registration")) if v]
            if trust_name:
                values.append(FieldValue("trust_name", trust_name, trust_name, None, "portal", 1, None, 1.0))
        else:
            values = [v for v in (facts.first(field, c) for c in cats) if v]
            if code == "CON-INSTNAME" and institution_name:
                values.append(FieldValue("institution_name", institution_name, institution_name, None, "portal", 1, None, 1.0))
        if len(values) < 2:
            continue
        level, score = _compare(values, kind)
        shown = "; ".join(f"{_where(v)}: “{v.original_text if v.category != 'portal' else v.value}”" for v in values)
        evidence = [v.evidence() for v in values if v.document_id is not None]
        if level == "exact":
            findings.append(FindingData(code, PASS, f"{label} consistent across documents",
                                        f"{label} matches across {len(values)} sources.", "low", "consistency",
                                        "consistency", "PASS", establishes=ESTABLISHES, evidence=evidence))
        elif level == "probable":
            findings.append(FindingData(code, REVIEW, f"{label} differs slightly between documents",
                                        f"Probable match (similarity {score:.0f}%). {shown}.", "low", "consistency",
                                        "consistency", "NEEDS_REVIEW", establishes=ESTABLISHES, evidence=evidence,
                                        params={"label": label, "values": shown}))
        else:
            findings.append(FindingData(code, REVIEW, f"{label} mismatch between documents",
                                        f"{label} does not match: {shown}.", sev, "consistency", "consistency",
                                        "NEEDS_REVIEW", establishes=ESTABLISHES, evidence=evidence,
                                        params={"label": label, "values": shown}))
    # Declared land area vs deed
    declared_land = facts.declared.get("land_area_acres")
    deed_land = facts.first("land_area_acres", "land_deed")
    if declared_land and deed_land and abs(deed_land.value - declared_land) / declared_land > 0.02:
        findings.append(FindingData("CON-LANDAREA", REVIEW, "Declared land area differs from the land deed",
                                    f"Portal declares {declared_land} acres; land deed shows {deed_land.value} acres.",
                                    "medium", "consistency", "consistency", "NEEDS_REVIEW", establishes=ESTABLISHES,
                                    evidence=[deed_land.evidence()],
                                    params={"declared": declared_land, "deed": deed_land.value}))
    return findings


LABELS = {"land_deed": "Land deed", "building_plan": "Building plan", "occupancy_certificate": "Occupancy certificate",
          "fire_noc": "Fire NOC", "affidavit": "Affidavit", "trust_registration": "Trust registration", "portal": "Portal"}


def _where(v: FieldValue) -> str:
    base = LABELS.get(v.category, v.category)
    return base if v.category == "portal" else f"{base} p.{v.page}"
