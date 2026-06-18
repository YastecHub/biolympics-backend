"""Async engine, session factory and the FastAPI DB dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", ""}

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _normalize_sqlite_url(url: str) -> str:
    """Anchor a *relative* sqlite file path to backend/ so the same database is
    used no matter the working directory uvicorn was launched from."""
    if not url.startswith("sqlite") or ":///" not in url:
        return url
    prefix, path = url.split(":///", 1)
    if not path or path == ":memory:":
        return url
    # Already absolute? (POSIX "/..." or Windows "C:/...")
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        return url
    rel = path[2:] if path.startswith("./") else path
    abs_path = (_BACKEND_DIR / rel).resolve().as_posix()
    return f"{prefix}:///{abs_path}"


def _prepare_postgres(url: str) -> tuple[str, dict]:
    """Translate libpq-style ``?sslmode=``/``?ssl=`` query params into asyncpg
    connect args (asyncpg doesn't read them from the URL), and require SSL by
    default for remote hosts such as Supabase. Returns (clean_url, connect_args)."""
    connect_args: dict = {}
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    ssl_value = query.pop("ssl", None) or query.pop("sslmode", None)
    host = parts.hostname or ""

    if ssl_value is None and host not in _LOCAL_HOSTS:
        ssl_value = "require"  # managed Postgres (Supabase/RDS/…) mandates TLS
    if ssl_value and ssl_value not in {"disable", "allow", "prefer"}:
        connect_args["ssl"] = "require"

    clean = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    return clean, connect_args


def _build_engine(url: str) -> AsyncEngine:
    url = _normalize_sqlite_url(url)
    connect_args: dict = {}
    kwargs: dict = {"echo": False, "pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        # SQLite (used by local dev + the test suite) needs no real pool.
        connect_args["check_same_thread"] = False
        kwargs.pop("pool_pre_ping")
    elif "asyncpg" in url:
        url, connect_args = _prepare_postgres(url)
    return create_async_engine(url, connect_args=connect_args, **kwargs)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine(settings.database_url)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
    return _sessionmaker


def configure_engine(url: str) -> None:
    """Reset the engine to a new URL (used by tests)."""
    global _engine, _sessionmaker
    _engine = _build_engine(url)
    _sessionmaker = async_sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        await session.close()
