"""Source-collection config, ingestion runs, raw artifacts, raw source items,
and connector checkpoints. datamodel.md §7-11."""

import enum
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class SourceCollectionConfig(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §7."""

    __tablename__ = "source_collection_config"
    __table_args__ = (
        CheckConstraint(
            "default_record_limit IS NULL OR default_record_limit > 0",
            name="ck_collection_config_limit_positive",
        ),
        CheckConstraint(
            "default_date_from IS NULL OR default_date_to IS NULL "
            "OR default_date_from <= default_date_to",
            name="ck_collection_config_date_range",
        ),
    )

    source_connector_id: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    configuration: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    default_record_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    default_date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_by_actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # NOTE: datamodel.md's partial-unique constraint
    # `UNIQUE (source_connector_id, name) WHERE deleted_at IS NULL` requires a
    # partial index; added in the migration directly rather than here since
    # SQLAlchemy Core UniqueConstraint doesn't express a WHERE clause.


class IngestionRunStatus(enum.StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ingestion_run_status_enum = Enum(
    IngestionRunStatus,
    name="ingestion_run_status",
    values_callable=lambda e: [m.value for m in e],
)


class IngestionRun(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §8. One attempt to collect data from one configuration."""

    __tablename__ = "ingestion_run"
    __table_args__ = (
        CheckConstraint("records_discovered >= 0", name="ck_ingestion_run_discovered_nonneg"),
        CheckConstraint("records_stored >= 0", name="ck_ingestion_run_stored_nonneg"),
        CheckConstraint("records_skipped >= 0", name="ck_ingestion_run_skipped_nonneg"),
        CheckConstraint("records_failed >= 0", name="ck_ingestion_run_failed_nonneg"),
        CheckConstraint(
            "requested_record_limit IS NULL OR requested_record_limit > 0",
            name="ck_ingestion_run_limit_positive",
        ),
        CheckConstraint(
            "date_from IS NULL OR date_to IS NULL OR date_from <= date_to",
            name="ck_ingestion_run_date_range",
        ),
    )

    source_collection_config_id: Mapped[UUID] = mapped_column(nullable=False)
    parent_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[IngestionRunStatus] = mapped_column(
        ingestion_run_status_enum,
        nullable=False,
        server_default=IngestionRunStatus.CREATED.value,
    )
    requested_record_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    configuration_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    checkpoint_start: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    checkpoint_end: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    records_discovered: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    records_stored: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    records_skipped: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 6), nullable=True)
    actual_cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 6), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RawArtifact(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §9. Immutable except retention/deletion metadata."""

    __tablename__ = "raw_artifact"
    __table_args__ = (
        UniqueConstraint("storage_backend", "storage_key", name="uq_raw_artifact_key"),
        CheckConstraint(
            "byte_size IS NULL OR byte_size >= 0", name="ck_raw_artifact_size_nonneg"
        ),
    )

    ingestion_run_id: Mapped[UUID] = mapped_column(nullable=False)
    storage_backend: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    response_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RawRecordType(enum.StrEnum):
    APP_REVIEW = "app_review"
    FORUM_POST = "forum_post"
    FORUM_COMMENT = "forum_comment"
    SOCIAL_POST = "social_post"
    SOCIAL_COMMENT = "social_comment"
    PRODUCT_REVIEW = "product_review"
    ARTICLE_PASSAGE = "article_passage"
    OTHER = "other"


raw_record_type_enum = Enum(
    RawRecordType, name="raw_record_type", values_callable=lambda e: [m.value for m in e]
)


class RawSourceItem(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §10. One source-native record extracted from a raw artifact."""

    __tablename__ = "raw_source_item"
    __table_args__ = (
        UniqueConstraint(
            "source_connector_id", "external_id", name="uq_raw_source_item_connector_external"
        ),
        CheckConstraint("rating IS NULL OR rating >= 0", name="ck_raw_source_item_rating_nonneg"),
        CheckConstraint(
            "rating_scale_max IS NULL OR rating_scale_max > 0",
            name="ck_raw_source_item_scale_positive",
        ),
        CheckConstraint(
            "rating IS NULL OR rating_scale_max IS NULL OR rating <= rating_scale_max",
            name="ck_raw_source_item_rating_within_scale",
        ),
        CheckConstraint(
            "engagement_count IS NULL OR engagement_count >= 0",
            name="ck_raw_source_item_engagement_nonneg",
        ),
        CheckConstraint(
            "reply_count IS NULL OR reply_count >= 0", name="ck_raw_source_item_replies_nonneg"
        ),
    )

    raw_artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    ingestion_run_id: Mapped[UUID] = mapped_column(nullable=False)
    source_connector_id: Mapped[UUID] = mapped_column(nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_parent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_type: Mapped[RawRecordType] = mapped_column(raw_record_type_enum, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author_external_id_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    rating_scale_max: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    engagement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    app_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    payload_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ConnectorCheckpointModel(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §11. Resumable connector state."""

    __tablename__ = "connector_checkpoint"

    source_collection_config_id: Mapped[UUID] = mapped_column(nullable=False)
    ingestion_run_id: Mapped[UUID] = mapped_column(nullable=False)
    checkpoint_type: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
