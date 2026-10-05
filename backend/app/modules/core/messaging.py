from sqlalchemy.orm import Session

from .models import Message


def queue_message(db: Session, facility_id: str, patient_id: str | None, phone: str, body: str, channel: str = "sms"):
    """Writes to the outbound queue. A gateway worker (AfricasTalking/Termii) will drain it later;
    until then the queue itself is the demo ("SMS queued locally, sent when network returns")."""
    db.add(Message(facility_id=facility_id, patient_id=patient_id, to_phone=phone, body=body, channel=channel))
