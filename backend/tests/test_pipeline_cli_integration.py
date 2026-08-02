"""End-to-end integration test over the real production orchestration path
(classify -> embed -> cluster -> retrieve), against the live Postgres, not
hand-built fixtures.

This is the test audit-2026-07-31.md's R-4 asks for: F-8 (clustering read a
hardcoded/wrong embedding configuration) and F-9/F-10 (classification and
clustering created two disconnected AnalysisRuns, so retrieval's
analysis_run-scoped join always matched zero rows) both passed a 180-test
suite because every existing fixture constructs the correct `AnalysisRun` /
`ThemeSet` / `FeedbackAnalysis` linkage by hand rather than letting the real
`scripts/pipeline.py`-style call sequence build it. This test drives
`classify_unclassified_records` -> `embed_unembedded_records` ->
`discover_themes` -> `_hybrid_record_candidates` exactly the way
`scripts/pipeline.py` does, under one shared `AnalysisRun`, and asserts
retrieval actually finds real records at the end — the thing F-9 broke.

The AI gateway (Groq/OpenRouter) is mocked, same as test_analysis_classify.py
— everything else (taxonomy load, embedding config resolution, real local
embeddings, real HDBSCAN clustering, real retrieval SQL) is real.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from instamart_engine.ai.gateway import AIGateway
from instamart_engine.analysis.classify import (
    classify_unclassified_records,
    ensure_classification_prompt_and_model,
)
from instamart_engine.analysis.embed import embed_unembedded_records
from instamart_engine.analysis.models import FeedbackAnalysis
from instamart_engine.analysis.repository import create_analysis_run
from instamart_engine.analysis.schemas import build_classification_output_model
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.research.retrieval import _hybrid_record_candidates
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.taxonomy.repository import get_dimensions_with_labels, get_published_taxonomy
from instamart_engine.taxonomy.seed_v2 import load_taxonomy_v2
from instamart_engine.themes.cluster import discover_themes
from instamart_engine.themes.models import ThemeSet

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


async def _seed_feedback_record(
    db_session, *, connector_id, body: str
) -> FeedbackRecord:
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
        source_connector_id=connector_id,
        external_id=str(uuid.uuid4()),
        record_type="app_review",
        body=body,
        payload_checksum="1" * 64,
    )
    db_session.add(raw_item)
    await db_session.flush()

    record = FeedbackRecord(
        raw_source_item_id=raw_item.id,
        source_connector_id=connector_id,
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


async def test_pipeline_shares_one_analysis_run_and_retrieval_finds_records(
    db_session,
) -> None:
    await load_taxonomy_v2(db_session)

    connector = SourceConnectorModel(
        key=f"test-pipeline-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    # 12 records, two semantically distinct clusters (delivery timing vs.
    # freshness information) — enough to clear MIN_RECORDS_FOR_CLUSTERING
    # and produce a real HDBSCAN cluster, not the small-data fallback.
    for i in range(6):
        await _seed_feedback_record(
            db_session,
            connector_id=connector.id,
            body=f"Delivery arrived very late again, order number {i}.",
        )
    for i in range(6):
        await _seed_feedback_record(
            db_session,
            connector_id=connector.id,
            body=f"I wish there was more information about product freshness, case {i}.",
        )
    await db_session.commit()

    taxonomy_version = await get_published_taxonomy(db_session)
    _prompt_version, model_configuration = await ensure_classification_prompt_and_model(db_session)
    await db_session.commit()

    dimensions = await get_dimensions_with_labels(
        db_session, taxonomy_version_id=taxonomy_version.id
    )
    primary_dimensions = [d for d in dimensions if d.key not in ("topic_main", "topic_sub")]
    output_model = build_classification_output_model(primary_dimensions)
    fake_output = output_model.model_validate(
        {
            "sentiment_label": "negative",
            "sentiment_score": -0.3,
            "sentiment_confidence": 0.7,
            "severity_value": 1,
            "severity_confidence": 0.6,
            "summary": "User reported a recurring service issue.",
            "overall_confidence": 0.6,
        }
    )
    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(fake_output))
    gateway = AIGateway(client=fake_client)

    # The one shared run — this is the actual fix under test. Everything
    # below is threaded through it exactly as scripts/pipeline.py does.
    analysis_run = await create_analysis_run(
        db_session,
        name="test-pipeline-run",
        taxonomy_version_id=taxonomy_version.id,
        classification_model_configuration_id=model_configuration.id,
        dataset_snapshot={},
    )
    await db_session.commit()

    classify_summary = await classify_unclassified_records(
        db_session,
        limit=20,
        gateway=gateway,
        source_connector_id=connector.id,
        analysis_run=analysis_run,
    )
    assert classify_summary.classified == 12

    embed_summary = await embed_unembedded_records(
        db_session, source_connector_id=connector.id, limit=20, provider="local"
    )
    assert embed_summary.embedded == 12

    cluster_summary = await discover_themes(
        db_session,
        analysis_run_id=analysis_run.id,
        source_connector_id=connector.id,
        min_cluster_size=3,
        provider="local",
    )
    assert cluster_summary.theme_count >= 1

    # The actual F-9 assertion: the theme set and every classification must
    # point at the SAME analysis_run — previously scripts/classify.py and
    # scripts/analyze.py always produced two different ones.
    theme_set = await db_session.get(ThemeSet, cluster_summary.theme_set_id)
    assert theme_set is not None
    assert theme_set.analysis_run_id == analysis_run.id

    analyses = (
        await db_session.scalars(
            select(FeedbackAnalysis).where(FeedbackAnalysis.analysis_run_id == analysis_run.id)
        )
    ).all()
    assert len(analyses) == 12

    # The actual F-9 regression check: retrieval scoped to this analysis_run
    # must find real records, not the empty list F-9 always returned.
    candidates = await _hybrid_record_candidates(
        db_session,
        analysis_run_id=analysis_run.id,
        question_text="delivery timing",
        effective_filters={},
        provider="local",
    )
    assert len(candidates) > 0
