"""DB access for the research workspace domain. architecture.md §17;
datamodel.md §39-46."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.feedback.models import QualityEventSeverity
from instamart_engine.insights.models import ConfidenceLevel, EvidenceRole, InsightType
from instamart_engine.research.models import (
    AnswerCitation,
    AnswerFinding,
    AnswerWarning,
    CitationObjectType,
    FindingSupportStatus,
    GeneratedAnswer,
    GroundingStatus,
    QueryIntent,
    QueryPlan,
    ResearchQuestion,
    ResearchQuestionStatus,
    ResearchSession,
    RetrievalObjectType,
    RetrievalResult,
    RetrievalStage,
)


async def create_research_session(
    session: AsyncSession,
    *,
    title: str,
    analysis_run_id: UUID,
    theme_set_id: UUID,
    insight_set_id: UUID | None = None,
    actor_id: UUID | None = None,
    default_filters: dict[str, Any] | None = None,
) -> ResearchSession:
    research_session = ResearchSession(
        title=title,
        actor_id=actor_id,
        analysis_run_id=analysis_run_id,
        theme_set_id=theme_set_id,
        insight_set_id=insight_set_id,
        default_filters=default_filters or {},
    )
    session.add(research_session)
    await session.flush()
    return research_session


async def get_research_session(
    session: AsyncSession, *, research_session_id: UUID
) -> ResearchSession | None:
    return await session.get(ResearchSession, research_session_id)


async def create_research_question(
    session: AsyncSession,
    *,
    research_session_id: UUID,
    question_text: str,
    requested_filters: dict[str, Any] | None = None,
    parent_question_id: UUID | None = None,
) -> ResearchQuestion:
    question = ResearchQuestion(
        research_session_id=research_session_id,
        parent_question_id=parent_question_id,
        question_text=question_text,
        requested_filters=requested_filters or {},
        effective_filters={},
    )
    session.add(question)
    await session.flush()
    return question


async def update_question_status(
    session: AsyncSession,
    *,
    question: ResearchQuestion,
    status: ResearchQuestionStatus,
    effective_filters: dict[str, Any] | None = None,
    answer_mode: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> ResearchQuestion:
    question.status = status
    if effective_filters is not None:
        question.effective_filters = effective_filters
    if answer_mode is not None:
        question.answer_mode = answer_mode
    if started_at is not None:
        question.started_at = started_at
    if completed_at is not None:
        question.completed_at = completed_at
    if failure_code is not None:
        question.failure_code = failure_code
    if failure_message is not None:
        question.failure_message = failure_message
    await session.flush()
    return question


async def save_query_plan(
    session: AsyncSession,
    *,
    research_question_id: UUID,
    model_call_id: UUID | None,
    research_dimensions: list[str],
    query_intent: QueryIntent,
    structured_filters: dict[str, Any],
    retrieval_strategy: dict[str, Any],
    ambiguity_warnings: list[str],
    requires_deterministic_aggregation: bool,
) -> QueryPlan:
    plan = QueryPlan(
        research_question_id=research_question_id,
        model_call_id=model_call_id,
        research_dimensions=research_dimensions,
        query_intent=query_intent,
        structured_filters=structured_filters,
        retrieval_strategy=retrieval_strategy,
        ambiguity_warnings={"warnings": ambiguity_warnings},
        requires_deterministic_aggregation=requires_deterministic_aggregation,
    )
    session.add(plan)
    await session.flush()
    return plan


async def upsert_retrieval_result(
    session: AsyncSession,
    *,
    research_question_id: UUID,
    object_type: RetrievalObjectType,
    object_id: UUID,
    retrieval_stage: RetrievalStage,
    vector_score: float | None = None,
    keyword_score: float | None = None,
    structured_filter_score: float | None = None,
    rerank_score: float | None = None,
    diversity_penalty: float | None = None,
    final_rank: int | None = None,
    selection_reason: dict[str, Any] | None = None,
) -> RetrievalResult:
    """A retrieval object has exactly one row per question (unique on
    question/object_type/object_id) that advances through `retrieval_stage`
    as it survives each funnel step — this is an upsert, not an append."""
    existing = await session.scalar(
        select(RetrievalResult).where(
            RetrievalResult.research_question_id == research_question_id,
            RetrievalResult.object_type == object_type,
            RetrievalResult.object_id == object_id,
        )
    )
    if existing is None:
        existing = RetrievalResult(
            research_question_id=research_question_id,
            object_type=object_type,
            object_id=object_id,
            retrieval_stage=retrieval_stage,
            selection_reason=selection_reason or {},
        )
        session.add(existing)

    existing.retrieval_stage = retrieval_stage
    if vector_score is not None:
        existing.vector_score = vector_score
    if keyword_score is not None:
        existing.keyword_score = keyword_score
    if structured_filter_score is not None:
        existing.structured_filter_score = structured_filter_score
    if rerank_score is not None:
        existing.rerank_score = rerank_score
    if diversity_penalty is not None:
        existing.diversity_penalty = diversity_penalty
    if final_rank is not None:
        existing.final_rank = final_rank
    if selection_reason is not None:
        existing.selection_reason = selection_reason
    await session.flush()
    return existing


async def create_generated_answer(
    session: AsyncSession,
    *,
    research_question_id: UUID,
    model_call_id: UUID | None,
    answer_text: str,
    answer_schema: dict[str, Any],
    grounding_status: GroundingStatus,
    grounding_score: float | None,
    citation_count: int,
    warning_count: int,
    observed_evidence_count: int,
    synthesized_insight_count: int,
    product_hypothesis_count: int,
    limitations: list[str],
    suggested_validations: list[str],
) -> GeneratedAnswer:
    answer = GeneratedAnswer(
        research_question_id=research_question_id,
        model_call_id=model_call_id,
        answer_text=answer_text,
        answer_schema=answer_schema,
        grounding_status=grounding_status,
        grounding_score=grounding_score,
        citation_count=citation_count,
        warning_count=warning_count,
        observed_evidence_count=observed_evidence_count,
        synthesized_insight_count=synthesized_insight_count,
        product_hypothesis_count=product_hypothesis_count,
        limitations=limitations,
        suggested_validations=suggested_validations,
    )
    session.add(answer)
    await session.flush()
    return answer


async def create_answer_finding(
    session: AsyncSession,
    *,
    generated_answer_id: UUID,
    position: int,
    finding_type: InsightType,
    statement: str,
    confidence_level: ConfidenceLevel,
    confidence_score: float | None,
    support_status: FindingSupportStatus,
) -> AnswerFinding:
    finding = AnswerFinding(
        generated_answer_id=generated_answer_id,
        position=position,
        finding_type=finding_type,
        statement=statement,
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        support_status=support_status,
    )
    session.add(finding)
    await session.flush()
    return finding


async def create_answer_citation(
    session: AsyncSession,
    *,
    answer_finding_id: UUID,
    citation_label: str,
    object_type: CitationObjectType,
    object_id: UUID,
    evidence_role: EvidenceRole,
    excerpt_snapshot: str | None,
    supports_claim: bool | None,
    validation_notes: str | None = None,
) -> AnswerCitation:
    citation = AnswerCitation(
        answer_finding_id=answer_finding_id,
        citation_label=citation_label,
        object_type=object_type,
        object_id=object_id,
        evidence_role=evidence_role,
        excerpt_snapshot=excerpt_snapshot,
        supports_claim=supports_claim,
        validation_notes=validation_notes,
    )
    session.add(citation)
    await session.flush()
    return citation


async def get_research_question(
    session: AsyncSession, *, research_question_id: UUID
) -> ResearchQuestion | None:
    return await session.get(ResearchQuestion, research_question_id)


async def get_query_plan_for_question(
    session: AsyncSession, *, research_question_id: UUID
) -> QueryPlan | None:
    return await session.scalar(
        select(QueryPlan).where(QueryPlan.research_question_id == research_question_id)
    )


async def get_generated_answer_for_question(
    session: AsyncSession, *, research_question_id: UUID
) -> GeneratedAnswer | None:
    return await session.scalar(
        select(GeneratedAnswer).where(GeneratedAnswer.research_question_id == research_question_id)
    )


async def get_findings_for_answer(
    session: AsyncSession, *, generated_answer_id: UUID
) -> list[AnswerFinding]:
    return list(
        (
            await session.scalars(
                select(AnswerFinding)
                .where(AnswerFinding.generated_answer_id == generated_answer_id)
                .order_by(AnswerFinding.position)
            )
        ).all()
    )


async def get_citations_for_finding(
    session: AsyncSession, *, answer_finding_id: UUID
) -> list[AnswerCitation]:
    return list(
        (
            await session.scalars(
                select(AnswerCitation).where(
                    AnswerCitation.answer_finding_id == answer_finding_id
                )
            )
        ).all()
    )


async def get_warnings_for_answer(
    session: AsyncSession, *, generated_answer_id: UUID
) -> list[AnswerWarning]:
    return list(
        (
            await session.scalars(
                select(AnswerWarning).where(
                    AnswerWarning.generated_answer_id == generated_answer_id
                )
            )
        ).all()
    )


async def create_answer_warning(
    session: AsyncSession,
    *,
    generated_answer_id: UUID,
    warning_type: str,
    severity: QualityEventSeverity,
    message: str,
    details: dict[str, Any] | None = None,
) -> AnswerWarning:
    warning = AnswerWarning(
        generated_answer_id=generated_answer_id,
        warning_type=warning_type,
        severity=severity,
        message=message,
        details=details or {},
    )
    session.add(warning)
    await session.flush()
    return warning
