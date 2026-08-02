"""Taxonomy domain: versioned dimensions and labels. datamodel.md §18-20.

Published taxonomy versions are immutable (datamodel.md §18) — a revision
creates a new `taxonomy_version` row rather than editing an existing one.
"""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, DateTime, Enum, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class TaxonomyStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


taxonomy_status_enum = Enum(
    TaxonomyStatus, name="taxonomy_status", values_callable=lambda e: [m.value for m in e]
)


class TaxonomyVersion(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §18."""

    __tablename__ = "taxonomy_version"
    __table_args__ = (UniqueConstraint("version_key", name="uq_taxonomy_version_key"),)

    version_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_file_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[TaxonomyStatus] = mapped_column(
        taxonomy_status_enum, nullable=False, server_default=TaxonomyStatus.DRAFT.value
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class TaxonomyCardinality(enum.StrEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"


taxonomy_cardinality_enum = Enum(
    TaxonomyCardinality,
    name="taxonomy_cardinality",
    values_callable=lambda e: [m.value for m in e],
)


class TaxonomyValueType(enum.StrEnum):
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    NUMERIC = "numeric"
    BOOLEAN = "boolean"


taxonomy_value_type_enum = Enum(
    TaxonomyValueType, name="taxonomy_value_type", values_callable=lambda e: [m.value for m in e]
)


class TaxonomyDimension(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §19. E.g. `journey_stage`, `exploration_barrier`."""

    __tablename__ = "taxonomy_dimension"
    __table_args__ = (
        UniqueConstraint("taxonomy_version_id", "key", name="uq_taxonomy_dimension_version_key"),
    )

    taxonomy_version_id: Mapped[UUID] = mapped_column(nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cardinality: Mapped[TaxonomyCardinality] = mapped_column(
        taxonomy_cardinality_enum, nullable=False
    )
    value_type: Mapped[TaxonomyValueType] = mapped_column(taxonomy_value_type_enum, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class TaxonomyLabel(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §20. The allowed label vocabulary within a dimension."""

    __tablename__ = "taxonomy_label"
    __table_args__ = (
        UniqueConstraint("taxonomy_dimension_id", "key", name="uq_taxonomy_label_dimension_key"),
    )

    taxonomy_dimension_id: Mapped[UUID] = mapped_column(nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    inclusion_examples: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    exclusion_examples: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    parent_label_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
