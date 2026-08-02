"""Validation workspace endpoints. architecture.md §20.7."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import ReviewStatus
from instamart_engine.api.schemas.validation import (
    EvaluationMetricResponse,
    EvaluationRunResponse,
    EvaluationTypeSummaryResponse,
    ReleaseGateDecisionResponse,
    ReviewDecisionResponse,
    ReviewQueueItemResponse,
    ReviewQueueListResponse,
    SubmitReviewRequest,
    ValidationSummaryResponse,
)
from instamart_engine.core.database import get_db_session
from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.models import EvaluationRun, EvaluationType, ReviewObjectType
from instamart_engine.validation.release_gates import (
    CONFIG_DIR,
    evaluate_release_gates,
    load_release_gate_config,
)
from instamart_engine.validation.reviews import (
    InvalidTaxonomyLabelError,
    MissingPreviousSnapshotError,
    ReviewReasonRequiredError,
    submit_review,
)

router = APIRouter(prefix="/api/v1/validation", tags=["validation"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

_RELEASE_GATE_CONFIG_PATH = CONFIG_DIR / "mvp-v1.yaml"


async def _serialize_run(session: DbSession, *, run: EvaluationRun) -> EvaluationRunResponse:
    metrics = await validation_repo.get_metrics_for_run(session, evaluation_run_id=run.id)

    release_gate_response = None
    if _RELEASE_GATE_CONFIG_PATH.exists():
        config = load_release_gate_config(_RELEASE_GATE_CONFIG_PATH)
        decision = evaluate_release_gates(config, metrics)
        release_gate_response = ReleaseGateDecisionResponse(
            release_profile=config.release_profile,
            status=decision.status,
            zero_tolerance_failures=list(decision.zero_tolerance_failures),
            metric_failures=list(decision.metric_failures),
        )

    return EvaluationRunResponse(
        id=run.id,
        evaluation_dataset_id=run.evaluation_dataset_id,
        status=run.status.value,
        items_evaluated=run.items_evaluated,
        items_failed=run.items_failed,
        created_at=run.created_at,
        completed_at=run.completed_at,
        metrics=[
            EvaluationMetricResponse(
                metric_key=m.metric_key,
                dimension_key=m.dimension_key,
                numeric_value=float(m.numeric_value) if m.numeric_value is not None else None,
                json_value=m.json_value,
                sample_count=m.sample_count,
                calculation_version=m.calculation_version,
            )
            for m in metrics
        ],
        release_gate=release_gate_response,
    )


async def _serialize_type_summary(
    session: DbSession, *, evaluation_type: EvaluationType
) -> EvaluationTypeSummaryResponse:
    runs = await validation_repo.get_latest_runs_by_type(
        session, evaluation_type=evaluation_type, limit=1
    )
    latest_run = await _serialize_run(session, run=runs[0]) if runs else None
    return EvaluationTypeSummaryResponse(
        evaluation_type=evaluation_type.value, latest_run=latest_run
    )


@router.get("/summary", response_model=ValidationSummaryResponse)
async def get_summary(session: DbSession) -> ValidationSummaryResponse:
    return ValidationSummaryResponse(
        classification=await _serialize_type_summary(
            session, evaluation_type=EvaluationType.CLASSIFICATION
        ),
        retrieval=await _serialize_type_summary(
            session, evaluation_type=EvaluationType.RETRIEVAL
        ),
        theme=await _serialize_type_summary(session, evaluation_type=EvaluationType.THEME),
        grounding=await _serialize_type_summary(
            session, evaluation_type=EvaluationType.GROUNDING
        ),
    )


@router.get("/classification", response_model=EvaluationTypeSummaryResponse)
async def get_classification(session: DbSession) -> EvaluationTypeSummaryResponse:
    return await _serialize_type_summary(session, evaluation_type=EvaluationType.CLASSIFICATION)


@router.get("/retrieval", response_model=EvaluationTypeSummaryResponse)
async def get_retrieval(session: DbSession) -> EvaluationTypeSummaryResponse:
    return await _serialize_type_summary(session, evaluation_type=EvaluationType.RETRIEVAL)


@router.get("/themes", response_model=EvaluationTypeSummaryResponse)
async def get_themes(session: DbSession) -> EvaluationTypeSummaryResponse:
    return await _serialize_type_summary(session, evaluation_type=EvaluationType.THEME)


@router.get("/grounding", response_model=EvaluationTypeSummaryResponse)
async def get_grounding(session: DbSession) -> EvaluationTypeSummaryResponse:
    return await _serialize_type_summary(session, evaluation_type=EvaluationType.GROUNDING)


_SUPPORTED_REVIEW_QUEUE_TYPES = {"analysis_label"}
DEFAULT_REVIEW_QUEUE_LIMIT = 25


@router.get("/reviews", response_model=ReviewQueueListResponse)
async def list_pending_reviews(
    session: DbSession,
    object_type: str = Query(default="analysis_label"),
    limit: int = Query(default=DEFAULT_REVIEW_QUEUE_LIMIT, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewQueueListResponse:
    """Phase A of the review queue (design.md §32.4) — only `analysis_label`
    is implemented so far; `feedback_relevance`, `feedback_analysis`,
    `theme`, `theme_membership`, `insight`, `insight_evidence`,
    `answer_finding`, and `answer_citation` are follow-up phases."""
    if object_type not in _SUPPORTED_REVIEW_QUEUE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"object_type={object_type!r} is not yet supported by the review queue "
                f"(supported: {sorted(_SUPPORTED_REVIEW_QUEUE_TYPES)})"
            ),
        )

    total_matching = await validation_repo.count_pending_analysis_label_reviews(session)
    pending = await validation_repo.get_pending_analysis_label_reviews(
        session, limit=limit, offset=offset
    )
    return ReviewQueueListResponse(
        total_matching=total_matching,
        limit=limit,
        offset=offset,
        items=[
            ReviewQueueItemResponse(
                object_type="analysis_label",
                object_id=item.analysis_label_id,
                excerpt=item.excerpt,
                dimension_key=item.dimension_key,
                dimension_display_name=item.dimension_display_name,
                label_key=item.label_key,
                label_display_name=item.label_display_name,
                confidence=item.confidence,
                previous_snapshot={
                    "dimension_key": item.dimension_key,
                    "label_key": item.label_key,
                    "confidence": item.confidence,
                },
                created_at=item.created_at,
            )
            for item in pending
        ],
    )


@router.post("/reviews", response_model=ReviewDecisionResponse, status_code=201)
async def create_review(
    body: SubmitReviewRequest, session: DbSession
) -> ReviewDecisionResponse:
    try:
        object_type = ReviewObjectType(body.object_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown object_type: {body.object_type}"
        ) from exc
    try:
        decision = ReviewStatus(body.decision)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown decision: {body.decision}") from exc

    try:
        review = await submit_review(
            session,
            object_type=object_type,
            object_id=body.object_id,
            decision=decision,
            previous_snapshot=body.previous_snapshot,
            edited_snapshot=body.edited_snapshot,
            reviewer_actor_id=body.reviewer_actor_id,
            reason_code=body.reason_code,
            notes=body.notes,
        )
    except (
        ReviewReasonRequiredError,
        InvalidTaxonomyLabelError,
        MissingPreviousSnapshotError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    return ReviewDecisionResponse(
        id=review.id,
        object_type=review.object_type.value,
        object_id=review.object_id,
        decision=review.decision.value,
        reason_code=review.reason_code,
        notes=review.notes,
        created_at=review.created_at,
    )
