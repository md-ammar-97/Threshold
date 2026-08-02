"""DB access for the insight domain. architecture.md §16; datamodel.md §35-38."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.insights.models import (
    ConfidenceLevel,
    EvidenceRole,
    Insight,
    InsightEvidence,
    InsightSet,
    InsightSetStatus,
    InsightTheme,
    InsightThemeRelationship,
    InsightType,
)


async def get_latest_insight_set(session: AsyncSession) -> InsightSet | None:
    """Most recently created insight_set regardless of status — mirrors
    `themes.repository.get_latest_theme_set` (the Insights surface shows
    whatever the latest real run produced, not just a published version)."""
    return await session.scalar(
        select(InsightSet).order_by(InsightSet.created_at.desc()).limit(1)
    )


async def get_insights_for_set(session: AsyncSession, *, insight_set_id: UUID) -> list[Insight]:
    return list(
        (
            await session.scalars(
                select(Insight)
                .where(Insight.insight_set_id == insight_set_id, Insight.deleted_at.is_(None))
                .order_by(Insight.opportunity_score.desc().nulls_last())
            )
        ).all()
    )


async def get_insight_by_id(session: AsyncSession, *, insight_id: UUID) -> Insight | None:
    return await session.scalar(
        select(Insight).where(Insight.id == insight_id, Insight.deleted_at.is_(None))
    )


async def get_insight_themes(session: AsyncSession, *, insight_id: UUID) -> list[InsightTheme]:
    return list(
        (
            await session.scalars(
                select(InsightTheme).where(InsightTheme.insight_id == insight_id)
            )
        ).all()
    )


async def get_insight_evidence(
    session: AsyncSession, *, insight_id: UUID
) -> list[InsightEvidence]:
    return list(
        (
            await session.scalars(
                select(InsightEvidence)
                .where(InsightEvidence.insight_id == insight_id)
                .order_by(InsightEvidence.relevance_score.desc())
            )
        ).all()
    )


async def create_insight_set(
    session: AsyncSession,
    *,
    theme_set_id: UUID,
    analysis_run_id: UUID,
    model_configuration_id: UUID,
    prompt_version_id: UUID,
) -> InsightSet:
    existing_max = await session.scalar(
        select(InsightSet.version_number)
        .where(InsightSet.theme_set_id == theme_set_id)
        .order_by(InsightSet.version_number.desc())
        .limit(1)
    )
    insight_set = InsightSet(
        theme_set_id=theme_set_id,
        analysis_run_id=analysis_run_id,
        version_number=(existing_max or 0) + 1,
        status=InsightSetStatus.PROCESSING,
        model_configuration_id=model_configuration_id,
        prompt_version_id=prompt_version_id,
    )
    session.add(insight_set)
    await session.flush()
    return insight_set


async def create_insight(
    session: AsyncSession,
    *,
    insight_set_id: UUID,
    insight_type: InsightType,
    title: str,
    finding: str,
    interpretation: str,
    affected_context: str | None,
    product_implication: str | None,
    validation_recommendation: str | None,
    confidence_level: ConfidenceLevel,
    confidence_score: float,
    opportunity_score: float | None,
    score_components: dict | None,
    model_call_id: UUID | None,
) -> Insight:
    insight = Insight(
        insight_set_id=insight_set_id,
        insight_type=insight_type,
        title=title,
        finding=finding,
        interpretation=interpretation,
        affected_context=affected_context,
        product_implication=product_implication,
        validation_recommendation=validation_recommendation,
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        opportunity_score=opportunity_score,
        score_components=score_components,
        model_call_id=model_call_id,
    )
    session.add(insight)
    await session.flush()
    return insight


async def add_insight_theme(
    session: AsyncSession,
    *,
    insight_id: UUID,
    theme_id: UUID,
    relationship_type: InsightThemeRelationship,
    relevance_score: float | None,
) -> InsightTheme:
    link = InsightTheme(
        insight_id=insight_id,
        theme_id=theme_id,
        relationship_type=relationship_type,
        relevance_score=relevance_score,
    )
    session.add(link)
    await session.flush()
    return link


async def add_insight_evidence(
    session: AsyncSession,
    *,
    insight_id: UUID,
    feedback_record_id: UUID,
    evidence_role: EvidenceRole,
    relevance_score: float,
    start_offset: int | None,
    end_offset: int | None,
    excerpt_snapshot: str,
) -> InsightEvidence:
    evidence = InsightEvidence(
        insight_id=insight_id,
        feedback_record_id=feedback_record_id,
        evidence_role=evidence_role,
        relevance_score=relevance_score,
        start_offset=start_offset,
        end_offset=end_offset,
        excerpt_snapshot=excerpt_snapshot,
    )
    session.add(evidence)
    await session.flush()
    return evidence


async def finalize_insight_set(
    session: AsyncSession,
    *,
    insight_set: InsightSet,
    insight_count: int,
    status: InsightSetStatus,
) -> InsightSet:
    insight_set.insight_count = insight_count
    insight_set.status = status
    if status == InsightSetStatus.PUBLISHED:
        insight_set.published_at = datetime.now()
    await session.flush()
    return insight_set
