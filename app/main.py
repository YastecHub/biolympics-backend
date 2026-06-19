"""FastAPI application entrypoint for BIOLYMPICS LIVE."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.db.session import get_engine
from app.services.events import bus

configure_logging(settings.log_level, json_logs=True)
log = get_logger("app")

_metrics = {"ws_connections": 0, "requests_total": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.connect()
    subscriber = asyncio.create_task(bus.run_subscriber())
    log.info("app.startup", env=settings.app_env, name=settings.app_name)
    try:
        yield
    finally:
        subscriber.cancel()
        await bus.close()
        log.info("app.shutdown")


app = FastAPI(
    title="BIOLYMPICS LIVE API",
    version="0.1.0",
    description="Live-score platform for the Life Sciences Dean's Games 2026.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "public", "description": "Read-only public endpoints"},
        {"name": "auth", "description": "Administrative authentication"},
        {"name": "admin", "description": "Fixture, scoring and content management"},
        {"name": "push", "description": "Browser push subscriptions"},
    ],
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.trusted_host_list:
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[*settings.trusted_host_list, "testserver"]
    )

app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def api_root() -> dict:
    return {
        "name": settings.app_name,
        "status": "ok",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "api": "/api/v1",
    }


@app.get("/api/v1/docs", include_in_schema=False)
async def api_v1_docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/api/docs", include_in_schema=False)
async def api_docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")


# --------------------------------------------------------------------------- #
# Consistent error envelopes
# --------------------------------------------------------------------------- #
@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    code = "http_error"
    message = detail if isinstance(detail, str) else "Request failed"
    extra = detail if isinstance(detail, dict) else None
    if isinstance(detail, dict) and "code" in detail:
        code = detail["code"]
        message = detail.get("message", message)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
                "detail": extra,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "request_id": getattr(request.state, "request_id", None),
                "detail": {"errors": exc.errors()},
            }
        },
    )


# --------------------------------------------------------------------------- #
# Operational endpoints
# --------------------------------------------------------------------------- #
@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/ready", tags=["ops"])
async def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    healthy = True
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
        healthy = False
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "not-ready", "checks": checks},
    )


@app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
async def metrics() -> str:
    # Minimal Prometheus exposition. Protect/scope this in production.
    from app.websocket.manager import manager

    lines = [
        "# HELP biolympics_ws_connections Active WebSocket connections",
        "# TYPE biolympics_ws_connections gauge",
        f"biolympics_ws_connections {manager.connection_count}",
    ]
    return "\n".join(lines) + "\n"
