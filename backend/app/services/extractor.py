"""Field extraction per document type. Every value keeps its original text, page, bbox and confidence.

Strategy: label-anchored patterns (English + Hindi/Marathi labels) over text lines. This is
deterministic and explainable; a local VLM/LLM can be plugged in for unusual layouts
(see services/llm.py), but its output is always re-validated by the same normalisers.
"""
import re
from datetime import date

import pymupdf

from .parser import extract_pages, is_image
from .types import FieldValue, PageText

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

DOC_CATEGORIES = {
    "land_deed": "Land deed / lease deed",
    "building_plan": "Approved building plan",
    "occupancy_certificate": "Occupancy / completion certificate",
    "fire_noc": "Fire safety certificate (NOC)",
    "affidavit": "Notarised affidavit",
    "trust_registration": "Trust / society registration",
    "faculty_list": "Faculty list",
    "campus_photo": "Campus / lab photograph",
}


# ---------- normalisers -------------------------------------------------------
def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(DEVANAGARI_DIGITS)).strip(" :;,-")


def parse_number(s: str) -> float | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", s.translate(DEVANAGARI_DIGITS))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_date(s: str) -> tuple[str | None, float]:
    """ISO date + confidence. dd/mm/yyyy is the Indian convention; if both parts <= 12 it is ambiguous."""
    s = s.translate(DEVANAGARI_DIGITS).strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _iso(y, mo, d), 1.0
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        conf = 0.7 if (d <= 12 and mo <= 12 and d != mo) else 1.0
        return _iso(y, mo, d), conf
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", s)
    if m and m.group(2)[:3].lower() in MONTHS:
        return _iso(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1))), 1.0
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1)[:3].lower() in MONTHS:
        return _iso(int(m.group(3)), MONTHS[m.group(1)[:3].lower()], int(m.group(2))), 1.0
    return None, 0.0


def _iso(y, mo, d):
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def norm_survey(s: str) -> str:
    return re.sub(r"[\s.]", "", s.translate(DEVANAGARI_DIGITS)).upper()


# ---------- field specs ---------------------------------------------------------
NUM = r"([\d०-९][\d०-९,]*(?:\.\d+)?)"
DATE = r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})"
TEXT = r"(.{3,120})"


def _spec(field, labels, value=TEXT, kind="text"):
    return {"field": field, "labels": labels, "value": value, "kind": kind}


SURVEY = _spec("survey_number", [r"survey\s*(?:no|number)\.?", r"gat\s*no\.?", r"khasra\s*no\.?", r"सर्वे\s*(?:क्रमांक|नं\.?)", r"सर्वेक्षण\s*संख्या"],
               r"([0-9०-९]+\s*(?:/\s*[0-9A-Za-z०-९]+)*)", "survey")
ADDRESS = _spec("address", [r"(?:campus\s*|site\s*|property\s*|institution\s*)?address", r"location\s*of\s*(?:site|property)", r"पता"])
INSTITUTION = _spec("institution_name", [r"name\s*of\s*(?:the\s*)?institut(?:e|ion)", r"institut(?:e|ion)\s*name", r"संस्था\s*का\s*नाम"])
LAT = _spec("latitude", [r"latitude", r"अक्षांश"], r"(-?\d{1,2}\.\d+)", "number")
LON = _spec("longitude", [r"longitude", r"देशांतर"], r"(-?\d{1,3}\.\d+)", "number")

SPECS: dict[str, list[dict]] = {
    "land_deed": [
        SURVEY, ADDRESS, LAT, LON,
        _spec("deed_type", [r"deed\s*type", r"nature\s*of\s*(?:deed|document)"], r"(sale|lease|gift|conveyance)", "lower"),
        _spec("owner_name", [r"(?:owner|lessee|purchaser|in\s*favou?r\s*of)", r"स्वामी"]),
        _spec("land_area_acres", [r"(?:total\s*)?land\s*area", r"area\s*of\s*land", r"भूमि\s*क्षेत्रफल"], NUM + r"\s*(?:acres?|एकड़)", "number"),
        _spec("registration_number", [r"registration\s*(?:no|number)\.?", r"document\s*no\.?"], r"([A-Z0-9][A-Z0-9/\-]{3,30})", "upper"),
        _spec("deed_date", [r"date\s*of\s*(?:registration|execution|deed)"], DATE, "date"),
        _spec("lease_start_date", [r"lease\s*(?:commencement|start)\s*date", r"lease\s*commenc\w*\s*(?:on|from)?"], DATE, "date"),
        _spec("lease_term_years", [r"(?:lease\s*)?(?:term|period|duration)\s*(?:of\s*lease)?"], NUM + r"\s*years?", "number"),
    ],
    "building_plan": [
        SURVEY, ADDRESS, INSTITUTION,
        _spec("total_built_up_area_sqm", [r"total\s*built[\s\-]*up\s*area", r"कुल\s*निर्मित\s*क्षेत्र"], NUM + r"\s*(?:sq\.?\s*m|sqm|m2|m²|वर्ग\s*मीटर)", "number"),
        _spec("plot_area_sqm", [r"plot\s*area", r"site\s*area"], NUM + r"\s*(?:sq\.?\s*m|sqm|m2|m²)", "number"),
        _spec("architect_name", [r"architect(?:'s)?\s*name", r"prepared\s*by\s*(?:architect)?"]),
        _spec("architect_reg_no", [r"(?:coa\s*)?reg(?:istration)?\.?\s*no\.?\s*(?:\(coa\))?", r"council\s*of\s*architecture\s*reg"], r"(CA/\d{4}/\d{3,6})", "upper"),
        _spec("plan_approval_no", [r"(?:plan\s*)?approval\s*(?:no|number)\.?", r"sanction\s*no\.?"], r"([A-Z0-9][A-Z0-9/\-]{3,30})", "upper"),
        _spec("approving_authority", [r"approv(?:ed|ing)\s*(?:by|authority)", r"sanctioning\s*authority"]),
    ],
    "occupancy_certificate": [
        SURVEY, ADDRESS,
        _spec("certificate_no", [r"(?:certificate|oc)\s*(?:no|number)\.?"], r"([A-Z0-9][A-Z0-9/\-]{3,30})", "upper"),
        _spec("built_up_area_sqm", [r"(?:total\s*)?built[\s\-]*up\s*area", r"area\s*certified"], NUM + r"\s*(?:sq\.?\s*m|sqm|m2|m²)", "number"),
        _spec("issue_date", [r"date\s*of\s*issue", r"issued\s*on", r"दिनांक"], DATE, "date"),
        _spec("issuing_authority", [r"issued\s*by", r"issuing\s*authority"]),
    ],
    "fire_noc": [
        ADDRESS, INSTITUTION,
        _spec("certificate_no", [r"(?:noc|certificate)\s*(?:no|number)\.?"], r"([A-Z0-9][A-Z0-9/\-]{3,30})", "upper"),
        _spec("issue_date", [r"date\s*of\s*issue", r"issued\s*on"], DATE, "date"),
        _spec("valid_until", [r"valid\s*(?:up\s*to|upto|until|till)", r"validity", r"वैध\s*(?:तिथि|तक)"], DATE, "date"),
        _spec("issuing_authority", [r"issued\s*by", r"issuing\s*authority"]),
    ],
    "affidavit": [
        INSTITUTION,
        _spec("trust_name", [r"name\s*of\s*(?:the\s*)?(?:trust|society|company)", r"(?:trust|society)\s*name", r"न्यास\s*का\s*नाम"]),
        _spec("requested_intake", [r"(?:total\s*)?(?:proposed|requested|applied)\s*intake", r"total\s*intake"], NUM, "number"),
        _spec("affidavit_date", [r"(?:sworn|solemnly\s*affirmed|dated?)\s*(?:on|at)?"], DATE, "date"),
    ],
    "trust_registration": [
        _spec("trust_name", [r"name\s*of\s*(?:the\s*)?(?:trust|society|company)", r"(?:trust|society)\s*name"]),
        _spec("registration_number", [r"registration\s*(?:no|number)\.?"], r"([A-Z0-9][A-Z0-9/\-]{3,30})", "upper"),
        _spec("registration_date", [r"date\s*of\s*registration"], DATE, "date"),
    ],
}

# Flags detected by keywords anywhere in the document
KEYWORD_FLAGS = {
    "affidavit": {
        "notarised": [r"\bnotary\b", r"notari[sz]ed", r"नोटरी"],
        "no_inquiry_pending": [r"\bno\s+(?:inquiry|enquiry|investigation)\b.{0,90}?\bpending\b", r"कोई\s+जांच\s+लंबित\s+नहीं"],
        "inquiry_pending": [r"\b(?:an|any|one)\s+(?:inquiry|enquiry|investigation)\s+(?:is\s+)?pending\s+against"],
    },
    "building_plan": {"architect_certified": [r"council\s+of\s+architecture", r"\bcoa\b", r"licensed\s+surveyor"]},
}


def _match_line(text: str, spec: dict):
    for label in spec["labels"]:
        m = re.search(label + r"\s*[:\-–=]?\s*" + spec["value"], text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _normalise(raw: str, kind: str):
    raw_clean = norm_text(raw)
    if kind == "number":
        return parse_number(raw_clean), 1.0
    if kind == "date":
        return parse_date(raw_clean)
    if kind == "survey":
        return norm_survey(raw_clean), 1.0
    if kind == "upper":
        return raw_clean.upper(), 1.0
    if kind == "lower":
        return raw_clean.lower(), 1.0
    return raw_clean, 1.0


def extract_fields(pages: list[PageText], category: str, document_id: int | None) -> list[FieldValue]:
    out: list[FieldValue] = []
    seen: set[str] = set()
    for spec in SPECS.get(category, []):
        for pt in pages:
            if spec["field"] in seen:
                break
            for ln in pt.lines:
                raw = _match_line(ln.text, spec)
                if raw is None:
                    continue
                value, conf = _normalise(raw, spec["kind"])
                if value in (None, ""):
                    continue
                note = "ambiguous date format (dd/mm vs mm/dd)" if spec["kind"] == "date" and conf < 1 else ""
                out.append(FieldValue(spec["field"], value, raw.strip(), document_id, category,
                                      pt.page, ln.bbox, round(min(conf, ln.conf), 3), note=note))
                seen.add(spec["field"])
                break
    # Declarations wrap across lines, so search the joined page text and map the hit back to its line.
    for flag, patterns in KEYWORD_FLAGS.get(category, {}).items():
        found = False
        for pt in pages:
            starts, text = [], ""
            for ln in pt.lines:
                starts.append(len(text))
                text += ln.text + " "
            for p in patterns:
                m = re.search(p, text, re.IGNORECASE | re.DOTALL)
                if m:
                    li = max(i for i, s in enumerate(starts) if s <= m.start())
                    lj = max(i for i, s in enumerate(starts) if s <= max(m.end() - 1, m.start()))
                    box = [min(l.bbox[0] for l in pt.lines[li:lj + 1]), pt.lines[li].bbox[1],
                           max(l.bbox[2] for l in pt.lines[li:lj + 1]), pt.lines[lj].bbox[3]]
                    out.append(FieldValue(flag, True, m.group(0)[:200], document_id, category, pt.page, box,
                                          min(l.conf for l in pt.lines[li:lj + 1])))
                    found = True
                    break
            if found:
                break
    return out


# ---------- faculty list (table) -------------------------------------------------
PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
AADHAAR_RE = re.compile(r"\b(\d{4}\s?\d{4}\s?\d{4})\b")
DESIGNATIONS = ["associate professor", "assistant professor", "professor", "principal", "director"]


def _designation(s: str) -> str:
    s = s.lower()
    for d in DESIGNATIONS:
        if d in s:
            return d.title()
    return ""


def extract_faculty(path: str, document_id: int | None) -> list[dict]:
    """Rows of the faculty table: name, dob, raw_id (hashed by caller, never stored), qualification, designation, doj."""
    rows: list[dict] = []
    if is_image(path):
        return rows
    with pymupdf.open(path) as doc:
        digital = sum(len(p.get_text()) for p in doc) > 50
        if digital:
            for pno, page in enumerate(doc, start=1):
                words = page.get_text("words")
                for table in page.find_tables().tables:
                    # Read each cell from the page's words (table.extract() can drop spaces with some fonts).
                    data = [[_cell_text(words, c) for c in row.cells] for row in table.rows]
                    header = [str(c or "").lower() for c in data[0]] if data else []
                    col = {k: next((i for i, h in enumerate(header) if k in h), None)
                           for k in ("name", "birth", "pan", "qualif", "design", "join")}
                    if col["name"] is None:
                        continue
                    for ri, cells in enumerate(data[1:], start=1):
                        cells = [norm_text(str(c or "")) for c in cells]
                        if not cells[col["name"]]:
                            continue
                        get = lambda k: cells[col[k]] if col[k] is not None and col[k] < len(cells) else ""
                        rbbox = list(table.rows[ri].bbox) if ri < len(table.rows) else list(table.bbox)
                        rows.append(_row(get("name"), get("birth"), get("pan"), get("qualif"),
                                         get("design"), get("join"), pno, rbbox, document_id))
            if rows:
                return rows
    # Fallback for scanned lists: one faculty member per OCR line.
    for pt in extract_pages(path):
        for ln in pt.lines:
            pan = PAN_RE.search(ln.text) or AADHAAR_RE.search(ln.text)
            desig = _designation(ln.text)
            if not pan or not desig:
                continue
            dates = re.findall(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}", ln.text)
            name = re.sub(r"^\d+[.)]?\s*", "", ln.text[: ln.text.find(dates[0])] if dates else ln.text).strip()
            qual = next((q for q in ("Ph.D", "PhD", "M.Tech", "M.E.", "ME", "M.S.", "B.Tech", "B.E.") if q.lower() in ln.text.lower()), "")
            rows.append(_row(name, dates[0] if dates else "", pan.group(1), qual, desig,
                             dates[1] if len(dates) > 1 else "", pt.page, ln.bbox, document_id))
    return rows


def _cell_text(words, cell) -> str:
    if not cell:
        return ""
    x0, y0, x1, y1 = cell
    inside = [w for w in words if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1]
    inside.sort(key=lambda w: (round(w[1]), w[0]))
    return " ".join(w[4] for w in inside)


def _row(name, dob, raw_id, qual, desig, doj, page, bbox, document_id):
    return {
        "name": name, "dob": parse_date(dob)[0] or "", "raw_id": raw_id.replace(" ", "").upper(),
        "qualification": qual, "designation": _designation(desig) or desig,
        "date_of_joining": parse_date(doj)[0] or "", "page": page,
        "bbox": [round(v, 1) for v in bbox], "document_id": document_id,
    }


def normalise_qualification(q: str) -> str:
    """Highest degree bucket: PHD | MASTERS | BACHELORS | OTHER."""
    s = q.lower().replace(".", "").replace(" ", "")
    if "phd" in s or "doctor" in s:
        return "PHD"
    if any(k in s for k in ("mtech", "me", "ms", "mba", "mca", "march", "mpharm", "mdes", "mplan", "msc")) and not s.startswith("b"):
        return "MASTERS"
    if any(k in s for k in ("btech", "be", "bsc", "barch", "bpharm")):
        return "BACHELORS"
    return "OTHER"
