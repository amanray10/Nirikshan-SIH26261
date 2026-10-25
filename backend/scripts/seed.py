"""Create a fresh database with demo users, APH norms/rules/clauses, and the synthetic dossiers,
then run the full verification pipeline on every application.

    python scripts/seed.py               # generate (if needed) + load + verify
    python scripts/seed.py --no-verify   # load only
    python scripts/seed.py --regenerate  # re-create the synthetic data first
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if os.environ.get("TZ") in ("Asia/Calcutta", "IST"):
    os.environ["TZ"] = "Asia/Kolkata"

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import (AphChunk, AphNorm, AphRule, Application, Document, Institution, User)  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.orchestrator import ensure_extracted, run_verification  # noqa: E402
from app.services.rules import REGISTRY  # noqa: E402

SYN = settings.data_dir / "synthetic"
DEMO_PASSWORD = {"admin": "admin123", "officer": "officer123", "institution": "college123"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args()

    if args.regenerate or not (SYN / "manifest.json").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_synthetic.py")], check=True)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    if settings.upload_dir.exists():
        shutil.rmtree(settings.upload_dir)
    settings.upload_dir.mkdir(parents=True)

    db = SessionLocal()
    # APH data
    norms = json.loads((settings.data_dir / "aph" / "norms.json").read_text(encoding="utf-8"))["norms"]
    for n in norms:
        db.add(AphNorm(edition=settings.aph_edition, **{k: n[k] for k in ("program", "norm_name", "value", "unit", "clause_ref",
                                                                           "source_status", "note")}))
    clauses = json.loads((settings.data_dir / "aph" / "aph_clauses.json").read_text(encoding="utf-8"))
    for c in clauses["clauses"]:
        db.add(AphChunk(clause_id=c["clause_id"], edition=clauses["edition"], chapter=c["chapter"], clause=c["clause"],
                        text=f"{c['title']}. {c['text']}", source_status=c["source_status"]))
    from app.services.rules.engine import clause_ref
    for code, r in REGISTRY.items():
        db.add(AphRule(rule_code=code, version=r.version, title=r.title, clause_ref=clause_ref(r.clause_id),
                       description=r.description, applies_to=r.applies_to, category=r.category))

    # users
    db.add(User(email="admin@nirikshan.demo", name="System Administrator", role="admin", password_hash=hash_password(DEMO_PASSWORD["admin"])))
    db.add(User(email="officer@nirikshan.demo", name="R. Kulkarni (Scrutiny Officer)", role="officer",
                password_hash=hash_password(DEMO_PASSWORD["officer"])))
    db.add(User(email="officer2@nirikshan.demo", name="S. Iyer (Scrutiny Officer)", role="officer",
                password_hash=hash_password(DEMO_PASSWORD["officer"])))

    manifest = json.loads((SYN / "manifest.json").read_text(encoding="utf-8"))
    insts = {}
    inst_pw = hash_password(DEMO_PASSWORD["institution"])
    for m in manifest["institutions"]:
        inst = Institution(aicte_id=m["aicte_id"], name=m["name"], state=m["state"], address=m["address"],
                           trust_name=m["trust"], latitude=m["lat"], longitude=m["lon"])
        db.add(inst)
        db.flush()
        insts[m["key"]] = inst
        db.add(User(email=f"{m['key'].lower()}@college.demo", name=f"Principal, {m['name']}", role="institution",
                    institution_id=inst.id, password_hash=inst_pw))

    apps = []
    base = datetime(2026, 1, 10, 9, 0)
    for a in sorted(manifest["applications"], key=lambda x: x["submit_order"]):
        inst = insts[a["institution"]]
        app = Application(ref_no="TMP", institution_id=inst.id, type=a["type"], academic_year=a["academic_year"],
                          requested_intake=a["requested_intake"], declared=a["declared"], status=a["status"],
                          submitted_at=(base if a["academic_year"] >= "2026" else base - timedelta(days=365))
                          + timedelta(hours=a["submit_order"] % 100))
        db.add(app)
        db.flush()
        app.ref_no = f"APP/{a['academic_year']}/{app.id:05d}"
        folder = settings.upload_dir / str(app.id)
        folder.mkdir(parents=True, exist_ok=True)
        for d in a["documents"]:
            src = SYN / d["file"]
            dest = folder / src.name
            shutil.copy(src, dest)
            db.add(Document(application_id=app.id, category=d["category"], filename=src.name, file_path=str(dest),
                            sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
        apps.append((a["key"], app.id, a["academic_year"]))
    db.commit()
    print(f"Loaded {len(insts)} institutions, {len(apps)} applications.")

    if args.no_verify:
        return
    # Pass 1: extract every dossier so cross-institution checks can see all of them.
    t0 = time.time()
    ext_times = {}
    for key, app_id, _ in apps:
        app = db.get(Application, app_id)
        t1 = time.perf_counter()
        ensure_extracted(db, app)
        db.commit()
        ext_times[key] = round((time.perf_counter() - t1) * 1000)
        print(f"  extracted {key} in {ext_times[key]} ms")
    (settings.data_dir / "evaluation").mkdir(exist_ok=True)
    (settings.data_dir / "evaluation" / "extraction_times.json").write_text(json.dumps(ext_times, indent=1))
    print(f"Extraction done in {time.time() - t0:.1f}s")
    # Pass 2: verify previous year first, then the current year.
    for key, app_id, ay in sorted(apps, key=lambda x: x[2]):
        app = db.get(Application, app_id)
        was = app.status
        run_id = run_verification(db, app_id, "scrutiny")
        app = db.get(Application, app_id)
        if was == "DECIDED":
            app.status, app.decision = "DECIDED", "APPROVE"
            db.commit()
        from app.models import VerificationRun
        run = db.get(VerificationRun, run_id)
        print(f"  verified {key:12s} risk {app.risk_score:5.0f} {app.risk_band:6s} {run.status} {run.duration_ms} ms"
              + (f"  ERROR {run.error[:300]}" if run.status != "DONE" else ""))
    db.close()
    print("\nDemo logins (password):")
    print(f"  officer@nirikshan.demo ({DEMO_PASSWORD['officer']})  admin@nirikshan.demo ({DEMO_PASSWORD['admin']})")
    print(f"  i01@college.demo … i14@college.demo ({DEMO_PASSWORD['institution']})")


if __name__ == "__main__":
    main()
