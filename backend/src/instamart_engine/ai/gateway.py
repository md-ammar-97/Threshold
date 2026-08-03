"""Provider-neutral AI gateway. architecture.md §12.

Every structured-output task in the system goes through
`AIGateway.call_structured`: it handles the bounded invalid-output repair
loop (MOD-003/004/007), transient-error backoff (MOD-001/002/016), automatic
failover to a backup provider, and audit logging to `model_call`
(architecture.md §12.4) in one place, so individual tasks (classification,
theme/insight synthesis, research question planning/answer generation)
don't reimplement this.

Groq (primary) and OpenRouter (fallback) are both OpenAI-compatible Chat
Completions APIs, reached through the `openai` SDK with a swapped
`base_url`/`api_key` — no provider-specific request shape to maintain.
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

import openai
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai import repository as repo
from instamart_engine.ai.exceptions import (
    ModelUnavailableError,
    ProviderConfigurationError,
    StructuredOutputError,
)
from instamart_engine.ai.models import ModelCall, ModelCallStatus, ModelConfiguration
from instamart_engine.core.config import Settings, get_settings
from instamart_engine.core.logging import get_logger

logger = get_logger(__name__)

OutputT = TypeVar("OutputT", bound=BaseModel)

# Seconds, indexed by attempt number (capped at the last value for further attempts).
_TRANSIENT_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)

_PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


@dataclass(frozen=True, slots=True)
class _ProviderAttempt:
    name: str
    client: openai.AsyncOpenAI
    model_name: str


def _api_key_for(provider: str, settings: Settings) -> str | None:
    if provider == "groq":
        return settings.GROQ_API_KEY
    if provider == "openrouter":
        return settings.OPENROUTER_API_KEY
    raise ProviderConfigurationError(f"Unknown LLM provider: {provider}")


def _build_client(provider: str, settings: Settings) -> openai.AsyncOpenAI:
    api_key = _api_key_for(provider, settings)
    if not api_key:
        # MOD-012 — fail configuration checks before queuing paid work.
        raise ProviderConfigurationError(f"{provider.upper()}_API_KEY is not configured")
    return _build_client_with_key(provider, api_key)


def _build_client_with_key(provider: str, api_key: str) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=api_key, base_url=_PROVIDER_BASE_URLS[provider])


class AIGateway:
    def __init__(
        self,
        client: openai.AsyncOpenAI | None = None,
        *,
        secondary_client: openai.AsyncOpenAI | None = None,
        secondary_provider: str | None = None,
        secondary_model: str | None = None,
        fallback_client: openai.AsyncOpenAI | None = None,
        fallback_provider: str | None = None,
        fallback_model: str | None = None,
    ) -> None:
        if client is None:
            settings = get_settings()
            client = _build_client(settings.LLM_PROVIDER, settings)
            # A second account on the *same* provider — tried after the
            # primary key is rate-limited/quota-exhausted but before falling
            # over to a different provider/model entirely. Only meaningful
            # when the primary provider is groq, since the whole point is
            # "same provider, different account", not a different model.
            if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY_SECONDARY:
                secondary_client = _build_client_with_key(
                    "groq", settings.GROQ_API_KEY_SECONDARY
                )
                secondary_provider = "groq-secondary"
                # Left unset deliberately: the secondary tier is the *same*
                # provider/model catalog as primary, just a different
                # account's key, so call_structured() reuses whatever
                # model_configuration.model_name the primary attempt used
                # rather than a fixed value that could drift from it.
            if settings.LLM_FALLBACK_PROVIDER and settings.LLM_FALLBACK_PROVIDER != (
                settings.LLM_PROVIDER
            ):
                fallback_client = _build_client(settings.LLM_FALLBACK_PROVIDER, settings)
                fallback_provider = settings.LLM_FALLBACK_PROVIDER
                fallback_model = settings.LLM_FALLBACK_MODEL
        self._client = client
        self._secondary_client = secondary_client
        self._secondary_provider = secondary_provider or "secondary"
        self._secondary_model = secondary_model
        self._fallback_client = fallback_client
        self._fallback_provider = fallback_provider or "fallback"
        self._fallback_model = fallback_model

    async def call_structured(
        self,
        session: AsyncSession,
        *,
        prompt_version_id: UUID,
        prompt_version_key: str,
        system_prompt: str,
        user_prompt: str,
        model_configuration: ModelConfiguration,
        output_format: type[OutputT],
        task_type: str,
        analysis_run_id: UUID | None = None,
        input_object_type: str | None = None,
        input_object_ids: list[UUID] | None = None,
    ) -> tuple[OutputT, ModelCall]:
        """`system_prompt`/`user_prompt` must already be fully rendered by
        the caller — including wrapping any untrusted content with
        `ai.prompt_safety.delimit_untrusted_content` — the gateway only
        calls the model and handles retries/audit, it does not know which
        placeholders a given task's template uses."""
        input_checksum = hashlib.sha256(
            (prompt_version_id.hex + user_prompt).encode("utf-8")
        ).hexdigest()

        call = await repo.create_model_call(
            session,
            prompt_version_id=prompt_version_id,
            model_configuration_id=model_configuration.id,
            task_type=task_type,
            input_checksum=input_checksum,
            # OBS-002 — never store the raw feedback text itself here, only
            # metadata about the request.
            request_payload_redacted={
                "prompt_version": prompt_version_key,
                "user_prompt_length": len(user_prompt),
                "model": model_configuration.model_name,
            },
            analysis_run_id=analysis_run_id,
            input_object_type=input_object_type,
            input_object_ids=input_object_ids,
        )
        await session.commit()

        attempts = [
            _ProviderAttempt(
                name=model_configuration.provider,
                client=self._client,
                model_name=model_configuration.model_name,
            )
        ]
        if self._secondary_client is not None:
            attempts.append(
                _ProviderAttempt(
                    name=self._secondary_provider,
                    client=self._secondary_client,
                    model_name=self._secondary_model or model_configuration.model_name,
                )
            )
        if self._fallback_client is not None and self._fallback_model:
            attempts.append(
                _ProviderAttempt(
                    name=self._fallback_provider,
                    client=self._fallback_client,
                    model_name=self._fallback_model,
                )
            )

        started = time.monotonic()
        last_error: Exception | None = None
        total_retries = 0
        succeeded_provider: str | None = None

        for provider_attempt in attempts:
            messages: list[dict[str, str]] = [{"role": "user", "content": user_prompt}]
            max_retries = model_configuration.max_retries

            for attempt in range(max_retries + 1):
                try:
                    response = await provider_attempt.client.beta.chat.completions.parse(
                        model=provider_attempt.model_name,
                        max_tokens=model_configuration.max_output_tokens or 2048,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            *messages,  # type: ignore[list-item]
                        ],
                        response_format=output_format,
                        temperature=(
                            float(model_configuration.temperature)
                            if model_configuration.temperature is not None
                            else 0.0
                        ),
                    )
                except (
                    openai.RateLimitError,
                    openai.APITimeoutError,
                    openai.APIConnectionError,
                    openai.InternalServerError,
                ) as exc:
                    last_error = exc
                    total_retries += attempt
                    if attempt >= max_retries:
                        break
                    delay = _TRANSIENT_RETRY_DELAYS_SECONDS[
                        min(attempt, len(_TRANSIENT_RETRY_DELAYS_SECONDS) - 1)
                    ]
                    logger.warning(
                        "model_call_transient_error",
                        provider=provider_attempt.name,
                        attempt=attempt,
                        error=str(exc),
                        retry_in_seconds=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                except openai.APIError as exc:
                    last_error = exc
                    total_retries += attempt
                    break  # non-transient provider error (e.g. 400/401) — try the next provider
                except (ValidationError, openai.LengthFinishReasonError) as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        total_retries += attempt
                        break
                    messages.append(_repair_request_message(str(exc)))
                    continue

                message = response.choices[0].message
                parsed = message.parsed
                if parsed is None:
                    last_error = StructuredOutputError(
                        message.refusal or "Model did not return structured output"
                    )
                    if attempt >= max_retries:
                        total_retries += attempt
                        break
                    messages.append(_repair_request_message(str(last_error)))
                    continue

                latency_ms = int((time.monotonic() - started) * 1000)
                usage = response.usage
                total_retries += attempt
                succeeded_provider = provider_attempt.name
                await repo.finalize_model_call(
                    session,
                    call=call,
                    status=ModelCallStatus.SUCCEEDED,
                    raw_response={
                        "stop_reason": response.choices[0].finish_reason,
                        "model": response.model,
                        "provider": succeeded_provider,
                    },
                    parsed_response=parsed.model_dump(mode="json"),
                    provider_request_id=response.id,
                    input_tokens=usage.prompt_tokens if usage else None,
                    output_tokens=usage.completion_tokens if usage else None,
                    latency_ms=latency_ms,
                    retry_count=total_retries,
                )
                await session.commit()
                return parsed, call

        latency_ms = int((time.monotonic() - started) * 1000)
        status, error_code = _map_failure(last_error)
        await repo.finalize_model_call(
            session,
            call=call,
            status=status,
            latency_ms=latency_ms,
            retry_count=total_retries,
            error_code=error_code,
            error_message=str(last_error) if last_error else "unknown error",
        )
        await session.commit()

        if status in (ModelCallStatus.RATE_LIMITED, ModelCallStatus.TIMED_OUT):
            raise ModelUnavailableError(str(last_error)) from last_error
        raise StructuredOutputError(str(last_error)) from last_error


def _repair_request_message(problem: str) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            f"Your previous response was invalid: {problem}. "
            "Reply again with ONLY valid JSON matching the required schema — no "
            "prose, no markdown fences."
        ),
    }


def _map_failure(error: Exception | None) -> tuple[ModelCallStatus, str]:
    if isinstance(error, openai.RateLimitError):
        return ModelCallStatus.RATE_LIMITED, "RATE_LIMITED"
    if isinstance(error, openai.APITimeoutError):
        return ModelCallStatus.TIMED_OUT, "TIMEOUT"
    if isinstance(error, (ValidationError, StructuredOutputError, openai.LengthFinishReasonError)):
        return ModelCallStatus.INVALID_OUTPUT, "INVALID_STRUCTURED_OUTPUT"
    return ModelCallStatus.FAILED, type(error).__name__ if error else "UNKNOWN"
