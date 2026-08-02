"""Structured logging setup.

Every log entry should carry request/run/job context (architecture.md §25.1)
and must never contain API keys or raw evidence text (edge cases OBS-001/002).
Callers are responsible for not passing secrets or raw payloads into `extra`.
"""

import logging
import sys

import structlog


def configure_logging(app_env: str) -> None:
    renderer = (
        structlog.dev.ConsoleRenderer()
        if app_env == "local"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
