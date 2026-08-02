"""DB access for the AI gateway domain. architecture.md §8.4."""

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai.models import (
    ModelCall,
    ModelCallStatus,
    ModelConfiguration,
    PromptTemplate,
    PromptVersion,
)


async def get_or_create_prompt_template(
    session: AsyncSession, *, task_key: str, name: str, description: str | None = None
) -> PromptTemplate:
    existing = await session.scalar(
        select(PromptTemplate).where(PromptTemplate.task_key == task_key)
    )
    if existing is not None:
        return existing
    template = PromptTemplate(task_key=task_key, name=name, description=description)
    session.add(template)
    await session.flush()
    return template


async def get_or_create_prompt_version(
    session: AsyncSession,
    *,
    prompt_template_id: UUID,
    version_key: str,
    system_prompt: str,
    user_prompt_template: str,
    response_schema: dict | None = None,
) -> PromptVersion:
    existing = await session.scalar(
        select(PromptVersion).where(
            PromptVersion.prompt_template_id == prompt_template_id,
            PromptVersion.version_key == version_key,
        )
    )
    if existing is not None:
        return existing

    checksum_source = (system_prompt + "\n" + user_prompt_template).encode("utf-8")
    version = PromptVersion(
        prompt_template_id=prompt_template_id,
        version_key=version_key,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        response_schema=response_schema,
        source_file_checksum=hashlib.sha256(checksum_source).hexdigest(),
        status="published",
        published_at=datetime.now(),
    )
    session.add(version)
    await session.flush()
    return version


async def get_or_create_model_configuration(
    session: AsyncSession,
    *,
    name: str,
    provider: str,
    model_name: str,
    task_type: str,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    timeout_seconds: int = 30,
    max_retries: int = 3,
    structured_output_mode: str = "native_output_format",
) -> ModelConfiguration:
    existing = await session.scalar(
        select(ModelConfiguration).where(ModelConfiguration.name == name)
    )
    if existing is not None:
        if existing.provider != provider or existing.model_name != model_name:
            # Settings-driven provider/model migrated (e.g. anthropic -> groq)
            # since this row was first created; sync it rather than silently
            # calling the dead provider/model forever.
            existing.provider = provider
            existing.model_name = model_name
            await session.flush()
        return existing

    config = ModelConfiguration(
        name=name,
        provider=provider,
        model_name=model_name,
        task_type=task_type,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        structured_output_mode=structured_output_mode,
    )
    session.add(config)
    await session.flush()
    return config


async def create_model_call(
    session: AsyncSession,
    *,
    prompt_version_id: UUID,
    model_configuration_id: UUID,
    task_type: str,
    input_checksum: str,
    request_payload_redacted: dict[str, Any],
    analysis_run_id: UUID | None = None,
    input_object_type: str | None = None,
    input_object_ids: list[UUID] | None = None,
) -> ModelCall:
    call = ModelCall(
        analysis_run_id=analysis_run_id,
        prompt_version_id=prompt_version_id,
        model_configuration_id=model_configuration_id,
        task_type=task_type,
        status=ModelCallStatus.RUNNING,
        input_object_type=input_object_type,
        input_object_ids=input_object_ids,
        input_checksum=input_checksum,
        request_payload_redacted=request_payload_redacted,
    )
    session.add(call)
    await session.flush()
    return call


async def finalize_model_call(
    session: AsyncSession,
    *,
    call: ModelCall,
    status: ModelCallStatus,
    raw_response: dict[str, Any] | None = None,
    parsed_response: dict[str, Any] | None = None,
    provider_request_id: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    retry_count: int = 0,
    error_code: str | None = None,
    error_message: str | None = None,
) -> ModelCall:
    call.status = status
    call.raw_response = raw_response
    call.parsed_response = parsed_response
    call.provider_request_id = provider_request_id
    call.input_tokens = input_tokens
    call.output_tokens = output_tokens
    call.latency_ms = latency_ms
    call.retry_count = retry_count
    call.error_code = error_code
    call.error_message = error_message
    call.completed_at = datetime.now()
    await session.flush()
    return call
