# Demo script (about 3 minutes)

Before you start: `scripts\run_windows.bat`, browser at http://localhost:8000, zoom 100%, Wi-Fi **off** (show it runs offline).

| # | Do | Say |
| --- | --- | --- |
| 1 | Login page, click **Scrutiny officer** | "AICTE receives thousands of dossiers a year. Nirikshan checks each one against the APH and across every other institution." |
| 2 | Queue | "Already checked and sorted by risk. Clean dossiers at the bottom move fast; 4 of our clean test dossiers have zero flags." |
| 3 | Open **Aravalli Heights** (risk 81) | "Why this score: every point traces to a finding, no black box." |
| 4 | Click **Built-up area below the norm** | The plan opens with 10,850 sq.m outlined. "10,850 against 12,000 required for intake 300, with the clause beside it. Deficiency: fixable, goes into the notice." |
| 5 | Click **3 faculty also listed by another institution** | Three rows outlined. "Same PAN, two colleges, same year. Only AICTE can see this. We store salted hashes, never the PAN." |
| 6 | Click **Photo matches another institution's submission** | "This lab photo was submitted by Kaveri Valley last year. Perceptual hashing survives resizing." |
| 7 | Tabs: Fire safety NOC has a green dot | "Digitally signed, signature verified (level 3). The affidavit says *not independently verified*: honest labels." |
| 8 | **Check trace** tab | "Eight fixed tools in order. No autonomous agent; every step is logged." |
| 9 | **Extracted fields** → Correct one value | "Officers can fix OCR; the original stays, the change is audited." |
| 10 | **Notice and decision** → हिन्दी tab | "Draft notice in English and Hindi, numbers straight from the rules, clause per item. Fraud signals are not in the notice; they go to the committee." |
| 11 | Choose **Refer to committee** → Record | Stamp lands. "The officer decides. Audit trail on the right." |
| 12 | **National view** | "Shared faculty, identical files, reused photos: a national map no single reviewer has." |
| 13 | Open **Upper Lake College** (risk 100) briefly | "Fire NOC edited after signing: the signature breaks. A scanned land deed with a pasted date: the patch has no scanner noise." |
| 14 | **APH assistant**, Hindi chip | "Answers only from APH clauses, cited. If no clause covers it, it says so." |
| 15 | **Evaluation** | "31 of 31 planted problems, 0 of 4 clean dossiers flagged, 192 of 193 fields. Measured, not claimed, with the caveats on screen." |
| 16 | (optional) Sign out → **Institution** → Start application → Reuse documents → Run self-check | "Colleges see the same deficiencies before submitting, fewer deficiency letters for AICTE." |

Lines to remember:
- "The AI never approves or rejects. It finds, explains and cites; the officer decides."
- "AICTE has a national view that no single scrutiny officer has."
- "Every finding links to the exact page and the exact APH clause."
- "Everything runs on-premise; no applicant data leaves AICTE."

If something breaks: re-run `backend\.venv\Scripts\python scripts\seed.py` (2–5 min) to reset all data.
