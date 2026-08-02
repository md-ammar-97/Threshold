"""Minimal read-only themes endpoints for the Phase 7 Themes surface
(design.md §28-29). architecture.md §20.4 describes a fuller theme/insight
management API; only list + detail are implemented here."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.api.schemas.themes import (
    EvidencePreviewResponse,
    ThemeDetailResponse,
    ThemeListResponse,
    ThemeSummaryResponse,
    ThemeTagResponse,
)
from instamart_engine.core.database import get_db_session
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.sources.models import SourceConnectorModel
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import Theme

router = APIRouter(prefix="/api/v1/themes", tags=["themes"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

EXCERPT_MAX_CHARS = 240
# Themes can have members classified under up to 9 taxonomy dimensions;
# capped so a single theme's tag list stays scannable rather than dumping
# every dimension x label combination that appears even once.
MAX_TAGS_PER_THEME = 20


def _to_summary(
    theme: Theme, tags: list[theme_repo.ThemeTaxonomyLabel] | None = None
) -> ThemeSummaryResponse:
    return ThemeSummaryResponse(
        id=theme.id,
        theme_key=theme.theme_key,
        name=theme.name,
        theme_type=theme.theme_type.value,
        short_summary=theme.short_summary,
        representative_record_count=theme.representative_record_count,
        confidence_score=(
            float(theme.confidence_score) if theme.confidence_score is not None else None
        ),
        opportunity_score=(
            float(theme.opportunity_score) if theme.opportunity_score is not None else None
        ),
        tags=[
            ThemeTagResponse(
                dimension_key=tag.dimension_key,
                dimension_display_name=tag.dimension_display_name,
                label_key=tag.label_key,
                label_display_name=tag.label_display_name,
                record_count=tag.record_count,
            )
            for tag in (tags or [])[:MAX_TAGS_PER_THEME]
        ],
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


def _to_preview(record: FeedbackRecord, source_keys: dict[UUID, str]) -> EvidencePreviewResponse:
    return EvidencePreviewResponse(
        id=record.id,
        excerpt=record.redacted_text[:EXCERPT_MAX_CHARS],
        source_connector_key=source_keys.get(record.source_connector_id, "unknown"),
        published_at=record.published_at.isoformat() if record.published_at else None,
    )


@router.get("", response_model=ThemeListResponse)
async def list_themes(session: DbSession) -> ThemeListResponse:
    theme_set = await theme_repo.get_latest_theme_set(session)
    if theme_set is None:
        return ThemeListResponse(
            theme_set_id=None, theme_set_status=None, analysis_run_id=None, themes=[]
        )

    themes = await theme_repo.get_themes_for_set(session, theme_set_id=theme_set.id)
    ranked = sorted(
        themes,
        key=lambda t: float(t.opportunity_score) if t.opportunity_score is not None else -1.0,
        reverse=True,
    )
    tags_by_theme = await theme_repo.get_taxonomy_labels_for_themes(
        session, theme_ids=[theme.id for theme in ranked]
    )
    return ThemeListResponse(
        theme_set_id=theme_set.id,
        theme_set_status=theme_set.status.value,
        analysis_run_id=theme_set.analysis_run_id,
        themes=[_to_summary(theme, tags_by_theme.get(theme.id)) for theme in ranked],
    )


@router.get("/{theme_id}", response_model=ThemeDetailResponse)
async def get_theme(theme_id: UUID, session: DbSession) -> ThemeDetailResponse:
    theme = await session.get(Theme, theme_id)
    if theme is None:
        raise HTTPException(status_code=404, detail="theme not found")

    representatives, counterexample = await theme_repo.get_theme_evidence(
        session, theme_id=theme.id
    )
    records = list(representatives) + ([counterexample] if counterexample else [])
    source_keys = await _source_keys_for(session, records)
    tags_by_theme = await theme_repo.get_taxonomy_labels_for_themes(
        session, theme_ids=[theme.id]
    )

    return ThemeDetailResponse(
        **_to_summary(theme, tags_by_theme.get(theme.id)).model_dump(),
        long_summary=theme.long_summary,
        theme_set_id=theme.theme_set_id,
        representative_evidence=[_to_preview(r, source_keys) for r in representatives],
        counterexample=_to_preview(counterexample, source_keys) if counterexample else None,
    )
