"""AI gateway tests against the live Postgres (model_call audit rows) with
a fully mocked openai-SDK-shaped client (Groq/OpenRouter are both
OpenAI-compatible) — no network access, no API key needed.
"""

import uuid
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from pydantic import BaseModel, ValidationError

from instamart_engine.ai import repository as ai_repo
from instamart_engine.ai.exceptions import ModelUnavailableError, StructuredOutputError
from instamart_engine.ai.gateway import AIGateway
from instamart_engine.ai.models import ModelCallStatus

pytestmark = pytest.mark.asyncio


class _Output(BaseModel):
    value: str


class _FakeUsage:
    def __init__(self, prompt_tokens: int = 10, completion_tokens: int = 5) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeMessage:
    def __init__(self, parsed: _Output | None, refusal: str | None = None) -> None:
        self.parsed = parsed
        self.refusal = refusal


class _FakeChoice:
    def __init__(self, parsed: _Output | None, refusal: str | None = None) -> None:
        self.message = _FakeMessage(parsed, refusal)
        self.finish_reason = "stop"


class _FakeResponse:
    def __init__(self, parsed_output: _Output | None, *, refusal: str | None = None) -> None:
        self.choices = [_FakeChoice(parsed_output, refusal)]
        self.model = "groq-test"
        self.id = "chatcmpl_test123"
        self.usage = _FakeUsage()


def _rate_limit_error() -> openai.RateLimitError:
    return openai.RateLimitError(
        "rate limited",
        response=httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com")),
        body=None,
    )


def _bad_request_error() -> openai.BadRequestError:
    return openai.BadRequestError(
        "bad request",
        response=httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com")),
        body=None,
    )


async def _make_model_configuration(db_session, max_retries: int = 2):
    return await ai_repo.get_or_create_model_configuration(
        db_session,
        name=f"test-config-{uuid.uuid4()}",
        provider="groq",
        model_name="groq-test-model",
        task_type="classification",
        max_retries=max_retries,
    )


async def test_successful_call_persists_succeeded_model_call(db_session) -> None:
    config = await _make_model_configuration(db_session)
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(_Output(value="ok")))
    gateway = AIGateway(client=client)

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "ok"
    assert call.status == ModelCallStatus.SUCCEEDED
    assert call.retry_count == 0
    assert call.input_tokens == 10
    assert call.output_tokens == 5


async def test_invalid_output_is_retried_then_succeeds(db_session) -> None:
    config = await _make_model_configuration(db_session, max_retries=2)
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(
        side_effect=[_FakeResponse(None), _FakeResponse(_Output(value="fixed"))]
    )
    gateway = AIGateway(client=client)

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "fixed"
    assert call.status == ModelCallStatus.SUCCEEDED
    assert call.retry_count == 1
    assert client.beta.chat.completions.parse.call_count == 2


async def test_invalid_output_exhausting_retries_raises_and_records_invalid_output(
    db_session,
) -> None:
    config = await _make_model_configuration(db_session, max_retries=1)
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(None))
    gateway = AIGateway(client=client)

    with pytest.raises(StructuredOutputError):
        await gateway.call_structured(
            db_session,
            prompt_version_id=uuid.uuid4(),
            prompt_version_key="v1",
            system_prompt="system",
            user_prompt="user",
            model_configuration=config,
            output_format=_Output,
            task_type="classification",
        )

    assert client.beta.chat.completions.parse.call_count == 2  # 1 initial + 1 retry


async def test_refusal_is_treated_as_invalid_output(db_session) -> None:
    config = await _make_model_configuration(db_session, max_retries=0)
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(
        return_value=_FakeResponse(None, refusal="I can't help with that")
    )
    gateway = AIGateway(client=client)

    with pytest.raises(StructuredOutputError, match="can't help"):
        await gateway.call_structured(
            db_session,
            prompt_version_id=uuid.uuid4(),
            prompt_version_key="v1",
            system_prompt="system",
            user_prompt="user",
            model_configuration=config,
            output_format=_Output,
            task_type="classification",
        )


async def test_rate_limit_retries_then_succeeds(db_session) -> None:
    config = await _make_model_configuration(db_session, max_retries=2)
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(
        side_effect=[_rate_limit_error(), _FakeResponse(_Output(value="ok"))]
    )
    gateway = AIGateway(client=client)

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "ok"
    assert call.status == ModelCallStatus.SUCCEEDED


async def test_rate_limit_exhausting_retries_raises_model_unavailable_without_fallback(
    db_session,
) -> None:
    config = await _make_model_configuration(db_session, max_retries=1)
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(side_effect=_rate_limit_error())
    gateway = AIGateway(client=client)  # no fallback configured

    with pytest.raises(ModelUnavailableError):
        await gateway.call_structured(
            db_session,
            prompt_version_id=uuid.uuid4(),
            prompt_version_key="v1",
            system_prompt="system",
            user_prompt="user",
            model_configuration=config,
            output_format=_Output,
            task_type="classification",
        )

    assert client.beta.chat.completions.parse.call_count == 2  # 1 initial + 1 retry


async def test_primary_exhausted_fails_over_to_fallback_provider(db_session) -> None:
    """Groq (primary) exhausts its retries on rate limits; OpenRouter
    (fallback) should be tried fresh and succeed."""
    config = await _make_model_configuration(db_session, max_retries=1)
    primary_client = AsyncMock()
    primary_client.beta.chat.completions.parse = AsyncMock(side_effect=_rate_limit_error())
    fallback_client = AsyncMock()
    fallback_client.beta.chat.completions.parse = AsyncMock(
        return_value=_FakeResponse(_Output(value="from-fallback"))
    )
    gateway = AIGateway(
        client=primary_client,
        fallback_client=fallback_client,
        fallback_provider="openrouter",
        fallback_model="fallback-test-model",
    )

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "from-fallback"
    assert call.status == ModelCallStatus.SUCCEEDED
    assert call.raw_response["provider"] == "openrouter"
    # 1 initial + 1 retry on primary, then 1 successful call on fallback.
    assert primary_client.beta.chat.completions.parse.call_count == 2
    assert fallback_client.beta.chat.completions.parse.call_count == 1


async def test_primary_exhausted_fails_over_to_secondary_groq_account(db_session) -> None:
    """A second Groq account's key (GROQ_API_KEY_SECONDARY) is tried after
    the primary key is rate-limited but before the fallback provider —
    doubles the effective free-tier budget without a paid Groq tier."""
    config = await _make_model_configuration(db_session, max_retries=1)
    primary_client = AsyncMock()
    primary_client.beta.chat.completions.parse = AsyncMock(side_effect=_rate_limit_error())
    secondary_client = AsyncMock()
    secondary_client.beta.chat.completions.parse = AsyncMock(
        return_value=_FakeResponse(_Output(value="from-secondary"))
    )
    fallback_client = AsyncMock()
    fallback_client.beta.chat.completions.parse = AsyncMock(
        return_value=_FakeResponse(_Output(value="from-fallback"))
    )
    gateway = AIGateway(
        client=primary_client,
        secondary_client=secondary_client,
        secondary_provider="groq-secondary",
        fallback_client=fallback_client,
        fallback_provider="openrouter",
        fallback_model="fallback-test-model",
    )

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "from-secondary"
    assert call.status == ModelCallStatus.SUCCEEDED
    assert call.raw_response["provider"] == "groq-secondary"
    # The secondary attempt reuses the primary's model_name since it's the
    # same provider/model catalog, just a different account's key.
    secondary_client.beta.chat.completions.parse.assert_called_once()
    assert (
        secondary_client.beta.chat.completions.parse.call_args.kwargs["model"]
        == config.model_name
    )
    assert fallback_client.beta.chat.completions.parse.call_count == 0


async def test_secondary_and_primary_exhausted_fails_over_to_fallback_provider(
    db_session,
) -> None:
    """The full three-tier chain: primary Groq account exhausted, secondary
    Groq account also exhausted, OpenRouter (fallback) succeeds."""
    config = await _make_model_configuration(db_session, max_retries=0)
    primary_client = AsyncMock()
    primary_client.beta.chat.completions.parse = AsyncMock(side_effect=_rate_limit_error())
    secondary_client = AsyncMock()
    secondary_client.beta.chat.completions.parse = AsyncMock(side_effect=_rate_limit_error())
    fallback_client = AsyncMock()
    fallback_client.beta.chat.completions.parse = AsyncMock(
        return_value=_FakeResponse(_Output(value="from-fallback"))
    )
    gateway = AIGateway(
        client=primary_client,
        secondary_client=secondary_client,
        secondary_provider="groq-secondary",
        fallback_client=fallback_client,
        fallback_provider="openrouter",
        fallback_model="fallback-test-model",
    )

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "from-fallback"
    assert call.raw_response["provider"] == "openrouter"
    assert primary_client.beta.chat.completions.parse.call_count == 1
    assert secondary_client.beta.chat.completions.parse.call_count == 1
    assert fallback_client.beta.chat.completions.parse.call_count == 1


async def test_both_providers_exhausted_raises_model_unavailable(db_session) -> None:
    config = await _make_model_configuration(db_session, max_retries=0)
    primary_client = AsyncMock()
    primary_client.beta.chat.completions.parse = AsyncMock(side_effect=_rate_limit_error())
    fallback_client = AsyncMock()
    fallback_client.beta.chat.completions.parse = AsyncMock(side_effect=_rate_limit_error())
    gateway = AIGateway(
        client=primary_client,
        fallback_client=fallback_client,
        fallback_provider="openrouter",
        fallback_model="fallback-test-model",
    )

    with pytest.raises(ModelUnavailableError):
        await gateway.call_structured(
            db_session,
            prompt_version_id=uuid.uuid4(),
            prompt_version_key="v1",
            system_prompt="system",
            user_prompt="user",
            model_configuration=config,
            output_format=_Output,
            task_type="classification",
        )

    assert primary_client.beta.chat.completions.parse.call_count == 1
    assert fallback_client.beta.chat.completions.parse.call_count == 1


async def test_non_retryable_api_error_fails_over_to_fallback(db_session) -> None:
    config = await _make_model_configuration(db_session, max_retries=3)
    primary_client = AsyncMock()
    primary_client.beta.chat.completions.parse = AsyncMock(side_effect=_bad_request_error())
    fallback_client = AsyncMock()
    fallback_client.beta.chat.completions.parse = AsyncMock(
        return_value=_FakeResponse(_Output(value="from-fallback"))
    )
    gateway = AIGateway(
        client=primary_client,
        fallback_client=fallback_client,
        fallback_provider="openrouter",
        fallback_model="fallback-test-model",
    )

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "from-fallback"
    # No retry for a 4xx client error — moves to the next provider immediately.
    assert primary_client.beta.chat.completions.parse.call_count == 1


async def test_non_retryable_api_error_fails_immediately_without_fallback(db_session) -> None:
    config = await _make_model_configuration(db_session, max_retries=3)
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(side_effect=_bad_request_error())
    gateway = AIGateway(client=client)

    with pytest.raises(StructuredOutputError):
        await gateway.call_structured(
            db_session,
            prompt_version_id=uuid.uuid4(),
            prompt_version_key="v1",
            system_prompt="system",
            user_prompt="user",
            model_configuration=config,
            output_format=_Output,
            task_type="classification",
        )

    assert client.beta.chat.completions.parse.call_count == 1  # no retry for a 4xx client error


async def test_pydantic_validation_error_triggers_repair_retry(db_session) -> None:
    config = await _make_model_configuration(db_session, max_retries=1)
    validation_error = ValidationError.from_exception_data("Output", [])
    client = AsyncMock()
    client.beta.chat.completions.parse = AsyncMock(
        side_effect=[validation_error, _FakeResponse(_Output(value="ok"))]
    )
    gateway = AIGateway(client=client)

    parsed, call = await gateway.call_structured(
        db_session,
        prompt_version_id=uuid.uuid4(),
        prompt_version_key="v1",
        system_prompt="system",
        user_prompt="user",
        model_configuration=config,
        output_format=_Output,
        task_type="classification",
    )

    assert parsed.value == "ok"
    assert call.retry_count == 1
