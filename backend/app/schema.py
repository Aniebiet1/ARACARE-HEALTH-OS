"""Single place that knows every table, and brings the database schema up to date with Alembic."""
import logging
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .db import Base, engine
from .modules.core import models as _core  # noqa: F401  (register tables)
from .modules.ehr import models as _ehr  # noqa: F401
from .modules.pulse import models as _pulse  # noqa: F401
from .modules.queues import models as _queues  # noqa: F401
from .modules.registration import models as _reg  # noqa: F401
from .modules.scribe import models as _scribe  # noqa: F401

log = logging.getLogger("aracare.schema")
BASELINE = "0001_baseline"
_INI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini")

__all__ = ["Base", "migrate"]


def migrate() -> None:
    """Upgrade to the latest revision. Databases created before migrations existed (by create_all)
    are stamped at the baseline first, so they upgrade in place instead of failing on 'table exists'."""
    cfg = Config(_INI)
    cfg.attributes["configure_logger"] = False
    sqlite = engine.dialect.name == "sqlite"
    with engine.connect() as conn:
        # SQLite batch mode rebuilds a table by DROP + rename; with FK enforcement on, dropping a referenced
        # table (e.g. facilities) fails. The pragma is ignored inside a transaction, so set it before begin().
        if sqlite:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.commit()
        try:
            with conn.begin():
                tables = set(inspect(conn).get_table_names())
                cfg.attributes["connection"] = conn
                if "patients" in tables and "alembic_version" not in tables:
                    log.warning("Existing database without migration history: stamping baseline %s", BASELINE)
                    command.stamp(cfg, BASELINE)
                command.upgrade(cfg, "head")
        finally:
            if sqlite:
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
                conn.commit()
