from contextlib import asynccontextmanager
from typing import Any

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from redis import Redis
from sqlalchemy import text

from app.api.router import api_router
from app.common.config import get_settings
from app.common.logging import configure_logging
from app.db.session import engine

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env, traces_sample_rate=0.1)
    logger.info("application_started", environment=settings.app_env, version="1.0.0")
    if settings.inline_task_execution:
        # No separate Celery worker: process durable jobs in this process and drain any
        # PENDING backlog left by a previous run/restart so no submission is stranded.
        try:
            from app.common.inline_runner import reconcile_pending_jobs

            reconciled = reconcile_pending_jobs()
            logger.info("inline_task_execution_enabled", reconciled_pending_jobs=reconciled)
        except Exception:
            logger.exception("inline_startup_reconcile_failed")
    yield
    engine.dispose()


app = FastAPI(
    title="ADRIS API",
    version="1.0.0",
    description="Agentic Digital Risk & Investigation Shield public and analyst API",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Incident-Token", "X-Correlation-ID"],
)
app.include_router(api_router)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next: Any):
    correlation_id = request.headers.get("X-Correlation-ID") or request.state.__dict__.get("correlation_id")
    if not correlation_id:
        from uuid import uuid4

        correlation_id = str(uuid4())
    request.state.correlation_id = correlation_id
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["health"])
def ready() -> ORJSONResponse:
    checks: dict[str, str] = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    code = status.HTTP_200_OK if all(value == "ok" for value in checks.values()) else status.HTTP_503_SERVICE_UNAVAILABLE
    return ORJSONResponse({"status": "ready" if code == 200 else "not_ready", "checks": checks}, status_code=code)
