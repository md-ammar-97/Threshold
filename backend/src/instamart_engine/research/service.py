"""Orchestrates one research question end to end: plan -> retrieve ->
generate. architecture.md §17.1. This is the synchronous "ask" pipeline;
the persisted `generated_answer` is authoritative regardless of how a caller
chooses to present progress (architecture.md §17.6) — see `api/routes/research.py`
for the thin SSE lifecycle wrapper around this same call.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai.exceptions import AIGatewayError
from instamart_engine.ai.gateway import AIGateway
from instamart_engine.core.logging import get_logger
from instamart_engine.research import generate, planner, query_filters, retrieval
from instamart_engine.research import repository as research_repo
from instamart_engine.research.generate import AnswerResult
from instamart_engine.research.models import (
    GroundingStatus,
    ResearchQuestion,
    ResearchQuestionStatus,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AskQuestionResult:
    question: ResearchQuestion
    answer_result: AnswerResult


async def ask_question(
    session: AsyncSession,
    *,
    research_session_id: UUID,
    question_text: str,
    requested_filters: dict[str, str] | None = None,
    gateway: AIGateway | None = None,
) -> AskQuestionResult:
    research_session = await research_repo.get_research_session(
        session, research_session_id=research_session_id
    )
    if research_session is None:
        raise ValueError(f"research_session {research_session_id} not found")

    requested_filters = requested_filters or {}
    question = await research_repo.create_research_question(
        session,
        research_session_id=research_session_id,
        question_text=question_text,
        requested_filters=requested_filters,
    )
    await session.commit()

    gateway = gateway or AIGateway()

    await research_repo.update_question_status(
        session,
        question=question,
        status=ResearchQuestionStatus.PLANNING,
        started_at=datetime.now(UTC),
    )
    await session.commit()

    try:
        plan_result = await planner.plan_question(
            session, research_question_id=question.id, question_text=question_text, gateway=gateway
        )
        await session.commit()

        # requested_filters (explicit, user-supplied) take precedence over
        # the planner's LLM-derived filters for the same key (QRY-018 —
        # any adjustment away from what was requested must be visible, so
        # both the raw request and the merged effective_filters are kept).
        requested_effective, requested_warnings = query_filters.validate_filters(
            requested_filters
        )
        effective_filters = {**plan_result.effective_filters, **requested_effective}
        if requested_warnings:
            logger.warning(
                "requested_filter_warnings",
                question_id=str(question.id),
                warnings=requested_warnings,
            )

        await research_repo.update_question_status(
            session,
            question=question,
            status=ResearchQuestionStatus.RETRIEVING,
            effective_filters=effective_filters,
            answer_mode=plan_result.query_plan.query_intent.value,
        )
        await session.commit()

        evidence_package = await retrieval.retrieve_evidence(
            session,
            research_question_id=question.id,
            theme_set_id=research_session.theme_set_id,
            insight_set_id=research_session.insight_set_id,
            analysis_run_id=research_session.analysis_run_id,
            question_text=question_text,
            effective_filters=effective_filters,
        )
        await session.commit()

        await research_repo.update_question_status(
            session, question=question, status=ResearchQuestionStatus.GENERATING
        )
        await session.commit()

        answer_result = await generate.generate_answer(
            session,
            research_question_id=question.id,
            question_text=question_text,
            query_intent=plan_result.query_plan.query_intent.value,
            evidence_package=evidence_package,
            gateway=gateway,
        )

        final_status = (
            ResearchQuestionStatus.COMPLETED
            if answer_result.grounding_status == GroundingStatus.PASSED
            else ResearchQuestionStatus.COMPLETED_WITH_WARNINGS
        )
        await research_repo.update_question_status(
            session,
            question=question,
            status=final_status,
            completed_at=datetime.now(UTC),
        )
        await session.commit()

        return AskQuestionResult(question=question, answer_result=answer_result)

    except AIGatewayError as exc:
        # ANS-013 — a failure here means the question is never marked
        # completed; the caller can safely retry.
        await research_repo.update_question_status(
            session,
            question=question,
            status=ResearchQuestionStatus.FAILED,
            completed_at=datetime.now(UTC),
            failure_code=type(exc).__name__,
            failure_message=str(exc),
        )
        await session.commit()
        raise
