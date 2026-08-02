"""Connector failure taxonomy, mapped from edgecases.md §7 (ING-*) and §6 (SRC-*).

Every connector raises one of these instead of a bare exception so the
ingestion service (Phase 1) can decide retryability without inspecting
provider-specific error types.
"""


class SourceConnectorError(Exception):
    """Base class for all connector failures."""

    retryable: bool = False

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable


class SourceConfigError(SourceConnectorError):
    """Invalid configuration (SRC-001/002/004/006/008/011/012). Never retryable."""

    retryable = False


class SSRFBlockedError(SourceConfigError):
    """URL resolves to a private/internal network (SRC-013). Never retryable."""


class SourceAuthError(SourceConnectorError):
    """401/403 or missing credentials (ING-001, MOD-012). Not retryable without
    a configuration change."""

    retryable = False


class SourceUnavailableError(SourceConnectorError):
    """404 / target permanently unavailable (ING-002). Not retryable."""

    retryable = False


class SourceRateLimitedError(SourceConnectorError):
    """429 (ING-003). Retryable with backoff; may carry a retry_after hint."""

    retryable = True

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message, retryable=True)
        self.retry_after_seconds = retry_after_seconds


class SourceTransientError(SourceConnectorError):
    """5xx, DNS, TLS, timeout, or other transient failure (ING-004/005/006/016).
    Retryable with bounded backoff."""

    retryable = True


class SourceBlockedContentError(SourceConnectorError):
    """CAPTCHA or login-gated content encountered (ING-012/013). Not retryable
    automatically — no automated bypass is permitted."""

    retryable = False
