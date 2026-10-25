"""APH rule engine: norms as data, rules as small deterministic, versioned, unit-tested functions.

Neuro-symbolic split: OCR/LLM supply facts and evidence; these rules make the decisions.
The LLM can never overrule a rule result.
"""
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from ...config import settings
from ..types import (DEFICIENCY, FRAUD, PASS, REVIEW, S_FAIL, S_NA, S_NOT_CHECKED, S_PASS, S_REVIEW,
                     Evidence, FieldValue, FindingData)

ALL_TYPES = ["EOA", "INTAKE_INCREASE", "NEW_INSTITUTION"]


# ---------- facts --------------------------------------------------------------
@dataclass
class CaseFacts:
    app_type: str
    program: str
    requested_intake: int
    academic_year: str
    declared: dict
    application_date: date
    fields: dict[str, list[FieldValue]] = field(default_factory=dict)
    categories: dict[str, list[int]] = field(default_factory=dict)  # category -> document ids
    faculty: list[dict] = field(default_factory=list)
    sources: dict[int, str] = field(default_factory=dict)  # document id -> text source (digital / ocr:...)

    def ocr_sourced(self, category: str) -> bool:
        return any(self.sources.get(d, "").startswith("ocr") for d in self.categories.get(category, []))

    def first(self, name: str, category: str | None = None) -> FieldValue | None:
        for fv in self.fields.get(name, []):
            if category is None or fv.category == category:
                return fv
        return None

    def all(self, name: str) -> list[FieldValue]:
        return self.fields.get(name, [])

    def has(self, category: str) -> bool:
        return bool(self.categories.get(category))


class Norms:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    @classmethod
    def from_file(cls):
        with open(settings.data_dir / "aph" / "norms.json", encoding="utf-8") as fh:
            return cls(json.load(fh)["norms"])

    def row(self, name: str, program: str) -> dict:
        for r in self.rows:
            if r["norm_name"] == name and r["program"] == program:
                return r
        for r in self.rows:
            if r["norm_name"] == name and r["program"] == "any":
                return r
        for r in self.rows:
            if r["norm_name"] == name:
                return r
        raise KeyError(f"norm {name} not defined for {program}")

    def get(self, name: str, program: str = "any") -> float:
        return float(self.row(name, program)["value"])


# ---------- clauses --------------------------------------------------------------
_CLAUSES: dict[str, dict] | None = None


def clauses() -> dict[str, dict]:
    global _CLAUSES
    if _CLAUSES is None:
        with open(settings.data_dir / "aph" / "aph_clauses.json", encoding="utf-8") as fh:
            data = json.load(fh)
        _CLAUSES = {c["clause_id"]: {**c, "edition": data["edition"]} for c in data["clauses"]}
    return _CLAUSES


def clause_ref(clause_id: str) -> str:
    c = clauses().get(clause_id)
    if not c:
        return clause_id
    if c["clause"][0].isdigit():
        prefix = "Appendix " if c["chapter"].startswith("Appendix") else "Clause "
        return f"{c['edition']}, {prefix}{c['clause']}"
    if c["chapter"].startswith("AICTE Regulations"):
        return f"{c['chapter']} – {c['clause']}"
    return f"{c['edition']}, {c['chapter'].split(':')[0]} – {c['clause']}"


# ---------- registry ---------------------------------------------------------------
@dataclass
class Outcome:
    status: str
    summary: str
    evidence: list[Evidence] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    severity: str | None = None
    kind: str | None = None  # override (e.g. gross overstatement -> FRAUD_SIGNAL)


@dataclass
class Rule:
    code: str
    title: str
    clause_id: str
    category: str
    applies_to: list[str]
    fn: Callable[[CaseFacts, Norms], Outcome]
    version: int = 1
    severity: str = "high"
    description: str = ""


REGISTRY: dict[str, Rule] = {}


def rule(code, title, clause_id, category, applies_to=None, version=1, severity="high"):
    def deco(fn):
        REGISTRY[code] = Rule(code, title, clause_id, category, applies_to or ALL_TYPES, fn, version,
                              severity, (fn.__doc__ or "").strip())
        return fn
    return deco


FAIL_TITLES = {'APH-DOC-01': 'Mandatory documents missing',
    'APH-BUA-01': 'Built-up area below the norm for the requested intake',
    'APH-BUA-02': 'Declared built-up area not supported by the plan',
    'APH-OC-01': 'Occupancy certificate does not cover the built-up area',
    'APH-PLAN-01': 'Building plan not certified by a registered architect',
    'APH-FIRE-01': 'Fire safety certificate expired',
    'APH-FSR-01': 'Faculty strength below the 1:20 ratio',
    'APH-FSR-02': 'Fewer faculty listed than declared',
    'APH-CADRE-01': 'Cadre ratio 1:2:6 not met',
    'APH-FQ-01': 'Faculty below the minimum qualification for their cadre',
    'APH-LAND-01': 'Land lease shorter than the norm',
    'APH-AFF-01': 'Affidavit not notarised or inconsistent',
    'APH-EXP-01': 'Fewer than three core branches for expansion',
    'APH-EXP-02': 'Inquiry pending; intake increase barred'}

ESTABLISHES = ("Deterministic check of extracted values against the APH norm table. "
               "It is as reliable as the extracted values it uses; each value links to its source page.")

KIND_BY_STATUS = {S_PASS: PASS, S_FAIL: DEFICIENCY, S_REVIEW: REVIEW, S_NOT_CHECKED: REVIEW}


def evaluate(facts: CaseFacts, norms: Norms, enabled: set[str] | None = None) -> tuple[list[dict], list[FindingData]]:
    """Run every applicable rule. Returns (rule evaluations, findings)."""
    from . import docs, faculty, infrastructure, legal  # noqa: F401  (register rules)

    evaluations, findings = [], []
    for code, r in REGISTRY.items():
        if enabled is not None and code not in enabled:
            continue
        if facts.app_type not in r.applies_to:
            evaluations.append({"rule_code": code, "rule_version": r.version, "status": S_NA, "detail": "", "evidence": []})
            continue
        try:
            out = r.fn(facts, norms)
        except Exception as exc:  # a broken rule must never crash the run
            out = Outcome(S_NOT_CHECKED, f"Check could not run: {exc}")
        evaluations.append({"rule_code": code, "rule_version": r.version, "status": out.status,
                            "detail": out.summary, "evidence": [e.dict() for e in out.evidence]})
        if out.status == S_NA:
            continue
        kind = out.kind or KIND_BY_STATUS[out.status]
        severity = out.severity or (r.severity if out.status == S_FAIL else
                                    "medium" if out.status == S_REVIEW else "low")
        findings.append(FindingData(
            code=code, kind=kind, title=FAIL_TITLES.get(code, r.title) if out.status == S_FAIL else r.title, summary=out.summary, severity=severity,
            category=r.category, source="rules", status=out.status, clause_id=r.clause_id,
            clause_ref=clause_ref(r.clause_id), establishes=ESTABLISHES, evidence=out.evidence,
            params=out.params, related={"rule_version": r.version},
        ))
    return evaluations, findings
