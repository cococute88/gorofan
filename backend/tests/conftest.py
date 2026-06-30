"""Test fixtures (design 8.15).

Uses a temp SQLite DB. Tables are created synchronously before the app lifespan
runs (so default-user seeding succeeds). AUTH is disabled (local mode), so the
default-user is injected automatically.
"""
from __future__ import annotations

import os
import tempfile

import pytest

_DB_PATH = os.path.join(tempfile.gettempdir(), "acw_test.db")
if os.path.exists(_DB_PATH):
    os.remove(_DB_PATH)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"
os.environ["AUTH_ENABLED"] = "false"
os.environ["APP_SECRET_KEY"] = "test-secret-key-for-unit-tests-0123456789"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    from sqlalchemy import create_engine

    from app.config import get_settings
    from app.db.base import Base
    from app import models  # noqa: F401  (register tables)

    get_settings.cache_clear()
    sync_engine = create_engine(f"sqlite:///{_DB_PATH}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    yield


@pytest.fixture()
def client():
    from starlette.testclient import TestClient

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
