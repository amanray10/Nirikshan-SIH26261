import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Application, Finding, Institution, User, VerificationRun
from ..security import require
from ..services import llm, ocr, retrieval

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
VISIBLE = ("SUBMITTED", "PROCESSING", "UNDER_REVIEW", "DECIDED")


@router.get("/overview")
def overview(academic_year: str | None = None, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    q = select(Application).where(Application.status.in_(VISIBLE))
    if academic_year:
        q = q.where(Application.academic_year == academic_year)
    apps = db.scalars(q).all()
    ids = [a.id for a in apps]
    bands = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for a in apps:
        if a.risk_band in bands:
            bands[a.risk_band] += 1
    kinds = dict(db.execute(select(Finding.kind, func.count()).where(Finding.application_id.in_(ids)).group_by(Finding.kind)).all()) if ids else {}
    top = db.execute(select(Finding.code, Finding.title, func.count()).where(
        Finding.application_id.in_(ids), Finding.kind.in_(["FRAUD_SIGNAL", "DEFICIENCY", "REVIEW_ITEM"]))
        .group_by(Finding.code, Finding.title).order_by(func.count().desc()).limit(8)).all() if ids else []
    durations = [r for (r,) in db.execute(select(VerificationRun.duration_ms).where(
        VerificationRun.application_id.in_(ids), VerificationRun.status == "DONE"))] if ids else []
    return {"applications": len(apps), "by_status": _count(a.status for a in apps), "risk_bands": bands,
            "finding_kinds": kinds, "top_findings": [{"code": c, "title": t, "count": n} for c, t, n in top],
            "avg_processing_s": round(sum(durations) / len(durations) / 1000, 1) if durations else None,
            "academic_years": sorted({a.academic_year for a in db.scalars(select(Application).where(Application.status.in_(VISIBLE)))}, reverse=True)}


def _count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return out


@router.get("/network")
def network(academic_year: str | None = None, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    """National view: institutions linked by shared faculty, reused photos or identical files."""
    q = select(Application, Institution).join(Institution).where(Application.status.in_(VISIBLE))
    if academic_year:
        q = q.where(Application.academic_year == academic_year)
    rows = db.execute(q).all()
    app_ids = {a.id for a, _ in rows}
    nodes = {i.id: {"id": i.id, "name": i.name, "aicte_id": i.aicte_id, "state": i.state, "risk_band": a.risk_band,
                    "risk_score": a.risk_score, "application_id": a.id, "lat": i.latitude, "lon": i.longitude} for a, i in rows}
    edges = {}
    fs = db.execute(select(Finding, Application).join(Application, Finding.application_id == Application.id).where(
        Finding.application_id.in_(app_ids), Finding.code.in_(["XIN-FACULTY", "XIN-PHOTO", "XIN-FILE", "XIN-LOOKALIKE"]))).all()
    for f, a in fs:
        other_app = db.get(Application, (f.related or {}).get("other_application_id", 0))
        if not other_app:
            continue
        key = tuple(sorted((a.institution_id, other_app.institution_id))) + (f.code,)
        e = edges.setdefault(key, {"source": key[0], "target": key[1], "type": f.code, "weight": 0, "detail": f.summary,
                                   "application_id": a.id})
        e["weight"] = max(e["weight"], (f.related or {}).get("params", {}).get("count", 1))
        if other_app.institution_id not in nodes:
            oi = db.get(Institution, other_app.institution_id)
            nodes[oi.id] = {"id": oi.id, "name": oi.name, "aicte_id": oi.aicte_id, "state": oi.state,
                            "risk_band": other_app.risk_band, "risk_score": other_app.risk_score,
                            "application_id": other_app.id, "lat": oi.latitude, "lon": oi.longitude}
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


@router.get("/evaluation")
def evaluation(user: User = Depends(require("officer", "admin"))):
    p = settings.data_dir / "evaluation" / "latest.json"
    if not p.exists():
        return {"available": False, "message": "Run: python scripts/evaluate.py"}
    return {"available": True, **json.loads(p.read_text(encoding="utf-8"))}


@router.get("/engines")
def engines(user: User = Depends(require("officer", "admin"))):
    return {"ocr": ocr.available_engine(), "retrieval": retrieval.engine_name(), "llm": llm.name(),
            "aph_edition": settings.aph_edition, "database": settings.database_url.split(":")[0]}
