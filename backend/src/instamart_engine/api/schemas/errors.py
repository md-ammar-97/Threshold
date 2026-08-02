"""Normalized error contract. architecture.md §20.9 — no stack traces leave the API."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    retryable: bool = False
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail
