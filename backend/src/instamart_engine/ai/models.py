"""AI gateway domain: versioned prompts, model configurations, and the
model-call audit log. datamodel.md §21-24; architecture.md §12."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CHAR,
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class PromptStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


prompt_status_enum = Enum(
    PromptStatus, name="prompt_status", values_callable=lambda e: [m.value for m in e]
)


class PromptTemplate(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §21 — a logical prompt task, e.g. `feedback_classification`."""

    __tablename__ = "prompt_template"
    __table_args__ = (UniqueConstraint("task_key", name="uq_prompt_template_task_key"),)

    task_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_schema_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class PromptVersion(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §22 — an immutable prompt version."""

    __tablename__ = "prompt_version"
    __table_args__ = (
        UniqueConstraint(
            "prompt_template_id", "version_key", name="uq_prompt_version_template_key"
        ),
    )

    prompt_template_id: Mapped[UUID] = mapped_column(nullable=False)
    version_key: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    response_schema: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    source_file_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[PromptStatus] = mapped_column(
        prompt_status_enum, nullable=False, server_default=PromptStatus.DRAFT.value
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ModelConfiguration(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §23. API keys are never stored here."""

    __tablename__ = "model_configuration"
    __table_args__ = (
        CheckConstraint(
            "temperature IS NULL OR temperature BETWEEN 0 AND 2",
            name="ck_model_configuration_temperature_range",
        ),
        CheckConstraint(
            "max_output_tokens IS NULL OR max_output_tokens > 0",
            name="ck_model_configuration_max_tokens_positive",
        ),
        CheckConstraint("timeout_seconds > 0", name="ck_model_configuration_timeout_positive"),
        CheckConstraint("max_retries >= 0", name="ck_model_configuration_retries_nonneg"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    structured_output_mode: Mapped[str] = mapped_column(Text, nullable=False)
    configuration: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class ModelCallStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    INVALID_OUTPUT = "invalid_output"
    RATE_LIMITED = "rate_limited"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"


model_call_status_enum = Enum(
    ModelCallStatus, name="model_call_status", values_callable=lambda e: [m.value for m in e]
)


class ModelCall(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §24 — the authoritative audit record for every LLM call."""

    __tablename__ = "model_call"

    analysis_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    research_question_id: Mapped[UUID | None] = mapped_column(nullable=True)
    prompt_version_id: Mapped[UUID] = mapped_column(nullable=False)
    model_configuration_id: Mapped[UUID] = mapped_column(nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ModelCallStatus] = mapped_column(
        model_call_status_enum, nullable=False, server_default=ModelCallStatus.QUEUED.value
    )
    input_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_object_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(Uuid()), nullable=True)
    input_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    request_payload_redacted: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    raw_response: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    parsed_response: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 6), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
