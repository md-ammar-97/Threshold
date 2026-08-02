"""Resolves an immutable evidence snapshot for a report evidence link at
link time (datamodel.md §66 report lineage — later edits to the draft
theme/insight must not silently change a published export)."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.insights.models import Insight
from instamart_engine.reports.models import ReportEvidenceType
from instamart_engine.research.models import GeneratedAnswer
from instamart_engine.themes.models import Theme, ThemeMetric

_EXCERPT_MAX_CHARS = 500


async def resolve_evidence_snapshot(
    session: AsyncSession, *, object_type: ReportEvidenceType, object_id: UUID
) -> dict[str, Any] | None:
    """Returns None if the referenced object doesn't exist — the caller
    must treat that as "cannot link this evidence," not silently link an
    empty snapshot."""
    if object_type == ReportEvidenceType.FEEDBACK_RECORD:
        record = await session.get(FeedbackRecord, object_id)
        if record is None:
            return None
        return {
            "excerpt": record.redacted_text[:_EXCERPT_MAX_CHARS],
            "published_at": record.published_at.isoformat() if record.published_at else None,
        }

    if object_type == ReportEvidenceType.THEME:
        theme = await session.get(Theme, object_id)
        if theme is None:
            return None
        return {
            "name": theme.name,
            "short_summary": theme.short_summary,
            "theme_type": theme.theme_type.value,
        }

    if object_type == ReportEvidenceType.THEME_METRIC:
        metric = await session.get(ThemeMetric, object_id)
        if metric is None:
            return None
        return {
            "metric_key": metric.metric_key,
            "numeric_value": (
                float(metric.numeric_value) if metric.numeric_value is not None else None
            ),
            "text_value": metric.text_value,
        }

    if object_type == ReportEvidenceType.INSIGHT:
        insight = await session.get(Insight, object_id)
        if insight is None:
            return None
        return {
            "title": insight.title,
            "finding": insight.finding,
            "insight_type": insight.insight_type.value,
        }

    if object_type == ReportEvidenceType.GENERATED_ANSWER:
        answer = await session.get(GeneratedAnswer, object_id)
        if answer is None:
            return None
        return {
            "answer_text": answer.answer_text[:_EXCERPT_MAX_CHARS],
            "citation_count": answer.citation_count,
        }

    return None
