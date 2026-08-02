"""AI gateway failure taxonomy. Mirrors edgecases.md §19 (MOD-*)."""


class AIGatewayError(Exception):
    """Base class for gateway failures."""


class StructuredOutputError(AIGatewayError):
    """MOD-003/004/007 — output never validated against the schema, even
    after bounded repair retries."""


class ModelUnavailableError(AIGatewayError):
    """MOD-001/002/016 — timeout, rate limit, or other transient provider
    failure that exhausted its retry budget."""


class ProviderConfigurationError(AIGatewayError):
    """MOD-012 — missing/invalid API key or similar setup problem. Never
    retryable; must fail before any paid call is attempted."""
