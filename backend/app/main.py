import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import settings
from .db import SessionLocal
from .events import subscribe
from .modules.core.router import router as core_router
from .modules.ehr.router import router as ehr_router
from .modules.queues import handlers as _queue_handlers  # noqa: F401  (registers event subscribers)
from .modules.queues import service as queue_service
from .modules.queues.router import router as queue_router
from .modules.registration.router import router as reg_router
from .modules.scribe.router import router as scribe_router
from .realtime import hub
from .schema import migrate
from .seed import seed

logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aracare")
VERSION = "0.2.0"


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


def _sweep_once() -> int:
    with SessionLocal() as db:
        changed = queue_service.tick(db)
        db.commit()
        return changed


async def _sweeper():
    while True:
        await asyncio.sleep(settings.sweep_interval_seconds)
        try:
            # off the event loop: the sweep does blocking DB work
            await asyncio.to_thread(_sweep_once)
        except Exception:  # never let the sweeper die
            log.exception("queue sweeper error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.check()
    migrate()
    seed()
    hub.loop = asyncio.get_running_loop()
    task = asyncio.create_task(_sweeper())
    log.info("AraCare %s started (env=%s)", VERSION, settings.env)
    yield
    task.cancel()


app = FastAPI(title="AraCare Health OS", version=VERSION, lifespan=lifespan,
              docs_url="/docs" if settings.enable_docs else None,
              redoc_url="/redoc" if settings.enable_docs else None,
              openapi_url="/openapi.json" if settings.enable_docs else None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type"])
for r in (core_router, reg_router, queue_router, ehr_router, scribe_router):
    app.include_router(r, prefix="/api")


@app.exception_handler(Exception)
async def _unhandled(request, exc):
    # log with the path; never leak a stack trace or SQL to the client
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. It has been logged."})


@app.get("/api/health")
def health():
    """Liveness + database check, for Docker/systemd/load-balancer health probes."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        log.exception("health check: database unreachable")
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
    return {"status": "ok", "version": VERSION, "env": settings.env}
