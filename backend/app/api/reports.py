from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import AuditLog, Finding, Notice, OfficerReview, RuleEvaluation, User, VerificationRun
from ..schemas import NoticeIn, ReviewIn, application_out, document_out, finding_out
from ..security import audit, current_user, get_app_or_404, require
from ..services import notices
from ..services.rules.engine import REGISTRY

router = APIRouter(prefix="/api", tags=["reports"])

APP_DECISIONS = {"APPROVE", "REJECT", "RECTIFY", "REFER_COMMITTEE", "SITE_VISIT"}


@router.get("/applications/{app_id}/notice")
def get_notice(app_id: int, lang: str = "en", user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    if user.role == "institution" and app.status not in ("DECIDED",):
        raise HTTPException(403, "Notice not issued yet")
    n = db.scalars(select(Notice).where(Notice.application_id == app.id, Notice.language == lang)
                   .order_by(Notice.id.desc())).first()
    return {"language": lang, "body": n.body if n else "", "status": n.status if n else "NONE"}


@router.put("/applications/{app_id}/notice")
def edit_notice(app_id: int, body: NoticeIn, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    n = db.scalars(select(Notice).where(Notice.application_id == app.id, Notice.language == body.language)
                   .order_by(Notice.id.desc())).first()
    if not n:
        n = Notice(application_id=app.id, language=body.language, body="")
        db.add(n)
    n.body, n.status = body.body, "EDITED"
    audit(db, user, "edit_notice", "application", app.id, language=body.language)
    db.commit()
    return {"ok": True}


@router.post("/applications/{app_id}/reviews")
def review(app_id: int, body: ReviewIn, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    if body.decision == "OVERRIDE" and len(body.reason.strip()) < 5:
        raise HTTPException(400, "An override needs a reason")
    if body.finding_id:
        f = db.get(Finding, body.finding_id)
        if not f or f.application_id != app.id:
            raise HTTPException(404, "Finding not found")
        f.review_status = "OVERRIDDEN" if body.decision == "OVERRIDE" else "ACCEPTED"
    elif body.decision in APP_DECISIONS:
        app.decision = body.decision
        if body.decision != "SITE_VISIT":
            app.status = "DECIDED"
        if body.decision in ("RECTIFY", "REJECT"):
            for n in db.scalars(select(Notice).where(Notice.application_id == app.id)):
                n.status = "ISSUED"
    else:
        raise HTTPException(400, "Finding-level decisions need a finding_id")
    db.add(OfficerReview(application_id=app.id, finding_id=body.finding_id, officer_id=user.id,
                         decision=body.decision, reason=body.reason))
    audit(db, user, "review", "application", app.id, finding_id=body.finding_id, decision=body.decision, reason=body.reason)
    db.commit()
    return {"ok": True, "application": application_out(app)}


@router.get("/applications/{app_id}/reviews")
def reviews(app_id: int, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    rows = db.scalars(select(OfficerReview).where(OfficerReview.application_id == app.id).order_by(OfficerReview.id)).all()
    return [{"id": r.id, "finding_id": r.finding_id, "decision": r.decision, "reason": r.reason,
             "officer_id": r.officer_id, "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/applications/{app_id}/audit")
def audit_trail(app_id: int, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    rows = db.scalars(select(AuditLog).where(AuditLog.entity == "application", AuditLog.entity_id == app.id)
                      .order_by(AuditLog.id.desc()).limit(200)).all()
    users = {u.id: u for u in db.scalars(select(User))}
    return [{"id": r.id, "action": r.action, "user": users[r.user_id].name if r.user_id in users else "system",
             "role": users[r.user_id].role if r.user_id in users else "system", "details": r.details,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/applications/{app_id}/checklist")
def checklist(app_id: int, user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    rows = [finding_out(f) for f in db.scalars(select(Finding).where(Finding.application_id == app.id))]
    return notices.site_visit_checklist(rows)


def _report_data(db: Session, app, user) -> dict:
    run = db.scalars(select(VerificationRun).where(VerificationRun.application_id == app.id, VerificationRun.status == "DONE")
                     .order_by(VerificationRun.id.desc())).first()
    fs = [finding_out(f) for f in db.scalars(select(Finding).where(Finding.application_id == app.id))]
    order = {"FRAUD_SIGNAL": 0, "DEFICIENCY": 1, "REVIEW_ITEM": 2, "VERIFIED": 3, "PASS": 4}
    fs.sort(key=lambda f: order.get(f["kind"], 9))
    evals = []
    if run:
        for r in db.scalars(select(RuleEvaluation).where(RuleEvaluation.run_id == run.id)):
            rule = REGISTRY.get(r.rule_code)
            evals.append({"rule_code": r.rule_code, "version": r.rule_version, "status": r.status, "detail": r.detail,
                          "title": rule.title if rule else r.rule_code})
    note = {n.language: n.body for n in db.scalars(select(Notice).where(Notice.application_id == app.id).order_by(Notice.id))}
    return {"application": application_out(app), "documents": [document_out(d) for d in app.documents], "findings": fs,
            "rule_evaluations": evals, "notice": note, "checklist": notices.site_visit_checklist(fs),
            "run": {"id": run.id, "duration_ms": run.duration_ms, "engines": run.engines, "tool_log": run.tool_log} if run else None,
            "generated_at": datetime.now().strftime("%d-%m-%Y %H:%M"), "edition": settings.aph_edition}


@router.get("/applications/{app_id}/report")
def report(app_id: int, format: str = "json", user: User = Depends(require("officer", "admin")), db: Session = Depends(get_db)):
    app = get_app_or_404(db, app_id, user)
    data = _report_data(db, app, user)
    audit(db, user, "view_report", "application", app.id, format=format)
    db.commit()
    if format == "html":
        return HTMLResponse(REPORT_HTML.render(**data))
    return data


REPORT_HTML = Template("""<!doctype html><html><head><meta charset="utf-8"><title>Scrutiny report {{ application.ref_no }}</title>
<style>
body{font:13px/1.5 system-ui,-apple-system,"Segoe UI","Nirmala UI","Noto Sans Devanagari",sans-serif;color:#1d2433;margin:32px;max-width:960px}
h1{font-size:20px;margin:0}h2{font-size:15px;margin:26px 0 8px;border-bottom:1px solid #d7dce5;padding-bottom:4px}
.muted{color:#5d6678}.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600}
.FRAUD_SIGNAL{background:#fde2e1;color:#9b1c1c}.DEFICIENCY{background:#fff1d6;color:#8a4b00}.REVIEW_ITEM{background:#e6eefc;color:#1d4ea8}
.VERIFIED{background:#dff5e6;color:#17663a}.PASS{background:#eef0f3;color:#4b5565}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #d7dce5;padding:6px 8px;text-align:left;vertical-align:top}th{background:#f4f6f9}
pre{white-space:pre-wrap;background:#fafbfc;border:1px solid #e3e7ee;padding:12px;font:12px/1.55 inherit}
.banner{background:#fff8e6;border:1px solid #f0d58c;padding:8px 12px;margin:12px 0}
@media print{body{margin:12mm}.noprint{display:none}}
</style></head><body>
<div class="noprint" style="text-align:right"><button onclick="print()">Print / Save as PDF</button></div>
<h1>Scrutiny report: {{ application.ref_no }}</h1>
<div class="muted">{{ application.institution.name }} ({{ application.institution.aicte_id }}) · {{ application.type|replace('_',' ') }} · AY {{ application.academic_year }} · requested intake {{ application.requested_intake }}</div>
<div class="banner">Generated by Nirikshan on {{ generated_at }} against the {{ edition }}. The system flags and explains; the scrutiny officer decides. Prototype output on synthetic data.</div>
<h2>Summary</h2>
<p>Risk score <b>{{ application.risk_score|round|int }}/100 ({{ application.risk_band }})</b> · Decision: <b>{{ application.decision or 'pending' }}</b>
{% if run %} · processed in {{ (run.duration_ms/1000)|round(1) }} s{% endif %}</p>
<h2>Findings</h2>
<table><tr><th>Kind</th><th>Finding</th><th>Evidence</th><th>Basis</th></tr>
{% for f in findings if f.kind != 'PASS' %}<tr><td><span class="pill {{ f.kind }}">{{ f.kind|replace('_',' ') }}</span><br><span class="muted">{{ f.severity }}</span></td>
<td><b>{{ f.title }}</b><br>{{ f.summary }}<br><span class="muted">{{ f.establishes }}</span>{% if f.review_status != 'OPEN' %}<br><i>Officer: {{ f.review_status }}</i>{% endif %}</td>
<td>{% for e in f.evidence %}{{ e.category|replace('_',' ') }} p.{{ e.page }}{% if e.original_text %}: “{{ e.original_text[:60] }}”{% endif %}<br>{% endfor %}</td>
<td>{{ f.clause_ref }}</td></tr>{% endfor %}</table>
<h2>Documents and authenticity</h2>
<table><tr><th>Document</th><th>Text source</th><th>Authenticity (what was established)</th><th>SHA-256</th></tr>
{% for d in documents %}<tr><td>{{ d.category|replace('_',' ') }}<br><span class="muted">{{ d.filename }}</span></td><td>{{ d.text_source }}</td>
<td>{{ d.authenticity.label or '-' }}</td><td class="muted" style="font-size:10px">{{ d.sha256[:20] }}…</td></tr>{% endfor %}</table>
<h2>APH rules evaluated</h2>
<table><tr><th>Rule</th><th>Status</th><th>Detail</th></tr>
{% for r in rule_evaluations %}<tr><td>{{ r.rule_code }} v{{ r.version }}<br><span class="muted">{{ r.title }}</span></td><td>{{ r.status }}</td><td>{{ r.detail }}</td></tr>{% endfor %}</table>
<h2>Expert Visit Committee checklist</h2>
<ol>{% for c in checklist %}<li>{{ c.item }} <span class="muted">({{ c.code }})</span></li>{% endfor %}</ol>
<h2>Draft rectification notice (English)</h2><pre>{{ notice.get('en','') }}</pre>
<h2>प्रारूप सुधार सूचना (हिन्दी)</h2><pre>{{ notice.get('hi','') }}</pre>
{% if run %}<h2>Processing trace</h2><table><tr><th>Tool</th><th>Output</th><th>ms</th></tr>
{% for t in run.tool_log %}<tr><td>{{ t.tool }}</td><td>{{ t.output }}</td><td>{{ t.ms }}</td></tr>{% endfor %}</table>
<p class="muted">Engines: OCR {{ run.engines.ocr }} · retrieval {{ run.engines.retrieval }} · LLM {{ run.engines.llm }}</p>{% endif %}
</body></html>""")
