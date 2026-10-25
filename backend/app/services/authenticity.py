"""Authenticity screening in layers, each labelled with exactly what it proves.

Level 1  File & metadata     -> signs of editing, not proof of fraud
Level 2  Visual forensics    -> suspicious regions to inspect (noise-level inconsistency on scans)
Level 3  Signatures & QR     -> strong: unaltered since signing / matches the issuer's record
Level 4  Issuer verification -> MOCK connector in the prototype, clearly labelled
"""
import io
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

from ..config import settings
from .parser import embedded_rasters, is_image, page_images
from .types import FRAUD, REVIEW, VERIFIED, Evidence, FieldValue, FindingData

EDIT_TOOLS = re.compile(r"photoshop|gimp|paint\.net|illustrator|inkscape|pdf\s*editor|sejda|ilovepdf|smallpdf|"
                        r"pdfescape|foxit\s*phantom|nitro\s*pro|pdf-xchange\s*editor|canva", re.I)
TRUST_DIR = settings.data_dir / "trust"


# ---------- Level 1 ----------------------------------------------------------------
def metadata_check(path: Path, doc_id: int, category: str) -> list[FindingData]:
    if is_image(path):
        return []
    out = []
    raw = path.read_bytes()
    with pymupdf.open(path) as pdf:
        meta = pdf.metadata or {}
        is_signed = any(w.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE for p in pdf for w in (p.widgets() or []))
    tools = " ".join(filter(None, [meta.get("producer"), meta.get("creator")]))
    reasons = []
    if EDIT_TOOLS.search(tools):
        reasons.append(f"created/modified with editing software ({tools.strip()})")
    revisions = raw.count(b"%%EOF")
    if revisions > 1 and not is_signed:
        reasons.append(f"file was saved {revisions} times (incremental edits after creation)")
    c, m = meta.get("creationDate", ""), meta.get("modDate", "")
    if c and m and m[2:10] > c[2:10] and not is_signed:
        reasons.append(f"modified on {m[2:6]}-{m[6:8]}-{m[8:10]}, after creation on {c[2:6]}-{c[6:8]}-{c[8:10]}")
    if reasons:
        out.append(FindingData("AUT-META", REVIEW, "Signs of editing in file metadata", "; ".join(reasons).capitalize() + ".",
                               "low", "authenticity", "authenticity", "NEEDS_REVIEW",
                               establishes="Level 1 (metadata): signs that the file was edited. Common for legitimate "
                                           "scans too; not proof of fraud.",
                               evidence=[Evidence(doc_id, category, 1, None, "metadata", tools)]))
    return out


# ---------- Level 2 ------------------------------------------------------------------
def noise_inconsistency(img: Image.Image, block: int = 16) -> list[list[int]] | None:
    """Scanned pages carry sensor/paper noise everywhere. A pasted, digitally-clean patch (white-out
    and retyped numbers) has almost no noise. Returns suspicious regions [x0,y0,x1,y1] in pixels, or
    None if the image has no measurable noise (born-digital: method not applicable)."""
    g = np.asarray(img.convert("L"), dtype=np.float32)
    if g.shape[0] < 200 or g.shape[1] < 200:
        return None
    resid = g - cv2.GaussianBlur(g, (0, 0), 1.5)
    h, w = (g.shape[0] // block) * block, (g.shape[1] // block) * block
    rb = resid[:h, :w].reshape(h // block, block, w // block, block)
    gb = g[:h, :w].reshape(h // block, block, w // block, block)
    std = rb.std(axis=(1, 3))
    mean = gb.mean(axis=(1, 3))
    paper = mean > 170
    if paper.sum() < 50:
        return None
    ref = float(np.median(std[paper]))
    if ref < 1.2:
        return None
    clean = (std < 0.3 * ref) & paper
    n, labels, stats, _ = cv2.connectedComponentsWithStats(clean.astype(np.uint8), connectivity=8)
    regions = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area >= 4 and bw * bh <= 0.25 * clean.size:
            regions.append([int(x * block), int(y * block), int((x + bw) * block), int((y + bh) * block)])
    return regions


def visual_check(path: Path, doc_id: int, category: str) -> list[FindingData]:
    if category == "campus_photo":
        return []
    out = []
    for page, im, rect, px_per_pt in embedded_rasters(path):
        regions = noise_inconsistency(im)
        if not regions:
            continue
        sx = (rect[2] - rect[0]) / im.width
        sy = (rect[3] - rect[1]) / im.height
        ev = [Evidence(doc_id, category, page,
                       [round(rect[0] + r[0] * sx, 1), round(rect[1] + r[1] * sy, 1),
                        round(rect[0] + r[2] * sx, 1), round(rect[1] + r[3] * sy, 1)],
                       "suspicious_region", None, "", "region with inconsistent noise") for r in regions[:5]]
        out.append(FindingData("AUT-VISUAL", FRAUD, "Possible alteration on scanned page",
                               f"{len(regions)} region(s) on page {page} lack the scanner noise present on the rest of the "
                               "page, a typical trace of pasted or retyped content.",
                               "high", "authenticity", "authenticity", "FLAGGED",
                               establishes="Level 2 (visual forensics): marks regions to inspect against the original. "
                                           "Screening signal, not proof.",
                               evidence=ev, params={"page": page, "regions": len(regions)}))
    return out


# ---------- Level 3: digital signatures ---------------------------------------------------
def _trust_context():
    from pyhanko.keys import load_cert_from_pemder
    from pyhanko_certvalidator import ValidationContext
    roots = [load_cert_from_pemder(str(p)) for p in TRUST_DIR.glob("*root*.pem")]
    return ValidationContext(trust_roots=roots, allow_fetching=False) if roots else ValidationContext(allow_fetching=False)


def signature_check(path: Path, doc_id: int, category: str) -> tuple[list[FindingData], dict | None]:
    if is_image(path):
        return [], None
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature
    except ImportError:
        return [], None
    with open(path, "rb") as fh:
        try:
            reader = PdfFileReader(fh, strict=False)
            sigs = list(reader.embedded_signatures)
        except Exception:
            return [], None
        if not sigs:
            return [], None
        sig = sigs[0]
        try:
            st = validate_pdf_signature(sig, _trust_context())
        except Exception as exc:
            return [FindingData("AUT-SIG", REVIEW, "Digital signature could not be validated", str(exc)[:200], "medium",
                                "authenticity", "authenticity", "NEEDS_REVIEW",
                                evidence=[Evidence(doc_id, category, 1)])], {"label": "Signature unreadable"}
    signer = "unknown signer"
    if st.signing_cert:
        subj = st.signing_cert.subject.native
        signer = subj.get("common_name") or st.signing_cert.subject.human_friendly
    ev = [Evidence(doc_id, category, 1, None, "digital_signature", signer)]
    if not st.intact or not st.valid:
        return [FindingData("AUT-SIG", FRAUD, "Document altered after it was digitally signed",
                            f"The signature by {signer} no longer matches the file contents: the document was modified after signing.",
                            "high", "authenticity", "authenticity", "FLAGGED",
                            establishes="Level 3 (cryptographic): the signed bytes were changed. Strong evidence of tampering.",
                            evidence=ev)], {"label": "Altered after signing", "level": 3, "signer": signer}
    if not st.trusted:
        return [FindingData("AUT-SIG", REVIEW, "Valid signature from an unrecognised signer",
                            f"Signature by {signer} is intact, but the signer's certificate is not in the trusted issuer list.",
                            "medium", "authenticity", "authenticity", "NEEDS_REVIEW",
                            establishes="Level 3: the file is unaltered since signing, but who signed it is not established.",
                            evidence=ev)], {"label": "Signed, signer not trusted", "level": 3, "signer": signer}
    return [FindingData("AUT-SIG", VERIFIED, "Digital signature valid",
                        f"Signed by {signer}; signature intact and certificate chain trusted.",
                        "low", "authenticity", "authenticity", "VERIFIED",
                        establishes="Level 3 (cryptographic): the document is unaltered since it was signed by a trusted issuer.",
                        evidence=ev)], {"label": "Verified: digital signature", "level": 3, "signer": signer}


# ---------- Level 3/4: QR codes + mock issuer registry ------------------------------------------
def _registry() -> dict:
    p = TRUST_DIR / "issuer_registry_mock.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def qr_check(path: Path, doc_id: int, category: str, fields: list[FieldValue]) -> tuple[list[FindingData], dict | None]:
    detector = cv2.QRCodeDetector()
    for page, im, scale in page_images(path, dpi=150):
        arr = cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR)
        data, pts, _ = detector.detectAndDecode(arr)
        if not data:
            continue
        bbox = None
        if pts is not None:
            p = pts.reshape(-1, 2) / scale
            bbox = [round(float(p[:, 0].min()), 1), round(float(p[:, 1].min()), 1),
                    round(float(p[:, 0].max()), 1), round(float(p[:, 1].max()), 1)]
        ev = [Evidence(doc_id, category, page, bbox, "qr_code", data[:120])]
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return [], {"label": "QR present (not machine-verifiable)", "level": 3}
        printed = {f.field: f for f in fields}
        mismatches = []
        for key in ("certificate_no", "valid_until"):
            if key in payload and key in printed and str(printed[key].value) != str(payload[key]):
                mismatches.append(f"{key.replace('_', ' ')}: printed “{printed[key].original_text}”, QR says “{payload[key]}”")
                ev.append(printed[key].evidence("differs from QR"))
        if mismatches:
            return [FindingData("AUT-QR", FRAUD, "Printed details differ from the certificate's QR code",
                                "; ".join(mismatches) + ".", "high", "authenticity", "authenticity", "FLAGGED",
                                establishes="Level 3: the QR is generated by the issuer; text that disagrees with it was "
                                            "probably edited.", evidence=ev,
                                params={"mismatches": mismatches})], {"label": "QR mismatch", "level": 3}
        rec = _registry().get(str(payload.get("certificate_no", "")))
        if rec and all(str(rec.get(k)) == str(payload.get(k)) for k in ("valid_until", "issuer") if k in rec):
            return [FindingData("AUT-QR", VERIFIED, "QR code matches the issuer registry (mock)",
                                f"Certificate {payload.get('certificate_no')} found in the {rec.get('issuer')} registry with the "
                                "same validity. Registry is a MOCK connector standing in for the issuer portal.",
                                "low", "authenticity", "authenticity", "VERIFIED",
                                establishes="Level 4 (issuer check, MOCK): in production this queries the issuing "
                                            "authority / DigiLocker. Labelled mock in the prototype.", evidence=ev)], \
                {"label": "Verified: QR + issuer registry (mock)", "level": 4}
        return [FindingData("AUT-QR", REVIEW, "Certificate not found in the issuer registry (mock)",
                            f"QR decoded (certificate {payload.get('certificate_no')}) but no matching record in the mock registry.",
                            "medium", "authenticity", "authenticity", "NEEDS_REVIEW",
                            establishes="Level 4 (MOCK): absence from a mock registry is only a prompt to check with the issuer.",
                            evidence=ev)], {"label": "QR read, not in registry", "level": 3}
    return [], None


# ---------- photos: perceptual hash + GPS -----------------------------------------------
def photo_info(path: Path) -> tuple[str | None, float | None, float | None]:
    import imagehash
    try:
        im = Image.open(path).convert("RGB")
        ph = f"{imagehash.phash(im)}{imagehash.dhash(im)}"  # 16 hex phash + 16 hex dhash
    except Exception:
        return None, None, None
    lat = lon = None
    try:
        import piexif
        gps = piexif.load(str(path)).get("GPS", {})
        if gps.get(2) and gps.get(4):
            def dms(v):
                return v[0][0] / v[0][1] + v[1][0] / v[1][1] / 60 + v[2][0] / v[2][1] / 3600
            lat, lon = dms(gps[2]), dms(gps[4])
            if gps.get(1) in (b"S", "S"):
                lat = -lat
            if gps.get(3) in (b"W", "W"):
                lon = -lon
    except Exception:
        pass
    return ph, lat, lon


def haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def gps_check(photos: list[tuple[int, str, float | None, float | None]], campus: tuple[float, float] | None,
              max_km: float) -> list[FindingData]:
    """photos: (doc_id, filename, lat, lon). Campus from land deed / institution record."""
    if not campus:
        return []
    out = []
    far = [(d, f, la, lo, haversine_km(campus[0], campus[1], la, lo)) for d, f, la, lo in photos if la is not None]
    far = [x for x in far if x[4] > max_km]
    if far:
        out.append(FindingData("GEO-PHOTO", REVIEW, "Photo location far from the declared campus",
                               "; ".join(f"“{f}” taken {km:.1f} km from the campus" for _, f, _, _, km in far[:5]) + ".",
                               "medium", "geospatial", "authenticity", "NEEDS_REVIEW",
                               establishes="Compares photo GPS metadata with the campus coordinates in the land deed. "
                                           "GPS can be missing or edited, so this is a screening signal.",
                               evidence=[Evidence(d, "campus_photo", 1, None, "gps", f"{la:.5f}, {lo:.5f}", "", f"{km:.1f} km away")
                                         for d, f, la, lo, km in far[:5]],
                               params={"campus": list(campus), "photos": [{"document_id": d, "lat": la, "lon": lo, "km": round(km, 2)}
                                                                         for d, f, la, lo, km in far]}))
    return out
