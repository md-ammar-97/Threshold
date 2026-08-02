"""Minimal read-only insights endpoints — mirrors `api/routes/themes.py`'s
exact shape (list + detail, nothing more). Insights were generated and
persisted by `insights/synthesize.py` since Phase 4 with no way for a user
to ever see one directly (audit-2026-07-31.md F-13/R-7) — only indirectly,
if `research/retrieval.py` happened to pull one into an Ask answer."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.api.schemas.insights import (
    InsightDetailResponse,
    InsightEvidencePreviewResponse,
    InsightListResponse,
    InsightSummaryResponse,
    InsightThemeLinkResponse,
)
from instamart_engine.core.database import get_db_session
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.insights import repository as insight_repo
from instamart_engine.insights.models import Insight
from instamart_engine.sources.models import SourceConnectorModel
from instamart_engine.themes.models import Theme

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

EXCERPT_MAX_CHARS = 240


def _to_summary(insight: Insight) -> InsightSummaryResponse:
    return InsightSummaryResponse(
        id=insight.id,
        insight_type=insight.insight_type.value,
        title=insight.title,
        finding=insight.finding,
        confidence_level=insight.confidence_level.value,
        confidence_score=(
            float(insight.confidence_score) if insight.confidence_score is not None else None
        ),
        opportunity_score=(
            float(insight.opportunity_score) if insight.opportunity_score is not None else None
        ),
    )


async def _source_keys_for(session: AsyncSession, records: list[FeedbackRecord]) -> dict[UUID, str]:
    connector_ids = {record.source_connector_id for record in records}
    if not connector_ids:
        return {}
    rows = await session.execute(
        select(SourceConnectorModel.id, SourceConnectorModel.key).where(
            SourceConnectorModel.id.in_(connector_ids)
        )
    )
    return {row[0]: row[1] for row in rows.all()}


@router.get("", response_model=InsightListResponse)
async def list_insights(session: DbSession) -> InsightListResponse:
    insight_set = await insight_repo.get_latest_insight_set(session)
    if insight_set is None:
        return InsightListResponse(
            insight_set_id=None, insight_set_status=None, theme_set_id=None,
            analysis_run_id=None, insights=[],
        )

    insights = await insight_repo.get_insights_for_set(session, insight_set_id=insight_set.id)
    return InsightListResponse(
        insight_set_id=insight_set.id,
        insight_set_status=insight_set.status.value,
        theme_set_id=insight_set.theme_set_id,
        analysis_run_id=insight_set.analysis_run_id,
        insights=[_to_summary(insight) for insight in insights],
    )


@router.get("/{insight_id}", response_model=InsightDetailResponse)
async def get_insight(insight_id: UUID, session: DbSession) -> InsightDetailResponse:
    insight = await insight_repo.get_insight_by_id(session, insight_id=insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="insight not found")

    theme_links = await insight_repo.get_insight_themes(session, insight_id=insight.id)
    theme_ids = [link.theme_id for link in theme_links]
    themes_by_id: dict[UUID, Theme] = {}
    if theme_ids:
        rows = await session.scalars(select(Theme).where(Theme.id.in_(theme_ids)))
        themes_by_id = {theme.id: theme for theme in rows.all()}

    evidence_links = await insight_repo.get_insight_evidence(session, insight_id=insight.id)
    record_ids = [link.feedback_record_id for link in evidence_links]
    records_by_id: dict[UUID, FeedbackRecord] = {}
    if record_ids:
        record_rows = await session.scalars(
            select(FeedbackRecord).where(FeedbackRecord.id.in_(record_ids))
        )
        records_by_id = {record.id: record for record in record_rows.all()}
    source_keys = await _source_keys_for(session, list(records_by_id.values()))

    return InsightDetailResponse(
        **_to_summary(insight).model_dump(),
        interpretation=insight.interpretation,
        affected_context=insight.affected_context,
        product_implication=insight.product_implication,
        validation_recommendation=insight.validation_recommendation,
        insight_set_id=insight.insight_set_id,
        themes=[
            InsightThemeLinkResponse(
                theme_id=link.theme_id,
                theme_name=(
                    themes_by_id[link.theme_id].name if link.theme_id in themes_by_id else "unknown"
                ),
                relationship_type=link.relationship_type.value,
            )
            for link in theme_links
        ],
        evidence=[
            InsightEvidencePreviewResponse(
                id=link.id,
                excerpt=(
                    records_by_id[link.feedback_record_id].redacted_text[:EXCERPT_MAX_CHARS]
                    if link.feedback_record_id in records_by_id
                    else link.excerpt_snapshot[:EXCERPT_MAX_CHARS]
                ),
                evidence_role=link.evidence_role.value,
                source_connector_key=(
                    source_keys.get(
                        records_by_id[link.feedback_record_id].source_connector_id, "unknown"
                    )
                    if link.feedback_record_id in records_by_id
                    else "unknown"
                ),
                published_at=(
                    published_at.isoformat()
                    if (record := records_by_id.get(link.feedback_record_id)) is not None
                    and (published_at := record.published_at) is not None
                    else None
                ),
            )
            for link in evidence_links
        ],
    )
