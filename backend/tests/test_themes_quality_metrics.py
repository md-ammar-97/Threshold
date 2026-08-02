"""Integration test for theme-set-level quality metrics (coverage, outlier
rate, overlap rate, duplicate-inflation rate — ai_evals.md §30's set-wide
numbers, distinct from the per-theme graders in
validation/graders/theme_quality.py) against the live Postgres.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from instamart_engine.analysis.models import AnalysisRun, AnalysisRunStatus
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import ThemeSet, ThemeSetStatus, ThemeType

pytestmark = pytest.mark.asyncio


async def _seed_record(db_session, connector_id) -> FeedbackRecord:
    body = f"Feedback record {uuid.uuid4()}"
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
        published_at=datetime.now(UTC) - timedelta(days=1),
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


async def _seed_theme_set(db_session, *, eligible: int, clustered: int, outliers: int) -> ThemeSet:
    connector = SourceConnectorModel(
        key=f"test-quality-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    analysis_run = AnalysisRun(
        name="test-run",
        status=AnalysisRunStatus.RUNNING,
        dataset_snapshot={},
        taxonomy_version_id=uuid.uuid4(),
        classification_model_configuration_id=uuid.uuid4(),
    )
    db_session.add(analysis_run)
    await db_session.flush()

    theme_set = ThemeSet(
        analysis_run_id=analysis_run.id,
        version_number=1,
        name="test-theme-set",
        status=ThemeSetStatus.READY_FOR_REVIEW,
        clustering_algorithm="hdbscan",
        clustering_configuration={},
        eligible_record_count=eligible,
        clustered_record_count=clustered,
        outlier_record_count=outliers,
    )
    db_session.add(theme_set)
    await db_session.flush()
    return theme_set, connector.id


async def test_compute_theme_set_quality_metrics_no_overlap(db_session) -> None:
    theme_set, connector_id = await _seed_theme_set(
        db_session, eligible=10, clustered=8, outliers=2
    )
    theme_a = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_0",
        placeholder_name="A",
        representative_record_count=4,
    )
    theme_a.theme_type = ThemeType.OTHER
    theme_b = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_1",
        placeholder_name="B",
        representative_record_count=4,
    )
    theme_b.theme_type = ThemeType.OTHER
    await db_session.flush()

    for theme in (theme_a, theme_b):
        for _i in range(4):
            record = await _seed_record(db_session, connector_id)
            await theme_repo.add_theme_membership(
                db_session,
                theme_id=theme.id,
                feedback_record_id=record.id,
                membership_score=0.8,
                assignment_method="test",
            )

    metrics = await theme_repo.compute_theme_set_quality_metrics(
        db_session, theme_set_id=theme_set.id
    )

    assert metrics.eligible_record_coverage == pytest.approx(0.8)
    assert metrics.outlier_rate == pytest.approx(0.2)
    assert metrics.overlap_rate == pytest.approx(0.0)
    assert metrics.duplicate_inflation_rate == pytest.approx(0.0)


async def test_compute_theme_set_quality_metrics_with_overlap(db_session) -> None:
    theme_set, connector_id = await _seed_theme_set(
        db_session, eligible=6, clustered=6, outliers=0
    )
    theme_a = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_0",
        placeholder_name="A",
        representative_record_count=3,
    )
    theme_b = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_1",
        placeholder_name="B",
        representative_record_count=3,
    )
    await db_session.flush()

    shared_records = [await _seed_record(db_session, connector_id) for _ in range(2)]
    only_a = await _seed_record(db_session, connector_id)
    only_b = await _seed_record(db_session, connector_id)

    for record in [*shared_records, only_a]:
        await theme_repo.add_theme_membership(
            db_session,
            theme_id=theme_a.id,
            feedback_record_id=record.id,
            membership_score=0.8,
            assignment_method="test",
        )
    for record in [*shared_records, only_b]:
        await theme_repo.add_theme_membership(
            db_session,
            theme_id=theme_b.id,
            feedback_record_id=record.id,
            membership_score=0.8,
            assignment_method="test",
        )

    metrics = await theme_repo.compute_theme_set_quality_metrics(
        db_session, theme_set_id=theme_set.id
    )

    # A={shared1, shared2, only_a}, B={shared1, shared2, only_b}
    # intersection=2, union=4 -> jaccard = 0.5
    assert metrics.overlap_rate == pytest.approx(0.5)
    # 2 records (the shared ones) appear in >1 theme, out of 4 distinct members
    assert metrics.duplicate_inflation_rate == pytest.approx(0.5)


async def test_compute_theme_set_quality_metrics_handles_zero_eligible(db_session) -> None:
    theme_set, _connector_id = await _seed_theme_set(
        db_session, eligible=0, clustered=0, outliers=0
    )
    metrics = await theme_repo.compute_theme_set_quality_metrics(
        db_session, theme_set_id=theme_set.id
    )
    assert metrics.eligible_record_coverage is None
    assert metrics.outlier_rate is None
    assert metrics.overlap_rate is None
    assert metrics.duplicate_inflation_rate == 0.0
