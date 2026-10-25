"""Request bodies (Pydantic) and response serialisers."""
from pydantic import BaseModel, Field

from .models import Application, Document, Finding, Institution, User


class LoginIn(BaseModel):
    email: str
    password: str


class ApplicationIn(BaseModel):
    type: str = Field(pattern="^(EOA|INTAKE_INCREASE|NEW_INSTITUTION)$")
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    program: str = "UG Engineering & Technology"
    requested_intake: int = Field(ge=0, le=5000)
    declared: dict = {}


class FieldCorrectionIn(BaseModel):
    value: str
    reason: str = ""


class ReviewIn(BaseModel):
    finding_id: int | None = None
    decision: str = Field(pattern="^(ACCEPT|OVERRIDE|APPROVE|REJECT|RECTIFY|REFER_COMMITTEE|SITE_VISIT)$")
    reason: str = ""


class NoticeIn(BaseModel):
    language: str = Field(pattern="^(en|hi)$")
    body: str


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    lang: str = "en"


class RulePatch(BaseModel):
    enabled: bool


class NormPatch(BaseModel):
    value: float
    source_status: str | None = None
    note: str | None = None


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "institution_id": u.institution_id}


def institution_out(i: Institution) -> dict:
    return {"id": i.id, "aicte_id": i.aicte_id, "name": i.name, "state": i.state, "address": i.address,
            "trust_name": i.trust_name, "latitude": i.latitude, "longitude": i.longitude}


def document_out(d: Document) -> dict:
    return {"id": d.id, "category": d.category, "filename": d.filename, "sha256": d.sha256, "page_count": d.page_count,
            "text_source": d.text_source, "status": d.status, "authenticity": d.authenticity or {},
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None}


def application_out(a: Application, counts: dict | None = None) -> dict:
    return {"id": a.id, "ref_no": a.ref_no, "type": a.type, "academic_year": a.academic_year, "program": a.program,
            "requested_intake": a.requested_intake, "declared": a.declared, "status": a.status,
            "risk_score": a.risk_score, "risk_band": a.risk_band, "decision": a.decision,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "institution": institution_out(a.institution) if a.institution else None, "counts": counts or {}}


def finding_out(f: Finding) -> dict:
    params = (f.related or {}).get("params", {})
    related = {k: v for k, v in (f.related or {}).items() if k != "params"}
    return {"finding_id": f"F-{f.id:04d}", "id": f.id, "code": f.code, "kind": f.kind, "severity": f.severity,
            "category": f.category, "source": f.source, "status": f.status, "title": f.title, "summary": f.summary,
            "explanation": f.explanation, "rule_id": f.code if f.source == "rules" else None, "clause_ref": f.clause_ref,
            "clause_id": f.clause_id, "establishes": f.establishes, "evidence": f.evidence_json or [],
            "requires_human_review": f.kind in ("FRAUD_SIGNAL", "DEFICIENCY", "REVIEW_ITEM"),
            "review_status": f.review_status, "params": params, "related": related}
