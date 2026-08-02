"""FastAPI application entry point.

Phase 0 wires up: request-ID correlation, structured logging, a normalized
error contract (architecture.md §20.9 — no stack traces to the client), CORS
for the local frontend, and the /health probe. Product routes are added
under /api/v1 starting in later phases (architecture.md §20).
"""

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from instamart_engine.api.routes.evidence import router as evidence_router
from instamart_engine.api.routes.health import router as health_router
from instamart_engine.api.routes.insights import router as insights_router
from instamart_engine.api.routes.reports import router as reports_router
from instamart_engine.api.routes.research import router as research_router
from instamart_engine.api.routes.runs import router as runs_router
from instamart_engine.api.routes.themes import router as themes_router
from instamart_engine.api.routes.validation import router as validation_router
from instamart_engine.api.schemas.errors import ErrorDetail, ErrorResponse
from instamart_engine.core.config import get_settings
from instamart_engine.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.APP_ENV)
logger = get_logger(__name__)


def _reject_debug_in_production() -> None:
    """DEP-015 — production must not start with debug/local defaults."""
    provider_key = settings.GROQ_API_KEY if settings.LLM_PROVIDER == "groq" else settings.OPENROUTER_API_KEY
    if settings.is_production and provider_key is None:
        raise RuntimeError(
            f"Refusing to start: APP_ENV=production but no API key is set for "
            f"LLM_PROVIDER={settings.LLM_PROVIDER!r}."
        )


_reject_debug_in_production()

app = FastAPI(
    title="Instamart Discovery Engine API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.unbind_contextvars("request_id")
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("x-request-id")
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    body = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. The team has been notified.",
            request_id=request_id,
            retryable=False,
        )
    )
    return JSONResponse(status_code=500, content=body.model_dump())


app.include_router(health_router)
app.include_router(research_router)
app.include_router(validation_router)
app.include_router(themes_router)
app.include_router(insights_router)
app.include_router(evidence_router)
app.include_router(runs_router)
app.include_router(reports_router)
