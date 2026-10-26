# Nirikshan (निरीक्षण)

**AI-assisted scrutiny workstation for AICTE approval applications.** SIH 2026, problem statement **26261**:
*AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification.*

> An evidence-linked scrutiny workstation that lets AICTE officers verify an institution's approval dossier
> against the Approval Process Handbook (APH) in minutes, and catches fraud that no single reviewer can see.

The AI never approves or rejects. It finds, explains and cites; the officer decides.

---

## What it does

| Problem-statement phrase | What Nirikshan does |
| --- | --- |
| **Application validation** | Required documents per application type; the portal declaration (built-up area, faculty count, intake) is checked against the documents themselves |
| **Regulatory compliance verification** | 14 APH rules as versioned, unit-tested Python (FSR 1:20, cadre 1:2:6 with the 25% low-admission reduction, built-up area, lease ≥30/25 years, clause 2.6(c)/(d)/(e) for intake increase, fire NOC validity, qualifications …). Every finding cites its clause |
| **Document authentication** | Four labelled levels: (1) metadata, (2) visual forensics on scans (noise-inconsistency finds pasted text), (3) digital signatures (pyHanko) and QR codes, (4) issuer registry (mock connector, clearly labelled) |
| **AI-powered** | OCR (Tesseract / PaddleOCR), clause retrieval (BGE-M3 + FAISS or TF-IDF), local LLM via Ollama for cited answers; deterministic rules make every decision (neuro-symbolic) |

### What sets it apart

1. **APH as code.** Norms are data (editable, marked *verified* or *to verify*); rules are small functions with tests.
2. **National cross-checks only AICTE can run.** Ghost faculty (salted hash of PAN/Aadhaar on two institutions' lists), photos recycled from another college (perceptual hashes), byte-identical files, look-alike faculty. The *National view* shows the links on a map.
3. **Year-over-year consistency.** Built-up area that shrank, survey numbers that changed, faculty lists that turned over.
4. **Evidence-linked.** Click a finding and the exact page opens with the value outlined; the APH clause sits beside it.
5. **Honest labels.** Fraud signal vs deficiency vs needs-review vs verified. "No anomaly detected; not independently verified" is said out loud.
6. **Two-sided.** Institutions run the same checks as a **self-check** before submitting (cross-institution intelligence stays with AICTE).
7. **Bilingual output.** Rectification notice drafted in English and Hindi with the numbers the rules computed; site-visit checklist for the Expert Visit Committee.
8. **On-premise and offline.** No applicant data leaves the machine; no cloud AI.

## Measured results (synthetic test set)

Run `python scripts/evaluate.py` to reproduce. Latest run: see [docs/EVALUATION.md](docs/EVALUATION.md) and the in-app **Evaluation** page.

| Metric | Result |
| --- | --- |
| Planted problems caught (29 types, 14 applications) | **31 / 31** |
| Flags that were correct | **31 / 32** (the extra one: OCR missed a row of a scanned faculty list; raised as *needs review*, not as a deficiency) |
| Clean applications wrongly flagged | **0 / 4** |
| Fields read correctly (incl. three fully scanned dossiers) | **192 / 193** |
| Right APH clause in top 5 (26 questions, English + Hindi) | **25 / 26** |

These measure the pipeline on data we generated; real dossiers will be harder. Officer time saved is **not measured yet**
(protocol in docs/EVALUATION.md). Do not quote numbers that are not in that file.

---

## Run it on Windows

Prerequisites: **Git**, **Python 3.11–3.13**, **Node.js 18+**, and (for scanned documents) **Tesseract OCR**
from <https://github.com/UB-Mannheim/tesseract/wiki> with Hindi and Marathi language data.

```powershell
git clone https://github.com/amanray10/Nirikshan-SIH26261.git
cd Nirikshan-SIH26261
scripts\setup_windows.bat      # venv, packages, frontend build, synthetic data, all checks, tests (2–5 min)
scripts\run_windows.bat        # opens http://localhost:8000
```

Linux / macOS: `scripts/setup.sh` then `scripts/run.sh`.
Development with hot reload: `scripts\dev_windows.ps1` (React on :5173, API on :8000, API docs at http://localhost:8000/docs).

No `.env` is needed: every setting has a working default (copy `backend/.env.example` to `backend/.env` to change any).
The virtual environment, `node_modules`, the database, uploads and the synthetic dossiers are **not** in the repo;
setup creates them on each machine. After `git pull`, re-run setup if `requirements.txt` or `package.json` changed.

### Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Scrutiny officer | officer@nirikshan.demo | officer123 |
| Administrator | admin@nirikshan.demo | admin123 |
| Institution (any of 14) | i01@college.demo … i14@college.demo | college123 |

The login page has one-click buttons for each. **i05** (Aravalli Heights) is the demo hero dossier.

**New institutions** can register from **Create an account** on the login page (one account per AICTE ID; officer and
admin accounts are issued by AICTE, never self-registered).

### Optional engines (auto-detected)

| Engine | Default | Upgrade |
| --- | --- | --- |
| OCR | Tesseract | `pip install -r backend/requirements-ai.txt` for PaddleOCR |
| Clause retrieval | TF-IDF (word + character n-grams, Hindi keyword bridge) | BGE-M3 + FAISS from requirements-ai.txt |
| LLM | none: deterministic templates and extractive answers | Install Ollama, `ollama pull qwen2.5:7b-instruct` (any local chat model is picked up) |
| Database | SQLite file | MySQL 8: set `DATABASE_URL=mysql+pymysql://…` in `backend/.env` |

To index the official handbook: `python scripts/ingest_aph.py APH_2024-27.pdf` (verbatim clauses with page numbers join the retrieval index).

---

## Architecture

```
React (Vite, Tailwind, TanStack Query)          institution self-check · officer queue · workspace · notice/decision
        │  REST + JWT (roles enforced in the API)          national view · APH assistant · evaluation · admin
FastAPI ──────────────────────────────────────────────────────────────────────────────────────────────
        │  background job per application
Orchestrator (fixed list of typed tools, logged trace; no free-form agent loops)
  1 extract_document_fields   PyMuPDF text + coordinates │ OCR for scans │ faculty table parser
  2 run_aph_rules             14 versioned rules over a norm table (APH 2024-27)
  3 compare_document_fields   survey no., address, trust, institution name, land area
  4 check_history             vs the institution's previous application
  5 check_cross_institution   hashed IDs, perceptual photo hashes, SHA-256 files across all institutions
  6 screen_authenticity       metadata · noise-inconsistency forensics · pyHanko signatures · QR + issuer mock · photo GPS
  7 retrieve_aph_clause       clause text attached to every finding
  8 generate_report           explainable risk score · EN/HI notice · EVC checklist
        │
SQLite / MySQL (16 tables, audit log)     uploads/ (outside web root, SHA-256)     APH clause index
```

Neural components supply facts (OCR, retrieval, optional LLM); symbolic rules decide. The LLM never overrides a rule and its
output is schema-validated. Document text is treated as data, never as instructions.

```
backend/
  app/
    main.py  config.py  db.py  models.py  schemas.py  security.py
    api/            auth · applications (upload, verify, self-check) · documents (page images, field corrections)
                    reports (report, notice, decisions, audit, checklist) · aph (ask, rules, norms) · analytics
    services/
      parser.py  ocr.py  extractor.py         document intelligence
      rules/  engine.py docs.py infrastructure.py faculty.py legal.py
      consistency.py  history.py  cross_institution.py  authenticity.py
      retrieval.py  llm.py  risk.py  notices.py  orchestrator.py
    tests/          56 tests: every rule, extractor, consistency, forensics, risk, API security
  data/aph/         norms.json · aph_clauses.json (clause summaries) · eval_questions.json
  scripts/          generate_synthetic.py · seed.py · evaluate.py · ingest_aph.py
frontend/src/       pages/ (Queue, Workspace, Decision, Network, Assistant, Evaluation, Admin, Institution*)
docs/               demo script, evaluation, APH verification checklist, team plan
```

## Security and privacy

Argon2 passwords, short-lived JWTs, rate-limited login, role checks on every endpoint (institutions see only their own
cases and never the cross-institution findings; officers never see drafts), file-type allow-list with magic-byte checks,
size limits, uploads outside the web root, SHA-256 per file, full audit log of views, corrections, overrides and
decisions. PAN/Aadhaar are stored only as salted hashes plus the last four characters (DPDP Act 2023: collect only what
scrutiny needs). Synthetic, fictional data only; nothing goes to a cloud service.

## Honest limitations

- Built-up-area norm values and some clause texts are placeholders marked **to verify**; copy them from the official
  APH 2024-27 (checklist in docs/APH_VERIFICATION_CHECKLIST.md). Faculty ratio, cadre ratio, the 25% reduction, lease
  terms and clause 2.6 conditions are taken from published AICTE material.
- Issuer verification (DigiLocker, land records, fire department) is a **mock** connector with a real interface.
- Field extraction uses label-anchored patterns; unusual layouts need the optional VLM/LLM path or new patterns.
- Visual forensics flags regions to inspect; it is a screening signal, not proof.
