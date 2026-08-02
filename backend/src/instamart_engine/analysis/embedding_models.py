"""Embedding domain: versioned embedding configurations and vectors.
datamodel.md §28-29; architecture.md §14.

Because PostgreSQL cannot enforce a polymorphic foreign key,
`embedding.object_type`/`object_id` are validated at the application level
(datamodel.md §29's own note) — the same pattern already used for the
plain-UUID cross-domain references elsewhere in this codebase (e.g.
`feedback_record.source_connector_id`).
"""

import enum
from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import CHAR, CheckConstraint, DateTime, Enum, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class EmbeddingConfiguration(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §28."""

    __tablename__ = "embedding_configuration"
    __table_args__ = (
        UniqueConstraint("version_key", name="uq_embedding_configuration_version_key"),
        CheckConstraint("dimension > 0", name="ck_embedding_configuration_dimension_positive"),
        CheckConstraint(
            "max_input_tokens IS NULL OR max_input_tokens > 0",
            name="ck_embedding_configuration_max_tokens_positive",
        ),
    )

    version_key: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(Text, nullable=False, server_default="cosine")
    max_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalization_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    configuration: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class EmbeddingObjectType(enum.StrEnum):
    FEEDBACK_RECORD = "feedback_record"
    FEEDBACK_CONTEXT_WINDOW = "feedback_context_window"
    THEME = "theme"
    INSIGHT = "insight"
    RESEARCH_QUESTION = "research_question"


embedding_object_type_enum = Enum(
    EmbeddingObjectType,
    name="embedding_object_type",
    values_callable=lambda e: [m.value for m in e],
)

# Physical vector width — must match EMBEDDING_DIMENSION / all-MiniLM-L6-v2's
# actual output (384). datamodel.md §29 notes this must be a fixed column
# width; supporting multiple dimensions would need separate tables.
EMBEDDING_VECTOR_DIMENSION = 384


class Embedding(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §29."""

    __tablename__ = "embedding"
    __table_args__ = (
        UniqueConstraint(
            "embedding_configuration_id",
            "object_type",
            "object_id",
            "text_checksum",
            name="uq_embedding_config_object_checksum",
        ),
        CheckConstraint(
            "token_count IS NULL OR token_count >= 0", name="ck_embedding_token_count_nonneg"
        ),
    )

    embedding_configuration_id: Mapped[UUID] = mapped_column(nullable=False)
    object_type: Mapped[EmbeddingObjectType] = mapped_column(
        embedding_object_type_enum, nullable=False
    )
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    text_variant: Mapped[str] = mapped_column(Text, nullable=False)
    text_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    embedding_vector: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_VECTOR_DIMENSION), nullable=False
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
