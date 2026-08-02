"""Normalization pipeline orchestration: raw_source_item -> feedback_record.

architecture.md §11 order: normalize -> language detect -> privacy redact ->
relevance/quality assess -> dedup -> canonical record. Never silently drops
a record (edgecases.md §3.1) — every raw item gets exactly one
feedback_record, however low-confidence or duplicate.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.feedback import repository as repo
from instamart_engine.feedback.dedup import (
    DEDUP_DECISION_VERSION,
    compute_content_hash,
    find_near_duplicate,
)
from instamart_engine.feedback.language import detect_language
from instamart_engine.feedback.models import DuplicateType, QualityEventSeverity, QualityStatus
from instamart_engine.feedback.normalize import normalize_text
from instamart_engine.feedback.privacy import redact
from instamart_engine.feedback.relevance import assess_quality, assess_relevance
from instamart_engine.ingestion.models import RawSourceItem


@dataclass(frozen=True, slots=True)
class ProcessingSummary:
    processed: int
    marked_duplicate: int
    marked_malformed: int


def _normalized_rating(item: RawSourceItem) -> float | None:
    if item.rating is None or not item.rating_scale_max:
        return None
    return float(item.rating) / float(item.rating_scale_max)


async def _process_one(session: AsyncSession, item: RawSourceItem) -> tuple[UUID, bool, bool]:
    """Returns (feedback_record_id, was_duplicate, was_malformed)."""
    original_text = item.body or ""
    normalized = normalize_text(original_text)
    language_result = detect_language(normalized)
    redacted_text, redaction_events = redact(normalized)
    content_hash = compute_content_hash(normalized)

    relevance_status = assess_relevance(normalized)
    quality_status = assess_quality(
        original_text=original_text,
        normalized_text=normalized,
        language_code=language_result.language_code,
        is_code_mixed=language_result.is_code_mixed,
        is_supported_language=language_result.is_supported,
    )

    duplicate_of: UUID | None = None
    duplicate_type: DuplicateType | None = None
    similarity: float | None = None

    exact_match = await repo.get_feedback_record_by_content_hash(session, content_hash=content_hash)
    if exact_match is not None:
        duplicate_of = exact_match.id
        duplicate_type = (
            DuplicateType.EXACT
            if exact_match.source_connector_id == item.source_connector_id
            else DuplicateType.CROSS_SOURCE_REPOST
        )
        similarity = 1.0
    else:
        candidates = await repo.get_recent_primary_texts(
            session, source_connector_id=item.source_connector_id
        )
        near = find_near_duplicate(normalized, candidates)
        if near is not None:
            duplicate_of, similarity = near
            duplicate_type = DuplicateType.NEAR_DUPLICATE

    source_metadata = item.source_metadata or {}

    record = await repo.insert_feedback_record(
        session,
        raw_source_item_id=item.id,
        source_connector_id=item.source_connector_id,
        record_type=item.record_type,
        source_url=item.source_url,
        published_at=item.published_at,
        ingested_at=datetime.now(UTC),
        original_title=item.title,
        original_text=original_text,
        normalized_text=normalized,
        redacted_text=redacted_text,
        language_code=language_result.language_code,
        language_confidence=language_result.confidence,
        is_code_mixed=language_result.is_code_mixed,
        content_hash=content_hash,
        rating_normalized=_normalized_rating(item),
        engagement_count=item.engagement_count,
        country_code=item.country_code,
        app_version=item.app_version,
        relevance_status=relevance_status,
        quality_status=quality_status,
        is_primary_for_counts=duplicate_of is None,
        media_url=source_metadata.get("media_url"),
        media_type=source_metadata.get("media_type"),
    )

    if redaction_events:
        await repo.insert_redaction_events(
            session, feedback_record_id=record.id, events=redaction_events
        )

    was_malformed = quality_status == QualityStatus.MALFORMED
    if was_malformed:
        await repo.insert_quality_event(
            session,
            feedback_record_id=record.id,
            event_type="normalization_produced_empty_text",
            severity=QualityEventSeverity.WARNING,
            stage="normalization",
            message="Original text was non-empty but normalization produced no usable text.",
        )

    was_duplicate = duplicate_of is not None
    if duplicate_of is not None and duplicate_type is not None:
        await repo.insert_duplicate_link(
            session,
            canonical_feedback_record_id=duplicate_of,
            duplicate_feedback_record_id=record.id,
            duplicate_type=duplicate_type.value,
            lexical_similarity=similarity,
            decision_method="rule",
            decision_version=DEDUP_DECISION_VERSION,
        )

    return record.id, was_duplicate, was_malformed


async def process_unprocessed_items(
    session: AsyncSession, *, source_connector_id: UUID | None = None, limit: int = 200
) -> ProcessingSummary:
    items = await repo.get_unprocessed_raw_source_items(
        session, source_connector_id=source_connector_id, limit=limit
    )

    processed = 0
    marked_duplicate = 0
    marked_malformed = 0

    for item in items:
        _record_id, was_duplicate, was_malformed = await _process_one(session, item)
        await session.commit()
        processed += 1
        marked_duplicate += int(was_duplicate)
        marked_malformed += int(was_malformed)

    return ProcessingSummary(
        processed=processed, marked_duplicate=marked_duplicate, marked_malformed=marked_malformed
    )
