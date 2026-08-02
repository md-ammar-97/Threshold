"""Minimal read-only evidence endpoints for the Phase 7 Evidence surface
(design.md §31). architecture.md §20.5 describes a fuller evidence API;
only list + detail (with basic source/keyword filters) are implemented
here."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.api.schemas.evidence import (
    EvidenceDetailResponse,
    EvidenceListResponse,
    EvidenceRowResponse,
    EvidenceSourceOption,
    EvidenceSourcesResponse,
)
from instamart_engine.core.database import get_db_session
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.sources.models import SourceConnectorModel

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

EXCERPT_MAX_CHARS = 240
DEFAULT_LIMIT = 25


def _to_row(record: FeedbackRecord, source_key: str) -> EvidenceRowResponse:
    return EvidenceRowResponse(
        id=record.id,
        excerpt=record.redacted_text[:EXCERPT_MAX_CHARS],
        source_connector_key=source_key,
        record_type=record.record_type.value,
        published_at=record.published_at.isoformat() if record.published_at else None,
        rating_normalized=(
            float(record.rating_normalized) if record.rating_normalized is not None else None
        ),
        relevance_status=record.relevance_status.value,
        quality_status=record.quality_status.value,
    )


@router.get("", response_model=EvidenceListResponse)
async def list_evidence(
    session: DbSession,
    source_connector_key: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EvidenceListResponse:
    stmt = select(FeedbackRecord).where(FeedbackRecord.deleted_at.is_(None))
    count_stmt = (
        select(func.count()).select_from(FeedbackRecord).where(FeedbackRecord.deleted_at.is_(None))
    )

    if source_connector_key:
        connector = await session.scalar(
            select(SourceConnectorModel).where(SourceConnectorModel.key == source_connector_key)
        )
        if connector is None:
            return EvidenceListResponse(total_matching=0, limit=limit, offset=offset, records=[])
        stmt = stmt.where(FeedbackRecord.source_connector_id == connector.id)
        count_stmt = count_stmt.where(FeedbackRecord.source_connector_id == connector.id)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(FeedbackRecord.redacted_text.ilike(pattern))
        count_stmt = count_stmt.where(FeedbackRecord.redacted_text.ilike(pattern))

    total_matching = await session.scalar(count_stmt) or 0
    records = (
        await session.scalars(
            stmt.order_by(FeedbackRecord.published_at.desc().nulls_last()).limit(limit).offset(offset)
        )
    ).all()

    connector_ids = {record.source_connector_id for record in records}
    source_keys: dict[UUID, str] = {}
    if connector_ids:
        rows = await session.execute(
            select(SourceConnectorModel.id, SourceConnectorModel.key).where(
                SourceConnectorModel.id.in_(connector_ids)
            )
        )
        source_keys = {row[0]: row[1] for row in rows.all()}

    return EvidenceListResponse(
        total_matching=total_matching,
        limit=limit,
        offset=offset,
        records=[
            _to_row(record, source_keys.get(record.source_connector_id, "unknown"))
            for record in records
        ],
    )


@router.get("/sources", response_model=EvidenceSourcesResponse)
async def list_evidence_sources(session: DbSession) -> EvidenceSourcesResponse:
    """Only sources with at least one (non-deleted) feedback record — keeps
    the filter free of connectors that are registered but have no evidence
    to show yet."""
    rows = await session.execute(
        select(SourceConnectorModel.key, SourceConnectorModel.display_name)
        .join(FeedbackRecord, FeedbackRecord.source_connector_id == SourceConnectorModel.id)
        .where(FeedbackRecord.deleted_at.is_(None))
        .distinct()
        .order_by(SourceConnectorModel.display_name)
    )
    return EvidenceSourcesResponse(
        sources=[EvidenceSourceOption(key=row.key, display_name=row.display_name) for row in rows]
    )


@router.get("/{record_id}", response_model=EvidenceDetailResponse)
async def get_evidence(record_id: UUID, session: DbSession) -> EvidenceDetailResponse:
    record = await session.get(FeedbackRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="feedback_record not found")

    connector = await session.get(SourceConnectorModel, record.source_connector_id)
    source_key = connector.key if connector else "unknown"

    return EvidenceDetailResponse(
        **_to_row(record, source_key).model_dump(),
        original_text=record.original_text,
        redacted_text=record.redacted_text,
        language_code=record.language_code,
        source_url=record.source_url,
    )
