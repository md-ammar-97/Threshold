"""Integration tests for the feedback normalization pipeline against the
live Postgres (see conftest.py's `db_session` — rolled back after each test).
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from instamart_engine.feedback.models import (
    FeedbackDuplicateLink,
    FeedbackRecord,
    QualityStatus,
    RelevanceStatus,
)
from instamart_engine.feedback.pipeline import process_unprocessed_items
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel

pytestmark = pytest.mark.asyncio


async def _seed_raw_item(
    db_session, *, external_id: str, body: str, connector_key: str = "test_connector"
):
    connector = await db_session.scalar(
        select(SourceConnectorModel).where(SourceConnectorModel.key == connector_key)
    )
    if connector is None:
        connector = SourceConnectorModel(
            key=connector_key,
            display_name="Test Connector",
            connector_type=ConnectorType.LIBRARY,
            implementation_version="test",
        )
        db_session.add(connector)
        await db_session.flush()

    artifact = RawArtifact(
        ingestion_run_id=uuid.uuid4(),
        storage_backend="filesystem",
        storage_key=f"raw/test/{external_id}.json",
        media_type="application/json",
        byte_size=len(body),
        sha256="0" * 64,
        captured_at=datetime.now(UTC),
    )
    db_session.add(artifact)
    await db_session.flush()

    item = RawSourceItem(
        raw_artifact_id=artifact.id,
        ingestion_run_id=artifact.ingestion_run_id,
        source_connector_id=connector.id,
        external_id=external_id,
        record_type="app_review",
        body=body,
        payload_checksum="1" * 64,
    )
    db_session.add(item)
    await db_session.flush()
    return item, connector


async def test_pipeline_processes_item_into_feedback_record(db_session) -> None:
    item, _connector = await _seed_raw_item(
        db_session,
        external_id="item-1",
        body="The delivery was fast but I wish there were more product categories to explore.",
    )

    summary = await process_unprocessed_items(db_session)

    assert summary.processed == 1
    assert summary.marked_duplicate == 0

    record = await db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.raw_source_item_id == item.id)
    )
    assert record is not None
    assert record.relevance_status == RelevanceStatus.UNREVIEWED
    assert record.quality_status == QualityStatus.USABLE
    assert record.is_primary_for_counts is True
    assert "delivery" in record.normalized_text


async def test_pipeline_redacts_pii_and_stores_events(db_session) -> None:
    item, _connector = await _seed_raw_item(
        db_session,
        external_id="item-pii",
        body="Great app, contact me at jane.doe@example.com if you want details about this order.",
    )

    await process_unprocessed_items(db_session)

    record = await db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.raw_source_item_id == item.id)
    )
    assert record is not None
    assert "jane.doe@example.com" not in record.redacted_text
    assert "[EMAIL]" in record.redacted_text
    assert "jane.doe@example.com" in record.original_text  # original is untouched


async def test_pipeline_marks_exact_duplicate_across_two_items(db_session) -> None:
    body = "The app crashed twice today while I was placing an order for groceries."
    item1, _c = await _seed_raw_item(db_session, external_id="dup-1", body=body)
    item2, _c2 = await _seed_raw_item(db_session, external_id="dup-2", body=body)

    summary = await process_unprocessed_items(db_session)

    assert summary.processed == 2
    assert summary.marked_duplicate == 1

    record1 = await db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.raw_source_item_id == item1.id)
    )
    record2 = await db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.raw_source_item_id == item2.id)
    )
    assert record1.is_primary_for_counts is True
    assert record2.is_primary_for_counts is False

    link = await db_session.scalar(
        select(FeedbackDuplicateLink).where(
            FeedbackDuplicateLink.duplicate_feedback_record_id == record2.id
        )
    )
    assert link is not None
    assert link.canonical_feedback_record_id == record1.id
    assert link.duplicate_type == "exact"


async def test_pipeline_never_drops_empty_or_malformed_records(db_session) -> None:
    item, _connector = await _seed_raw_item(db_session, external_id="empty-1", body="   ")

    summary = await process_unprocessed_items(db_session)

    assert summary.processed == 1
    record = await db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.raw_source_item_id == item.id)
    )
    assert record is not None  # never silently discarded
    assert record.relevance_status == RelevanceStatus.INSUFFICIENT_CONTENT


async def test_process_unprocessed_items_is_idempotent_across_calls(db_session) -> None:
    await _seed_raw_item(db_session, external_id="idem-1", body="A perfectly ordinary review here.")

    first = await process_unprocessed_items(db_session)
    second = await process_unprocessed_items(db_session)

    assert first.processed == 1
    assert second.processed == 0  # nothing left unprocessed
