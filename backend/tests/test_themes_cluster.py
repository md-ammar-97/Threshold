"""Clustering tests using synthetic 384-dim vectors for determinism — the
embedding model itself is already validated for real in
test_analysis_embed.py. This isolates the clustering algorithm/persistence
logic from model nondeterminism.
"""

import uuid
from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy import select

from instamart_engine.analysis import embedding_repository as embedding_repo
from instamart_engine.analysis.embed import EMBEDDING_VERSION_KEY
from instamart_engine.analysis.models import AnalysisRun, AnalysisRunStatus
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.taxonomy.seed_v1 import load_taxonomy_v1
from instamart_engine.themes.cluster import discover_themes
from instamart_engine.themes.models import Theme, ThemeMembership

pytestmark = pytest.mark.asyncio

VECTOR_DIM = 384


def _synthetic_vector(base_index: int, jitter_seed: int) -> list[float]:
    rng = np.random.default_rng(jitter_seed)
    vector = np.zeros(VECTOR_DIM, dtype=np.float32)
    vector[base_index] = 1.0
    vector += rng.normal(scale=0.02, size=VECTOR_DIM).astype(np.float32)
    norm = np.linalg.norm(vector)
    return (vector / norm).tolist()


async def _seed_record_with_embedding(
    db_session, *, connector_id, embedding_config_id, body: str, vector: list[float]
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

    checksum = str(uuid.uuid4())
    await embedding_repo.upsert_embedding(
        db_session,
        embedding_configuration_id=embedding_config_id,
        object_type="feedback_record",
        object_id=record.id,
        text_variant="normalized",
        text_checksum=checksum,
        vector=vector,
    )
    return record


async def test_discover_themes_separates_two_obvious_clusters(db_session) -> None:
    await load_taxonomy_v1(db_session)
    connector = SourceConnectorModel(
        key=f"test-cluster-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    embedding_config = await embedding_repo.get_or_create_embedding_configuration(
        db_session,
        version_key=EMBEDDING_VERSION_KEY,
        provider="local",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=VECTOR_DIM,
        normalization_strategy="l2_normalize",
    )
    await db_session.commit()

    # Cluster A: 6 records near basis vector 0. Cluster B: 6 near basis
    # vector 1. Plus 2 far-flung outliers.
    for i in range(6):
        await _seed_record_with_embedding(
            db_session,
            connector_id=connector.id,
            embedding_config_id=embedding_config.id,
            body=f"Delivery arrived late again, order number {i}.",
            vector=_synthetic_vector(0, jitter_seed=i),
        )
    for i in range(6):
        await _seed_record_with_embedding(
            db_session,
            connector_id=connector.id,
            embedding_config_id=embedding_config.id,
            body=f"I wish there was more information about product freshness, case {i}.",
            vector=_synthetic_vector(1, jitter_seed=100 + i),
        )
    for i in range(2):
        await _seed_record_with_embedding(
            db_session,
            connector_id=connector.id,
            embedding_config_id=embedding_config.id,
            body=f"Completely unrelated one-off comment {i}.",
            vector=_synthetic_vector(50 + i, jitter_seed=200 + i),
        )
    await db_session.commit()

    analysis_run = AnalysisRun(
        name="test-run",
        status=AnalysisRunStatus.RUNNING,
        dataset_snapshot={},
        taxonomy_version_id=uuid.uuid4(),
        classification_model_configuration_id=uuid.uuid4(),
    )
    db_session.add(analysis_run)
    await db_session.flush()

    summary = await discover_themes(
        db_session,
        analysis_run_id=analysis_run.id,
        source_connector_id=connector.id,
        min_cluster_size=3,
        provider="local",
    )

    assert summary.eligible_record_count == 14
    assert summary.theme_count == 2  # the two obvious clusters, outliers excluded
    assert summary.clustered_record_count == 12
    assert summary.outlier_record_count == 2

    themes = (
        await db_session.scalars(select(Theme).where(Theme.theme_set_id == summary.theme_set_id))
    ).all()
    assert len(themes) == 2
    for theme in themes:
        memberships = (
            await db_session.scalars(
                select(ThemeMembership).where(ThemeMembership.theme_id == theme.id)
            )
        ).all()
        assert len(memberships) == 6
        representative_count = sum(1 for m in memberships if m.is_representative)
        assert representative_count == 5  # MAX_REPRESENTATIVE_PER_THEME, capped by cluster size
        counterexample_count = sum(1 for m in memberships if m.is_counterexample)
        assert counterexample_count == 1


async def test_discover_themes_with_no_eligible_records_returns_empty_summary(db_session) -> None:
    analysis_run = AnalysisRun(
        name="test-run-empty",
        status=AnalysisRunStatus.RUNNING,
        dataset_snapshot={},
        taxonomy_version_id=uuid.uuid4(),
        classification_model_configuration_id=uuid.uuid4(),
    )
    db_session.add(analysis_run)
    await db_session.flush()

    summary = await discover_themes(
        db_session, analysis_run_id=analysis_run.id, source_connector_id=uuid.uuid4()
    )

    assert summary.theme_set_id is None
    assert summary.eligible_record_count == 0
    assert summary.theme_count == 0


async def test_small_dataset_uses_fallback_and_produces_no_themes(db_session) -> None:
    """THM-002 — below MIN_RECORDS_FOR_CLUSTERING, don't force clusters."""
    connector = SourceConnectorModel(
        key=f"test-cluster-small-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    embedding_config = await embedding_repo.get_or_create_embedding_configuration(
        db_session,
        version_key=EMBEDDING_VERSION_KEY,
        provider="local",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=VECTOR_DIM,
        normalization_strategy="l2_normalize",
    )
    await db_session.commit()

    for i in range(4):
        await _seed_record_with_embedding(
            db_session,
            connector_id=connector.id,
            embedding_config_id=embedding_config.id,
            body=f"Some feedback {i}.",
            vector=_synthetic_vector(0, jitter_seed=i),
        )
    await db_session.commit()

    analysis_run = AnalysisRun(
        name="test-run-small",
        status=AnalysisRunStatus.RUNNING,
        dataset_snapshot={},
        taxonomy_version_id=uuid.uuid4(),
        classification_model_configuration_id=uuid.uuid4(),
    )
    db_session.add(analysis_run)
    await db_session.flush()

    summary = await discover_themes(
        db_session, analysis_run_id=analysis_run.id, source_connector_id=connector.id, provider="local"
    )

    assert summary.eligible_record_count == 4
    assert summary.theme_count == 0
    assert summary.outlier_record_count == 4
