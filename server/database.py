import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Prefer app settings if available; fall back to environment variable.
try:
    from .config import get_settings  # type: ignore
except Exception:  # pragma: no cover
    get_settings = None  # type: ignore[assignment]


def _resolve_database_url() -> str:
    if get_settings is not None:
        try:
            settings = get_settings()
            url = getattr(settings, "database_url", None)
            if url:
                return url
        except Exception:
            pass
    return os.getenv("DATABASE_URL", "sqlite:///./chessguard.db")


DATABASE_URL = _resolve_database_url()

# SQLite-specific configuration for better concurrency
if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # Wait up to 30 seconds for lock
    }
else:
    connect_args = {}

engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)

# Enable WAL mode for SQLite (better concurrent access)
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
