"""DB access for the analysis domain. architecture.md §8.4."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import (
    AnalysisEvidenceSpan,
    AnalysisLabel,
    AnalysisRun,
    AnalysisRunStatus,
    FeedbackAnalysis,
    FeedbackAnalysisStatus,
    LabelSource,
    TextVariant,
)
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus

_CLASSIFIABLE_QUALITY = (QualityStatus.USABLE, QualityStatus.LOW_INFORMATION)
_SKIPPED_RELEVANCE = (RelevanceStatus.INSUFFICIENT_CONTENT, RelevanceStatus.SPAM_OR_PROMOTION)


async def get_unclassified_feedback_records(
    session: AsyncSession, *, source_connector_id: UUID | None = None, limit: int = 100
) -> list[FeedbackRecord]:
    """CLS-013 — unsupported-language/malformed/privacy-blocked records
    never reach the classifier; INS/REL scoring already decided those
    aren't worth spending a paid call on."""
    already_classified = select(FeedbackAnalysis.feedback_record_id)
    stmt = (
        select(FeedbackRecord)
        .where(
            FeedbackRecord.id.not_in(already_classified),
            FeedbackRecord.quality_status.in_(_CLASSIFIABLE_QUALITY),
            FeedbackRecord.relevance_status.not_in(_SKIPPED_RELEVANCE),
            FeedbackRecord.deleted_at.is_(None),
        )
        .order_by(FeedbackRecord.created_at)
        .limit(limit)
    )
    if source_connector_id is not None:
        stmt = stmt.where(FeedbackRecord.source_connector_id == source_connector_id)
    return list((await session.scalars(stmt)).all())


async def create_analysis_run(
    session: AsyncSession,
    *,
    name: str,
    taxonomy_version_id: UUID,
    classification_model_configuration_id: UUID,
    dataset_snapshot: dict[str, Any],
) -> AnalysisRun:
    run = AnalysisRun(
        name=name,
        status=AnalysisRunStatus.RUNNING,
        dataset_snapshot=dataset_snapshot,
        taxonomy_version_id=taxonomy_version_id,
        classification_model_configuration_id=classification_model_configuration_id,
        started_at=datetime.now(),
    )
    session.add(run)
    await session.flush()
    return run


async def finalize_analysis_run(
    session: AsyncSession,
    *,
    run: AnalysisRun,
    records_selected: int,
    records_classified: int,
    records_failed: int,
) -> AnalysisRun:
    run.records_selected = records_selected
    run.records_classified = records_classified
    run.records_failed = records_failed
    run.completed_at = datetime.now()
    if records_failed > 0 and records_classified > 0:
        run.status = AnalysisRunStatus.PARTIALLY_COMPLETED
    elif records_failed > 0 and records_classified == 0:
        run.status = AnalysisRunStatus.FAILED
    else:
        run.status = AnalysisRunStatus.COMPLETED
    await session.flush()
    return run


async def insert_feedback_analysis(
    session: AsyncSession,
    *,
    feedback_record_id: UUID,
    analysis_run_id: UUID,
    taxonomy_version_id: UUID,
    model_call_id: UUID | None,
    status: FeedbackAnalysisStatus,
    overall_confidence: float | None,
    sentiment_score: float | None,
    sentiment_confidence: float | None,
    severity_value: int | None,
    severity_confidence: float | None,
    summary: str | None,
) -> FeedbackAnalysis:
    analysis = FeedbackAnalysis(
        feedback_record_id=feedback_record_id,
        analysis_run_id=analysis_run_id,
        taxonomy_version_id=taxonomy_version_id,
        model_call_id=model_call_id,
        status=status,
        overall_confidence=overall_confidence,
        sentiment_score=sentiment_score,
        sentiment_confidence=sentiment_confidence,
        severity_value=severity_value,
        severity_confidence=severity_confidence,
        summary=summary,
    )
    session.add(analysis)
    await session.flush()
    return analysis


async def insert_analysis_label(
    session: AsyncSession,
    *,
    feedback_analysis_id: UUID,
    taxonomy_dimension_id: UUID,
    taxonomy_label_id: UUID,
    confidence: float,
) -> AnalysisLabel:
    label = AnalysisLabel(
        feedback_analysis_id=feedback_analysis_id,
        taxonomy_dimension_id=taxonomy_dimension_id,
        taxonomy_label_id=taxonomy_label_id,
        confidence=confidence,
        source=LabelSource.MODEL,
    )
    session.add(label)
    await session.flush()
    return label


async def insert_evidence_span(
    session: AsyncSession,
    *,
    analysis_label_id: UUID,
    feedback_record_id: UUID,
    excerpt_snapshot: str,
    start_offset: int,
    end_offset: int,
    support_strength: float | None,
) -> AnalysisEvidenceSpan:
    span = AnalysisEvidenceSpan(
        analysis_label_id=analysis_label_id,
        feedback_record_id=feedback_record_id,
        text_variant=TextVariant.NORMALIZED,
        start_offset=start_offset,
        end_offset=end_offset,
        excerpt_snapshot=excerpt_snapshot,
        support_strength=support_strength,
    )
    session.add(span)
    await session.flush()
    return span
