"""Shared pytest fixtures.

ASGITransport does not run the FastAPI lifespan, so database tables are created
explicitly here. DATABASE_URL is set at import time (before app modules load) to
an isolated temporary SQLite file, keeping tests deterministic and avoiding the
real data/sessions.db.
"""

import os
import tempfile

# Configure an isolated database before any app module is imported.
_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"

import pytest_asyncio


@pytest_asyncio.fixture
async def _init_test_db():
    from app.core.database import init_db, close_db

    await init_db()
    yield
    await close_db()
    try:
        os.unlink(_db_path)
    except OSError:
        pass
