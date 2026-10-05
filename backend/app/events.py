"""In-process event bus with a transactional outbox.

Modules never import each other's internals for cross-module reactions; they
publish a domain event and other modules subscribe. Every event is written to
`outbox_events` in the same transaction as the state change, so the same table
later feeds SMS dispatch and local->cloud sync.
"""
import logging
from collections import defaultdict
from typing import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session

from .modules.core.models import OutboxEvent
from .realtime import hub

log = logging.getLogger("aracare.events")
_handlers: dict[str, list[Callable]] = defaultdict(list)


def subscribe(event_type: str):
    def deco(fn):
        _handlers[event_type].append(fn)
        return fn
    return deco


def publish(db: Session, event_type: str, payload: dict, facility_id: str, room: str | None = None):
    ev = OutboxEvent(facility_id=facility_id, event_type=event_type, payload=payload)
    db.add(ev)
    db.flush()
    for handler in list(_handlers.get(event_type, ())) + list(_handlers.get("*", ())):
        handler(db, ev)
    if room:
        db.info.setdefault("broadcasts", []).append((room, {"event": event_type}))
    return ev


@event.listens_for(Session, "after_commit")
def _flush_broadcasts(session):
    for room, msg in session.info.pop("broadcasts", []):
        hub.broadcast(room, msg)


@event.listens_for(Session, "after_rollback")
def _drop_broadcasts(session):
    session.info.pop("broadcasts", None)
