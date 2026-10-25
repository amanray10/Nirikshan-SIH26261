# Team plan: from this prototype to submission

The full pipeline, UI and evaluation already run. The two days go into **making it AICTE-accurate, robust on real
layouts, and well presented**, not into building from scratch. Idea submission deadline on the portal: **28 Oct 2026**.

| Member | Owns | First tasks |
| --- | --- | --- |
| 1 Backend | `app/api`, `orchestrator.py`, MySQL | Run on MySQL 8 (`DATABASE_URL`), add Alembic migrations, keep `main` green |
| 2 Document intelligence | `parser.py`, `ocr.py`, `extractor.py` | Collect 10 publicly posted EoA affidavits/approval letters; add label patterns until fields extract; try PaddleOCR on scans |
| 3 APH rule engine | `rules/`, `norms.json` | Work through docs/APH_VERIFICATION_CHECKLIST.md; add 4–6 more rules (library, labs, computers) with tests |
| 4 Cross-checks and authenticity | `cross_institution.py`, `history.py`, `authenticity.py` | Add copy-move detection; test noise forensics on real scans; tune thresholds and record false alarms |
| 5 Frontend | `frontend/src` | Demo polish, 60-second screen recording of docs/DEMO_SCRIPT.md, screenshots for the PPT |
| 6 RAG, LLM, data, metrics | `retrieval.py`, `llm.py`, `scripts/` | Ingest the official APH PDF, enable Ollama, extend `eval_questions.json` with real officer-style questions, run the officer-time study |

Ground rules: agree API changes before making them; every rule gets a test; never quote a number that is not in
`data/evaluation/latest.json`; never commit `uploads/`, `.env` or real personal documents.

## Pitch checklist
- [ ] Problem slide with real AICTE numbers (applications per year, scrutiny time) from AICTE's own published data
- [ ] Architecture slide (README diagram)
- [ ] "Why we're different": APH as code, national cross-checks, year-over-year, self-check, evidence-linked, honest labels
- [ ] Screenshots: queue, workspace with outlined evidence, Hindi notice + stamp, national view, evaluation
- [ ] Results slide copied from the Evaluation page, with its caveat
- [ ] Feasibility and limitations slide (what is verified vs screened vs mocked)
