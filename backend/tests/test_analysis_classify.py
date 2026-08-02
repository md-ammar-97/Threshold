"""Integration test for the classification service against the live
Postgres. The Groq/OpenRouter (openai-SDK-shaped) client is mocked;
everything else (taxonomy load, prompt/model registration, dynamic schema,
persistence) is real.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from instamart_engine.ai.gateway import AIGateway
from instamart_engine.analysis.classify import classify_unclassified_records
from instamart_engine.analysis.models import AnalysisLabel, FeedbackAnalysis
from instamart_engine.analysis.schemas import build_classification_output_model
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.taxonomy.repository import get_dimensions_with_labels, get_published_taxonomy
from instamart_engine.taxonomy.seed_v1 import load_taxonomy_v1

pytestmark = pytest.mark.asyncio


class _FakeUsage:
    prompt_tokens = 20
    completion_tokens = 15


class _FakeMessage:
    def __init__(self, parsed_output) -> None:
        self.parsed = parsed_output
        self.refusal = None


class _FakeChoice:
    def __init__(self, parsed_output) -> None:
        self.message = _FakeMessage(parsed_output)
        self.finish_reason = "stop"


class _FakeResponse:
    def __init__(self, parsed_output) -> None:
        self.choices = [_FakeChoice(parsed_output)]
        self.model = "groq-test"
        self.id = "chatcmpl_test"
        self.usage = _FakeUsage()


async def _seed_feedback_record(db_session, *, body: str) -> FeedbackRecord:
    connector = SourceConnectorModel(
        key=f"test-classify-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    artifact = RawArtifact(
        ingestion_run_id=uuid.uuid4(),
        storage_backend="filesystem",
        storage_key=f"raw/test/{uuid.uuid4()}.json",
        media_type="application/json",
        byte_size=len(body),
        sha256="0" * 64,
        captured_at=datetime.now(UTC),
    )
    db_session.add(artifact)
    await db_session.flush()

    raw_item = RawSourceItem(
        raw_artifact_id=artifact.id,
        ingestion_run_id=artifact.ingestion_run_id,
        source_connector_id=connector.id,
        external_id=str(uuid.uuid4()),
        record_type="app_review",
        body=body,
        payload_checksum="1" * 64,
    )
    db_session.add(raw_item)
    await db_session.flush()

    record = FeedbackRecord(
        raw_source_item_id=raw_item.id,
        source_connector_id=connector.id,
        record_type="app_review",
        ingested_at=datetime.now(UTC),
        original_text=body,
        normalized_text=body,
        redacted_text=body,
        content_hash=str(uuid.uuid4()),
        normalized_length=len(body),
        relevance_status=RelevanceStatus.UNREVIEWED,
        quality_status=QualityStatus.USABLE,
    )
    db_session.add(record)
    await db_session.flush()
    return record


async def test_classify_unclassified_records_persists_labels_and_evidence(db_session) -> None:
    await load_taxonomy_v1(db_session)
    record = await _seed_feedback_record(
        db_session,
        body="I could not find any information about product freshness before buying, "
        "so I did not try the new vegetable category.",
    )
    connector_id = record.source_connector_id

    taxonomy_version = await get_published_taxonomy(db_session)
    dimensions = await get_dimensions_with_labels(
        db_session, taxonomy_version_id=taxonomy_version.id
    )
    output_model = build_classification_output_model(dimensions)

    fake_output = output_model.model_validate(
        {
            "sentiment_label": "negative",
            "sentiment_score": -0.4,
            "sentiment_confidence": 0.8,
            "severity_value": 1,
            "severity_confidence": 0.7,
            "summary": "User avoided a new category due to lack of freshness information.",
            "overall_confidence": 0.7,
            "exploration_barrier": [
                {
                    "label": "insufficient_information",
                    "confidence": 0.85,
                    "evidence_excerpt": "could not find any information about product freshness",
                }
            ],
        }
    )

    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(fake_output))
    gateway = AIGateway(client=fake_client)

    summary = await classify_unclassified_records(
        db_session, limit=10, gateway=gateway, source_connector_id=connector_id
    )

    assert summary.selected == 1
    assert summary.classified == 1
    assert summary.failed == 0

    analysis = await db_session.scalar(
        select(FeedbackAnalysis).where(FeedbackAnalysis.feedback_record_id == record.id)
    )
    assert analysis is not None
    assert analysis.sentiment_score is not None
    assert float(analysis.sentiment_score) == pytest.approx(-0.4)

    labels = (
        await db_session.scalars(
            select(AnalysisLabel).where(AnalysisLabel.feedback_analysis_id == analysis.id)
        )
    ).all()
    assert len(labels) == 1


async def test_classify_unclassified_records_is_idempotent(db_session) -> None:
    await load_taxonomy_v1(db_session)
    record = await _seed_feedback_record(db_session, body="Delivery was late again this week.")
    connector_id = record.source_connector_id

    taxonomy_version = await get_published_taxonomy(db_session)
    dimensions = await get_dimensions_with_labels(
        db_session, taxonomy_version_id=taxonomy_version.id
    )
    output_model = build_classification_output_model(dimensions)
    fake_output = output_model.model_validate(
        {
            "sentiment_label": "negative",
            "sentiment_score": -0.3,
            "sentiment_confidence": 0.7,
            "severity_value": 1,
            "severity_confidence": 0.6,
            "summary": "Delivery delay reported.",
            "overall_confidence": 0.6,
        }
    )
    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(fake_output))
    gateway = AIGateway(client=fake_client)

    first = await classify_unclassified_records(
        db_session, limit=10, gateway=gateway, source_connector_id=connector_id
    )
    second = await classify_unclassified_records(
        db_session, limit=10, gateway=gateway, source_connector_id=connector_id
    )

    assert first.classified == 1
    assert second.selected == 0  # nothing left unclassified
