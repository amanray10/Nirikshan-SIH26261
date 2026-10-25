"""Database schema (project brief section 9). Works on SQLite and MySQL 8."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now():
    return mapped_column(DateTime, server_default=func.now())


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    aicte_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    trust_name: Mapped[str] = mapped_column(String(255), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = _now()
    applications: Mapped[list["Application"]] = relationship(back_populates="institution")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))  # institution | officer | admin
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    created_at: Mapped[datetime] = _now()


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    ref_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))  # EOA | INTAKE_INCREASE | NEW_INSTITUTION
    academic_year: Mapped[str] = mapped_column(String(9))  # e.g. 2026-27
    program: Mapped[str] = mapped_column(String(64), default="UG Engineering & Technology")
    requested_intake: Mapped[int] = mapped_column(Integer, default=0)
    # Values the institution declared on the portal; documents are checked against them.
    declared: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")
    # DRAFT -> SELF_CHECK -> SUBMITTED -> PROCESSING -> UNDER_REVIEW -> DECIDED
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_band: Mapped[str] = mapped_column(String(8), default="")
    decision: Mapped[str] = mapped_column(String(32), default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = _now()
    institution: Mapped[Institution] = relationship(back_populates="applications")
    documents: Mapped[list["Document"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    text_source: Mapped[str] = mapped_column(String(16), default="")  # digital | ocr:tesseract | ...
    status: Mapped[str] = mapped_column(String(16), default="UPLOADED")
    # Per-document authenticity summary with an honest label (what was actually established)
    authenticity: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_at: Mapped[datetime] = _now()
    application: Mapped[Application] = relationship(back_populates="documents")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str] = mapped_column(Text)
    original_text: Mapped[str] = mapped_column(Text, default="")
    page: Mapped[int] = mapped_column(Integer, default=1)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    corrected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)


class FacultyRecord(Base):
    __tablename__ = "faculty_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    dob: Mapped[str] = mapped_column(String(10), default="")
    id_hash: Mapped[str] = mapped_column(String(64), index=True)  # salted SHA-256, never the raw ID
    id_last4: Mapped[str] = mapped_column(String(4), default="")
    qualification: Mapped[str] = mapped_column(String(64), default="")
    designation: Mapped[str] = mapped_column(String(64), default="")
    date_of_joining: Mapped[str] = mapped_column(String(10), default="")
    page: Mapped[int] = mapped_column(Integer, default=1)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)


class MediaHash(Base):
    __tablename__ = "media_hashes"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer, default=1)
    phash: Mapped[str] = mapped_column(String(32), index=True)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(Float, nullable=True)


class AphNorm(Base):
    __tablename__ = "aph_norms"
    id: Mapped[int] = mapped_column(primary_key=True)
    program: Mapped[str] = mapped_column(String(64))
    norm_name: Mapped[str] = mapped_column(String(64), index=True)
    intake_band: Mapped[str] = mapped_column(String(32), default="any")
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="")
    clause_ref: Mapped[str] = mapped_column(String(128), default="")
    edition: Mapped[str] = mapped_column(String(32), default="")
    source_status: Mapped[str] = mapped_column(String(16), default="verified")  # verified | to_verify
    note: Mapped[str] = mapped_column(Text, default="")


class AphRule(Base):
    __tablename__ = "aph_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    clause_ref: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    applies_to: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(32), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    effective_from: Mapped[str] = mapped_column(String(10), default="2024-04-01")
    effective_to: Mapped[str | None] = mapped_column(String(10), nullable=True)


class VerificationRun(Base):
    __tablename__ = "verification_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(16), default="scrutiny")  # scrutiny | selfcheck
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")
    started_at: Mapped[datetime] = _now()
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    tool_log: Mapped[list] = mapped_column(JSON, default=list)
    engines: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("verification_runs.id", ondelete="CASCADE"), index=True)
    rule_code: Mapped[str] = mapped_column(String(32))
    rule_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("verification_runs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(48), index=True)  # rule or check code
    kind: Mapped[str] = mapped_column(String(16))  # FRAUD_SIGNAL | DEFICIENCY | REVIEW_ITEM | VERIFIED | PASS
    severity: Mapped[str] = mapped_column(String(8), default="medium")
    category: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="")  # rules | consistency | history | cross_institution | authenticity
    status: Mapped[str] = mapped_column(String(16), default="")
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    clause_ref: Mapped[str] = mapped_column(String(128), default="")
    clause_id: Mapped[str] = mapped_column(String(32), default="")
    establishes: Mapped[str] = mapped_column(Text, default="")  # honest label: what this check proves
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    related: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN | ACCEPTED | OVERRIDDEN


class OfficerReview(Base):
    __tablename__ = "officer_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    officer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = _now()


class Notice(Base):
    __tablename__ = "notices"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(4))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    created_at: Mapped[datetime] = _now()


class AphChunk(Base):
    __tablename__ = "aph_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    clause_id: Mapped[str] = mapped_column(String(32), index=True)
    edition: Mapped[str] = mapped_column(String(32))
    chapter: Mapped[str] = mapped_column(String(128), default="")
    clause: Mapped[str] = mapped_column(String(64), default="")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    source_status: Mapped[str] = mapped_column(String(16), default="summary")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = _now()
