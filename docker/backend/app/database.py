"""
Database engine and session factory.

Supports SQLite (default, no Docker) and PostgreSQL (production).
"""

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""
    pass


def build_engine(url: str | None = None):
    """Create SQLAlchemy engine from settings or explicit URL."""
    if url is None:
        url = get_settings().database_url

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # Ensure the directory exists
        db_path = url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args=connect_args,
        echo=False,
    )

    # Enable WAL mode for SQLite (better concurrent read/write)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_session_factory(engine=None) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    if engine is None:
        engine = build_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Module-level defaults (lazy initialization)
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = build_session_factory(get_engine())
    return _SessionLocal


def get_db():
    """FastAPI dependency — yields a database session and closes it after."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist (works for both SQLite and PostgreSQL)."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info(f"Database initialized: {get_settings().database_url.split('///')[0]}")


def check_connection() -> bool:
    """Test the database connection. Returns True if successful."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection OK")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
