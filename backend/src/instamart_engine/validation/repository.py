"""DB access for the validation domain. architecture.md §18; datamodel.md §47-52."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import AnalysisLabel, FeedbackAnalysis, ReviewStatus
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.taxonomy.models import TaxonomyDimension, TaxonomyLabel
from instamart_engine.validation.models import (
    Annotation,
    EvaluationDataset,
    EvaluationDatasetItem,
    EvaluationDatasetStatus,
    EvaluationMetric,
    EvaluationObjectType,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationType,
    ReviewDecision,
    ReviewObjectType,
)


async def create_evaluation_dataset(
    session: AsyncSession,
    *,
    version_key: str,
    name: str,
    evaluation_type: EvaluationType,
    description: str | None = None,
    taxonomy_version_id: UUID | None = None,
    selection_method: dict[str, Any] | None = None,
) -> EvaluationDataset:
    dataset = EvaluationDataset(
        version_key=version_key,
        name=name,
        evaluation_type=evaluation_type,
        description=description,
        taxonomy_version_id=taxonomy_version_id,
        selection_method=selection_method or {},
    )
    session.add(dataset)
    await session.flush()
    return dataset


async def get_evaluation_dataset(
    session: AsyncSession, *, evaluation_dataset_id: UUID
) -> EvaluationDataset | None:
    return await session.get(EvaluationDataset, evaluation_dataset_id)


async def get_evaluation_dataset_by_version_key(
    session: AsyncSession, *, version_key: str
) -> EvaluationDataset | None:
    return await session.scalar(
        select(EvaluationDataset).where(EvaluationDataset.version_key == version_key)
    )


async def lock_evaluation_dataset(
    session: AsyncSession, *, dataset: EvaluationDataset
) -> EvaluationDataset:
    dataset.status = EvaluationDatasetStatus.LOCKED
    dataset.locked_at = datetime.now()
    await session.flush()
    return dataset


async def add_evaluation_dataset_item(
    session: AsyncSession,
    *,
    evaluation_dataset_id: UUID,
    object_type: EvaluationObjectType,
    object_id: UUID,
    input_snapshot: dict[str, Any],
    gold_output: dict[str, Any] | None = None,
    item_metadata: dict[str, Any] | None = None,
) -> EvaluationDatasetItem:
    item = EvaluationDatasetItem(
        evaluation_dataset_id=evaluation_dataset_id,
        object_type=object_type,
        object_id=object_id,
        input_snapshot=input_snapshot,
        gold_output=gold_output,
        item_metadata=item_metadata or {},
    )
    session.add(item)
    await session.flush()

    dataset = await session.get(EvaluationDataset, evaluation_dataset_id)
    assert dataset is not None
    dataset.item_count += 1
    await session.flush()
    return item


async def get_dataset_items(
    session: AsyncSession, *, evaluation_dataset_id: UUID
) -> list[EvaluationDatasetItem]:
    return list(
        (
            await session.scalars(
                select(EvaluationDatasetItem).where(
                    EvaluationDatasetItem.evaluation_dataset_id == evaluation_dataset_id
                )
            )
        ).all()
    )


async def get_dataset_item_by_object(
    session: AsyncSession,
    *,
    evaluation_dataset_id: UUID,
    object_type: EvaluationObjectType,
    object_id: UUID,
) -> EvaluationDatasetItem | None:
    return await session.scalar(
        select(EvaluationDatasetItem).where(
            EvaluationDatasetItem.evaluation_dataset_id == evaluation_dataset_id,
            EvaluationDatasetItem.object_type == object_type,
            EvaluationDatasetItem.object_id == object_id,
        )
    )


async def set_dataset_item_gold_output(
    session: AsyncSession, *, item: EvaluationDatasetItem, gold_output: dict[str, Any]
) -> EvaluationDatasetItem:
    item.gold_output = gold_output
    await session.flush()
    return item


async def create_annotation(
    session: AsyncSession,
    *,
    evaluation_dataset_item_id: UUID,
    annotation_round: int,
    annotation_output: dict[str, Any],
    annotator_actor_id: UUID | None = None,
    confidence: float | None = None,
    is_adjudicated: bool = False,
    notes: str | None = None,
) -> Annotation:
    annotation = Annotation(
        evaluation_dataset_item_id=evaluation_dataset_item_id,
        annotator_actor_id=annotator_actor_id,
        annotation_round=annotation_round,
        annotation_output=annotation_output,
        confidence=confidence,
        is_adjudicated=is_adjudicated,
        notes=notes,
    )
    session.add(annotation)
    await session.flush()
    return annotation


async def get_annotations_for_item(
    session: AsyncSession, *, evaluation_dataset_item_id: UUID
) -> list[Annotation]:
    return list(
        (
            await session.scalars(
                select(Annotation)
                .where(Annotation.evaluation_dataset_item_id == evaluation_dataset_item_id)
                .order_by(Annotation.annotation_round)
            )
        ).all()
    )


async def get_adjudicated_annotation(
    session: AsyncSession, *, evaluation_dataset_item_id: UUID
) -> Annotation | None:
    return await session.scalar(
        select(Annotation)
        .where(
            Annotation.evaluation_dataset_item_id == evaluation_dataset_item_id,
            Annotation.is_adjudicated.is_(True),
        )
        .order_by(Annotation.updated_at.desc())
        .limit(1)
    )


async def create_evaluation_run(
    session: AsyncSession,
    *,
    evaluation_dataset_id: UUID,
    configuration_snapshot: dict[str, Any],
    analysis_run_id: UUID | None = None,
    model_configuration_id: UUID | None = None,
    prompt_version_id: UUID | None = None,
) -> EvaluationRun:
    run = EvaluationRun(
        evaluation_dataset_id=evaluation_dataset_id,
        analysis_run_id=analysis_run_id,
        model_configuration_id=model_configuration_id,
        prompt_version_id=prompt_version_id,
        status=EvaluationRunStatus.RUNNING,
        configuration_snapshot=configuration_snapshot,
        started_at=datetime.now(),
    )
    session.add(run)
    await session.flush()
    return run


async def finalize_evaluation_run(
    session: AsyncSession,
    *,
    run: EvaluationRun,
    status: EvaluationRunStatus,
    items_evaluated: int,
    items_failed: int,
) -> EvaluationRun:
    run.status = status
    run.items_evaluated = items_evaluated
    run.items_failed = items_failed
    run.completed_at = datetime.now()
    await session.flush()
    return run


async def set_evaluation_metric(
    session: AsyncSession,
    *,
    evaluation_run_id: UUID,
    metric_key: str,
    sample_count: int,
    calculation_version: str,
    dimension_key: str | None = None,
    numeric_value: float | None = None,
    json_value: dict[str, Any] | None = None,
) -> EvaluationMetric:
    metric = EvaluationMetric(
        evaluation_run_id=evaluation_run_id,
        metric_key=metric_key,
        dimension_key=dimension_key,
        numeric_value=numeric_value,
        json_value=json_value,
        sample_count=sample_count,
        calculation_version=calculation_version,
    )
    session.add(metric)
    await session.flush()
    return metric


async def get_metrics_for_run(
    session: AsyncSession, *, evaluation_run_id: UUID
) -> list[EvaluationMetric]:
    return list(
        (
            await session.scalars(
                select(EvaluationMetric).where(
                    EvaluationMetric.evaluation_run_id == evaluation_run_id
                )
            )
        ).all()
    )


async def get_latest_run_for_dataset(
    session: AsyncSession, *, evaluation_dataset_id: UUID
) -> EvaluationRun | None:
    return await session.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.evaluation_dataset_id == evaluation_dataset_id)
        .order_by(EvaluationRun.created_at.desc())
        .limit(1)
    )


async def get_latest_runs_by_type(
    session: AsyncSession, *, evaluation_type: EvaluationType, limit: int = 10
) -> list[EvaluationRun]:
    return list(
        (
            await session.scalars(
                select(EvaluationRun)
                .join(
                    EvaluationDataset,
                    EvaluationDataset.id == EvaluationRun.evaluation_dataset_id,
                )
                .where(EvaluationDataset.evaluation_type == evaluation_type)
                .order_by(EvaluationRun.created_at.desc())
                .limit(limit)
            )
        ).all()
    )


async def create_review_decision(
    session: AsyncSession,
    *,
    object_type: ReviewObjectType,
    object_id: UUID,
    decision: ReviewStatus,
    previous_snapshot: dict[str, Any],
    edited_snapshot: dict[str, Any] | None = None,
    reviewer_actor_id: UUID | None = None,
    reason_code: str | None = None,
    notes: str | None = None,
) -> ReviewDecision:
    review = ReviewDecision(
        object_type=object_type,
        object_id=object_id,
        reviewer_actor_id=reviewer_actor_id,
        decision=decision,
        previous_snapshot=previous_snapshot,
        edited_snapshot=edited_snapshot,
        reason_code=reason_code,
        notes=notes,
    )
    session.add(review)
    await session.flush()
    return review


async def get_review_decisions_for_object(
    session: AsyncSession, *, object_type: ReviewObjectType, object_id: UUID
) -> list[ReviewDecision]:
    return list(
        (
            await session.scalars(
                select(ReviewDecision)
                .where(
                    ReviewDecision.object_type == object_type,
                    ReviewDecision.object_id == object_id,
                )
                .order_by(ReviewDecision.created_at)
            )
        ).all()
    )


@dataclass(frozen=True, slots=True)
class PendingAnalysisLabelReview:
    """One `analysis_label` awaiting human review (Phase A of the review
    queue, design.md §32.4) — joined with just enough evidence/taxonomy
    context to render a review row and to reconstruct the exact
    `previous_snapshot` `POST /validation/reviews` requires back."""

    analysis_label_id: UUID
    confidence: float
    feedback_record_id: UUID
    excerpt: str
    dimension_key: str
    dimension_display_name: str
    label_key: str
    label_display_name: str
    created_at: datetime


async def count_pending_analysis_label_reviews(session: AsyncSession) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(AnalysisLabel)
            .where(AnalysisLabel.review_status == ReviewStatus.UNREVIEWED)
        )
    ) or 0


async def get_pending_analysis_label_reviews(
    session: AsyncSession, *, limit: int, offset: int
) -> list[PendingAnalysisLabelReview]:
    rows = await session.execute(
        select(
            AnalysisLabel.id,
            AnalysisLabel.confidence,
            FeedbackRecord.id,
            FeedbackRecord.redacted_text,
            TaxonomyDimension.key,
            TaxonomyDimension.display_name,
            TaxonomyLabel.key,
            TaxonomyLabel.display_name,
            AnalysisLabel.created_at,
        )
        .join(FeedbackAnalysis, AnalysisLabel.feedback_analysis_id == FeedbackAnalysis.id)
        .join(FeedbackRecord, FeedbackAnalysis.feedback_record_id == FeedbackRecord.id)
        .join(TaxonomyDimension, AnalysisLabel.taxonomy_dimension_id == TaxonomyDimension.id)
        .join(TaxonomyLabel, AnalysisLabel.taxonomy_label_id == TaxonomyLabel.id)
        .where(AnalysisLabel.review_status == ReviewStatus.UNREVIEWED)
        .order_by(AnalysisLabel.confidence.asc())
        .limit(limit)
        .offset(offset)
    )
    return [
        PendingAnalysisLabelReview(
            analysis_label_id=row[0],
            confidence=float(row[1]),
            feedback_record_id=row[2],
            excerpt=row[3][:240],
            dimension_key=row[4],
            dimension_display_name=row[5],
            label_key=row[6],
            label_display_name=row[7],
            created_at=row[8],
        )
        for row in rows.all()
    ]
