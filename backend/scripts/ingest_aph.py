"""Ingest the OFFICIAL Approval Process Handbook PDF into clause-level chunks for retrieval.

    python scripts/ingest_aph.py path/to/APH_2024-27.pdf [--edition "APH 2024-27"]

Writes data/aph/aph_clauses_official.json (verbatim text, page numbers). The retrieval index picks it up
automatically on the next start, alongside the team's clause summaries that the rules cite.
Chunks follow the handbook's own numbering (2.6, 2.6(a), Appendix 7 ...) instead of fixed character windows.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
HEAD = re.compile(r"^\s*(?:(\d{1,2}(?:\.\d{1,2}){1,3})\s+(\S.{2,140})|(Appendix[\s-]*\d+[A-Z]?)\b[\s:.\-]*(.{0,140})|(Annexure[\s-]*\d+[A-Z]?)\b[\s:.\-]*(.{0,140}))$", re.I)
MAX = 1400


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--edition", default="APH 2024-27")
    a = ap.parse_args()
    doc = pymupdf.open(a.pdf)
    chunks, cur = [], None
    for pno, page in enumerate(doc, start=1):
        for line in page.get_text().splitlines():
            m = HEAD.match(line)
            if m:
                if cur:
                    chunks.append(cur)
                num = m.group(1) or m.group(3) or m.group(5)
                title = (m.group(2) or m.group(4) or m.group(6) or "").strip()
                cur = {"clause": num.strip(), "title": title or num.strip(), "page": pno, "text": ""}
            elif cur is not None:
                cur["text"] += " " + line.strip()
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        text = re.sub(r"\s+", " ", c["text"]).strip()
        if len(text) < 40:
            continue
        for j in range(0, len(text), MAX):
            out.append({"clause_id": f"OFF-{i:04d}{'-' + str(j // MAX) if j else ''}", "chapter": "Official text",
                        "clause": c["clause"], "title": c["title"][:140], "text": text[j:j + MAX], "page": c["page"],
                        "ref": f"{a.edition}, {c['clause']} (p.{c['page']})", "source_status": "verbatim"})
    dest = ROOT / "data" / "aph" / "aph_clauses_official.json"
    dest.write_text(json.dumps({"edition": a.edition, "source": Path(a.pdf).name, "clauses": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} clause chunks from {doc.page_count} pages -> {dest}")


if __name__ == "__main__":
    sys.exit(main())
