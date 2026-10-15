"""Database session helpers for the API service."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/road_risk"


def _database_url() -> str:
    return os.environ.get("ROAD_RISK_DATABASE_URL", DEFAULT_DATABASE_URL)


@lru_cache
def get_engine():
    return create_engine(_database_url(), pool_pre_ping=True)


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
