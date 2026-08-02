"""Canonical feedback domain: feedback_record and its satellite tables.
datamodel.md §12-16."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
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
from instamart_engine.ingestion.models import RawRecordType, raw_record_type_enum


class RelevanceStatus(enum.StrEnum):
    UNREVIEWED = "unreviewed"
    RELEVANT_USER_FEEDBACK = "relevant_user_feedback"
    RELEVANT_COMPETITOR_FEEDBACK = "relevant_competitor_feedback"
    INDUSTRY_COMMENTARY = "industry_commentary"
    IRRELEVANT = "irrelevant"
    SPAM_OR_PROMOTION = "spam_or_promotion"
    INSUFFICIENT_CONTENT = "insufficient_content"


relevance_status_enum = Enum(
    RelevanceStatus, name="relevance_status", values_callable=lambda e: [m.value for m in e]
)


class QualityStatus(enum.StrEnum):
    UNASSESSED = "unassessed"
    USABLE = "usable"
    LOW_INFORMATION = "low_information"
    MALFORMED = "malformed"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    PRIVACY_BLOCKED = "privacy_blocked"
    COLLECTION_INCOMPLETE = "collection_incomplete"


quality_status_enum = Enum(
    QualityStatus, name="quality_status", values_callable=lambda e: [m.value for m in e]
)


class FeedbackProcessingStatus(enum.StrEnum):
    COLLECTED = "collected"
    NORMALIZED = "normalized"
    REDACTED = "redacted"
    RELEVANCE_ASSESSED = "relevance_assessed"
    DEDUPLICATED = "deduplicated"
    CLASSIFIED = "classified"
    EMBEDDED = "embedded"
    THEMED = "themed"
    INSIGHT_LINKED = "insight_linked"
    REVIEWED = "reviewed"
    FAILED = "failed"


feedback_processing_status_enum = Enum(
    FeedbackProcessingStatus,
    name="feedback_processing_status",
    values_callable=lambda e: [m.value for m in e],
)


class MediaType(enum.StrEnum):
    IMAGE = "image"
    VIDEO = "video"


media_type_enum = Enum(MediaType, name="media_type", values_callable=lambda e: [m.value for m in e])


class FeedbackRecord(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §12. The central normalized unit of research evidence."""

    __tablename__ = "feedback_record"
    __table_args__ = (
        UniqueConstraint("raw_source_item_id", name="uq_feedback_record_raw_source_item"),
        CheckConstraint("normalized_length >= 0", name="ck_feedback_record_length_nonneg"),
        CheckConstraint(
            "token_estimate IS NULL OR token_estimate >= 0",
            name="ck_feedback_record_token_estimate_nonneg",
        ),
        CheckConstraint(
            "rating_normalized IS NULL OR rating_normalized BETWEEN 0 AND 1",
            name="ck_feedback_record_rating_normalized_range",
        ),
        CheckConstraint(
            "language_confidence IS NULL OR language_confidence BETWEEN 0 AND 1",
            name="ck_feedback_record_language_confidence_range",
        ),
    )

    raw_source_item_id: Mapped[UUID] = mapped_column(nullable=False)
    source_connector_id: Mapped[UUID] = mapped_column(nullable=False)
    record_type: Mapped[RawRecordType] = mapped_column(raw_record_type_enum, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    redacted_text: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_code_mixed: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    normalized_length: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_normalized: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    engagement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country_code: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    app_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_status: Mapped[RelevanceStatus] = mapped_column(
        relevance_status_enum, nullable=False, server_default=RelevanceStatus.UNREVIEWED.value
    )
    quality_status: Mapped[QualityStatus] = mapped_column(
        quality_status_enum, nullable=False, server_default=QualityStatus.UNASSESSED.value
    )
    processing_status: Mapped[FeedbackProcessingStatus] = mapped_column(
        feedback_processing_status_enum,
        nullable=False,
        server_default=FeedbackProcessingStatus.COLLECTED.value,
    )
    is_primary_for_counts: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[MediaType | None] = mapped_column(media_type_enum, nullable=True)
    extracted_media_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted_at_source: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    source_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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


class ThreadRelationType(enum.StrEnum):
    REPLY_TO = "reply_to"
    COMMENT_ON = "comment_on"
    QUOTED_BY = "quoted_by"
    CONTEXT_FOR = "context_for"


thread_relation_type_enum = Enum(
    ThreadRelationType,
    name="thread_relation_type",
    values_callable=lambda e: [m.value for m in e],
)


class FeedbackThreadRelation(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §13."""

    __tablename__ = "feedback_thread_relation"
    __table_args__ = (
        UniqueConstraint(
            "parent_feedback_record_id",
            "child_feedback_record_id",
            "relation_type",
            name="uq_feedback_thread_relation",
        ),
        CheckConstraint(
            "parent_feedback_record_id != child_feedback_record_id",
            name="ck_feedback_thread_relation_no_self_reference",
        ),
        CheckConstraint(
            "depth IS NULL OR depth >= 0", name="ck_feedback_thread_relation_depth_nonneg"
        ),
    )

    parent_feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    child_feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    relation_type: Mapped[ThreadRelationType] = mapped_column(
        thread_relation_type_enum, nullable=False
    )
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_in_thread: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class DuplicateType(enum.StrEnum):
    EXACT = "exact"
    NEAR_DUPLICATE = "near_duplicate"
    CROSS_SOURCE_REPOST = "cross_source_repost"
    QUOTED_COPY = "quoted_copy"


duplicate_type_enum = Enum(
    DuplicateType, name="duplicate_type", values_callable=lambda e: [m.value for m in e]
)


class FeedbackDuplicateLink(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §14."""

    __tablename__ = "feedback_duplicate_link"
    __table_args__ = (
        UniqueConstraint(
            "duplicate_feedback_record_id", name="uq_feedback_duplicate_link_duplicate"
        ),
        CheckConstraint(
            "canonical_feedback_record_id != duplicate_feedback_record_id",
            name="ck_feedback_duplicate_link_no_self_reference",
        ),
        CheckConstraint(
            "lexical_similarity IS NULL OR lexical_similarity BETWEEN 0 AND 1",
            name="ck_feedback_duplicate_link_lexical_range",
        ),
        CheckConstraint(
            "semantic_similarity IS NULL OR semantic_similarity BETWEEN 0 AND 1",
            name="ck_feedback_duplicate_link_semantic_range",
        ),
    )

    canonical_feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    duplicate_feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    duplicate_type: Mapped[DuplicateType] = mapped_column(duplicate_type_enum, nullable=False)
    lexical_similarity: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    semantic_similarity: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    decision_method: Mapped[str] = mapped_column(Text, nullable=False)
    decision_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RedactionType(enum.StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    ORDER_ID = "order_id"
    PAYMENT_IDENTIFIER = "payment_identifier"
    PERSON_NAME = "person_name"
    USERNAME = "username"
    OTHER = "other"


redaction_type_enum = Enum(
    RedactionType, name="redaction_type", values_callable=lambda e: [m.value for m in e]
)


class FeedbackRedaction(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §15. Never stores the original sensitive substring."""

    __tablename__ = "feedback_redaction"

    feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    redaction_type: Mapped[RedactionType] = mapped_column(redaction_type_enum, nullable=False)
    start_offset_original: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset_original: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replacement_token: Mapped[str] = mapped_column(Text, nullable=False)
    detector: Mapped[str] = mapped_column(Text, nullable=False)
    detector_version: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class QualityEventSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


quality_event_severity_enum = Enum(
    QualityEventSeverity,
    name="quality_event_severity",
    values_callable=lambda e: [m.value for m in e],
)


class FeedbackQualityEvent(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §16. Quality checks and processing warnings."""

    __tablename__ = "feedback_quality_event"

    feedback_record_id: Mapped[UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[QualityEventSeverity] = mapped_column(
        quality_event_severity_enum, nullable=False
    )
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
