"""Required-document rules."""
from ..extractor import DOC_CATEGORIES
from ..types import S_FAIL, S_PASS
from .engine import CaseFacts, Norms, Outcome, rule

REQUIRED_DOCUMENTS = {
    "EOA": ["land_deed", "occupancy_certificate", "fire_noc", "affidavit", "faculty_list"],
    "INTAKE_INCREASE": ["land_deed", "building_plan", "occupancy_certificate", "fire_noc", "affidavit",
                        "trust_registration", "faculty_list", "campus_photo"],
    "NEW_INSTITUTION": ["land_deed", "building_plan", "occupancy_certificate", "fire_noc", "affidavit",
                        "trust_registration", "faculty_list", "campus_photo"],
}


@rule("APH-DOC-01", "Mandatory documents for this application type", "DOC.INC", "documents")
def required_documents(f: CaseFacts, n: Norms) -> Outcome:
    """Every document category required for the application type is uploaded."""
    required = REQUIRED_DOCUMENTS.get(f.app_type, [])
    missing = [c for c in required if not f.has(c)]
    if missing:
        names = ", ".join(DOC_CATEGORIES[c] for c in missing)
        return Outcome(S_FAIL, f"{len(missing)} mandatory document(s) missing: {names}.",
                       params={"missing": [DOC_CATEGORIES[c] for c in missing], "count": len(missing)})
    return Outcome(S_PASS, f"All {len(required)} mandatory documents for {f.app_type.replace('_', ' ').title()} are present.")
