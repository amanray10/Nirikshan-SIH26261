"""Year-over-year consistency: this year's submission vs the institution's previous application."""
from .rules.engine import CaseFacts
from .types import PASS, REVIEW, FindingData

ESTABLISHES = ("Compares facts with the institution's own previous submission. Changes can be legitimate "
               "(new construction, re-survey); unexplained ones need a closer look.")


def run(cur: CaseFacts, prev: CaseFacts | None, prev_ref: str, cur_ids: set[str], prev_ids: set[str]) -> list[FindingData]:
    if prev is None:
        return []
    out: list[FindingData] = []
    rel = {"previous_application": prev_ref, "previous_year": prev.academic_year}

    def add(code, title, summary, sev, evidence=None, params=None):
        out.append(FindingData(code, REVIEW, title, summary, sev, "history", "history", "NEEDS_REVIEW",
                               establishes=ESTABLISHES, evidence=evidence or [], params=params or {}, related=rel))

    a = cur.first("total_built_up_area_sqm", "building_plan") or cur.first("built_up_area_sqm", "occupancy_certificate")
    b = prev.first("total_built_up_area_sqm", "building_plan") or prev.first("built_up_area_sqm", "occupancy_certificate")
    if a and b and a.value < b.value * 0.98:
        add("HIS-BUA", "Built-up area shrank since last year",
            f"Built-up area fell from {b.value:,.0f} sq.m ({prev.academic_year}) to {a.value:,.0f} sq.m ({cur.academic_year}).",
            "high", [a.evidence()], {"prev": round(b.value), "cur": round(a.value), "prev_year": prev.academic_year})

    a, b = cur.first("survey_number", "land_deed"), prev.first("survey_number", "land_deed")
    if a and b and a.value != b.value:
        add("HIS-SURVEY", "Land survey number changed since last year",
            f"Survey number was {b.original_text} in {prev.academic_year}; now {a.original_text}.", "high", [a.evidence()],
            {"prev": b.original_text, "cur": a.original_text, "prev_year": prev.academic_year})

    a, b = cur.first("land_area_acres", "land_deed"), prev.first("land_area_acres", "land_deed")
    if a and b and abs(a.value - b.value) / b.value > 0.05:
        add("HIS-LAND", "Land area changed since last year",
            f"Land area was {b.value} acres in {prev.academic_year}; now {a.value} acres.", "medium", [a.evidence()])

    nc, np_ = len(cur.faculty), len(prev.faculty)
    if np_ and nc:
        new = cur_ids - prev_ids
        jump = (nc - np_) / np_
        if len(new) >= 10 and len(new) / nc >= 0.4:
            add("HIS-FACULTY", "Large share of faculty are new since last year",
                f"{len(new)} of {nc} faculty were not on last year's list ({np_} faculty in {prev.academic_year}); "
                f"strength changed by {jump:+.0%}.", "high",
                params={"new": len(new), "total": nc, "prev_total": np_, "prev_year": prev.academic_year})
    if not out:
        out.append(FindingData("HIS-OK", PASS, "Consistent with last year's submission",
                               f"Key facts match the {prev.academic_year} application ({prev_ref}).", "low", "history",
                               "history", "PASS", establishes=ESTABLISHES, related=rel))
    return out
