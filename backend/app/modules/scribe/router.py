import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db
from ..core.models import Consent, Staff
from ..core.security import audit, require
from ..ehr.models import AllergyRecord, Vitals
from ..registration.models import Patient, Visit
from ..registration.service import age_years
from . import asr, service, structure
from .models import ScribeSession

router = APIRouter(prefix="/scribe", tags=["ai-scribe"])
log = logging.getLogger("aracare.scribe")
AUDIO_EXT = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4", ".aac", ".flac"}
ROLES = ("nurse", "doctor")


def _visit(db: Session, staff: Staff, visit_id: str) -> Visit:
    v = db.get(Visit, visit_id)
    if not v or v.facility_id != staff.facility_id:
        raise HTTPException(404, "Visit not found")
    return v


@router.get("/status")
def status(staff: Staff = Depends(require(*ROLES))):
    return {"asr": asr.engine_name(), "llm": structure.llm_engine_name(),
            "asr_available": asr.available(),
            "note": "Audio is processed on this server and discarded. Drafts are never saved to the record until signed."}


class ConsentIn(BaseModel):
    visit_id: str
    granted: bool


@router.post("/consent")
def record_consent(body: ConsentIn, staff: Staff = Depends(require(*ROLES)), db: Session = Depends(get_db)):
    v = _visit(db, staff, body.visit_id)
    db.add(Consent(facility_id=v.facility_id, patient_id=v.patient_id, consent_type="voice_scribe",
                   granted=body.granted, recorded_by=staff.id))
    audit(db, staff, "consent_voice" if body.granted else "refuse_voice", "patient", v.patient_id, v.patient_id)
    db.commit()
    return {"granted": body.granted}


@router.post("/transcribe")
async def transcribe(visit_id: str = Form(...), language: str = Form("en"), audio: UploadFile = File(...),
                     staff: Staff = Depends(require(*ROLES)), db: Session = Depends(get_db)):
    v = _visit(db, staff, visit_id)
    if not service.has_voice_consent(db, v.patient_id):
        raise HTTPException(403, "Record the patient's consent to voice dictation first")
    if not asr.available():
        raise HTTPException(503, "Local Whisper is not installed (pip install faster-whisper). "
                                 "You can type or paste the dictation instead.")
    suffix = os.path.splitext(audio.filename or "")[1].lower()
    suffix = suffix if suffix in AUDIO_EXT else ".webm"
    limit = settings.max_audio_mb * 1024 * 1024
    data = await audio.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Recording is larger than {settings.max_audio_mb} MB; dictate in shorter parts")
    if not data:
        raise HTTPException(422, "Recording is empty")
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        from starlette.concurrency import run_in_threadpool
        try:
            text = await run_in_threadpool(asr.transcribe, path, language or None)
        except asr.ASRUnavailable:
            log.exception("Speech-to-text failed")
            raise HTTPException(503, "Speech-to-text could not start because the server is low on memory. "
                                     "Close some programs on the server and try again, or type the note instead.")
        except Exception:
            log.exception("Could not transcribe %s upload", suffix)
            raise HTTPException(422, "That recording could not be read. Try recording again, or type the note instead.")
    finally:
        os.remove(path)          # audio is never retained
    audit(db, staff, "scribe_transcribe", "visit", v.id, v.patient_id)
    db.commit()
    return {"transcript": text}


class DraftIn(BaseModel):
    visit_id: str
    transcript: str
    role: str | None = None   # defaults to the caller's role


@router.post("/draft", status_code=201)
def make_draft(body: DraftIn, staff: Staff = Depends(require(*ROLES)), db: Session = Depends(get_db)):
    v = _visit(db, staff, body.visit_id)
    role = body.role or staff.role
    if role not in ROLES or (role == "doctor" and staff.role != "doctor"):
        raise HTTPException(403, "You cannot create this kind of draft")
    if not service.has_voice_consent(db, v.patient_id):
        raise HTTPException(403, "Record the patient's consent to voice dictation first")
    text = body.transcript.strip()
    if len(text) < 5:
        raise HTTPException(422, "Transcript is empty")
    if len(text) > 20000:
        raise HTTPException(413, "Transcript is too long; draft it in shorter parts")
    p = db.get(Patient, v.patient_id)
    allergies = db.scalars(select(AllergyRecord).where(AllergyRecord.patient_id == p.id)).all()
    vit = db.scalar(select(Vitals).where(Vitals.visit_id == v.id).order_by(Vitals.recorded_at.desc()))
    context = (f"Patient: {age_years(p.date_of_birth)}-year-old {p.gender}. "
               f"Known allergies: {', '.join(a.allergen_name for a in allergies) or 'none recorded'}. "
               + (f"Triage vitals: BP {vit.bp_systolic}/{vit.bp_diastolic}, temp {vit.temperature}, pulse {vit.pulse_rate}, "
                  f"SpO2 {vit.spo2}, weight {vit.weight_kg}. Chief complaint: {vit.chief_complaint}." if vit else ""))
    draft, dropped, llm = structure.build_draft(role, text, context)
    suggestions = service.map_icd10(db, draft.get("suggested_diagnoses", [])) if role == "doctor" else []
    s = ScribeSession(facility_id=v.facility_id, visit_id=v.id, patient_id=p.id, staff_id=staff.id, role=role,
                      transcript=text, draft=draft, dropped=dropped, engine={"asr": asr.engine_name(), "llm": llm})
    db.add(s)
    db.flush()
    audit(db, staff, "scribe_draft", "scribe_session", s.id, p.id, detail=f"llm={llm}")
    db.commit()
    return {"session_id": s.id, "status": s.status, "role": role, "draft": draft, "icd10_suggestions": suggestions,
            "dropped": dropped, "engine": s.engine, "transcript": text}


@router.post("/sessions/{session_id}/discard")
def discard(session_id: str, staff: Staff = Depends(require(*ROLES)), db: Session = Depends(get_db)):
    s = db.get(ScribeSession, session_id)
    if not s or s.facility_id != staff.facility_id:
        raise HTTPException(404, "Session not found")
    if s.status != "ai_draft":
        raise HTTPException(409, f"This draft is already {s.status}")
    s.status = "discarded"
    audit(db, staff, "scribe_discarded", "scribe_session", s.id, s.patient_id)
    db.commit()
    return {"ok": True}
