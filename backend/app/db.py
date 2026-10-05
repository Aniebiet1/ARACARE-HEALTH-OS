import uuid
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_sqlite = settings.database_url.startswith("sqlite")
_args = {"check_same_thread": False, "timeout": 15} if _sqlite else {}
engine = create_engine(settings.database_url, connect_args=_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
TZ = ZoneInfo(settings.timezone)

if _sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        # WAL lets readers work while one request writes; busy_timeout waits instead of failing "database is locked"
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    pass


def uid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    # naive UTC keeps SQLite and Postgres behaviour identical
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_today() -> date:
    """The facility's calendar day. Queues and patient-number years follow this, not the server's clock zone."""
    return datetime.now(TZ).date()


def local_day_start_utc(day: date | None = None) -> datetime:
    """Local midnight of `day` (default today) as naive UTC, for comparing with stored timestamps."""
    start = datetime.combine(day or local_today(), time.min, tzinfo=TZ)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


def insert_ignore(db: Session, model, **values) -> None:
    """INSERT ... ON CONFLICT DO NOTHING, so concurrent requests can both 'create if missing' safely."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect}")
    db.execute(insert(model).values(**values).on_conflict_do_nothing())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
