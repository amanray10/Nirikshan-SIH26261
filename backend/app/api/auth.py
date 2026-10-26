import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Institution, User
from ..schemas import LoginIn, SignupIn, institution_out, user_out
from ..security import audit, check_rate_limit, create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session(db: Session, user: User) -> dict:
    inst = db.get(Institution, user.institution_id) if user.institution_id else None
    return {"token": create_token(user), "user": user_out(user), "institution": institution_out(inst) if inst else None}


def _password_problem(pw: str) -> str | None:
    if len(pw) < 8:
        return "Use at least 8 characters"
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Use both letters and numbers"
    return None


@router.post("/signup")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    """Self-registration for institutions only. Officer and admin accounts are created by AICTE."""
    email = body.email.strip().lower()
    check_rate_limit(f"signup:{email}")
    if problem := _password_problem(body.password):
        raise HTTPException(400, problem)
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(409, "An account with this email already exists; sign in instead")
    aicte_id = body.aicte_id.strip().upper()
    inst = db.scalars(select(Institution).where(Institution.aicte_id == aicte_id)).first()
    if inst:
        if db.scalars(select(User).where(User.institution_id == inst.id)).first():
            raise HTTPException(409, "This institution already has an account. Ask its existing user, or AICTE, for access")
    else:
        inst = Institution(aicte_id=aicte_id, name=body.institution_name.strip(), state=body.state.strip(),
                           address=body.address.strip(), trust_name=body.trust_name.strip())
        db.add(inst)
        db.flush()
    user = User(email=email, name=body.name.strip(), role="institution", institution_id=inst.id,
                password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    audit(db, user, "signup", "user", user.id, institution_id=inst.id)
    db.commit()
    return _session(db, user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    check_rate_limit(body.email.lower())
    user = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    audit(db, user, "login", "user", user.id)
    db.commit()
    return _session(db, user)


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    inst = db.get(Institution, user.institution_id) if user.institution_id else None
    return {"user": user_out(user), "institution": institution_out(inst) if inst else None}


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Only for the hackathon demo login screen: lists seeded demo accounts (passwords are documented in README)."""
    users = db.scalars(select(User).order_by(User.role, User.id)).all()
    out = []
    for u in users:
        inst = db.get(Institution, u.institution_id) if u.institution_id else None
        out.append({"email": u.email, "role": u.role, "name": u.name, "institution": inst.name if inst else None})
    return out[:20]
