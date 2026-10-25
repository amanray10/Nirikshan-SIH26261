from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AphNorm, AphRule, User
from ..schemas import AskIn, NormPatch, RulePatch
from ..security import audit, current_user, require
from ..services import retrieval
from ..services.rules.engine import REGISTRY, clause_ref

router = APIRouter(prefix="/api", tags=["aph"])


@router.post("/aph/ask")
def ask(body: AskIn, user: User = Depends(current_user)):
    return retrieval.ask(body.question, body.lang)


@router.get("/aph/search")
def search(q: str, k: int = 5, user: User = Depends(current_user)):
    return retrieval.search(q, min(k, 10))


@router.get("/aph/clauses")
def all_clauses(user: User = Depends(current_user)):
    return [{**c, "ref": clause_ref(c["clause_id"])} for c in retrieval.corpus()]


@router.get("/rules")
def rules(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = {r.rule_code: r for r in db.scalars(select(AphRule))}
    out = []
    for code, r in REGISTRY.items():
        row = rows.get(code)
        out.append({"rule_code": code, "version": r.version, "title": r.title, "clause_ref": clause_ref(r.clause_id),
                    "clause_id": r.clause_id, "category": r.category, "applies_to": r.applies_to,
                    "description": r.description, "enabled": row.enabled if row else True,
                    "effective_from": row.effective_from if row else "2024-04-01"})
    return out


@router.patch("/rules/{code}")
def toggle_rule(code: str, body: RulePatch, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    row = db.scalars(select(AphRule).where(AphRule.rule_code == code)).first()
    if not row:
        raise HTTPException(404, "Unknown rule")
    row.enabled = body.enabled
    audit(db, user, "toggle_rule", "rule", row.id, code=code, enabled=body.enabled)
    db.commit()
    return {"ok": True}


@router.get("/norms")
def norms(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": n.id, "program": n.program, "norm_name": n.norm_name, "value": n.value, "unit": n.unit,
             "clause_ref": n.clause_ref, "edition": n.edition, "source_status": n.source_status, "note": n.note}
            for n in db.scalars(select(AphNorm).order_by(AphNorm.id))]


@router.patch("/norms/{norm_id}")
def edit_norm(norm_id: int, body: NormPatch, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    n = db.get(AphNorm, norm_id)
    if not n:
        raise HTTPException(404, "Unknown norm")
    old = n.value
    n.value = body.value
    if body.source_status:
        n.source_status = body.source_status
    if body.note is not None:
        n.note = body.note
    audit(db, user, "edit_norm", "norm", n.id, name=n.norm_name, old=old, new=body.value)
    db.commit()
    return {"ok": True}
