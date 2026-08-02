"""DB access for the theme domain. architecture.md §8.4."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import AnalysisLabel, FeedbackAnalysis
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.taxonomy.models import TaxonomyDimension, TaxonomyLabel
from instamart_engine.themes.models import (
    ScoringProfile,
    Theme,
    ThemeMembership,
    ThemeMetric,
    ThemeSet,
    ThemeSetStatus,
    ThemeStatus,
    ThemeType,
)


async def get_latest_theme_set(session: AsyncSession) -> ThemeSet | None:
    """Most recently created theme_set regardless of status — the frontend
    Themes surface (design.md §28) shows whatever the latest real run
    produced, including an in-progress one, rather than requiring a
    published version to exist first."""
    return await session.scalar(select(ThemeSet).order_by(ThemeSet.created_at.desc()).limit(1))


async def get_themes_for_set(session: AsyncSession, *, theme_set_id: UUID) -> list[Theme]:
    return list(
        (
            await session.scalars(
                select(Theme).where(Theme.theme_set_id == theme_set_id).order_by(Theme.theme_key)
            )
        ).all()
    )


async def get_theme_evidence(
    session: AsyncSession, *, theme_id: UUID
) -> tuple[list[FeedbackRecord], FeedbackRecord | None]:
    """Returns (representative_records_ordered_by_rank, counterexample_record)."""
    representative_stmt = (
        select(FeedbackRecord)
        .join(ThemeMembership, ThemeMembership.feedback_record_id == FeedbackRecord.id)
        .where(ThemeMembership.theme_id == theme_id, ThemeMembership.is_representative.is_(True))
        .order_by(ThemeMembership.rank_within_theme)
    )
    representatives = list((await session.scalars(representative_stmt)).all())

    counterexample_stmt = (
        select(FeedbackRecord)
        .join(ThemeMembership, ThemeMembership.feedback_record_id == FeedbackRecord.id)
        .where(ThemeMembership.theme_id == theme_id, ThemeMembership.is_counterexample.is_(True))
        .limit(1)
    )
    counterexample = await session.scalar(counterexample_stmt)

    return representatives, counterexample


@dataclass(frozen=True, slots=True)
class ThemeSetQualityMetrics:
    """Set-wide numbers from ai_evals.md §30 that don't fit a per-theme
    grader (`validation/graders/theme_quality.py` covers the per-theme
    tier) — computed directly from real `theme_set`/`theme_membership` data,
    no gold/human rubric needed."""

    eligible_record_coverage: float | None
    outlier_rate: float | None
    overlap_rate: float | None
    duplicate_inflation_rate: float


async def compute_theme_set_quality_metrics(
    session: AsyncSession, *, theme_set_id: UUID
) -> ThemeSetQualityMetrics:
    theme_set = await session.get(ThemeSet, theme_set_id)
    if theme_set is None:
        raise ValueError(f"theme_set {theme_set_id} not found")

    eligible = theme_set.eligible_record_count
    coverage = (theme_set.clustered_record_count / eligible) if eligible else None
    outlier_rate = (theme_set.outlier_record_count / eligible) if eligible else None

    themes = await get_themes_for_set(session, theme_set_id=theme_set_id)
    member_sets: list[set[UUID]] = []
    membership_counts: dict[UUID, int] = defaultdict(int)
    for theme in themes:
        member_ids = set(
            (
                await session.scalars(
                    select(ThemeMembership.feedback_record_id).where(
                        ThemeMembership.theme_id == theme.id
                    )
                )
            ).all()
        )
        member_sets.append(member_ids)
        for record_id in member_ids:
            membership_counts[record_id] += 1

    overlap_scores = []
    for i in range(len(member_sets)):
        for j in range(i + 1, len(member_sets)):
            union = member_sets[i] | member_sets[j]
            if union:
                overlap_scores.append(len(member_sets[i] & member_sets[j]) / len(union))
    overlap_rate = sum(overlap_scores) / len(overlap_scores) if overlap_scores else None

    duplicated_members = sum(1 for count in membership_counts.values() if count > 1)
    duplicate_inflation_rate = (
        duplicated_members / len(membership_counts) if membership_counts else 0.0
    )

    return ThemeSetQualityMetrics(
        eligible_record_coverage=coverage,
        outlier_rate=outlier_rate,
        overlap_rate=overlap_rate,
        duplicate_inflation_rate=duplicate_inflation_rate,
    )


async def get_theme_membership_count(session: AsyncSession, *, theme_id: UUID) -> int:
    stmt = select(ThemeMembership).where(ThemeMembership.theme_id == theme_id)
    result = await session.scalars(stmt)
    return len(result.all())


@dataclass(frozen=True, slots=True)
class ThemeTaxonomyLabel:
    """One taxonomy label applied to at least one of a theme's member
    records, with how many distinct members carry it — the aggregation the
    Themes surface needs to show real tags/classifications (previously
    nothing queried `analysis_label` on this path at all)."""

    theme_id: UUID
    dimension_key: str
    dimension_display_name: str
    label_key: str
    label_display_name: str
    record_count: int


async def get_taxonomy_labels_for_themes(
    session: AsyncSession, *, theme_ids: list[UUID]
) -> dict[UUID, list[ThemeTaxonomyLabel]]:
    """Batched across all `theme_ids` in one query (not one query per theme)
    so the list view doesn't N+1. Only reflects whatever taxonomy version(s)
    a theme's member records actually have `analysis_label` rows for —
    records classified before a newer taxonomy version was published won't
    show that version's dimensions until reclassified; this function doesn't
    backfill or fabricate anything, it reports what's really in the DB."""
    if not theme_ids:
        return {}

    distinct_member_count = func.count(func.distinct(ThemeMembership.feedback_record_id))
    stmt = (
        select(
            ThemeMembership.theme_id,
            TaxonomyDimension.key,
            TaxonomyDimension.display_name,
            TaxonomyLabel.key,
            TaxonomyLabel.display_name,
            distinct_member_count,
        )
        .join(
            FeedbackAnalysis,
            FeedbackAnalysis.feedback_record_id == ThemeMembership.feedback_record_id,
        )
        .join(AnalysisLabel, AnalysisLabel.feedback_analysis_id == FeedbackAnalysis.id)
        .join(TaxonomyLabel, TaxonomyLabel.id == AnalysisLabel.taxonomy_label_id)
        .join(TaxonomyDimension, TaxonomyDimension.id == AnalysisLabel.taxonomy_dimension_id)
        .where(ThemeMembership.theme_id.in_(theme_ids))
        .group_by(
            ThemeMembership.theme_id,
            TaxonomyDimension.key,
            TaxonomyDimension.display_name,
            TaxonomyLabel.key,
            TaxonomyLabel.display_name,
        )
        .order_by(ThemeMembership.theme_id, distinct_member_count.desc())
    )
    rows = await session.execute(stmt)

    result: dict[UUID, list[ThemeTaxonomyLabel]] = defaultdict(list)
    for theme_id, dim_key, dim_name, label_key, label_name, record_count in rows.all():
        result[theme_id].append(
            ThemeTaxonomyLabel(
                theme_id=theme_id,
                dimension_key=dim_key,
                dimension_display_name=dim_name,
                label_key=label_key,
                label_display_name=label_name,
                record_count=record_count,
            )
        )
    return dict(result)


async def create_theme_set(
    session: AsyncSession,
    *,
    analysis_run_id: UUID,
    name: str,
    clustering_algorithm: str,
    clustering_configuration: dict[str, Any],
    eligible_record_count: int,
) -> ThemeSet:
    existing_max = await session.scalar(
        select(ThemeSet.version_number)
        .where(ThemeSet.analysis_run_id == analysis_run_id)
        .order_by(ThemeSet.version_number.desc())
        .limit(1)
    )
    theme_set = ThemeSet(
        analysis_run_id=analysis_run_id,
        version_number=(existing_max or 0) + 1,
        name=name,
        status=ThemeSetStatus.PROCESSING,
        clustering_algorithm=clustering_algorithm,
        clustering_configuration=clustering_configuration,
        eligible_record_count=eligible_record_count,
    )
    session.add(theme_set)
    await session.flush()
    return theme_set


async def create_provisional_theme(
    session: AsyncSession,
    *,
    theme_set_id: UUID,
    theme_key: str,
    placeholder_name: str,
    representative_record_count: int,
) -> Theme:
    theme = Theme(
        theme_set_id=theme_set_id,
        theme_key=theme_key,
        name=placeholder_name,
        short_summary="(pending synthesis)",
        theme_type=ThemeType.OTHER,
        status=ThemeStatus.UNREVIEWED,
        representative_record_count=representative_record_count,
    )
    session.add(theme)
    await session.flush()
    return theme


async def add_theme_membership(
    session: AsyncSession,
    *,
    theme_id: UUID,
    feedback_record_id: UUID,
    membership_score: float,
    assignment_method: str,
    is_representative: bool = False,
    is_counterexample: bool = False,
    rank_within_theme: int | None = None,
) -> ThemeMembership:
    membership = ThemeMembership(
        theme_id=theme_id,
        feedback_record_id=feedback_record_id,
        membership_score=membership_score,
        assignment_method=assignment_method,
        is_representative=is_representative,
        is_counterexample=is_counterexample,
        rank_within_theme=rank_within_theme,
    )
    session.add(membership)
    await session.flush()
    return membership


async def finalize_theme_set(
    session: AsyncSession,
    *,
    theme_set: ThemeSet,
    clustered_record_count: int,
    outlier_record_count: int,
    theme_count: int,
    status: ThemeSetStatus = ThemeSetStatus.PUBLISHED,
) -> ThemeSet:
    theme_set.clustered_record_count = clustered_record_count
    theme_set.outlier_record_count = outlier_record_count
    theme_set.theme_count = theme_count
    theme_set.status = status
    if status == ThemeSetStatus.PUBLISHED:
        theme_set.published_at = datetime.now()
    await session.flush()
    return theme_set


async def update_theme_synthesis(
    session: AsyncSession,
    *,
    theme: Theme,
    name: str,
    short_summary: str,
    long_summary: str,
    theme_type: ThemeType,
    confidence_score: float,
    model_call_id: UUID | None,
) -> Theme:
    theme.name = name
    theme.short_summary = short_summary
    theme.long_summary = long_summary
    theme.theme_type = theme_type
    theme.confidence_score = confidence_score
    theme.model_call_id = model_call_id
    theme.status = ThemeStatus.UNREVIEWED
    await session.flush()
    return theme


async def set_theme_metric(
    session: AsyncSession,
    *,
    theme_id: UUID,
    metric_key: str,
    calculation_version: str,
    numeric_value: float | None = None,
    text_value: str | None = None,
    json_value: dict[str, Any] | None = None,
    segment_key: str | None = None,
) -> ThemeMetric:
    metric = ThemeMetric(
        theme_id=theme_id,
        metric_key=metric_key,
        segment_key=segment_key,
        numeric_value=numeric_value,
        text_value=text_value,
        json_value=json_value,
        calculation_version=calculation_version,
    )
    session.add(metric)
    await session.flush()
    return metric


async def update_theme_scores(
    session: AsyncSession,
    *,
    theme: Theme,
    discovery_relevance_score: float,
    actionability_score: float,
    coherence_score: float | None,
    opportunity_score: float,
    score_components: dict[str, Any],
) -> Theme:
    theme.discovery_relevance_score = discovery_relevance_score
    theme.actionability_score = actionability_score
    theme.coherence_score = coherence_score
    theme.opportunity_score = opportunity_score
    theme.score_components = score_components
    await session.flush()
    return theme


async def get_or_create_scoring_profile(
    session: AsyncSession,
    *,
    version_key: str,
    name: str,
    weights: dict[str, float],
    formula_expression: str,
) -> ScoringProfile:
    existing = await session.scalar(
        select(ScoringProfile).where(ScoringProfile.version_key == version_key)
    )
    if existing is not None:
        return existing
    profile = ScoringProfile(
        version_key=version_key,
        name=name,
        weights=weights,
        formula_expression=formula_expression,
        status="published",
        published_at=datetime.now(),
    )
    session.add(profile)
    await session.flush()
    return profile
