import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..models import Application, Document, FacultyRecord, Finding, RuleEvaluation, User, VerificationRun
from ..schemas import ApplicationIn, application_out, document_out, finding_out
from ..security import audit, current_user, get_app_or_404, require
from ..services.extractor import DOC_CATEGORIES
from ..services.orchestrator import run_verification

router = APIRouter(prefix="/api", tags=["applications"])

ALLOWED = {".pdf": b"%PDF-", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG"}


def finding_counts(db: Session, app_id: int) -> dict:
    rows = db.execute(select(Finding.kind, func.count()).where(Finding.application_id == app_id).group_by(Finding.kind)).all()
    return {k: n for k, n in rows}


@router.get("/applications")
def list_applications(user: User = Depends(current_user), db: Session = Depends(get_db), status: str | None = None,
                      academic_year: str | None = None):
    q = select(Application)
    if user.role == "institution":
        q = q.where(Application.institution_id == user.institution_id)
    else:
        q = q.where(Application.status.notin_(["DRAFT", "SELF_CHECK"]))
    if status:
        q = q.where(Application.status == status)
    if academic_year:
        q = q.where(Application.academic_year == academic_year)
    apps = db.scalars(q.order_by(Application.risk_score.desc(), Application.submitted_at)).all()
    return [application_out(a, finding_counts(db, a.id)) for a in apps]


@router.post("/applications")
def create_application(body: ApplicationIn, user: User = Depends(require("institution")), db: Session = Depends(get_db)):
    app = Application(ref_no=f"TMP-{uuid.uuid4().hex[:8]}", institution_id=user.institution_id, type=body.type,
                      academic_year=body.academic_year, program=body.program, requested_intake=body.requested_intake,
                      declared=body.declared, status="DRAFT")
    db.add(app)
    db.flush()
    app.ref_no = f"APP/{body.academic_year}/{app.id:05d}"
    audit(db, user, "create_application", "application", app.id)
    db.commit()
    return application_out(app)


@router.get("/applications/{app_id}")
def get_application(app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    run = db.scalars(select(VerificationRun).where(VerificationRun.application_id == app.id)
                     .order_by(VerificationRun.id.desc())).first()
    if user.role in ("officer", "admin"):
        audit(db, user, "view_application", "application", app.id)
        db.commit()
    out = application_out(app, finding_counts(db, app.id))
    out["documents"] = [document_out(d) for d in app.documents]
    out["run"] = _run_out(run) if run else None
    return out


@router.post("/applications/{app_id}/submit")
def submit(app_id: int, background: BackgroundTasks, user: User = Depends(require("institution")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    if app.status not in ("DRAFT", "SELF_CHECK"):
        raise HTTPException(400, "Application already submitted")
    if not app.documents:
        raise HTTPException(400, "Upload documents before submitting")
    app.status, app.submitted_at = "SUBMITTED", datetime.now()
    audit(db, user, "submit_application", "application", app.id)
    db.commit()
    background.add_task(_verify_bg, app.id, "scrutiny")
    return application_out(app)


@router.post("/applications/{app_id}/documents")
async def upload(app_id: int, category: str = Form(...), files: list[UploadFile] = File(...),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    if user.role == "institution" and app.status not in ("DRAFT", "SELF_CHECK"):
        raise HTTPException(400, "Application is locked after submission")
    if category not in DOC_CATEGORIES:
        raise HTTPException(400, f"Unknown category; use one of {list(DOC_CATEGORIES)}")
    saved = []
    folder = settings.upload_dir / str(app.id)
    folder.mkdir(parents=True, exist_ok=True)
    for up in files:
        ext = Path(up.filename or "").suffix.lower()
        data = await up.read()
        if ext not in ALLOWED or not data.startswith(ALLOWED[ext]):
            raise HTTPException(400, f"{up.filename}: only PDF, JPG and PNG files with valid content are accepted")
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(400, f"{up.filename}: larger than {settings.max_upload_mb} MB")
        if category != "campus_photo":  # one file per category, re-upload replaces and triggers re-verification
            for old in [d for d in app.documents if d.category == category]:
                db.delete(old)
        dest = folder / f"{uuid.uuid4().hex}{ext}"
        dest.write_bytes(data)
        doc = Document(application_id=app.id, category=category, filename=Path(up.filename).name[:250],
                       file_path=str(dest), sha256=hashlib.sha256(data).hexdigest(), status="UPLOADED")
        db.add(doc)
        db.flush()
        saved.append(doc)
        audit(db, user, "upload_document", "document", doc.id, category=category, sha256=doc.sha256)
    db.commit()
    return [document_out(d) for d in saved]


@router.post("/applications/{app_id}/copy-documents/{src_id}")
def copy_documents(app_id: int, src_id: int, user: User = Depends(require("institution")), db: Session = Depends(get_db)):
    """Re-use the documents of one of the institution's earlier applications (common for Extension of Approval)."""
    app = get_app_or_404(db, app_id, user)
    src = get_app_or_404(db, src_id, user)
    if app.status not in ("DRAFT", "SELF_CHECK"):
        raise HTTPException(400, "Application is locked after submission")
    folder = settings.upload_dir / str(app.id)
    folder.mkdir(parents=True, exist_ok=True)
    have = {d.category for d in app.documents if d.category != "campus_photo"}
    n = 0
    for d in src.documents:
        if d.category in have:
            continue
        data = Path(d.file_path).read_bytes()
        dest = folder / f"{uuid.uuid4().hex}{Path(d.file_path).suffix}"
        dest.write_bytes(data)
        db.add(Document(application_id=app.id, category=d.category, filename=d.filename, file_path=str(dest),
                        sha256=d.sha256, status="UPLOADED"))
        n += 1
    audit(db, user, "copy_documents", "application", app.id, source=src.id, count=n)
    db.commit()
    return {"copied": n}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, user: User = Depends(require("institution")), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    app = get_app_or_404(db, doc.application_id, user)
    if app.status not in ("DRAFT", "SELF_CHECK"):
        raise HTTPException(400, "Application is locked after submission")
    db.delete(doc)
    audit(db, user, "delete_document", "document", doc_id)
    db.commit()
    return {"ok": True}


def _verify_bg(app_id: int, mode: str):
    db = SessionLocal()
    try:
        run_verification(db, app_id, mode)
    finally:
        db.close()


@router.post("/applications/{app_id}/verify")
def verify(app_id: int, background: BackgroundTasks, user: User = Depends(require("officer", "admin")),
           db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    audit(db, user, "start_verification", "application", app.id)
    db.commit()
    background.add_task(_verify_bg, app.id, "scrutiny")
    return {"status": "started", "application_id": app.id}


@router.post("/selfcheck")
def selfcheck(body: dict, user: User = Depends(require("institution")), db: Session = Depends(get_db)):
    """Institution runs the same pipeline before submitting. Nothing is sent to AICTE."""
    app = get_app_or_404(db, int(body.get("application_id", 0)), user)
    if app.status not in ("DRAFT", "SELF_CHECK"):
        raise HTTPException(400, "Self-check is only for unsubmitted applications")
    app.status = "SELF_CHECK"
    db.commit()
    run_id = run_verification(db, app.id, mode="selfcheck", force_extract=True)
    run = db.get(VerificationRun, run_id)
    findings = db.scalars(select(Finding).where(Finding.application_id == app.id)).all()
    # Institutions see their own deficiencies and review items; cross-institution intelligence stays with AICTE.
    visible = [finding_out(f) for f in findings if f.source != "cross_institution"]
    return {"run": _run_out(run), "findings": visible}


@router.get("/runs/{run_id}")
def get_run(run_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    run = db.get(VerificationRun, run_id)
    if not run:
        raise HTTPException(404, "Not found")
    get_app_or_404(db, run.application_id, user)
    return _run_out(run)


def _run_out(run: VerificationRun) -> dict:
    return {"id": run.id, "mode": run.mode, "status": run.status, "duration_ms": run.duration_ms,
            "started_at": run.started_at.isoformat() if run.started_at else None, "tool_log": run.tool_log,
            "engines": run.engines, "error": run.error[:500] if run.error else ""}


@router.get("/applications/{app_id}/findings")
def findings(app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    rows = db.scalars(select(Finding).where(Finding.application_id == app.id)).all()
    order = {"FRAUD_SIGNAL": 0, "DEFICIENCY": 1, "REVIEW_ITEM": 2, "VERIFIED": 3, "PASS": 4}
    sev = {"high": 0, "medium": 1, "low": 2}
    out = [finding_out(f) for f in rows
           if not (user.role == "institution" and f.source == "cross_institution")]
    return sorted(out, key=lambda f: (order.get(f["kind"], 9), sev.get(f["severity"], 9)))


@router.get("/applications/{app_id}/evaluations")
def evaluations(app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    run = db.scalars(select(VerificationRun).where(VerificationRun.application_id == app.id, VerificationRun.status == "DONE")
                     .order_by(VerificationRun.id.desc())).first()
    if not run:
        return []
    rows = db.scalars(select(RuleEvaluation).where(RuleEvaluation.run_id == run.id)).all()
    return [{"rule_code": r.rule_code, "rule_version": r.rule_version, "status": r.status, "detail": r.detail} for r in rows]


@router.get("/applications/{app_id}/faculty")
def faculty(app_id: int, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    rows = db.scalars(select(FacultyRecord).where(FacultyRecord.application_id == app.id)).all()
    return [{"id": r.id, "name": r.name, "dob": r.dob, "id_masked": f"••••••{r.id_last4}", "qualification": r.qualification,
             "designation": r.designation, "date_of_joining": r.date_of_joining, "document_id": r.document_id,
             "page": r.page, "bbox": r.bbox} for r in rows]


@router.get("/document-categories")
def categories():
    from ..services.rules.docs import REQUIRED_DOCUMENTS
    return {"categories": DOC_CATEGORIES, "required": REQUIRED_DOCUMENTS}
