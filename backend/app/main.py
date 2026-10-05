import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, SessionLocal, engine
from .events import subscribe
from .modules.core import models as _core  # noqa: F401  (register tables)
from .modules.core.router import router as core_router
from .modules.ehr import models as _ehr  # noqa: F401
from .modules.ehr.router import router as ehr_router
from .modules.queues import handlers as _queue_handlers  # noqa: F401  (registers event subscribers)
from .modules.queues import models as _queues  # noqa: F401
from .modules.queues import service as queue_service
from .modules.queues.router import router as queue_router
from .modules.registration import models as _reg  # noqa: F401
from .modules.registration.router import router as reg_router
from .modules.scribe import models as _scribe  # noqa: F401
from .modules.scribe.router import router as scribe_router
from .realtime import hub
from .seed import seed

log = logging.getLogger("aracare")


@subscribe("*")
def log_event(db, ev):
    """Stand-in for modules that are not built yet (Billing, Inventory, cloud sync).
    They will subscribe to the same events; nothing upstream changes."""
    stub = {"VisitCheckedIn": "Billing: would open DRAFT invoice + collect deposit",
            "NoteSigned": "Billing: would add consultation charge; HMO claim data = ICD-10 on note",
            "LabOrdered": "Billing/Lab: would add lab charges and a LAB ticket",
            "Prescribed": "Pharmacy/Inventory: would reserve stock and open a PHARM ticket",
            "JourneyClinicalCompleted": "Billing: would move invoice to PENDING_PAYMENT and open CASH ticket"}
    if ev.event_type in stub:
        log.info("[stub] %s -> %s", ev.event_type, stub[ev.event_type])


async def _sweeper():
    while True:
        await asyncio.sleep(15)
        try:
            with SessionLocal() as db:
                if queue_service.tick(db):
                    db.commit()
        except Exception:  # never let the sweeper die
            log.exception("queue sweeper error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    hub.loop = asyncio.get_running_loop()
    task = asyncio.create_task(_sweeper())
    yield
    task.cancel()


app = FastAPI(title="AraCare Health OS", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
for r in (core_router, reg_router, queue_router, ehr_router, scribe_router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
