"""Research workspace endpoints. architecture.md §20.6.

`POST .../questions` runs the plan -> retrieve -> generate pipeline
synchronously and returns the persisted, authoritative answer
(architecture.md §17.6 — "the final persisted answer is authoritative;
partial tokens are presentation-only"). `GET .../events` replays that same
persisted state as an SSE lifecycle for a client reconnecting after the
fact (SSE-002/005); it does not stream live model tokens — the AI gateway's
`messages.parse` call is not itself a token stream, so true concurrent
token-by-token SSE is deferred to when that gateway capability exists.
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from instamart_engine.ai.exceptions import AIGatewayError
from instamart_engine.api.schemas.research import (
    AnswerCitationResponse,
    AnswerFindingResponse,
    AnswerWarningResponse,
    CreateQuestionRequest,
    CreateResearchSessionRequest,
    GeneratedAnswerResponse,
    QueryPlanResponse,
    ResearchQuestionResponse,
    ResearchSessionResponse,
)
from instamart_engine.core.database import get_db_session
from instamart_engine.research import repository as research_repo
from instamart_engine.research import service as research_service

router = APIRouter(prefix="/api/v1/research", tags=["research"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def _serialize_question(
    session: AsyncSession, *, question_id: UUID
) -> ResearchQuestionResponse:
    question = await research_repo.get_research_question(session, research_question_id=question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="research_question not found")

    query_plan = await research_repo.get_query_plan_for_question(
        session, research_question_id=question.id
    )
    query_plan_response = (
        QueryPlanResponse(
            research_dimensions=query_plan.research_dimensions,
            query_intent=query_plan.query_intent.value,
            structured_filters=query_plan.structured_filters,
            ambiguity_warnings=query_plan.ambiguity_warnings,
            requires_deterministic_aggregation=query_plan.requires_deterministic_aggregation,
        )
        if query_plan is not None
        else None
    )

    answer = await research_repo.get_generated_answer_for_question(
        session, research_question_id=question.id
    )
    answer_response = None
    if answer is not None:
        findings = await research_repo.get_findings_for_answer(
            session, generated_answer_id=answer.id
        )
        finding_responses = []
        for finding in findings:
            citations = await research_repo.get_citations_for_finding(
                session, answer_finding_id=finding.id
            )
            finding_responses.append(
                AnswerFindingResponse(
                    position=finding.position,
                    finding_type=finding.finding_type.value,
                    statement=finding.statement,
                    confidence_level=finding.confidence_level.value,
                    confidence_score=(
                        float(finding.confidence_score)
                        if finding.confidence_score is not None
                        else None
                    ),
                    support_status=finding.support_status.value,
                    citations=[
                        AnswerCitationResponse(
                            citation_label=c.citation_label,
                            object_type=c.object_type.value,
                            object_id=c.object_id,
                            evidence_role=c.evidence_role.value,
                            excerpt_snapshot=c.excerpt_snapshot,
                            supports_claim=c.supports_claim,
                        )
                        for c in citations
                    ],
                )
            )
        warnings = await research_repo.get_warnings_for_answer(
            session, generated_answer_id=answer.id
        )
        answer_response = GeneratedAnswerResponse(
            id=answer.id,
            answer_text=answer.answer_text,
            grounding_status=answer.grounding_status.value,
            grounding_score=(
                float(answer.grounding_score) if answer.grounding_score is not None else None
            ),
            citation_count=answer.citation_count,
            warning_count=answer.warning_count,
            observed_evidence_count=answer.observed_evidence_count,
            synthesized_insight_count=answer.synthesized_insight_count,
            product_hypothesis_count=answer.product_hypothesis_count,
            limitations=list(answer.limitations),
            suggested_validations=list(answer.suggested_validations),
            findings=finding_responses,
            warnings=[
                AnswerWarningResponse(
                    warning_type=w.warning_type,
                    severity=w.severity.value,
                    message=w.message,
                    details=w.details,
                )
                for w in warnings
            ],
        )

    return ResearchQuestionResponse(
        id=question.id,
        research_session_id=question.research_session_id,
        question_text=question.question_text,
        status=question.status.value,
        requested_filters=question.requested_filters,
        effective_filters=question.effective_filters,
        answer_mode=question.answer_mode,
        failure_code=question.failure_code,
        failure_message=question.failure_message,
        query_plan=query_plan_response,
        answer=answer_response,
    )


@router.post("/sessions", response_model=ResearchSessionResponse, status_code=201)
async def create_session(
    body: CreateResearchSessionRequest,
    session: DbSession,
) -> ResearchSessionResponse:
    research_session = await research_repo.create_research_session(
        session,
        title=body.title,
        analysis_run_id=body.analysis_run_id,
        theme_set_id=body.theme_set_id,
        insight_set_id=body.insight_set_id,
        default_filters=body.default_filters,
    )
    await session.commit()
    return ResearchSessionResponse(
        id=research_session.id,
        title=research_session.title,
        analysis_run_id=research_session.analysis_run_id,
        theme_set_id=research_session.theme_set_id,
        insight_set_id=research_session.insight_set_id,
        status=research_session.status.value,
        created_at=research_session.created_at,
    )


@router.get("/sessions/{session_id}", response_model=ResearchSessionResponse)
async def get_session(
    session_id: UUID, session: DbSession
) -> ResearchSessionResponse:
    research_session = await research_repo.get_research_session(
        session, research_session_id=session_id
    )
    if research_session is None:
        raise HTTPException(status_code=404, detail="research_session not found")
    return ResearchSessionResponse(
        id=research_session.id,
        title=research_session.title,
        analysis_run_id=research_session.analysis_run_id,
        theme_set_id=research_session.theme_set_id,
        insight_set_id=research_session.insight_set_id,
        status=research_session.status.value,
        created_at=research_session.created_at,
    )


@router.post("/sessions/{session_id}/questions", response_model=ResearchQuestionResponse)
async def ask_question(
    session_id: UUID,
    body: CreateQuestionRequest,
    session: DbSession,
) -> ResearchQuestionResponse:
    try:
        result = await research_service.ask_question(
            session,
            research_session_id=session_id,
            question_text=body.question_text,
            requested_filters=body.requested_filters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIGatewayError as exc:
        raise HTTPException(
            status_code=502, detail=f"{type(exc).__name__}: {exc}"
        ) from exc

    return await _serialize_question(session, question_id=result.question.id)


@router.get("/questions/{question_id}", response_model=ResearchQuestionResponse)
async def get_question(
    question_id: UUID, session: DbSession
) -> ResearchQuestionResponse:
    return await _serialize_question(session, question_id=question_id)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _question_event_stream(
    session: AsyncSession, *, question_id: UUID
) -> AsyncIterator[str]:
    question_response = await _serialize_question(session, question_id=question_id)
    yield _sse_event("answer.started", {"question_id": str(question_id)})

    if question_response.answer is not None:
        for finding in question_response.answer.findings:
            for citation in finding.citations:
                yield _sse_event(
                    "citation.added",
                    {"position": finding.position, "citation_label": citation.citation_label},
                )
        for warning in question_response.answer.warnings:
            yield _sse_event("warning.added", {"warning_type": warning.warning_type})

    if question_response.status in ("completed", "completed_with_warnings"):
        yield _sse_event(
            "answer.completed",
            {"question_id": str(question_id), "status": question_response.status},
        )
    elif question_response.status == "failed":
        yield _sse_event(
            "answer.failed",
            {
                "question_id": str(question_id),
                "failure_code": question_response.failure_code,
                "failure_message": question_response.failure_message,
            },
        )
    else:
        # SSE-005 — no terminal event yet; a client seeing only this should
        # poll GET /questions/{id} for the current persisted status rather
        # than assume the stream is complete.
        yield _sse_event("heartbeat", {"status": question_response.status})


@router.get("/questions/{question_id}/events")
async def get_question_events(
    question_id: UUID, session: DbSession
) -> StreamingResponse:
    return StreamingResponse(
        _question_event_stream(session, question_id=question_id),
        media_type="text/event-stream",
    )
