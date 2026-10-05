import hashlib
import hmac
import os
from datetime import timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db, insert_ignore, utcnow
from .models import AuditLog, Counter, Staff


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(pw: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split("$")
    check = hash_password(pw, bytes.fromhex(salt_hex)).split("$")[1]
    return hmac.compare_digest(check, dk_hex)


def check_password_strength(pw: str) -> None:
    if len(pw) < settings.password_min_length:
        raise HTTPException(422, f"Password must be at least {settings.password_min_length} characters")
    if pw.isdigit() or pw.isalpha() or pw.lower() in ("password", "demo1234", "aracare123"):
        raise HTTPException(422, "Password is too easy to guess: mix letters with numbers or symbols")


def make_token(staff: Staff) -> str:
    exp = utcnow() + timedelta(hours=settings.token_ttl_hours)
    return jwt.encode({"sub": staff.id, "ver": staff.token_version or 0, "exp": exp},
                      settings.secret_key, algorithm="HS256")


def current_staff(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Staff:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Not authenticated")
    staff = db.get(Staff, data.get("sub"))
    if not staff or not staff.is_active or data.get("ver", 0) != (staff.token_version or 0):
        raise HTTPException(401, "Not authenticated")
    return staff


def require(*roles: str):
    """Role gate. Admin may do everything except clinical writes (enforced per-route)."""
    def dep(staff: Staff = Depends(current_staff)) -> Staff:
        # a temporary password (new account, admin reset, first production admin) only opens
        # /auth/me and /auth/change-password, which use current_staff directly
        if staff.must_change_password:
            raise HTTPException(403, {"code": "password_change_required",
                                      "message": "Choose a new password before you continue."})
        if staff.role not in roles:
            raise HTTPException(403, f"Role '{staff.role}' is not allowed to do this")
        return staff
    return dep


def audit(db: Session, staff: Staff | None, action: str, record_type: str,
          record_id: str | None = None, patient_id: str | None = None, detail: str | None = None):
    db.add(AuditLog(
        facility_id=staff.facility_id if staff else "system", staff_id=staff.id if staff else None,
        patient_id=patient_id, action=action, record_type=record_type,
        record_id=record_id, detail=detail,
    ))


def next_counter(db: Session, key: str) -> int:
    """Atomically increments a named counter (row-locked on Postgres; SQLite serialises writers)."""
    insert_ignore(db, Counter, key=key, value=0)
    c = db.scalar(select(Counter).where(Counter.key == key).with_for_update())
    c.value += 1
    db.flush()
    return c.value
