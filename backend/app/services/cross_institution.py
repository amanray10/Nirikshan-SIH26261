"""Cross-institution fraud detection: the check only AICTE can run, because only AICTE sees every dossier.

- Ghost faculty: same (hashed) identifier listed as faculty at two or more institutions in the same year.
- Possible same person under a different ID: same name + date of birth.
- Recycled evidence: campus/lab photos whose perceptual hash matches another institution's photo.
- Identical files: byte-identical documents (SHA-256) submitted by different institutions.

Scale note: hashes are indexed columns; for millions of photos use multi-index hashing / BK-trees.
"""
from collections import defaultdict

import imagehash
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Application, Document, FacultyRecord, Institution, MediaHash
from .types import FRAUD, PASS, REVIEW, Evidence, FindingData

VISIBLE = ("SUBMITTED", "PROCESSING", "UNDER_REVIEW", "DECIDED")
PHASH_MAX, DHASH_MAX = 6, 8  # bits of 64; both must agree (measured on the synthetic set)


def run(db: Session, app: Application) -> list[FindingData]:
    out: list[FindingData] = []
    out += _ghost_faculty(db, app)
    out += _photos(db, app)
    out += _identical_files(db, app)
    if not out:
        out.append(FindingData("XIN-OK", PASS, "No cross-institution matches",
                               "No shared faculty, reused photos or identical files found across other institutions.",
                               "low", "fraud", "cross_institution", "PASS",
                               establishes="Searched all submitted applications nationally."))
    return out


def _others(db: Session, app: Application):
    return (select(Application, Institution).join(Institution, Application.institution_id == Institution.id)
            .where(Application.institution_id != app.institution_id, Application.status.in_(VISIBLE)))


def _faculty_ev(r: FacultyRecord, note: str) -> Evidence:
    return Evidence(r.document_id, "faculty_list", r.page, r.bbox, "faculty_row", r.name,
                    f"{r.name} · DOB {r.dob} · ID ••••{r.id_last4} · {r.designation}", note)


def _ghost_faculty(db: Session, app: Application) -> list[FindingData]:
    mine = db.scalars(select(FacultyRecord).where(FacultyRecord.application_id == app.id)).all()
    if not mine:
        return []
    other_apps = {a.id: (a, i) for a, i in db.execute(_others(db, app).where(Application.academic_year == app.academic_year))}
    if not other_apps:
        return []
    theirs = db.scalars(select(FacultyRecord).where(FacultyRecord.application_id.in_(other_apps))).all()
    by_hash = defaultdict(list)
    for r in theirs:
        by_hash[r.id_hash].append(r)

    shared: dict[int, list[tuple[FacultyRecord, FacultyRecord]]] = defaultdict(list)
    lookalike: list[tuple[FacultyRecord, FacultyRecord]] = []
    for m in mine:
        for t in by_hash.get(m.id_hash, []):
            shared[t.application_id].append((m, t))
        if m.id_hash not in by_hash:
            for t in theirs:
                if m.dob and m.dob == t.dob and fuzz.token_sort_ratio(m.name, t.name) >= 92:
                    lookalike.append((m, t))
                    break

    out = []
    for app_id, pairs in shared.items():
        other, inst = other_apps[app_id]
        names = ", ".join(m.name for m, _ in pairs[:6]) + (f" and {len(pairs) - 6} more" if len(pairs) > 6 else "")
        out.append(FindingData(
            "XIN-FACULTY", FRAUD, f"{len(pairs)} faculty also listed by another institution",
            f"{names} also appear as full-time faculty of {inst.name} ({inst.aicte_id}) in {other.academic_year} "
            f"(application {other.ref_no}). Matched on salted hash of PAN/Aadhaar.",
            "high", "fraud", "cross_institution", "FLAGGED",
            establishes="Same government identifier on two institutions' faculty lists in the same year. Strong signal of "
                        "ghost faculty; the committee should confirm with salary/attendance records.",
            evidence=[_faculty_ev(m, f"also at {inst.name}") for m, _ in pairs[:10]],
            params={"count": len(pairs), "other": inst.name, "other_id": inst.aicte_id, "names": [m.name for m, _ in pairs]},
            related={"other_application_id": other.id, "other_ref": other.ref_no, "other_institution": inst.name,
                     "faculty": [{"name": m.name, "designation_here": m.designation, "designation_there": t.designation,
                                  "id_last4": m.id_last4} for m, t in pairs]},
        ))
    for m, t in lookalike[:5]:
        other, inst = other_apps[t.application_id]
        out.append(FindingData(
            "XIN-LOOKALIKE", REVIEW, "Possible same person under a different ID",
            f"{m.name} (DOB {m.dob}) closely matches {t.name} (same DOB) at {inst.name}, but the ID numbers differ.",
            "medium", "fraud", "cross_institution", "NEEDS_REVIEW",
            establishes="Name and date-of-birth similarity only; could be two different people.",
            evidence=[_faculty_ev(m, f"look-alike at {inst.name}")],
            related={"other_application_id": other.id, "other_institution": inst.name},
        ))
    return out


def _dist(a: str, b: str) -> tuple[int, int]:
    """(phash distance, dhash distance) between two stored 32-hex-char hashes."""
    hp = imagehash.hex_to_hash
    return int(hp(a[:16]) - hp(b[:16])), int(hp(a[16:]) - hp(b[16:])) if len(a) >= 32 and len(b) >= 32 else 0


def _first_seen(app: Application) -> tuple:
    """Ordering key: earlier academic year first, then earlier submission time."""
    return (app.academic_year, app.submitted_at or app.created_at)


def _photos(db: Session, app: Application) -> list[FindingData]:
    mine = db.execute(select(MediaHash, Document).join(Document, MediaHash.document_id == Document.id)
                      .where(Document.application_id == app.id)).all()
    if not mine:
        return []
    rows = db.execute(
        select(MediaHash, Document, Application, Institution)
        .join(Document, MediaHash.document_id == Document.id)
        .join(Application, Document.application_id == Application.id)
        .join(Institution, Application.institution_id == Institution.id)
        .where(Application.status.in_(VISIBLE + ("DECIDED",)) | (Application.id == app.id))
    ).all()
    out = []
    for mh, doc in mine:
        close = []
        for omh, odoc, oapp, oinst in rows:
            dp, dd = _dist(mh.phash, omh.phash)
            if dp <= PHASH_MAX and dd <= DHASH_MAX:
                close.append((dp, odoc, oapp, oinst))
        ours = [c for c in close if c[2].institution_id == app.institution_id]
        theirs = [c for c in close if c[2].institution_id != app.institution_id]
        if not theirs:
            continue
        our_first = min((_first_seen(c[2]) for c in ours), default=_first_seen(app))
        first = min(theirs, key=lambda c: _first_seen(c[2]))
        if _first_seen(first[2]) > our_first:
            continue  # we submitted this photo first; the other institution is the one to question
        d, odoc, oapp, oinst = min(theirs, key=lambda c: (c[0], _first_seen(c[2])))
        sim = round((1 - d / 64) * 100)
        out.append(FindingData(
            "XIN-PHOTO", FRAUD, "Photo matches another institution's submission",
            f"“{doc.filename}” matches “{odoc.filename}” submitted by {oinst.name} for {first[2].academic_year} "
            f"(perceptual similarity {sim}%), before this institution first used it.",
            "high", "fraud", "cross_institution", "FLAGGED",
            establishes="Perceptual hashes survive resizing and recompression. A near-identical photo first submitted by "
                        "another institution suggests recycled evidence; verify on site.",
            evidence=[Evidence(doc.id, doc.category, mh.page, mh.bbox, "photo", doc.filename, "", "this application"),
                      Evidence(odoc.id, odoc.category, 1, None, "photo", odoc.filename, "", f"{oinst.name} {oapp.academic_year}")],
            params={"other": oinst.name, "year": first[2].academic_year, "similarity": sim},
            related={"other_application_id": oapp.id, "other_document_id": odoc.id, "other_institution": oinst.name,
                     "hamming_distance": d},
        ))
    return out


def _identical_files(db: Session, app: Application) -> list[FindingData]:
    mine = db.scalars(select(Document).where(Document.application_id == app.id)).all()
    out = []
    for doc in mine:
        match = db.execute(
            select(Document, Application, Institution)
            .join(Application, Document.application_id == Application.id)
            .join(Institution, Application.institution_id == Institution.id)
            .where(Document.sha256 == doc.sha256, Application.institution_id != app.institution_id,
                   Application.status.in_(VISIBLE))
            .order_by(Application.academic_year, Application.submitted_at)
        ).first()
        if match and _first_seen(match[1]) < _first_seen(app):
            odoc, oapp, oinst = match
            out.append(FindingData(
                "XIN-FILE", FRAUD, "Identical file submitted by another institution",
                f"“{doc.filename}” is byte-for-byte identical to a file submitted by {oinst.name} ({oapp.ref_no}).",
                "high", "fraud", "cross_institution", "FLAGGED",
                establishes="Identical SHA-256 fingerprints mean identical files. It does not say which copy is genuine.",
                evidence=[Evidence(doc.id, doc.category, 1, None, "file", doc.filename)],
                related={"other_application_id": oapp.id, "other_institution": oinst.name},
            ))
    return out
