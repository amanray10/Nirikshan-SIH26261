"""Explainable risk score: fraud signals weigh most, then failed rules, then review items.
Never a black box: the score is returned with the list of findings that produced it."""
from .types import DEFICIENCY, FRAUD, REVIEW, FindingData

WEIGHTS = {
    (FRAUD, "high"): 30, (FRAUD, "medium"): 20, (FRAUD, "low"): 10,
    (DEFICIENCY, "high"): 12, (DEFICIENCY, "medium"): 8, (DEFICIENCY, "low"): 4,
    (REVIEW, "high"): 6, (REVIEW, "medium"): 3, (REVIEW, "low"): 1,
}


def score(findings: list[FindingData]) -> tuple[float, str, list[dict]]:
    parts = []
    for f in findings:
        w = WEIGHTS.get((f.kind, f.severity), 0)
        if w:
            parts.append({"code": f.code, "title": f.title, "kind": f.kind, "severity": f.severity, "points": w})
    total = min(100.0, float(sum(p["points"] for p in parts)))
    band = "HIGH" if total >= 50 or any(p["kind"] == FRAUD and p["severity"] == "high" for p in parts) else \
           "MEDIUM" if total >= 15 else "LOW"
    parts.sort(key=lambda p: -p["points"])
    return total, band, parts
