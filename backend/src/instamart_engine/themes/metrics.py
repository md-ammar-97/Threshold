"""Deterministic theme metrics and opportunity scoring. architecture.md §15.4,
§16.4. Every input here comes from stored data or simple, documented
heuristics — never from an LLM (architecture.md §3.2).

`discovery_relevance` and `actionability` are the two components without an
objective ground truth in Phase 3 (no dedicated classifier exists yet); they
use an explicit, documented heuristic keyed off `theme_type` rather than
being silently guessed by the synthesis model. Refining them is expected
(context.md §18 Phase 2/3 iteration note) — the point here is that they are
*deterministic and visible*, matching architecture.md §14 "component values
must remain visible", not that they are already well-calibrated.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import FeedbackAnalysis
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import ThemeMembership, ThemeSet, ThemeType

METRICS_CALCULATION_VERSION = "v1"
SCORING_PROFILE_VERSION = "default-v1"
RECENCY_WINDOW_DAYS = 90
DEFAULT_SEVERITY_WHEN_UNCLASSIFIED = 2.0  # midpoint of the 0-5 scale

DEFAULT_WEIGHTS = {
    "frequency": 0.25,
    "severity": 0.20,
    "recency": 0.10,
    "source_breadth": 0.15,
    "confidence": 0.10,
    "discovery_relevance": 0.10,
    "actionability": 0.10,
}

# Heuristic: does this theme_type inherently bear on category exploration
# behaviour (the research brief's central question), vs. general service
# quality? See module docstring.
_HIGH_DISCOVERY_RELEVANCE_TYPES = {
    ThemeType.REPEAT_CATEGORY_DRIVER,
    ThemeType.EXPLORATION_BARRIER,
    ThemeType.DISCOVERY_MECHANISM,
    ThemeType.HABIT_SIGNAL,
    ThemeType.EXPERIMENTATION_SIGNAL,
    ThemeType.UNMET_NEED,
    ThemeType.INFORMATION_NEED,
}


@dataclass(frozen=True, slots=True)
class ThemeMetricsResult:
    theme_id: UUID
    record_count: int
    opportunity_score: float


async def _get_theme_records_and_memberships(
    session: AsyncSession, *, theme_id: UUID
) -> list[tuple[FeedbackRecord, ThemeMembership]]:
    stmt = (
        select(FeedbackRecord, ThemeMembership)
        .join(ThemeMembership, ThemeMembership.feedback_record_id == FeedbackRecord.id)
        .where(ThemeMembership.theme_id == theme_id)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def _average_severity(
    session: AsyncSession, *, feedback_record_ids: list[UUID]
) -> float | None:
    if not feedback_record_ids:
        return None
    stmt = select(FeedbackAnalysis.severity_value).where(
        FeedbackAnalysis.feedback_record_id.in_(feedback_record_ids),
        FeedbackAnalysis.severity_value.isnot(None),
    )
    values = [row[0] for row in (await session.execute(stmt)).all()]
    if not values:
        return None
    return sum(float(v) for v in values) / len(values)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


async def compute_theme_metrics_and_scores(
    session: AsyncSession, *, theme_set_id: UUID, total_source_connectors: int = 1
) -> list[ThemeMetricsResult]:
    theme_set = await session.get(ThemeSet, theme_set_id)
    if theme_set is None:
        raise ValueError(f"theme_set {theme_set_id} not found")

    scoring_profile = await theme_repo.get_or_create_scoring_profile(
        session,
        version_key=SCORING_PROFILE_VERSION,
        name="Default Opportunity Scoring",
        weights=DEFAULT_WEIGHTS,
        formula_expression="weighted sum of normalized components (see DEFAULT_WEIGHTS)",
    )
    await session.commit()

    themes = await theme_repo.get_themes_for_set(session, theme_set_id=theme_set_id)
    results: list[ThemeMetricsResult] = []
    now = datetime.now(UTC)
    recency_cutoff = now - timedelta(days=RECENCY_WINDOW_DAYS)

    for theme in themes:
        records_and_memberships = await _get_theme_records_and_memberships(
            session, theme_id=theme.id
        )
        records = [record for record, _ in records_and_memberships]
        memberships = [membership for _, membership in records_and_memberships]
        record_count = len(records)

        record_share = (
            record_count / theme_set.eligible_record_count
            if theme_set.eligible_record_count
            else 0.0
        )
        source_ids = {record.source_connector_id for record in records}
        source_breadth = len(source_ids)
        source_breadth_normalized = _clamp01(source_breadth / max(1, total_source_connectors))

        recent_count = sum(
            1 for record in records if record.published_at and record.published_at >= recency_cutoff
        )
        recency_share = recent_count / record_count if record_count else 0.0

        avg_severity = await _average_severity(
            session, feedback_record_ids=[record.id for record in records]
        )
        severity_normalized = (
            _clamp01(avg_severity / 5.0)
            if avg_severity is not None
            else _clamp01(DEFAULT_SEVERITY_WHEN_UNCLASSIFIED / 5.0)
        )

        coherence_score = (
            sum(float(m.membership_score) for m in memberships) / len(memberships)
            if memberships
            else None
        )
        confidence_score = (
            float(theme.confidence_score) if theme.confidence_score is not None else 0.5
        )

        discovery_relevance_score = (
            0.9 if theme.theme_type in _HIGH_DISCOVERY_RELEVANCE_TYPES else 0.5
        )
        # Heuristic: themes with both clear representative evidence and an
        # acknowledged counterexample are more "actionable" (the pattern is
        # legible enough to design around) than single-note clusters.
        has_counterexample = any(m.is_counterexample for m in memberships)
        actionability_score = _clamp01(
            0.5 + (0.2 if has_counterexample else 0.0) + (0.2 * (coherence_score or 0.0))
        )

        components = {
            "frequency": _clamp01(record_share),
            "severity": severity_normalized,
            "recency": _clamp01(recency_share),
            "source_breadth": source_breadth_normalized,
            "confidence": _clamp01(confidence_score),
            "discovery_relevance": discovery_relevance_score,
            "actionability": actionability_score,
        }
        weights = scoring_profile.weights
        opportunity_score = sum(components[key] * weights[key] for key in components) * 100

        for metric_key, numeric_value in (
            ("record_count", float(record_count)),
            ("record_share", record_share),
            ("source_breadth", float(source_breadth)),
            ("coherence_score", coherence_score),
            ("opportunity_score", opportunity_score),
        ):
            if numeric_value is None:
                continue
            await theme_repo.set_theme_metric(
                session,
                theme_id=theme.id,
                metric_key=metric_key,
                calculation_version=METRICS_CALCULATION_VERSION,
                numeric_value=numeric_value,
            )
        await theme_repo.set_theme_metric(
            session,
            theme_id=theme.id,
            metric_key="source_distribution",
            calculation_version=METRICS_CALCULATION_VERSION,
            json_value={str(sid): None for sid in source_ids},
        )

        await theme_repo.update_theme_scores(
            session,
            theme=theme,
            discovery_relevance_score=discovery_relevance_score,
            actionability_score=actionability_score,
            coherence_score=coherence_score,
            opportunity_score=opportunity_score,
            score_components=components,
        )
        await session.commit()

        results.append(
            ThemeMetricsResult(
                theme_id=theme.id, record_count=record_count, opportunity_score=opportunity_score
            )
        )

    return results
