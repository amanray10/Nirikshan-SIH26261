"""Shared types. Every module returns findings in ONE shape so the UI needs one component."""
from dataclasses import asdict, dataclass, field
from typing import Any

# Finding kinds (brief section 10)
FRAUD = "FRAUD_SIGNAL"
DEFICIENCY = "DEFICIENCY"
REVIEW = "REVIEW_ITEM"
VERIFIED = "VERIFIED"
PASS = "PASS"

# Rule statuses (brief section 7.D)
S_PASS, S_FAIL, S_REVIEW, S_NOT_CHECKED, S_NA = "PASS", "FAIL", "NEEDS_REVIEW", "NOT_CHECKED", "NOT_APPLICABLE"


@dataclass
class Evidence:
    document_id: int | None
    category: str = ""
    page: int = 1
    bbox: list[float] | None = None
    field: str = ""
    value: Any = None
    original_text: str = ""
    note: str = ""

    def dict(self):
        return asdict(self)


@dataclass
class FindingData:
    code: str
    kind: str
    title: str
    summary: str
    severity: str = "medium"  # high | medium | low
    category: str = ""
    source: str = ""
    status: str = ""
    clause_ref: str = ""
    clause_id: str = ""
    establishes: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    params: dict = field(default_factory=dict)  # numbers for bilingual notice templates
    related: dict = field(default_factory=dict)


@dataclass
class Line:
    text: str
    bbox: list[float]  # PDF points [x0, y0, x1, y1]
    conf: float = 1.0


@dataclass
class PageText:
    page: int
    width: float
    height: float
    lines: list[Line]
    source: str  # digital | ocr:<engine> | image | empty


@dataclass
class FieldValue:
    """One extracted fact with its provenance."""
    field: str
    value: Any
    original_text: str
    document_id: int | None
    category: str
    page: int
    bbox: list[float] | None
    confidence: float
    field_id: int | None = None
    note: str = ""

    def evidence(self, note: str = "") -> Evidence:
        return Evidence(self.document_id, self.category, self.page, self.bbox, self.field,
                        self.value, self.original_text, note or self.note)
