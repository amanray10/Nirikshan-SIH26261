from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Document, ExtractedField, User
from ..schemas import FieldCorrectionIn
from ..security import audit, current_user, get_app_or_404, require
from ..services.parser import render_page_png

router = APIRouter(prefix="/api", tags=["documents"])


def _doc(db: Session, doc_id: int, user: User) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    get_app_or_404(db, doc.application_id, user)
    return doc


@router.get("/documents/{doc_id}/page/{n}")
def page_image(doc_id: int, n: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Page image for the evidence viewer. Headers carry the page size in PDF points (bbox coordinate space)."""
    doc = _doc(db, doc_id, user)
    if n < 1 or (doc.page_count and n > doc.page_count):
        raise HTTPException(404, "No such page")
    png, w, h = render_page_png(Path(doc.file_path), n)
    return Response(png, media_type="image/png", headers={"X-Page-Width": str(w), "X-Page-Height": str(h),
                                                          "Access-Control-Expose-Headers": "X-Page-Width, X-Page-Height",
                                                          "Cache-Control": "private, max-age=600"})


@router.get("/documents/{doc_id}/file")
def original(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _doc(db, doc_id, user)
    audit(db, user, "download_original", "document", doc.id)
    db.commit()
    return FileResponse(doc.file_path, filename=doc.filename)


@router.get("/documents/{doc_id}/fields")
def fields(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _doc(db, doc_id, user)
    rows = db.scalars(select(ExtractedField).where(ExtractedField.document_id == doc.id)).all()
    return [{"id": r.id, "field": r.field_name, "value": r.value, "corrected_value": r.corrected_value,
             "original_text": r.original_text, "page": r.page, "bbox": r.bbox, "confidence": r.confidence} for r in rows]


@router.patch("/fields/{field_id}")
def correct_field(field_id: int, body: FieldCorrectionIn, user: User = Depends(require("officer", "admin")),
                  db: Session = Depends(get_db)):
    """Officer corrects an extracted value. The original is kept; re-run verification to apply it."""
    f = db.get(ExtractedField, field_id)
    if not f:
        raise HTTPException(404, "Not found")
    doc = _doc(db, f.document_id, user)
    old = f.corrected_value if f.corrected_value is not None else f.value
    f.corrected_value, f.corrected_by = body.value, user.id
    audit(db, user, "correct_field", "extracted_field", f.id, field=f.field_name, old=old, new=body.value,
          reason=body.reason, application_id=doc.application_id)
    db.commit()
    return {"ok": True, "id": f.id, "value": f.value, "corrected_value": f.corrected_value}
