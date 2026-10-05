import hashlib
import hmac
import os
from datetime import timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db, utcnow
from .models import AuditLog, Staff


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(pw: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split("$")
    check = hash_password(pw, bytes.fromhex(salt_hex)).split("$")[1]
    return hmac.compare_digest(check, dk_hex)


def make_token(staff: Staff) -> str:
    exp = utcnow() + timedelta(hours=settings.token_ttl_hours)
    return jwt.encode({"sub": staff.id, "exp": exp}, settings.secret_key, algorithm="HS256")


def current_staff(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Staff:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Not authenticated")
    staff = db.get(Staff, data["sub"])
    if not staff or not staff.is_active:
        raise HTTPException(401, "Not authenticated")
    return staff


def require(*roles: str):
    """Role gate. Admin may do everything except clinical writes (enforced per-route)."""
    def dep(staff: Staff = Depends(current_staff)) -> Staff:
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
