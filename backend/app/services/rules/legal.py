"""Land tenure, affidavit and intake-expansion eligibility rules."""
from datetime import date

from ..types import S_FAIL, S_NOT_CHECKED, S_PASS, S_REVIEW
from .engine import CaseFacts, Norms, Outcome, rule


@rule("APH-LAND-01", "Land ownership or lease term", "LAND.L", "land")
def land_tenure(f: CaseFacts, n: Norms) -> Outcome:
    """Owned land passes; leased land needs >= 30-year lease with >= 25 years remaining."""
    if not f.has("land_deed"):
        return Outcome(S_NOT_CHECKED, "Land document not uploaded.")
    kind = f.first("deed_type", "land_deed")
    if kind is None:
        return Outcome(S_REVIEW, "Could not determine whether the land is owned or leased.")
    if kind.value in ("sale", "gift", "conveyance"):
        return Outcome(S_PASS, f"Land held under a registered {kind.value} deed.", [kind.evidence()])
    term = f.first("lease_term_years", "land_deed")
    start = f.first("lease_start_date", "land_deed")
    min_term, min_left = n.get("lease_min_years"), n.get("lease_min_remaining_years")
    if term is None or start is None:
        return Outcome(S_REVIEW, "Lease deed found but the lease term or start date could not be read.", [kind.evidence()])
    elapsed = (f.application_date - date.fromisoformat(start.value)).days / 365.25
    left = term.value - elapsed
    params = {"term": int(term.value), "left": round(left, 1), "min_term": int(min_term), "min_left": int(min_left)}
    ev = [term.evidence(), start.evidence()]
    if term.value < min_term:
        return Outcome(S_FAIL, f"Lease term is {term.value:.0f} years; at least {min_term:.0f} years is required.", ev, params)
    if left < min_left:
        return Outcome(S_FAIL, f"Only {left:.1f} years of the lease remain; at least {min_left:.0f} must remain live.", ev, params)
    return Outcome(S_PASS, f"{term.value:.0f}-year lease with {left:.1f} years remaining.", ev, params)


@rule("APH-AFF-01", "Affidavit notarisation and consistency", "DOC.AFF", "legal", severity="medium")
def affidavit(f: CaseFacts, n: Norms) -> Outcome:
    """Affidavit is notarised and declares the same total intake as the application."""
    if not f.has("affidavit"):
        return Outcome(S_NOT_CHECKED, "Affidavit not uploaded.")
    problems, ev = [], []
    notary = f.first("notarised", "affidavit")
    if not notary:
        problems.append("no notarisation found")
    else:
        ev.append(notary.evidence())
    intake = f.first("requested_intake", "affidavit")
    if intake is None:
        problems.append("declared intake not found")
    else:
        ev.append(intake.evidence())
        if int(intake.value) != f.requested_intake:
            problems.append(f"affidavit declares intake {int(intake.value)} but the application requests {f.requested_intake}")
    if not problems:
        return Outcome(S_PASS, f"Affidavit is notarised and declares intake {f.requested_intake}.", ev)
    status = S_FAIL if any("no notarisation" in p or "declares intake" in p for p in problems) else S_REVIEW
    return Outcome(status, "Affidavit: " + "; ".join(problems) + ".", ev, {"problems": problems})


@rule("APH-EXP-01", "Core branches before expansion", "C2.6c", "eligibility",
      applies_to=["INTAKE_INCREASE"], severity="medium")
def core_branches(f: CaseFacts, n: Norms) -> Outcome:
    """Institution already runs >= 3 core-branch courses (Clause 2.6(c))."""
    courses = f.declared.get("courses", [])
    core = [c["name"] for c in courses if c.get("core") and c.get("existing_intake", c.get("intake", 0)) > 0]
    need = int(n.get("min_core_branches_for_expansion", f.program))
    params = {"core": len(core), "need": need}
    if len(core) >= need:
        return Outcome(S_PASS, f"{len(core)} core branches already offered: {', '.join(core)}.", params=params)
    return Outcome(S_FAIL, f"Only {len(core)} core branch(es) offered ({', '.join(core) or 'none'}); {need} required before expansion.", params=params)


@rule("APH-EXP-02", "Pending inquiry by an investigating agency", "C2.6e", "eligibility",
      applies_to=["INTAKE_INCREASE"])
def no_inquiry(f: CaseFacts, n: Norms) -> Outcome:
    """Increase in intake is barred while a central/state agency inquiry is pending (Clause 2.6(e))."""
    pending_flag = f.first("inquiry_pending", "affidavit")
    if f.declared.get("investigation_pending") or pending_flag:
        return Outcome(S_FAIL, "An inquiry by an investigating agency is declared pending; intake increase is not permitted.",
                       [pending_flag.evidence()] if pending_flag else [])
    clear = f.first("no_inquiry_pending", "affidavit")
    if clear:
        return Outcome(S_PASS, "Affidavit declares that no inquiry is pending.", [clear.evidence()])
    return Outcome(S_REVIEW, "No declaration about pending inquiries found in the affidavit.")
