# APH verification checklist (do this before the demo)

The rule engine reads its numbers from `backend/data/aph/norms.json` (or the Admin page). Items below are marked
**to verify** in the app until a team member copies the value and clause number from the official
**APH 2024-27** PDF (aicte-india.org → Approval Process Handbook). Saving a value in Admin marks it *verified*.

| Item | Where it is used | Current value | Status | Owner |
| --- | --- | --- | --- | --- |
| Built-up area per programme and intake (instructional, administrative, amenities) | `APH-BUA-01` | demo formula 3,000 + 30 × intake sq.m | **to verify**: replace with the APH appendix table | |
| Access and circulation area (25%?) | clause `BUA.ACA` | 25% (from APH 2018-19) | **to verify** | |
| Documents required per application type (EoA, increase in intake, new) | `APH-DOC-01` | see `rules/docs.py` | **to verify** | |
| Fire NOC requirement wording | `APH-FIRE-01` | valid on application date | **to verify** | |
| Affidavit requirement wording (stamp paper, notarised) | `APH-AFF-01` | notarised + intake matches | **to verify** | |
| Maximum intake per course (240 with NBA?) | not used yet | | **to verify** before adding | |
| Adjunct faculty up to 10% | clause `A7.ADJ` | 10% | **to verify** | |
| Penal action clause wording | clause `PEN.F` | summary | **to verify** | |
| FSR 1:20 UG, 1:25 diploma, 1:15 PG | `APH-FSR-01` | from Appendix 7 | verified (public extract) | |
| Cadre ratio 1:2:6, R = 9; Associate may stand in for Professor | `APH-CADRE-01` | Appendix 7 | verified (public extract) | |
| 25% faculty reduction when admissions ≤ 50% | `APH-FSR-01` | Appendix 7 | verified (public extract) | |
| Lease ≥ 30 years with ≥ 25 remaining | `APH-LAND-01` | | verified (news report of APH change; confirm clause no.) | |
| Clause 2.6(c) three core branches, 2.6(d) CoA architect, 2.6(e) pending inquiry | `APH-EXP-01/02`, `APH-PLAN-01` | | verified (APH 2024-27 p.16) | |

Then run `python scripts/ingest_aph.py <APH.pdf>` so the assistant also searches the verbatim text with page numbers.

Sources used so far: AICTE APH Appendix 7 extract (faculty norms); APH 2024-27 page 16 (clause 2.6); The Hitavada,
25 Mar 2023, "New rules for engineering colleges: AICTE relaxes land norms, FSR to be 1:20"; Kerala DTE circular
L3/996/24/DTE (EoA document list).
