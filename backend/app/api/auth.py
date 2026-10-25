from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Institution, User
from ..schemas import LoginIn, institution_out, user_out
from ..security import audit, check_rate_limit, create_token, current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    check_rate_limit(body.email.lower())
    user = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    audit(db, user, "login", "user", user.id)
    db.commit()
    inst = db.get(Institution, user.institution_id) if user.institution_id else None
    return {"token": create_token(user), "user": user_out(user), "institution": institution_out(inst) if inst else None}


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
