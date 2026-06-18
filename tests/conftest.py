"""Pytest fixtures. Uses a file-backed SQLite database so the API, seeds and
tests all share one schema without needing Postgres running."""

from __future__ import annotations

import os
import pathlib

# Configure the environment BEFORE importing application modules.
_TEST_DB = pathlib.Path(__file__).parent / "_test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("INITIAL_ADMIN_EMAIL", "admin@biolympics.ng")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "DevPassword!2026")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.session import configure_engine, get_engine, get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture(scope="function")
async def db_setup():
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    configure_engine(os.environ["DATABASE_URL"])
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()


@pytest_asyncio.fixture
async def session(db_setup):
    async with get_sessionmaker()() as s:
        yield s


@pytest_asyncio.fixture
async def seeded(db_setup):
    from app.seeds.seed import seed

    async with get_sessionmaker()() as s:
        await seed(s, with_demo=True)
    yield


@pytest_asyncio.fixture
async def client(db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def admin_email() -> str:
    return os.environ["INITIAL_ADMIN_EMAIL"]


@pytest.fixture
def admin_password() -> str:
    return os.environ["INITIAL_ADMIN_PASSWORD"]
