"""Database connection and session management for the training data warehouse."""

from __future__ import annotations

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base

# Default to SQLite for development, PostgreSQL for production
DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_DB_URL = f"sqlite:///{DATA_DIR / 'training_warehouse.db'}"

DATABASE_URL = os.environ.get("TRAINING_DB_URL", DEFAULT_DB_URL)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    # SQLite-specific settings
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Session:
    """Get a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
