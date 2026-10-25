"""Built-up area, occupancy certificate, building plan and fire-safety rules."""
from datetime import date

from ..types import FRAUD, S_FAIL, S_NOT_CHECKED, S_PASS, S_REVIEW
from .engine import CaseFacts, Norms, Outcome, rule


def required_bua(f: CaseFacts, n: Norms) -> float:
    return n.get("bua_base_sqm", f.program) + n.get("bua_per_intake_sqm", f.program) * f.requested_intake


@rule("APH-BUA-01", "Built-up area for the requested intake", "BUA.T", "infrastructure")
def built_up_area(f: CaseFacts, n: Norms) -> Outcome:
    """Built-up area on the approved plan >= APH requirement for the total requested intake."""
    claimed = f.first("total_built_up_area_sqm", "building_plan") or f.first("built_up_area_sqm", "occupancy_certificate")
    required = required_bua(f, n)
    params = {"required": round(required), "intake": f.requested_intake}
    if claimed is None:
        return Outcome(S_REVIEW, "Built-up area could not be found in the building plan or occupancy certificate.", params=params)
    params["claimed"] = round(claimed.value)
    if claimed.value >= required:
        return Outcome(S_PASS, f"{claimed.value:,.0f} sq.m meets the {required:,.0f} sq.m required for intake {f.requested_intake}.",
                       [claimed.evidence()], params)
    short = required - claimed.value
    params["shortfall"] = round(short)
    return Outcome(S_FAIL, f"Built-up area {claimed.value:,.0f} sq.m is {short:,.0f} sq.m below the {required:,.0f} sq.m "
                   f"required for intake {f.requested_intake}.", [claimed.evidence()], params)


@rule("APH-BUA-02", "Declared built-up area vs approved plan", "C2.6b", "infrastructure")
def declared_area(f: CaseFacts, n: Norms) -> Outcome:
    """Area declared on the portal is supported by the building plan (overstatement check)."""
    declared = f.declared.get("built_up_area_sqm")
    plan = f.first("total_built_up_area_sqm", "building_plan")
    if declared is None or plan is None:
        return Outcome(S_NOT_CHECKED, "Declared or plan built-up area not available for comparison.")
    tol = n.get("declared_vs_document_tolerance_pct") / 100
    params = {"declared": round(declared), "plan": round(plan.value)}
    if plan.value >= declared * (1 - tol):
        return Outcome(S_PASS, f"Declared {declared:,.0f} sq.m is supported by the plan ({plan.value:,.0f} sq.m).", [plan.evidence()], params)
    over = (declared - plan.value) / plan.value * 100
    params["over_pct"] = round(over, 1)
    out = Outcome(S_FAIL, f"Declared {declared:,.0f} sq.m but the approved plan shows {plan.value:,.0f} sq.m "
                  f"({over:.1f}% overstated).", [plan.evidence()], params)
    if over > 10:
        out.kind, out.severity = FRAUD, "high"  # gross overstatement is misrepresentation -> committee
    return out


@rule("APH-OC-01", "Occupancy certificate coverage", "DOC.OC", "infrastructure", severity="medium")
def oc_coverage(f: CaseFacts, n: Norms) -> Outcome:
    """Built-up area certified in the OC is at least the area on the approved plan."""
    oc = f.first("built_up_area_sqm", "occupancy_certificate")
    plan = f.first("total_built_up_area_sqm", "building_plan")
    if not f.has("occupancy_certificate"):
        return Outcome(S_NOT_CHECKED, "Occupancy certificate not uploaded.")
    if oc is None:
        return Outcome(S_REVIEW, "Certified area not found on the occupancy certificate.")
    if plan is None:
        return Outcome(S_PASS, f"Occupancy certificate certifies {oc.value:,.0f} sq.m.", [oc.evidence()])
    tol = n.get("declared_vs_document_tolerance_pct") / 100
    params = {"oc": round(oc.value), "plan": round(plan.value)}
    if oc.value >= plan.value * (1 - tol):
        return Outcome(S_PASS, f"OC certifies {oc.value:,.0f} sq.m, covering the plan's {plan.value:,.0f} sq.m.", [oc.evidence(), plan.evidence()], params)
    return Outcome(S_FAIL, f"OC certifies only {oc.value:,.0f} sq.m of the {plan.value:,.0f} sq.m on the plan; "
                   f"{plan.value - oc.value:,.0f} sq.m is not covered.", [oc.evidence(), plan.evidence()], params)


@rule("APH-PLAN-01", "Building plan certified by a registered architect", "C2.6d", "infrastructure",
      applies_to=["INTAKE_INCREASE", "NEW_INSTITUTION"], severity="medium")
def architect(f: CaseFacts, n: Norms) -> Outcome:
    """Plan carries a Council of Architecture registration number (or licensed surveyor)."""
    if not f.has("building_plan"):
        return Outcome(S_NOT_CHECKED, "Building plan not uploaded.")
    reg = f.first("architect_reg_no", "building_plan")
    if reg:
        return Outcome(S_PASS, f"Plan certified by a CoA-registered architect ({reg.value}).", [reg.evidence()],
                       {"reg": reg.value})
    certified = f.first("architect_certified", "building_plan")
    if certified:
        return Outcome(S_REVIEW, "Plan mentions an architect/surveyor but no CoA registration number was found.", [certified.evidence()])
    return Outcome(S_FAIL, "No Council of Architecture registration or licensed-surveyor certification found on the building plan.")


@rule("APH-FIRE-01", "Fire safety certificate validity", "DOC.FIRE", "safety")
def fire_noc(f: CaseFacts, n: Norms) -> Outcome:
    """Fire NOC valid-until date is on or after the application date."""
    if not f.has("fire_noc"):
        return Outcome(S_NOT_CHECKED, "Fire safety certificate not uploaded.")
    v = f.first("valid_until", "fire_noc")
    if v is None:
        return Outcome(S_REVIEW, "Validity date not found on the fire safety certificate.")
    until = date.fromisoformat(v.value)
    params = {"valid_until": until.strftime("%d-%m-%Y"), "app_date": f.application_date.strftime("%d-%m-%Y")}
    if v.confidence < 1:
        return Outcome(S_REVIEW, f"Validity date '{v.original_text}' is ambiguous (dd/mm vs mm/dd); please confirm.", [v.evidence()], params)
    if until >= f.application_date:
        return Outcome(S_PASS, f"Fire NOC valid until {params['valid_until']}.", [v.evidence()], params)
    return Outcome(S_FAIL, f"Fire NOC expired on {params['valid_until']}, before the application date {params['app_date']}.", [v.evidence()], params)
