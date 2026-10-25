"""Synthetic dossier generator (brief section 12).

Creates fictional institutions with full document sets (PDFs + JPEG photos) for two academic years,
deliberately injects known problems, and writes a ground-truth file so detection can be MEASURED.

All institutions, people, numbers and certificates are fictional. Issuers are "(Demo)" mock issuers.

    python scripts/generate_synthetic.py            # writes data/synthetic/
"""
import datetime as dt
import io
import json
import os
import random
import shutil
import sys
from pathlib import Path

import numpy as np
import piexif
import pymupdf
import qrcode
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

# tzlocal (used by pyhanko) rejects legacy zone names such as Asia/Calcutta
if os.environ.get("TZ") in ("Asia/Calcutta", "IST"):
    os.environ["TZ"] = "Asia/Kolkata"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "synthetic"
TRUST = ROOT / "data" / "trust"
DEVA = ROOT / "data" / "fonts" / "NotoSansDevanagari-400.ttf"
SALT_SEED = 2026

FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Arjun", "Rohan", "Kabir", "Anaya", "Diya", "Saanvi", "Meera", "Kavya",
         "Priya", "Neha", "Rahul", "Amit", "Sanjay", "Vikram", "Pooja", "Sneha", "Nikhil", "Tanvi", "Harsh", "Ritika",
         "Manoj", "Suresh", "Lakshmi", "Deepa", "Gaurav", "Swati", "Ajay", "Varun", "Shreya", "Anil", "Kiran", "Farhan",
         "Zoya", "Imran", "Gurpreet", "Simran", "Joseph", "Mary", "Arvind", "Bhavna", "Chetan", "Divya", "Esha", "Girish"]
LAST = ["Sharma", "Patil", "Iyer", "Nair", "Reddy", "Kulkarni", "Deshmukh", "Gupta", "Verma", "Joshi", "Rao", "Menon",
        "Singh", "Kaur", "Das", "Banerjee", "Mukherjee", "Pillai", "Shetty", "Chavan", "Pawar", "Jain", "Mehta", "Shah",
        "Bhat", "Hegde", "Naidu", "Khan", "Qureshi", "Fernandes", "D'Souza", "Thomas", "Yadav", "Mishra", "Pandey"]
CORE = ["Computer Science & Engineering", "Mechanical Engineering", "Civil Engineering", "Electrical Engineering",
        "Electronics & Communication Engg."]

# ------------------------------------------------------------------ institutions & planted problems
CITIES = [  # (city, district, state, lat, lon)
    ("Pune", "Pune", "Maharashtra", 18.5204, 73.8567), ("Nashik", "Nashik", "Maharashtra", 19.9975, 73.7898),
    ("Nagpur", "Nagpur", "Maharashtra", 21.1458, 79.0882), ("Indore", "Indore", "Madhya Pradesh", 22.7196, 75.8577),
    ("Jaipur", "Jaipur", "Rajasthan", 26.9124, 75.7873), ("Coimbatore", "Coimbatore", "Tamil Nadu", 11.0168, 76.9558),
    ("Mysuru", "Mysuru", "Karnataka", 12.2958, 76.6394), ("Vijayawada", "Krishna", "Andhra Pradesh", 16.5062, 80.6480),
    ("Bhopal", "Bhopal", "Madhya Pradesh", 23.2599, 77.4126), ("Lucknow", "Lucknow", "Uttar Pradesh", 26.8467, 80.9462),
    ("Kochi", "Ernakulam", "Kerala", 9.9312, 76.2673), ("Bhubaneswar", "Khordha", "Odisha", 20.2961, 85.8245),
    ("Dehradun", "Dehradun", "Uttarakhand", 30.3165, 78.0322), ("Surat", "Surat", "Gujarat", 21.1702, 72.8311),
]
NAMES = ["Kaveri Valley Institute of Technology", "Sahyadri Ridge College of Engineering", "Narmada Tech Institute of Engineering",
         "Vindhya Crest Institute of Technology", "Aravalli Heights College of Engineering", "Nilgiri Vale Institute of Technology",
         "Chamundi Hills Engineering College", "Krishna Delta Institute of Technology", "Upper Lake College of Engineering",
         "Gomti Riverside Institute of Technology", "Periyar Coast College of Engineering", "Mahanadi Institute of Engineering",
         "Doon Foothills Institute of Technology", "Tapi Bank College of Engineering"]
TRUSTS = ["Kaveri Shikshan Prasarak Mandal", "Sahyadri Education Trust", "Narmada Vidya Pratishthan", "Vindhya Gyan Foundation",
          "Aravalli Shiksha Samiti", "Nilgiri Educational Society", "Chamundi Vidya Trust", "Krishna Delta Education Society",
          "Upper Lake Vidya Mandal", "Gomti Shiksha Trust", "Periyar Educational Trust", "Mahanadi Vidya Parishad",
          "Doon Valley Education Society", "Tapi Shikshan Sanstha"]

# expected codes per planted problem, plus allowed side-effects (not counted as false positives)
PROBLEMS = {
    "bua_shortfall": (["APH-BUA-01"], []),
    "declared_overstated": (["APH-BUA-02"], []),
    "oc_partial": (["APH-OC-01"], []),
    "survey_mismatch": (["CON-SURVEY"], []),
    "address_mismatch": (["CON-ADDRESS"], []),
    "trust_mismatch": (["CON-TRUST"], []),
    "ghost_faculty": (["XIN-FACULTY"], []),
    "faculty_lookalike": (["XIN-LOOKALIKE"], []),
    "photo_reuse": (["XIN-PHOTO"], []),
    "identical_file": (["XIN-FILE"], ["CON-ADDRESS", "CON-INSTNAME"]),
    "fire_expired": (["APH-FIRE-01"], []),
    "faculty_shortfall": (["APH-FSR-01"], ["APH-CADRE-01"]),
    "declared_faculty_overstated": (["APH-FSR-02"], []),
    "unqualified_faculty": (["APH-FQ-01"], []),
    "cadre_shortfall": (["APH-CADRE-01"], []),
    "lease_short": (["APH-LAND-01"], []),
    "affidavit_not_notarised": (["APH-AFF-01"], []),
    "affidavit_intake_mismatch": (["APH-AFF-01"], []),
    "missing_document": (["APH-DOC-01"], ["CON-TRUST"]),
    "no_architect_reg": (["APH-PLAN-01"], []),
    "core_branches": (["APH-EXP-01"], []),
    "inquiry_pending": (["APH-EXP-02"], []),
    "history_bua_shrink": (["HIS-BUA"], []),
    "history_survey_change": (["HIS-SURVEY"], []),
    "history_faculty_churn": (["HIS-FACULTY"], []),
    "tamper_scan": (["AUT-VISUAL"], []),
    "sig_tamper": (["AUT-SIG"], ["AUT-QR"]),
    "qr_mismatch": (["AUT-QR"], []),
    "gps_far": (["GEO-PHOTO"], []),
}

PROFILES = [  # key, type, problems, extras
    ("I01", "EOA", [], {}),
    ("I02", "INTAKE_INCREASE", [], {"scan_all": True}),
    ("I03", "EOA", [], {"lease": True, "scan_affidavit": True, "low_admissions": True}),
    ("I04", "INTAKE_INCREASE", [], {"hindi": True}),
    ("I05", "INTAKE_INCREASE", ["bua_shortfall", "survey_mismatch", "ghost_faculty", "photo_reuse", "faculty_lookalike"], {"hero": True}),
    ("I06", "EOA", ["ghost_faculty", "faculty_shortfall", "fire_expired", "faculty_lookalike"], {}),
    ("I07", "INTAKE_INCREASE", ["declared_overstated", "oc_partial", "history_bua_shrink"], {}),
    ("I08", "EOA", ["lease_short", "trust_mismatch", "unqualified_faculty"], {"scan_all": True}),
    ("I09", "INTAKE_INCREASE", ["tamper_scan", "sig_tamper", "missing_document"], {}),
    ("I10", "EOA", ["qr_mismatch", "affidavit_not_notarised", "history_faculty_churn"], {}),
    ("I11", "INTAKE_INCREASE", ["no_architect_reg", "core_branches", "inquiry_pending"], {}),
    ("I12", "EOA", ["cadre_shortfall", "declared_faculty_overstated", "gps_far", "history_survey_change"], {"scan_all": True}),
    ("I13", "INTAKE_INCREASE", ["affidavit_intake_mismatch", "address_mismatch"], {"hindi": True}),
    ("I14", "EOA", ["identical_file"], {"scan_affidavit": True}),
]

AY_PREV, AY_CUR = "2025-26", "2026-27"
APP_DATE = {AY_PREV: dt.date(2025, 1, 17), AY_CUR: dt.date(2026, 1, 20)}


def rnd_pan(r: random.Random) -> str:
    L = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(r.choice(L) for _ in range(3)) + "P" + r.choice(L) + f"{r.randint(1000, 9999)}" + r.choice(L)


def make_faculty(r: random.Random, n: int, cadre=(1, 2, 6), bad_qual=0, joined_recently=0, year=2025) -> list[dict]:
    t = sum(cadre)
    n_p = max(1, round(n * cadre[0] / t)) + 1
    n_a = round(n * cadre[1] / t) + 1
    out = []
    for i in range(n):
        desig = "Professor" if i < n_p else "Associate Professor" if i < n_p + n_a else "Assistant Professor"
        qual = "Ph.D" if desig != "Assistant Professor" or r.random() < 0.25 else r.choice(["M.Tech", "M.E."])
        yr = r.randint(1965, 1995)
        doj_year = r.randint(2008, year - 1)
        out.append({"name": f"{r.choice(FIRST)} {r.choice(LAST)}", "dob": dt.date(yr, r.randint(1, 12), r.randint(1, 28)),
                    "pan": rnd_pan(r), "qualification": qual, "designation": desig,
                    "doj": dt.date(doj_year, r.randint(1, 12), r.randint(1, 28))})
    for f in out[-bad_qual:] if bad_qual else []:
        f["qualification"] = "B.Tech"
    return out


# ------------------------------------------------------------------ PDF helpers
class Sheet:
    """A4 page builder with a letterhead band and label: value lines."""

    def __init__(self, doc, issuer: str, title: str, hindi_title: str | None = None, ref: str = ""):
        self.doc = doc
        self.page = doc.new_page(width=595, height=842)
        p = self.page
        p.draw_rect(pymupdf.Rect(0, 0, 595, 70), color=None, fill=(0.93, 0.95, 0.98))
        p.insert_text((40, 32), issuer, fontname="hebo", fontsize=13, color=(0.1, 0.2, 0.45))
        if ref:
            p.insert_text((40, 52), ref, fontname="helv", fontsize=9, color=(0.35, 0.35, 0.35))
        y = 100
        if hindi_title and DEVA.exists():
            p.insert_htmlbox(pymupdf.Rect(40, 78, 555, 100), f"<div style='font-family:deva;font-size:13px;text-align:center'>{hindi_title}</div>",
                             css="@font-face {font-family: deva; src: url(NotoSansDevanagari-400.ttf);}",
                             archive=pymupdf.Archive(str(DEVA.parent)))
            y = 112
        p.insert_text((297 - pymupdf.get_text_length(title, "hebo", 14) / 2, y), title, fontname="hebo", fontsize=14)
        p.draw_line((40, y + 10), (555, y + 10), color=(0.6, 0.6, 0.6), width=0.6)
        self.y = y + 36

    def kv(self, label: str, value: str, gap: float = 22):
        self.page.insert_text((50, self.y), f"{label}:", fontname="hebo", fontsize=10.5)
        self.page.insert_text((230, self.y), str(value), fontname="helv", fontsize=10.5)
        self.y += gap

    def para(self, text: str, size: float = 10.5, height: float | None = None):
        h = height or (14 + 13.5 * (len(text) // 88 + 1))
        self.page.insert_textbox(pymupdf.Rect(50, self.y - 10, 545, self.y - 10 + h), text, fontname="helv", fontsize=size)
        self.y += h

    def hindi(self, text: str, height: float = 22):
        if DEVA.exists():
            self.page.insert_htmlbox(pymupdf.Rect(50, self.y - 12, 545, self.y - 12 + height),
                                     f"<div style='font-family:deva;font-size:11px'>{text}</div>",
                                     css="@font-face {font-family: deva; src: url(NotoSansDevanagari-400.ttf);}",
                                     archive=pymupdf.Archive(str(DEVA.parent)))
            self.y += height

    def stamp(self, text: str, x=430, y=None, color=(0.55, 0.1, 0.1)):
        y = y or self.y + 30
        self.page.draw_circle((x, y), 38, color=color, width=1.4)
        self.page.draw_circle((x, y), 33, color=color, width=0.6)
        for i, part in enumerate(text.split("\n")):
            w = pymupdf.get_text_length(part, "hebo", 7)
            self.page.insert_text((x - w / 2, y - 6 + i * 9), part, fontname="hebo", fontsize=7, color=color)

    def signature(self, name: str, role: str, x=60):
        y = self.y + 40
        self.page.draw_bezier((x, y), (x + 20, y - 18), (x + 45, y + 12), (x + 80, y - 8), color=(0.1, 0.1, 0.5), width=1)
        self.page.insert_text((x, y + 18), name, fontname="helv", fontsize=9.5)
        self.page.insert_text((x, y + 31), role, fontname="helv", fontsize=8.5, color=(0.3, 0.3, 0.3))
        self.y = y + 60

    def qr(self, payload: dict, x=470, y=740, size=80):
        img = qrcode.make(json.dumps(payload, separators=(",", ":")), box_size=4, border=2)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        self.page.insert_image(pymupdf.Rect(x, y, x + size, y + size), stream=buf.getvalue())
        self.page.insert_text((x - 4, y + size + 10), "Scan to verify", fontname="helv", fontsize=7)


def save_pdf(doc, path: Path, producer="Municipal e-Office (Demo)", expand=False):
    doc.set_metadata({"producer": producer, "creator": producer, "creationDate": "D:20251201100000",
                      "modDate": "D:20251201100000"})
    data = doc.tobytes(expand=255 if expand else 0, garbage=3, deflate=not expand)
    path.write_bytes(data)
    return data


def scan_pdf(clean: bytes, path: Path, tamper: tuple[str, str] | None = None, seed=0):
    """Simulate a scanned copy: raster at 200 dpi, paper tint, sensor noise, slight blur, JPEG.
    tamper=(original_text, new_text): after 'scanning', paste a clean patch with new text (the forgery)."""
    rng = np.random.default_rng(seed)
    src = pymupdf.open(stream=clean, filetype="pdf")
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=200)
        im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L").filter(ImageFilter.GaussianBlur(0.6))
        arr = np.asarray(im, dtype=np.float32) * 0.96 + 4
        arr += rng.normal(0, 7.5, arr.shape)
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        if tamper:
            hits = page.search_for(tamper[0])
            if hits:
                s = 200 / 72
                r = hits[0]
                box = [int(r.x0 * s) - 6, int(r.y0 * s) - 5, int(r.x1 * s) + 40, int(r.y1 * s) + 5]
                d = ImageDraw.Draw(im)
                d.rectangle(box, fill=246)
                tmp = pymupdf.open()
                tp = tmp.new_page(width=r.width + 40, height=r.height + 4)
                tp.insert_text((0, r.height - 1), tamper[1], fontname="helv", fontsize=10.5)
                tpix = tp.get_pixmap(dpi=200)
                patch = Image.open(io.BytesIO(tpix.tobytes("png"))).convert("L")
                patch = Image.fromarray(np.where(np.asarray(patch) > 200, 246, np.asarray(patch)).astype(np.uint8))
                im.paste(patch, (box[0] + 6, box[1] + 4))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        np_ = out.new_page(width=page.rect.width, height=page.rect.height)
        np_.insert_image(np_.rect, stream=buf.getvalue())
    out.set_metadata({"producer": "ScanSnap Manager (Demo)", "creator": "ScanSnap Manager (Demo)",
                      "creationDate": "D:20251210093000", "modDate": "D:20251210093000"})
    path.write_bytes(out.tobytes(garbage=3, deflate=True))


# ------------------------------------------------------------------ trust material (demo PKI)
def demo_pki():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    TRUST.mkdir(parents=True, exist_ok=True)
    keys = OUT / "_pki"
    keys.mkdir(parents=True, exist_ok=True)
    now = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)

    def name(cn):
        return x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Demo Issuers (Mock)"),
                          x509.NameAttribute(NameOID.COMMON_NAME, cn)])

    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root = (x509.CertificateBuilder().subject_name(name("Demo Root CA (Mock)")).issuer_name(name("Demo Root CA (Mock)"))
            .public_key(root_key.public_key()).serial_number(1001).not_valid_before(now)
            .not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
            .sign(root_key, hashes.SHA256()))
    sk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer = (x509.CertificateBuilder().subject_name(name("State Fire Services (Demo Issuer)")).issuer_name(root.subject)
              .public_key(sk.public_key()).serial_number(2002).not_valid_before(now)
              .not_valid_after(now + dt.timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
              .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
              .sign(root_key, hashes.SHA256()))
    (TRUST / "demo_root_ca.pem").write_bytes(root.public_bytes(serialization.Encoding.PEM))
    (keys / "signer.pem").write_bytes(signer.public_bytes(serialization.Encoding.PEM))
    (keys / "signer.key").write_bytes(sk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                       serialization.NoEncryption()))
    return keys


def sign_pdf(data: bytes, keys: Path) -> bytes:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    signer = signers.SimpleSigner.load(str(keys / "signer.key"), str(keys / "signer.pem"),
                                       ca_chain_files=(str(TRUST / "demo_root_ca.pem"),))
    w = IncrementalPdfFileWriter(io.BytesIO(data), strict=False)
    out = io.BytesIO()
    signers.sign_pdf(w, signers.PdfSignatureMetadata(field_name="IssuerSignature", reason="Issued by State Fire Services (Demo)"),
                     signer=signer, output=out)
    return out.getvalue()


# ------------------------------------------------------------------ photos
def make_photo(seed: int, kind: str) -> Image.Image:
    r = random.Random(seed)
    W, H = 960, 640
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    if kind == "building":
        for y in range(H):  # sky gradient
            t = y / H
            d.line([(0, y), (W, y)], fill=(int(120 + 80 * t), int(170 + 50 * t), int(230 - 20 * t)))
        d.rectangle([0, int(H * 0.78), W, H], fill=(r.randint(70, 110), r.randint(110, 150), r.randint(60, 90)))
        for _ in range(r.randint(2, 3)):
            x0 = r.randint(20, W // 2)
            w = r.randint(260, 460)
            top = r.randint(120, 260)
            col = tuple(r.randint(150, 225) for _ in range(3))
            d.rectangle([x0, top, x0 + w, int(H * 0.8)], fill=col, outline=(90, 90, 90))
            for wy in range(top + 20, int(H * 0.78) - 30, r.randint(42, 56)):
                for wx in range(x0 + 16, x0 + w - 30, r.randint(38, 52)):
                    d.rectangle([wx, wy, wx + 22, wy + 26], fill=(r.randint(40, 90), r.randint(80, 120), r.randint(120, 170)))
        for _ in range(r.randint(3, 7)):
            tx = r.randint(0, W)
            d.rectangle([tx - 5, int(H * 0.7), tx + 5, int(H * 0.82)], fill=(90, 60, 30))
            d.ellipse([tx - 40, int(H * 0.55), tx + 40, int(H * 0.73)], fill=(30, r.randint(100, 140), 40))
    else:  # lab / library interior
        wall = tuple(r.randint(190, 235) for _ in range(3))
        d.rectangle([0, 0, W, H], fill=wall)
        d.polygon([(0, int(H * 0.62)), (W, int(H * 0.62)), (W, H), (0, H)], fill=tuple(r.randint(120, 170) for _ in range(3)))
        for i in range(r.randint(2, 3)):
            wx = 60 + i * 300 + r.randint(-20, 20)
            d.rectangle([wx, 60, wx + 200, 230], fill=(170, 210, 240), outline=(120, 120, 120), width=4)
        rows = r.randint(2, 4)
        for row in range(rows):
            y = int(H * 0.55) + row * 55
            d.rectangle([40, y, W - 40, y + 18], fill=(120, 80, 50))
            for cx in range(70, W - 80, r.randint(110, 150)):
                if kind == "lab":
                    d.rectangle([cx, y - 46, cx + 56, y - 6], fill=(25, 25, 30), outline=(80, 80, 80))
                    d.rectangle([cx + 4, y - 42, cx + 52, y - 10], fill=(r.randint(40, 90), r.randint(90, 160), r.randint(150, 220)))
                else:
                    d.rectangle([cx, y - 30, cx + 70, y - 2], fill=tuple(r.randint(60, 200) for _ in range(3)))
    return im.filter(ImageFilter.GaussianBlur(0.8))


def to_deg(v):
    d = int(v)
    m = int((v - d) * 60)
    s = round(((v - d) * 60 - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def save_photo(im: Image.Image, path: Path, lat: float, lon: float, when: str, quality=90):
    exif = {"0th": {piexif.ImageIFD.Make: b"DemoCam", piexif.ImageIFD.Model: b"DC-1"},
            "Exif": {piexif.ExifIFD.DateTimeOriginal: when.encode()},
            "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: to_deg(lat),
                    piexif.GPSIFD.GPSLongitudeRef: b"E", piexif.GPSIFD.GPSLongitude: to_deg(lon)}}
    im.save(path, "JPEG", quality=quality, exif=piexif.dump(exif))


# ------------------------------------------------------------------ documents
def land_deed(inst, ctx, folder: Path, problems, extras, scan=False, tamper=False):
    doc = pymupdf.open()
    s = Sheet(doc, f"Office of the Sub-Registrar, {inst['district']} (Demo)", "REGISTERED " + ("LEASE" if ctx["lease"] else "SALE") + " DEED: EXTRACT",
              ref=f"Document No. {ctx['deed_reg']}")
    s.kv("Registration No.", ctx["deed_reg"])
    s.kv("Date of Registration", ctx["deed_date"].strftime("%d-%m-%Y"))
    s.kv("Deed Type", "Lease" if ctx["lease"] else "Sale")
    s.kv("In favour of", ctx["deed_owner"])
    s.kv("Survey No.", ctx["survey_deed"])
    s.kv("Total Land Area", f"{ctx['land_acres']} acres")
    s.kv("Property Address", ctx["address_deed"])
    s.kv("Latitude", f"{inst['lat']:.5f}")
    s.kv("Longitude", f"{inst['lon']:.5f}")
    if ctx["lease"]:
        s.kv("Lease Commencement Date", ctx["lease_start"].strftime("%d-%m-%Y"))
        s.kv("Term of Lease", f"{ctx['lease_term']} years")
    s.y += 6
    s.para("The property described above is registered in the records of this office. This extract is issued for the purpose "
           "of submission to the regulator and does not by itself confer any right not recorded in the original deed.")
    s.signature("Sub-Registrar (Demo)", f"Sub-Registry Office, {inst['district']}")
    s.stamp("SUB-REGISTRAR\n" + inst["district"].upper() + "\n(DEMO)", y=s.y + 50)
    data = save_pdf(doc, folder / "_clean_land.pdf")
    path = folder / "land_deed.pdf"
    if scan:
        scan_pdf(data, path, tamper=(ctx["deed_date"].strftime("%d-%m-%Y"), ctx["deed_date_tampered"]) if tamper else None,
                 seed=sum(map(ord, inst["key"])))
    else:
        shutil.copy(folder / "_clean_land.pdf", path)
    (folder / "_clean_land.pdf").unlink()
    return path


def building_plan(inst, ctx, folder: Path, problems):
    doc = pymupdf.open()
    s = Sheet(doc, f"{inst['city']} Municipal Corporation: Building Permission Dept. (Demo)", "APPROVED BUILDING PLAN: SUMMARY SHEET",
              ref=f"Plan Approval No. {ctx['plan_no']}")
    s.kv("Name of the Institution", inst["name"])
    s.kv("Survey No.", ctx["survey_plan"])
    s.kv("Site Address", ctx["address_plan"])
    s.kv("Plot Area", f"{ctx['plot_sqm']:,.2f} Sq.m")
    s.kv("Approval No.", ctx["plan_no"])
    s.kv("Approving Authority", f"{inst['city']} Municipal Corporation (Demo)")
    s.y += 4
    # floor-wise table
    blocks = ctx["floors"]
    x = [50, 230, 340, 450, 545]
    s.page.insert_text((50, s.y), "Floor-wise built-up area", fontname="hebo", fontsize=10)
    s.y += 8
    top = s.y
    rows = [("Block / Floor", "Use", "Floors", "Area (Sq.m)")] + blocks
    for i, row in enumerate(rows):
        yy = top + i * 18
        for j, cell in enumerate(row):
            s.page.insert_text((x[j] + 4, yy + 13), str(cell), fontname="hebo" if i == 0 else "helv", fontsize=9)
    for i in range(len(rows) + 1):
        s.page.draw_line((x[0], top + i * 18), (x[-1], top + i * 18), width=0.5)
    for xx in x:
        s.page.draw_line((xx, top), (xx, top + len(rows) * 18), width=0.5)
    s.y = top + len(rows) * 18 + 24
    s.kv("Total Built-up Area", f"{ctx['bua_plan']:,.2f} Sq.m")
    s.y += 4
    # simple site sketch (bottom-right, clear of the text)
    sk = pymupdf.Rect(300, 560, 545, 700)
    s.page.draw_rect(sk, color=(0.4, 0.4, 0.4), width=0.6)
    r = random.Random(inst["key"])
    for _ in range(4):
        bx, by = r.uniform(sk.x0 + 8, sk.x1 - 70), r.uniform(sk.y0 + 8, sk.y1 - 40)
        s.page.draw_rect(pymupdf.Rect(bx, by, bx + r.uniform(30, 60), by + r.uniform(18, 32)), color=(0.2, 0.3, 0.6), fill=(0.85, 0.9, 1), width=0.6)
    s.page.insert_text((sk.x0 + 4, sk.y1 + 10), "Site layout (not to scale)", fontname="helv", fontsize=7)
    if "no_architect_reg" in problems:
        s.kv("Prepared by", f"{ctx['architect']}, Draughtsman")
    else:
        s.kv("Architect's Name", ctx["architect"])
        s.kv("CoA Reg. No.", ctx["coa"])
        s.para("Certified that this plan is prepared by an Architect registered with the Council of Architecture.", height=34)
    s.signature(ctx["architect"], "Architect" if "no_architect_reg" not in problems else "Draughtsman")
    s.stamp("APPROVED\nMUNICIPAL CORP.\n(DEMO)", x=470, y=760, color=(0.1, 0.35, 0.15))
    path = folder / "building_plan.pdf"
    save_pdf(doc, path)
    return path


def occupancy_certificate(inst, ctx, folder: Path, problems, registry):
    doc = pymupdf.open()
    s = Sheet(doc, f"{inst['city']} Municipal Corporation (Demo)", "OCCUPANCY / COMPLETION CERTIFICATE", ref=f"Certificate No. {ctx['oc_no']}")
    s.kv("Certificate No.", ctx["oc_no"])
    s.kv("Date of Issue", ctx["oc_date"].strftime("%d-%m-%Y"))
    s.kv("Issued to", inst["name"])
    s.kv("Survey No.", ctx["survey_oc"])
    s.kv("Site Address", ctx["address_oc"])
    s.kv("Total Built-up Area", f"{ctx['bua_oc']:,.2f} Sq.m")
    s.kv("Issuing Authority", f"Executive Engineer, {inst['city']} Municipal Corporation (Demo)")
    s.y += 6
    s.para("Certified that the buildings described above have been completed in accordance with the sanctioned plan and are "
           "fit for occupation for educational use.")
    s.signature("Executive Engineer (Demo)", f"{inst['city']} Municipal Corporation")
    payload_valid = ctx["oc_date"].isoformat()
    payload = {"issuer": "MOCK-MUNICIPAL-OC", "certificate_no": ctx["oc_no"], "issued": payload_valid}
    s.qr(payload)
    registry[ctx["oc_no"]] = {"issuer": "MOCK-MUNICIPAL-OC", "issued": payload_valid}
    path = folder / "occupancy_certificate.pdf"
    save_pdf(doc, path)
    return path


def fire_noc(inst, ctx, folder: Path, problems, registry, keys):
    doc = pymupdf.open()
    s = Sheet(doc, "State Fire Services: Fire Prevention Wing (Demo Issuer)", "FIRE SAFETY CERTIFICATE (NOC)", ref=f"NOC No. {ctx['noc_no']}")
    s.kv("NOC No.", ctx["noc_no"])
    s.kv("Name of the Institution", inst["name"])
    s.kv("Campus Address", ctx["address_fire"])
    s.kv("Date of Issue", ctx["noc_issue"].strftime("%d-%m-%Y"))
    printed_valid = ctx["noc_valid_printed"]
    s.kv("Valid Upto", printed_valid.strftime("%d-%m-%Y"))
    s.kv("Issued by", "Chief Fire Officer, State Fire Services (Demo)")
    s.y += 6
    s.para("The fire prevention and life-safety measures installed in the above premises were inspected and found satisfactory "
           "for educational occupancy, subject to annual maintenance and renewal before the validity date.")
    s.signature("Chief Fire Officer (Demo)", "State Fire Services")
    payload = {"issuer": "MOCK-STATE-FIRE", "certificate_no": ctx["noc_no"], "valid_until": ctx["noc_valid"].isoformat()}
    s.qr(payload)
    registry[ctx["noc_no"]] = {"issuer": "MOCK-STATE-FIRE", "valid_until": ctx["noc_valid"].isoformat()}
    path = folder / "fire_noc.pdf"
    data = save_pdf(doc, path, producer="State Fire e-NOC (Demo)", expand=True)
    if ctx["sign_noc"]:
        signed = sign_pdf(data, keys)
        if "sig_tamper" in ctx["problems"]:
            target = printed_valid.strftime("%d-%m-%Y").encode().hex().encode()
            i = signed.find(target)
            assert i > 0, "could not locate validity date to tamper"
            # change the year digit "6"->"7" (hex 36->37) inside the signed byte range
            j = i + len(target) - 2
            signed = signed[:j] + b"37" + signed[j + 2:]
        path.write_bytes(signed)
    return path


def affidavit(inst, ctx, folder: Path, problems, hindi=False, scan=False):
    doc = pymupdf.open()
    s = Sheet(doc, "NON-JUDICIAL STAMP PAPER  Rs. 100/-  (Demo)", "AFFIDAVIT", hindi_title="शपथपत्र" if hindi else None)
    s.kv("Name of the Trust", ctx["trust_aff"])
    s.kv("Name of the Institution", inst["name"])
    s.kv("Total Proposed Intake", str(ctx["intake_aff"]))
    s.y += 4
    s.para(f"I, {ctx['chairman']}, Chairman of {ctx['trust_aff']}, do hereby solemnly affirm that the information submitted in the "
           f"application for the academic year {ctx['ay']} is true and correct to the best of my knowledge, and that the land, "
           "buildings, faculty and facilities stated in the application are available as declared.", height=80)
    if "inquiry_pending" in problems:
        s.para("I further declare that an inquiry is pending against the institution before a State investigating agency, "
               "details of which are enclosed.", height=44)
    else:
        s.para("I further declare that no inquiry by any central or state investigating agency is pending against the institution.", height=44)
        if hindi:
            s.hindi("मैं यह भी घोषित करता हूँ कि संस्था के विरुद्ध कोई जांच लंबित नहीं है।")
    s.para(f"Solemnly affirmed at {inst['city']} on {ctx['aff_date'].strftime('%d-%m-%Y')}.", height=30)
    s.signature(ctx["chairman"], f"Chairman, {ctx['trust_aff']}")
    if "affidavit_not_notarised" not in problems:
        s.para(f"Identified and attested before me. NOTARY PUBLIC, {inst['district']} (Demo). Reg. No. N/{random.Random(inst['key']).randint(1000, 9999)}", height=30)
        s.stamp("NOTARY\n" + inst["district"].upper() + "\n(DEMO)", x=470, y=730, color=(0.1, 0.1, 0.55))
    data = save_pdf(doc, folder / "_aff.pdf")
    path = folder / "affidavit.pdf"
    if scan:
        scan_pdf(data, path, seed=7 + len(inst["key"]))
    else:
        shutil.copy(folder / "_aff.pdf", path)
    (folder / "_aff.pdf").unlink()
    return path


def trust_registration(inst, ctx, folder: Path):
    doc = pymupdf.open()
    s = Sheet(doc, f"Office of the Charity Commissioner / Registrar of Societies, {inst['state']} (Demo)",
              "CERTIFICATE OF REGISTRATION", ref=f"Registration No. {ctx['trust_reg']}")
    s.kv("Name of the Trust", ctx["trust_reg_name"])
    s.kv("Registration No.", ctx["trust_reg"])
    s.kv("Date of Registration", ctx["trust_date"].strftime("%d-%m-%Y"))
    s.kv("Registered Office", f"{inst['city']}, {inst['state']}")
    s.para("Certified that the above trust/society is registered under the applicable State Act and that its objects include "
           "the establishment and management of educational institutions.")
    s.signature("Registrar (Demo)", inst["state"])
    path = folder / "trust_registration.pdf"
    save_pdf(doc, path)
    return path


def faculty_list(inst, faculty, folder: Path, ay: str):
    doc = pymupdf.open()
    cols = [("S.No", 34), ("Name of Faculty", 120), ("Date of Birth", 66), ("PAN", 74), ("Qualification", 70),
            ("Designation", 104), ("Date of Joining", 66)]
    per_page = 30
    for start in range(0, len(faculty), per_page):
        s = Sheet(doc, inst["name"], f"FACULTY LIST: ACADEMIC YEAR {ay}", ref=f"AICTE Permanent ID {inst['aicte_id']} (synthetic)")
        top = s.y - 10
        rows = [[c for c, _ in cols]] + [[str(i + 1), f["name"], f["dob"].strftime("%d-%m-%Y"), f["pan"], f["qualification"],
                                          f["designation"], f["doj"].strftime("%d-%m-%Y")]
                                         for i, f in list(enumerate(faculty))[start:start + per_page]]
        xs = [42]
        for _, w in cols:
            xs.append(xs[-1] + w)
        for i, row in enumerate(rows):
            yy = top + i * 19
            for j, cell in enumerate(row):
                s.page.insert_text((xs[j] + 3, yy + 13), cell, fontname="hebo" if i == 0 else "helv", fontsize=7.6)
        for i in range(len(rows) + 1):
            s.page.draw_line((xs[0], top + i * 19), (xs[-1], top + i * 19), width=0.4)
        for xx in xs:
            s.page.draw_line((xx, top), (xx, top + len(rows) * 19), width=0.4)
        s.page.insert_text((42, 815), f"Page {start // per_page + 1}. Certified by the Principal.", fontname="helv", fontsize=7)
    path = folder / "faculty_list.pdf"
    save_pdf(doc, path, producer="Institute ERP (Demo)")
    return path


# ------------------------------------------------------------------ main
def main():
    rng = random.Random(SALT_SEED)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    keys = demo_pki()
    registry: dict = {}
    manifest = {"generated": dt.date.today().isoformat(), "note": "Synthetic, fictional data for testing Nirikshan.",
                "institutions": [], "applications": []}
    truth = {"applications": {}, "problems": PROBLEMS}

    insts = []
    for idx, (key, app_type, problems, extras) in enumerate(PROFILES):
        city, district, state, lat, lon = CITIES[idx]
        inst = {"key": key, "aicte_id": f"1-DEMO-{10001 + idx}", "name": NAMES[idx], "trust": TRUSTS[idx], "city": city,
                "district": district, "state": state, "lat": round(lat + rng.uniform(-0.05, 0.05), 5),
                "lon": round(lon + rng.uniform(-0.05, 0.05), 5), "type": app_type, "problems": problems, "extras": extras}
        inst["address"] = f"Plot {rng.randint(10, 400)}, {rng.choice(['MIDC Road', 'Ring Road', 'College Road', 'Highway Bypass', 'Station Road'])}, {city}, Dist. {district}, {state}"
        insts.append(inst)
        manifest["institutions"].append({k: inst[k] for k in ("key", "aicte_id", "name", "trust", "city", "state", "address", "lat", "lon")})

    shared_photo_src = None
    ghost_pool = None
    fire_copy_src = None

    for inst in insts:
        r = random.Random(SALT_SEED + int(inst["key"][1:]))
        problems, extras = inst["problems"], inst["extras"]
        # courses
        n_core = 2 if "core_branches" in problems else r.choice([3, 4])
        courses = [{"name": CORE[i], "existing_intake": 60, "intake": 60, "core": True} for i in range(n_core)]
        courses.append({"name": "Artificial Intelligence & Data Science", "existing_intake": 60, "intake": 60, "core": False})
        if inst["type"] == "INTAKE_INCREASE":
            courses[0]["intake"] = 120
        existing = sum(c["existing_intake"] for c in courses)
        requested = sum(c["intake"] for c in courses)
        prev_faculty = None
        survey_base = f"{r.randint(20, 380)}/{r.randint(1, 9)}{r.choice('ABC')}"
        base_bua = round(3000 + 30 * requested + r.uniform(500, 1500), 2)
        survey_prev = survey_base
        const = {  # facts that do not change between years
            "deed_reg": f"{inst['district'][:3].upper()}-{r.randint(1000, 9999)}/{r.randint(2003, 2015)}",
            "deed_date": dt.date(r.randint(2003, 2012), r.randint(1, 12), r.randint(13, 28)),
            "land_acres": round(r.uniform(8, 20), 2), "plot_sqm": round(r.uniform(32000, 60000), 2),
            "plan_no": f"BP/{inst['city'][:3].upper()}/{r.randint(100, 999)}/{2015 + r.randint(0, 8)}",
            "architect": f"Ar. {r.choice(FIRST)} {r.choice(LAST)}", "coa": f"CA/{r.randint(1995, 2015)}/{r.randint(10000, 99999)}",
            "oc_no": f"OC/{inst['city'][:3].upper()}/{r.randint(1000, 9999)}", "oc_date": dt.date(2019, r.randint(1, 12), r.randint(13, 28)),
            "chairman": f"Shri {r.choice(FIRST)} {r.choice(LAST)}",
            "trust_reg": f"E-{r.randint(1000, 9999)}/{inst['district'][:3].upper()}",
            "trust_date": dt.date(r.randint(1985, 2005), r.randint(1, 12), r.randint(13, 28)),
        }

        for ay in (AY_PREV, AY_CUR):
            cur = ay == AY_CUR
            p = problems if cur else []
            intake = requested if cur else existing
            folder = OUT / f"{inst['key']}_{ay}"
            folder.mkdir()
            req_fac = int(np.ceil(intake * 4 / 20))
            low_adm = extras.get("low_admissions")
            if low_adm:
                req_fac = int(np.ceil(req_fac * 0.75))
            # faculty
            n_fac = req_fac + r.randint(1, 4)
            if "faculty_shortfall" in p:
                n_fac = req_fac - 7
            if prev_faculty is None or not cur:
                faculty = make_faculty(r, n_fac, bad_qual=0)
            else:
                keep = prev_faculty[:]
                if "history_faculty_churn" in p:
                    keep = keep[: len(keep) // 3]
                faculty = keep + make_faculty(r, max(0, n_fac - len(keep)))
                faculty = faculty[:n_fac] if len(faculty) > n_fac else faculty
                # keep cadre sane
                faculty.sort(key=lambda f: ["Professor", "Associate Professor", "Assistant Professor"].index(f["designation"]))
            if cur and "unqualified_faculty" in p:
                for f in [x for x in faculty if x["designation"] == "Assistant Professor"][:3]:
                    f["qualification"] = "B.Tech"
                for f in [x for x in faculty if x["designation"] == "Associate Professor"][:1]:
                    f["qualification"] = "M.Tech"
            if cur and "cadre_shortfall" in p:
                for f in faculty:
                    if f["designation"] in ("Professor", "Associate Professor"):
                        f["designation"] = "Assistant Professor"
                for f in faculty[:2]:
                    f["designation"] = "Professor"
                    f["qualification"] = "Ph.D"
            if cur and "ghost_faculty" in p:
                if ghost_pool is None:
                    ghost_pool = [dict(f) for f in faculty if f["designation"] == "Assistant Professor"][:3]
                else:
                    asst = [i for i, f in enumerate(faculty) if f["designation"] == "Assistant Professor"]
                    for i, g in zip(asst[:3], ghost_pool):
                        faculty[i] = dict(g)
            if cur and "faculty_lookalike" in p:
                victim = next(x for x in insts if x["key"] == "I05")
                lk = victim.setdefault("_lookalike", None)
                # copy a Professor from I05's current list with a different PAN
                if victim.get("_cur_faculty"):
                    src = [f for f in victim["_cur_faculty"] if f["designation"] == "Professor"][0]
                    i = next(i for i, f in enumerate(faculty) if f["designation"] == "Professor")
                    faculty[i] = {**src, "pan": rnd_pan(r)}
            if cur:
                inst["_cur_faculty"] = faculty
            else:
                prev_faculty = [dict(f) for f in faculty]

            # infrastructure numbers
            bua_plan = base_bua if cur else round(base_bua - (30 * (requested - existing)) - r.uniform(0, 200), 2)
            if not cur and "history_bua_shrink" in problems:
                bua_plan = round(base_bua + 2100, 2)
            if not cur and "bua_shortfall" in problems:
                bua_plan = round(3000 + 30 * requested - 1150 - r.uniform(50, 200), 2)
            if cur and "bua_shortfall" in p:
                bua_plan = round(3000 + 30 * intake - 1150, 2)
            declared_bua = bua_plan
            if cur and "declared_overstated" in p:
                declared_bua = round(bua_plan * 1.18)
            bua_oc = bua_plan if not (cur and "oc_partial" in p) else round(bua_plan - 1800, 2)
            survey = survey_base
            if cur and "history_survey_change" in p:
                survey = f"{r.randint(400, 600)}/{r.randint(1, 9)}"
                survey_prev = survey_base
            lease = extras.get("lease") or ("lease_short" in p)
            ctx = {
                "ay": ay, "problems": p, "lease": lease,
                "deed_reg": f"{inst['district'][:3].upper()}-{r.randint(1000, 9999)}/{r.randint(2003, 2015)}",
                "deed_date": dt.date(r.randint(2003, 2012), r.randint(1, 12), r.randint(13, 28)),
                "deed_owner": inst["trust"] if not (cur and "trust_mismatch" in p) else f"{r.choice(LAST)} Builders and Developers Pvt. Ltd.",
                "survey_deed": survey, "survey_plan": survey if not (cur and "survey_mismatch" in p) else survey.split("/")[0] + "/" + str(int(survey.split('/')[1][0]) + 3),
                "survey_oc": survey, "land_acres": round(r.uniform(8, 20), 2),
                "address_deed": inst["address"], "address_plan": inst["address"], "address_oc": inst["address"],
                "address_fire": inst["address"] if not (cur and "address_mismatch" in p) else f"Survey Road, Near Bus Depot, {r.choice(['Akola', 'Latur', 'Satara'])}, {inst['state']}",
                "lease_start": dt.date(2003, 6, 1) if "lease_short" in p else dt.date(2011, 4, 1),
                "lease_term": 30 if "lease_short" in p else 99,
                "plan_no": f"BP/{inst['city'][:3].upper()}/{r.randint(100, 999)}/{2015 + r.randint(0, 8)}",
                "plot_sqm": round(r.uniform(32000, 60000), 2),
                "floors": [("Academic Block A", "Instructional", "G+3", f"{bua_plan * 0.45:,.2f}"),
                           ("Academic Block B", "Instructional", "G+2", f"{bua_plan * 0.25:,.2f}"),
                           ("Admin & Library", "Administrative", "G+2", f"{bua_plan * 0.18:,.2f}"),
                           ("Amenities Block", "Amenities", "G+1", f"{bua_plan * 0.12:,.2f}")],
                "bua_plan": bua_plan, "bua_oc": bua_oc,
                "architect": f"Ar. {r.choice(FIRST)} {r.choice(LAST)}", "coa": f"CA/{r.randint(1995, 2015)}/{r.randint(10000, 99999)}",
                "oc_no": f"OC/{inst['city'][:3].upper()}/{r.randint(1000, 9999)}", "oc_date": dt.date(2019, r.randint(1, 12), r.randint(13, 28)),
                "noc_no": f"FS/NOC/{r.randint(10000, 99999)}/{ay[:4]}", "noc_issue": APP_DATE[ay] - dt.timedelta(days=r.randint(40, 200)),
                "sign_noc": inst["key"] not in ("I03", "I13") and not (cur and "qr_mismatch" in p),
                "trust_aff": inst["trust"], "trust_reg_name": inst["trust"], "chairman": f"Shri {r.choice(FIRST)} {r.choice(LAST)}",
                "intake_aff": intake if not (cur and "affidavit_intake_mismatch" in p) else intake + 60,
                "aff_date": APP_DATE[ay] - dt.timedelta(days=r.randint(3, 12)),
                "trust_reg": f"E-{r.randint(1000, 9999)}/{inst['district'][:3].upper()}", "trust_date": dt.date(r.randint(1985, 2005), r.randint(1, 12), r.randint(13, 28)),
            }
            ctx.update(const)
            ctx["deed_date_tampered"] = (ctx["deed_date"] + dt.timedelta(days=372)).strftime("%d-%m-%Y")
            ctx["noc_valid"] = dt.date(int(ay[:4]) + 1, 3, 31)
            if cur and "fire_expired" in p:
                ctx["noc_valid"] = dt.date(2025, 11, 30)
            ctx["noc_valid_printed"] = ctx["noc_valid"]
            if cur and "qr_mismatch" in p:
                ctx["noc_valid"] = dt.date(2025, 12, 31)          # what the issuer actually granted (in QR)
                ctx["noc_valid_printed"] = dt.date(2027, 3, 31)  # what the institution printed
            if cur and "sig_tamper" in p:
                ctx["noc_valid"] = ctx["noc_valid_printed"] = dt.date(2026, 3, 31)  # bytes edited to 2027 after signing

            docs = []
            scan_land = cur and ("tamper_scan" in p)
            docs.append(("land_deed", land_deed(inst, ctx, folder, p, extras, scan=scan_land, tamper=scan_land)))
            if inst["type"] != "EOA" or True:
                docs.append(("building_plan", building_plan(inst, ctx, folder, p)))
            docs.append(("occupancy_certificate", occupancy_certificate(inst, ctx, folder, p, registry)))
            fpath = fire_noc(inst, ctx, folder, p, registry, keys)
            if cur and "identical_file" in p and fire_copy_src:
                shutil.copy(fire_copy_src, fpath)
            if cur and inst["key"] == "I02":
                fire_copy_src = fpath
            docs.append(("fire_noc", fpath))
            docs.append(("affidavit", affidavit(inst, ctx, folder, p, hindi=extras.get("hindi", False),
                                                scan=extras.get("scan_affidavit", False))))
            if not (cur and "missing_document" in p):
                docs.append(("trust_registration", trust_registration(inst, ctx, folder)))
            docs.append(("faculty_list", faculty_list(inst, faculty, folder, ay)))
            # photos
            plat, plon = (inst["lat"], inst["lon"]) if not (cur and "gps_far" in p) else (inst["lat"] + 0.38, inst["lon"] + 0.21)
            for k, kind in enumerate(("building", "lab", "library")):
                pth = folder / f"campus_photo_{kind}.jpg"
                if cur and "photo_reuse" in p and kind == "lab" and shared_photo_src:
                    im = Image.open(shared_photo_src).convert("RGB").resize((930, 620))
                    im = ImageEnhance.Brightness(im).enhance(1.06)
                    save_photo(im, pth, plat, plon, f"{ay[:4]}:12:0{k + 1} 11:00:00", quality=82)
                else:
                    save_photo(make_photo(int(inst["key"][1:]) * 10 + k, kind), pth, plat, plon, f"{ay[:4]}:11:2{k} 10:30:00")
                if inst["key"] == "I01" and ay == AY_PREV and kind == "lab":
                    shared_photo_src = pth
                docs.append(("campus_photo", pth))

            if cur and extras.get("scan_all"):
                for cat, pth in docs:
                    if pth.suffix == ".pdf" and cat != "fire_noc":  # fire NOC stays a signed e-certificate
                        scan_pdf(pth.read_bytes(), pth, seed=len(cat) + int(inst["key"][1:]))
            declared = {
                "application_date": APP_DATE[ay].isoformat(), "courses": courses if cur else [{**c, "intake": c["existing_intake"]} for c in courses],
                "built_up_area_sqm": declared_bua, "land_area_acres": ctx["land_acres"],
                "faculty_count": len([f for f in faculty]) + (8 if cur and "declared_faculty_overstated" in p else 0),
                "avg_admission_ratio": 0.48 if low_adm else round(r.uniform(0.72, 0.96), 2),
                "investigation_pending": False, "trust_name": inst["trust"],
            }
            app_key = f"{inst['key']}_{ay}"
            manifest["applications"].append({
                "key": app_key, "institution": inst["key"], "academic_year": ay,
                "type": inst["type"] if cur else "EOA", "requested_intake": intake, "declared": declared,
                "status": "SUBMITTED" if cur else "DECIDED", "submit_order": int(inst["key"][1:]) + (0 if cur else -100),
                "documents": [{"category": c, "file": str(pth.relative_to(OUT)).replace("\\", "/")} for c, pth in docs],
            })
            if cur:
                exp, allow = set(), set()
                for prob in p:
                    e, a = PROBLEMS[prob]
                    exp |= set(e)
                    allow |= set(a)
                ns = lambda v: str(v).replace(" ", "").replace(".", "").upper()
                fields = {
                    "land_deed": {"survey_number": ns(ctx["survey_deed"]), "land_area_acres": ctx["land_acres"],
                                  "deed_type": "lease" if ctx["lease"] else "sale",
                                  "deed_date": dt.datetime.strptime(ctx["deed_date_tampered"], "%d-%m-%Y").date().isoformat()
                                  if scan_land else ctx["deed_date"].isoformat()},
                    "building_plan": {"survey_number": ns(ctx["survey_plan"]), "total_built_up_area_sqm": bua_plan},
                    "occupancy_certificate": {"survey_number": ns(ctx["survey_oc"]), "built_up_area_sqm": bua_oc,
                                              "certificate_no": ctx["oc_no"]},
                    "fire_noc": {"certificate_no": ctx["noc_no"],
                                 "valid_until": "2027-03-31" if "sig_tamper" in p else ctx["noc_valid_printed"].isoformat()},
                    "affidavit": {"requested_intake": ctx["intake_aff"]},
                    "faculty_list": {"rows": len(faculty)},
                }
                if "identical_file" in p:
                    fields.pop("fire_noc")
                if "no_architect_reg" not in p:
                    fields["building_plan"]["architect_reg_no"] = ctx["coa"]
                truth["applications"][app_key] = {"institution": inst["name"], "aicte_id": inst["aicte_id"], "problems": p,
                                                  "expected": sorted(exp), "allowed": sorted(allow), "clean": not p,
                                                  "fields": fields}

    (TRUST / "issuer_registry_mock.json").write_text(json.dumps(registry, indent=1))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str))
    (OUT / "ground_truth.json").write_text(json.dumps(truth, indent=1))
    shutil.rmtree(OUT / "_pki", ignore_errors=True)
    n_docs = sum(len(a["documents"]) for a in manifest["applications"])
    print(f"Generated {len(insts)} institutions, {len(manifest['applications'])} applications, {n_docs} documents -> {OUT}")


if __name__ == "__main__":
    main()
