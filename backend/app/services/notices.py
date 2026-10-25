"""Bilingual (English + Hindi) rectification notice drafts and Expert Visit Committee checklist.

Deterministic templates filled with the numbers each rule produced, so the notice can never state a
figure the rule engine did not compute. The officer edits and approves before anything is sent."""
from datetime import date

from .extractor import DOC_CATEGORIES
from .types import DEFICIENCY, FRAUD, REVIEW

T = {
    "APH-DOC-01": ("The following mandatory documents have not been uploaded: {missing}. Please upload them.",
                   "निम्नलिखित अनिवार्य दस्तावेज़ अपलोड नहीं किए गए हैं: {missing}। कृपया इन्हें अपलोड करें।"),
    "APH-BUA-01": ("The built-up area on the approved building plan is {claimed} sq.m against {required} sq.m required for the requested intake of {intake}; shortfall of {shortfall} sq.m.",
                   "स्वीकृत भवन नक्शे में निर्मित क्षेत्रफल {claimed} वर्ग मीटर है, जबकि अनुरोधित प्रवेश क्षमता {intake} के लिए {required} वर्ग मीटर आवश्यक है; कमी {shortfall} वर्ग मीटर।"),
    "APH-BUA-02": ("The built-up area declared on the portal ({declared} sq.m) is not supported by the approved building plan ({plan} sq.m). Please correct the declaration or submit the revised approved plan.",
                   "पोर्टल पर घोषित निर्मित क्षेत्रफल ({declared} वर्ग मीटर) स्वीकृत भवन नक्शे ({plan} वर्ग मीटर) से समर्थित नहीं है। कृपया घोषणा सुधारें या संशोधित स्वीकृत नक्शा प्रस्तुत करें।"),
    "APH-OC-01": ("The occupancy certificate covers {oc} sq.m whereas the building plan shows {plan} sq.m. Please submit an occupancy/completion certificate covering the full built-up area.",
                  "अधिभोग प्रमाणपत्र केवल {oc} वर्ग मीटर को कवर करता है, जबकि भवन नक्शे में {plan} वर्ग मीटर दर्शाया गया है। कृपया पूरे निर्मित क्षेत्र के लिए अधिभोग/पूर्णता प्रमाणपत्र प्रस्तुत करें।"),
    "APH-PLAN-01": ("The building plan does not carry the registration number of an architect registered with the Council of Architecture (or a licensed surveyor's certification). Please submit a duly certified plan.",
                    "भवन नक्शे पर वास्तुकला परिषद में पंजीकृत वास्तुकार की पंजीकरण संख्या (या लाइसेंसधारी सर्वेक्षक का प्रमाणन) नहीं है। कृपया विधिवत प्रमाणित नक्शा प्रस्तुत करें।"),
    "APH-FIRE-01": ("The fire safety certificate expired on {valid_until}, before the date of application ({app_date}). Please submit a valid certificate from the competent fire authority.",
                    "अग्नि सुरक्षा प्रमाणपत्र की वैधता {valid_until} को समाप्त हो गई, जो आवेदन की तिथि ({app_date}) से पहले है। कृपया सक्षम अग्निशमन प्राधिकरण से वैध प्रमाणपत्र प्रस्तुत करें।"),
    "APH-FSR-01": ("The faculty list shows {actual} teaching faculty against {required} required (S = {S}, faculty-student ratio 1:{ratio}); shortfall of {shortfall}. Please recruit and submit the updated faculty list.",
                   "संकाय सूची में {actual} शिक्षण संकाय सदस्य हैं, जबकि {required} आवश्यक हैं (S = {S}, संकाय-छात्र अनुपात 1:{ratio}); कमी {shortfall}। कृपया नियुक्ति करके अद्यतन संकाय सूची प्रस्तुत करें।"),
    "APH-FSR-02": ("{declared} faculty were declared on the portal, but only {actual} appear in the uploaded faculty list. Please reconcile the two.",
                   "पोर्टल पर {declared} संकाय सदस्य घोषित किए गए, किंतु अपलोड की गई संकाय सूची में केवल {actual} हैं। कृपया मिलान करें।"),
    "APH-CADRE-01": ("The cadre ratio is not met: {prof} Professors and {assoc} Associate Professors against {req_prof} and {req_assoc} required (1:2:6).",
                     "संवर्ग अनुपात पूरा नहीं है: {prof} प्रोफेसर और {assoc} एसोसिएट प्रोफेसर हैं, जबकि क्रमशः {req_prof} और {req_assoc} आवश्यक हैं (1:2:6)।"),
    "APH-FQ-01": ("{count} faculty member(s) do not hold the minimum qualification for their cadre: {names}. Please submit qualification proofs or revise designations.",
                  "{count} संकाय सदस्य अपने संवर्ग की न्यूनतम योग्यता नहीं रखते: {names}। कृपया योग्यता प्रमाण प्रस्तुत करें या पदनाम संशोधित करें।"),
    "APH-LAND-01": ("The land is held on a lease of {term} years with {left} years remaining; at least {min_term} years with {min_left} years remaining is required.",
                    "भूमि {term} वर्ष के पट्टे पर है जिसमें {left} वर्ष शेष हैं; कम से कम {min_term} वर्ष का पट्टा और {min_left} वर्ष शेष होना आवश्यक है।"),
    "APH-AFF-01": ("The affidavit has the following issues: {problems}. Please submit a corrected, notarised affidavit.",
                   "शपथपत्र में निम्न कमियाँ हैं: {problems}। कृपया संशोधित एवं नोटरीकृत शपथपत्र प्रस्तुत करें।"),
    "APH-EXP-01": ("Only {core} core branch(es) are offered; at least {need} are required before an increase in intake.",
                   "केवल {core} मुख्य शाखा(एँ) संचालित हैं; प्रवेश क्षमता वृद्धि से पहले कम से कम {need} आवश्यक हैं।"),
    "APH-EXP-02": ("An inquiry by an investigating agency is declared pending; an increase in intake cannot be considered.",
                   "किसी जांच एजेंसी की जांच लंबित घोषित है; प्रवेश क्षमता वृद्धि पर विचार नहीं किया जा सकता।"),
}

TYPE_LABEL = {"EOA": ("Extension of Approval", "अनुमोदन का विस्तार"),
              "INTAKE_INCREASE": ("Increase in Intake", "प्रवेश क्षमता में वृद्धि"),
              "NEW_INSTITUTION": ("Approval of New Institution", "नई संस्था का अनुमोदन")}


def _fmt(tpl: str, params: dict, fallback: str) -> str:
    p = {k: (", ".join(map(str, v)) if isinstance(v, list) else (f"{v:,}" if isinstance(v, int) and v > 9999 else v))
         for k, v in params.items()}
    try:
        return tpl.format(**p)
    except (KeyError, IndexError, ValueError):
        return fallback


def build(app, institution, findings, edition: str) -> dict[str, str]:
    """findings: list of dicts/objects with code, kind, title, summary, clause_ref, params."""
    deficiencies = [f for f in findings if f["kind"] == DEFICIENCY and f.get("review_status") != "OVERRIDDEN"]
    today = date.today().strftime("%d-%m-%Y")
    t_en, t_hi = TYPE_LABEL.get(app.type, (app.type, app.type))
    lines_en, lines_hi = [], []
    for i, f in enumerate(deficiencies, start=1):
        en, hi = T.get(f["code"], ("{_}", "{_}"))
        p = f.get("params") or {}
        lines_en.append(f"{i}. {_fmt(en, p, f['summary'])}\n   (Reference: {f['clause_ref']})")
        lines_hi.append(f"{i}. {_fmt(hi, p, f['summary'])}\n   (संदर्भ: {f['clause_ref']})")
    if not deficiencies:
        lines_en = ["No deficiencies were found against the rules checked."]
        lines_hi = ["जांचे गए नियमों के अनुसार कोई कमी नहीं पाई गई।"]

    en = f"""DRAFT RECTIFICATION NOTICE: for scrutiny officer review (prototype output, not an official communication)

Ref: {app.ref_no}/DEF   Date: {today}

To
The Principal / Director
{institution.name} ({institution.aicte_id})
{institution.address}

Subject: Deficiencies observed in application {app.ref_no} for {t_en}, Academic Year {app.academic_year}

Sir/Madam,

On scrutiny of the above application against the {edition}, the following deficiencies have been observed:

{chr(10).join(lines_en)}

You are requested to rectify the above deficiencies and upload the compliance report with supporting documents on the portal within the period permitted under the {edition}.

Scrutiny Officer
"""
    hi = f"""प्रारूप सुधार सूचना: संवीक्षा अधिकारी की समीक्षा हेतु (प्रोटोटाइप आउटपुट, आधिकारिक पत्र नहीं)

संदर्भ: {app.ref_no}/DEF   दिनांक: {today}

सेवा में
प्राचार्य / निदेशक
{institution.name} ({institution.aicte_id})
{institution.address}

विषय: शैक्षणिक वर्ष {app.academic_year} हेतु {t_hi} के आवेदन {app.ref_no} में पाई गई कमियाँ

महोदय/महोदया,

उपर्युक्त आवेदन की {edition} के अनुसार संवीक्षा करने पर निम्नलिखित कमियाँ पाई गई हैं:

{chr(10).join(lines_hi)}

आपसे अनुरोध है कि उपर्युक्त कमियों को दूर करके सहायक दस्तावेज़ों सहित अनुपालन रिपोर्ट {edition} के अंतर्गत निर्धारित अवधि में पोर्टल पर अपलोड करें।

संवीक्षा अधिकारी
"""
    return {"en": en, "hi": hi}


CHECK = {
    "XIN-FACULTY": "Verify that {names} are on this institution's payroll and teaching full-time (salary credits, attendance, timetable).",
    "XIN-LOOKALIKE": "Confirm the identity of the faculty member flagged as a possible duplicate.",
    "XIN-PHOTO": "Locate and photograph the facility shown in the flagged photo; confirm it exists on this campus.",
    "XIN-FILE": "Ask for the original of the file that is identical to another institution's submission.",
    "APH-BUA-01": "Measure the built-up area of instructional, administrative and amenity blocks against the approved plan.",
    "APH-BUA-02": "Check the actual constructed area; the declared area exceeds the approved plan.",
    "APH-OC-01": "Identify blocks in use that are not covered by the occupancy certificate.",
    "CON-SURVEY": "Match the survey number on the land records with the plan and the physical site.",
    "CON-ADDRESS": "Confirm the campus address on site against the documents.",
    "CON-TRUST": "Verify the legal owner of the land and the managing trust/society.",
    "HIS-BUA": "Ask why the built-up area decreased since last year and inspect the affected blocks.",
    "HIS-SURVEY": "Verify the change of land survey number with the land records office.",
    "HIS-FACULTY": "Interview a sample of newly joined faculty; check appointment letters and joining reports.",
    "AUT-VISUAL": "Inspect the original paper document for the region flagged on the scanned page.",
    "AUT-SIG": "Obtain a fresh certified copy from the issuing authority.",
    "AUT-QR": "Verify the certificate directly with the issuing authority.",
    "GEO-PHOTO": "Record GPS-tagged photos of the campus and labs during the visit.",
    "APH-FIRE-01": "Inspect fire-safety installations and the current fire NOC on site.",
    "APH-FSR-01": "Count faculty present against the faculty list.",
    "APH-CADRE-01": "Verify Professors and Associate Professors in position.",
}


def site_visit_checklist(findings) -> list[dict]:
    items, seen = [], set()
    order = {FRAUD: 0, DEFICIENCY: 1, REVIEW: 2}
    for f in sorted(findings, key=lambda f: order.get(f["kind"], 9)):
        if f["kind"] not in order or f["code"] in seen or f["code"] not in CHECK:
            continue
        seen.add(f["code"])
        p = f.get("params") or {}
        text = CHECK[f["code"]]
        if "{names}" in text:
            text = text.replace("{names}", ", ".join(p.get("names", [])[:6]) or "the flagged faculty")
        items.append({"code": f["code"], "kind": f["kind"], "item": text, "context": f["summary"]})
    return items


__all__ = ["build", "site_visit_checklist", "DOC_CATEGORIES"]
