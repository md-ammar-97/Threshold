"""Research workspace domain: sessions, questions, query plans, retrieval
results, and generated answers. datamodel.md §39-46; architecture.md §17."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
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
from instamart_engine.feedback.models import QualityEventSeverity, quality_event_severity_enum
from instamart_engine.insights.models import (
    ConfidenceLevel,
    EvidenceRole,
    InsightType,
    confidence_level_enum,
    evidence_role_enum,
    insight_type_enum,
)


class ResearchSessionStatus(enum.StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


research_session_status_enum = Enum(
    ResearchSessionStatus,
    name="research_session_status",
    values_callable=lambda e: [m.value for m in e],
)


class ResearchSession(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §39 — a user's research workspace or conversation."""

    __tablename__ = "research_session"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    analysis_run_id: Mapped[UUID] = mapped_column(nullable=False)
    theme_set_id: Mapped[UUID] = mapped_column(nullable=False)
    insight_set_id: Mapped[UUID | None] = mapped_column(nullable=True)
    default_filters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[ResearchSessionStatus] = mapped_column(
        research_session_status_enum,
        nullable=False,
        server_default=ResearchSessionStatus.ACTIVE.value,
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


class ResearchQuestionStatus(enum.StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


research_question_status_enum = Enum(
    ResearchQuestionStatus,
    name="research_question_status",
    values_callable=lambda e: [m.value for m in e],
)


class ResearchQuestion(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §40 — one natural-language research question."""

    __tablename__ = "research_question"
    __table_args__ = (
        CheckConstraint(
            "char_length(question_text) > 0", name="ck_research_question_text_nonempty"
        ),
    )

    research_session_id: Mapped[UUID] = mapped_column(nullable=False)
    parent_question_id: Mapped[UUID | None] = mapped_column(nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ResearchQuestionStatus] = mapped_column(
        research_question_status_enum,
        nullable=False,
        server_default=ResearchQuestionStatus.CREATED.value,
    )
    requested_filters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    effective_filters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    answer_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class QueryIntent(enum.StrEnum):
    EXPLAIN = "explain"
    COUNT = "count"
    COMPARE = "compare"
    RANK = "rank"
    FIND_EXAMPLES = "find_examples"
    SUMMARIZE = "summarize"
    VALIDATE_HYPOTHESIS = "validate_hypothesis"


query_intent_enum = Enum(
    QueryIntent, name="query_intent", values_callable=lambda e: [m.value for m in e]
)


class QueryPlan(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §41 — the validated structured interpretation of a question."""

    __tablename__ = "query_plan"
    __table_args__ = (
        UniqueConstraint("research_question_id", name="uq_query_plan_research_question"),
    )

    research_question_id: Mapped[UUID] = mapped_column(nullable=False)
    model_call_id: Mapped[UUID | None] = mapped_column(nullable=True)
    research_dimensions: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    query_intent: Mapped[QueryIntent] = mapped_column(query_intent_enum, nullable=False)
    structured_filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retrieval_strategy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ambiguity_warnings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    requires_deterministic_aggregation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RetrievalObjectType(enum.StrEnum):
    FEEDBACK_RECORD = "feedback_record"
    THEME = "theme"
    INSIGHT = "insight"


retrieval_object_type_enum = Enum(
    RetrievalObjectType,
    name="retrieval_object_type",
    values_callable=lambda e: [m.value for m in e],
)


class RetrievalStage(enum.StrEnum):
    CANDIDATE = "candidate"
    RERANKED = "reranked"
    SELECTED = "selected"
    EXCLUDED = "excluded"


retrieval_stage_enum = Enum(
    RetrievalStage, name="retrieval_stage", values_callable=lambda e: [m.value for m in e]
)


class RetrievalResult(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §42 — one candidate evidence object considered for an answer."""

    __tablename__ = "retrieval_result"
    __table_args__ = (
        UniqueConstraint(
            "research_question_id",
            "object_type",
            "object_id",
            name="uq_retrieval_result_question_object",
        ),
        CheckConstraint(
            "final_rank IS NULL OR final_rank > 0", name="ck_retrieval_result_rank_positive"
        ),
    )

    research_question_id: Mapped[UUID] = mapped_column(nullable=False)
    object_type: Mapped[RetrievalObjectType] = mapped_column(
        retrieval_object_type_enum, nullable=False
    )
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    retrieval_stage: Mapped[RetrievalStage] = mapped_column(retrieval_stage_enum, nullable=False)
    vector_score: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    keyword_score: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    structured_filter_score: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    rerank_score: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    diversity_penalty: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    final_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selection_reason: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class GroundingStatus(enum.StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    HUMAN_REVIEWED = "human_reviewed"


grounding_status_enum = Enum(
    GroundingStatus, name="grounding_status", values_callable=lambda e: [m.value for m in e]
)


class GeneratedAnswer(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §43 — the final persisted answer, not transient stream tokens."""

    __tablename__ = "generated_answer"
    __table_args__ = (
        UniqueConstraint("research_question_id", name="uq_generated_answer_research_question"),
        CheckConstraint("citation_count >= 0", name="ck_generated_answer_citation_count_nonneg"),
        CheckConstraint("warning_count >= 0", name="ck_generated_answer_warning_count_nonneg"),
    )

    research_question_id: Mapped[UUID] = mapped_column(nullable=False)
    model_call_id: Mapped[UUID | None] = mapped_column(nullable=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    grounding_status: Mapped[GroundingStatus] = mapped_column(
        grounding_status_enum, nullable=False, server_default=GroundingStatus.PENDING.value
    )
    grounding_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observed_evidence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    synthesized_insight_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    product_hypothesis_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    limitations: Mapped[dict] = mapped_column(
        JSONB(none_as_null=True), nullable=False, server_default=text("'[]'::jsonb")
    )
    suggested_validations: Mapped[dict] = mapped_column(
        JSONB(none_as_null=True), nullable=False, server_default=text("'[]'::jsonb")
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


class FindingSupportStatus(enum.StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


finding_support_status_enum = Enum(
    FindingSupportStatus,
    name="finding_support_status",
    values_callable=lambda e: [m.value for m in e],
)


class AnswerFinding(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §44 — one atomic claim unit within an answer."""

    __tablename__ = "answer_finding"
    __table_args__ = (
        UniqueConstraint(
            "generated_answer_id", "position", name="uq_answer_finding_answer_position"
        ),
        CheckConstraint("position > 0", name="ck_answer_finding_position_positive"),
        CheckConstraint(
            "confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1",
            name="ck_answer_finding_confidence_range",
        ),
    )

    generated_answer_id: Mapped[UUID] = mapped_column(nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_type: Mapped[InsightType] = mapped_column(insight_type_enum, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(confidence_level_enum, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    support_status: Mapped[FindingSupportStatus] = mapped_column(
        finding_support_status_enum,
        nullable=False,
        server_default=FindingSupportStatus.UNVERIFIED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class CitationObjectType(enum.StrEnum):
    FEEDBACK_RECORD = "feedback_record"
    THEME = "theme"
    THEME_METRIC = "theme_metric"
    INSIGHT = "insight"


citation_object_type_enum = Enum(
    CitationObjectType, name="citation_object_type", values_callable=lambda e: [m.value for m in e]
)


class AnswerCitation(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §45 — links an answer finding to a stable evidence object."""

    __tablename__ = "answer_citation"
    __table_args__ = (
        UniqueConstraint(
            "answer_finding_id", "citation_label", name="uq_answer_citation_finding_label"
        ),
    )

    answer_finding_id: Mapped[UUID] = mapped_column(nullable=False)
    citation_label: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[CitationObjectType] = mapped_column(
        citation_object_type_enum, nullable=False
    )
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    evidence_role: Mapped[EvidenceRole] = mapped_column(evidence_role_enum, nullable=False)
    excerpt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    supports_claim: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class AnswerWarning(UUIDPrimaryKeyMixin, Base):
    """datamodel.md §46 — explicit caveats and grounding warnings."""

    __tablename__ = "answer_warning"

    generated_answer_id: Mapped[UUID] = mapped_column(nullable=False)
    warning_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[QualityEventSeverity] = mapped_column(
        quality_event_severity_enum, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
