"""DB access for the canonical feedback domain. architecture.md §8.4."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.feedback.models import (
    FeedbackDuplicateLink,
    FeedbackQualityEvent,
    FeedbackRecord,
    FeedbackRedaction,
    QualityEventSeverity,
    QualityStatus,
    RelevanceStatus,
)
from instamart_engine.feedback.privacy import RedactionEvent
from instamart_engine.ingestion.models import RawRecordType, RawSourceItem


async def get_unprocessed_raw_source_items(
    session: AsyncSession, *, source_connector_id: UUID | None = None, limit: int = 200
) -> list[RawSourceItem]:
    """Raw items with no canonical feedback_record yet (datamodel.md §12's
    `UNIQUE (raw_source_item_id)` is what makes "unprocessed" well-defined)."""
    already_processed = select(FeedbackRecord.raw_source_item_id)
    stmt = select(RawSourceItem).where(RawSourceItem.id.not_in(already_processed))
    if source_connector_id is not None:
        stmt = stmt.where(RawSourceItem.source_connector_id == source_connector_id)
    stmt = stmt.order_by(RawSourceItem.created_at).limit(limit)
    return list((await session.scalars(stmt)).all())


async def get_recent_primary_texts(
    session: AsyncSession, *, source_connector_id: UUID, limit: int = 500
) -> list[tuple[UUID, str]]:
    """Bounded candidate set for lexical near-duplicate comparison
    (DUP-004/EMB-012 note — full-corpus comparison is Phase 3's job once
    embeddings exist)."""
    stmt = (
        select(FeedbackRecord.id, FeedbackRecord.normalized_text)
        .where(
            FeedbackRecord.source_connector_id == source_connector_id,
            FeedbackRecord.is_primary_for_counts.is_(True),
            FeedbackRecord.deleted_at.is_(None),
        )
        .order_by(FeedbackRecord.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def get_feedback_record_by_content_hash(
    session: AsyncSession, *, content_hash: str
) -> FeedbackRecord | None:
    """Exact-duplicate lookup, deliberately not scoped to one connector —
    the same text appearing in a different source is DUP-002
    (cross-source repost), not just an in-source exact duplicate."""
    return await session.scalar(
        select(FeedbackRecord)
        .where(
            FeedbackRecord.content_hash == content_hash,
            FeedbackRecord.deleted_at.is_(None),
        )
        .order_by(FeedbackRecord.created_at)
        .limit(1)
    )


async def get_distinct_source_connector_count(session: AsyncSession) -> int:
    """How many source connectors have contributed at least one
    feedback_record — the denominator theme source-breadth scoring needs to
    tell "one source" from "genuinely cross-platform" (metrics.py's
    `total_source_connectors`, previously always defaulted to 1)."""
    count = await session.scalar(
        select(func.count(func.distinct(FeedbackRecord.source_connector_id))).where(
            FeedbackRecord.deleted_at.is_(None)
        )
    )
    return count or 0


async def insert_feedback_record(
    session: AsyncSession,
    *,
    raw_source_item_id: UUID,
    source_connector_id: UUID,
    record_type: RawRecordType,
    source_url: str | None,
    published_at: datetime | None,
    ingested_at: datetime,
    original_title: str | None,
    original_text: str,
    normalized_text: str,
    redacted_text: str,
    language_code: str | None,
    language_confidence: float | None,
    is_code_mixed: bool,
    content_hash: str,
    rating_normalized: float | None,
    engagement_count: int | None,
    country_code: str | None,
    app_version: str | None,
    relevance_status: RelevanceStatus,
    quality_status: QualityStatus,
    is_primary_for_counts: bool,
    media_url: str | None = None,
    media_type: str | None = None,
) -> FeedbackRecord:
    from instamart_engine.feedback.models import FeedbackProcessingStatus

    record = FeedbackRecord(
        raw_source_item_id=raw_source_item_id,
        source_connector_id=source_connector_id,
        record_type=record_type,
        source_url=source_url,
        published_at=published_at,
        ingested_at=ingested_at,
        original_title=original_title,
        original_text=original_text,
        normalized_text=normalized_text,
        redacted_text=redacted_text,
        language_code=language_code,
        language_confidence=language_confidence,
        is_code_mixed=is_code_mixed,
        content_hash=content_hash,
        normalized_length=len(normalized_text),
        rating_normalized=rating_normalized,
        engagement_count=engagement_count,
        country_code=country_code,
        app_version=app_version,
        relevance_status=relevance_status,
        quality_status=quality_status,
        processing_status=FeedbackProcessingStatus.DEDUPLICATED,
        is_primary_for_counts=is_primary_for_counts,
        media_url=media_url,
        media_type=media_type,
    )
    session.add(record)
    await session.flush()
    return record


async def get_feedback_records_pending_media_extraction(
    session: AsyncSession, *, source_connector_id: UUID | None = None, limit: int = 50
) -> list[FeedbackRecord]:
    """Records with a captured media URL that haven't been through OCR/STT
    yet. `extracted_media_text` is set to `""` (not left NULL) on extraction
    failure — see `feedback/media_extraction.py` — specifically so failed
    records aren't picked up here forever."""
    stmt = select(FeedbackRecord).where(
        FeedbackRecord.media_url.is_not(None),
        FeedbackRecord.extracted_media_text.is_(None),
        FeedbackRecord.deleted_at.is_(None),
    )
    if source_connector_id is not None:
        stmt = stmt.where(FeedbackRecord.source_connector_id == source_connector_id)
    stmt = stmt.order_by(FeedbackRecord.created_at).limit(limit)
    return list((await session.scalars(stmt)).all())


async def update_feedback_record_media_extraction(
    session: AsyncSession,
    *,
    record: FeedbackRecord,
    extracted_media_text: str,
    normalized_text: str,
    redacted_text: str,
    quality_status: QualityStatus | None = None,
    relevance_status: RelevanceStatus | None = None,
) -> FeedbackRecord:
    """Persists OCR/transcript output folded into the record's text, plus
    any quality/relevance re-assessment that changed as a result (a
    media-only post with a thin caption may have been marked
    LOW_INFORMATION before extraction ran)."""
    record.extracted_media_text = extracted_media_text
    record.normalized_text = normalized_text
    record.redacted_text = redacted_text
    record.normalized_length = len(normalized_text)
    if quality_status is not None:
        record.quality_status = quality_status
    if relevance_status is not None:
        record.relevance_status = relevance_status
    await session.flush()
    return record


async def mark_feedback_record_media_extraction_failed(
    session: AsyncSession, *, record: FeedbackRecord
) -> FeedbackRecord:
    """Sets the `""` (not NULL) sentinel so a permanently-failing download/
    OCR/transcription isn't retried on every future run — leaves
    normalized_text/redacted_text untouched since there's no new content to
    fold in."""
    record.extracted_media_text = ""
    await session.flush()
    return record


async def insert_redaction_events(
    session: AsyncSession, *, feedback_record_id: UUID, events: list[RedactionEvent]
) -> None:
    from instamart_engine.feedback.privacy import REDACTION_DETECTOR_VERSION

    for event in events:
        session.add(
            FeedbackRedaction(
                feedback_record_id=feedback_record_id,
                redaction_type=event.redaction_type,
                start_offset_original=event.start_offset,
                end_offset_original=event.end_offset,
                replacement_token=event.replacement_token,
                detector="rule",
                detector_version=REDACTION_DETECTOR_VERSION,
                confidence=event.confidence,
            )
        )
    if events:
        await session.flush()


async def insert_quality_event(
    session: AsyncSession,
    *,
    feedback_record_id: UUID,
    event_type: str,
    severity: QualityEventSeverity,
    stage: str,
    message: str,
    details: dict | None = None,
) -> FeedbackQualityEvent:
    event = FeedbackQualityEvent(
        feedback_record_id=feedback_record_id,
        event_type=event_type,
        severity=severity,
        stage=stage,
        message=message,
        details=details or {},
    )
    session.add(event)
    await session.flush()
    return event


async def insert_duplicate_link(
    session: AsyncSession,
    *,
    canonical_feedback_record_id: UUID,
    duplicate_feedback_record_id: UUID,
    duplicate_type: str,
    lexical_similarity: float | None,
    decision_method: str,
    decision_version: str,
) -> FeedbackDuplicateLink:
    link = FeedbackDuplicateLink(
        canonical_feedback_record_id=canonical_feedback_record_id,
        duplicate_feedback_record_id=duplicate_feedback_record_id,
        duplicate_type=duplicate_type,
        lexical_similarity=lexical_similarity,
        decision_method=decision_method,
        decision_version=decision_version,
    )
    session.add(link)
    await session.flush()
    return link
