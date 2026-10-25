"""Authentication (JWT + Argon2) and role checks. Authorisation is enforced here, never in the UI."""
import hashlib
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Application, AuditLog, User

_ph = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except VerifyMismatchError:
        return False


def hash_identifier(raw: str) -> str:
    """Salted hash of a PAN/Aadhaar-like identifier. Used only for duplicate detection."""
    norm = "".join(ch for ch in raw.upper() if ch.isalnum())
    return hashlib.sha256(f"{settings.id_hash_salt}:{norm}".encode()).hexdigest()


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


# Simple in-memory login rate limiter: 10 attempts per minute per email.
_attempts: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str):
    now = time.time()
    _attempts[key] = [t for t in _attempts[key] if now - t < 60]
    if len(_attempts[key]) >= 10:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts; try again in a minute")
    _attempts[key].append(now)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted for your role")
        return user
    return dep


def can_access_application(user: User, app: Application) -> bool:
    if user.role in ("officer", "admin"):
        # Officers never see drafts or private self-checks.
        return app.status not in ("DRAFT", "SELF_CHECK") or user.role == "admin"
    return user.institution_id == app.institution_id


def get_app_or_404(db: Session, app_id: int, user: User) -> Application:
    app = db.get(Application, app_id)
    if not app or not can_access_application(user, app):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return app


def audit(db: Session, user: User | None, action: str, entity: str, entity_id: int | None, **details):
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity,
                    entity_id=entity_id, details=details))
