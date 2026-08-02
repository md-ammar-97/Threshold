"""Integration test for deterministic theme metrics and opportunity
scoring against the live Postgres.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from instamart_engine.analysis.models import (
    AnalysisRun,
    AnalysisRunStatus,
    FeedbackAnalysis,
    FeedbackAnalysisStatus,
)
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.metrics import compute_theme_metrics_and_scores
from instamart_engine.themes.models import Theme, ThemeMetric, ThemeSet, ThemeSetStatus, ThemeType

pytestmark = pytest.mark.asyncio


async def _seed_theme_with_n_records(
    db_session, *, n: int, theme_type: ThemeType, severities: list[int | None]
) -> tuple[Theme, ThemeSet]:
    connector = SourceConnectorModel(
        key=f"test-metrics-{uuid.uuid4()}",
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
        eligible_record_count=n,
    )
    db_session.add(theme_set)
    await db_session.flush()

    theme = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_0",
        placeholder_name="Unnamed cluster 0",
        representative_record_count=n,
    )
    theme.theme_type = theme_type
    theme.confidence_score = 0.7
    await db_session.flush()

    for i in range(n):
        body = f"Feedback record {i}"
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

        await theme_repo.add_theme_membership(
            db_session,
            theme_id=theme.id,
            feedback_record_id=record.id,
            membership_score=0.85,
            assignment_method="test",
            is_representative=(i == 0),
            rank_within_theme=i + 1,
        )

        severity = severities[i] if i < len(severities) else None
        if severity is not None:
            db_session.add(
                FeedbackAnalysis(
                    feedback_record_id=record.id,
                    analysis_run_id=analysis_run.id,
                    taxonomy_version_id=uuid.uuid4(),
                    status=FeedbackAnalysisStatus.SUCCEEDED,
                    severity_value=severity,
                )
            )

    await db_session.commit()
    return theme, theme_set


async def test_metrics_and_opportunity_score_are_computed(db_session) -> None:
    theme, theme_set = await _seed_theme_with_n_records(
        db_session,
        n=4,
        theme_type=ThemeType.EXPLORATION_BARRIER,
        severities=[4, 4, 3, None],
    )

    results = await compute_theme_metrics_and_scores(db_session, theme_set_id=theme_set.id)

    assert len(results) == 1
    assert results[0].record_count == 4
    assert results[0].opportunity_score > 0

    refreshed = await db_session.get(Theme, theme.id)
    assert refreshed.opportunity_score is not None
    assert refreshed.discovery_relevance_score == pytest.approx(0.9)  # high-relevance theme_type
    assert refreshed.score_components is not None
    assert set(refreshed.score_components.keys()) == {
        "frequency",
        "severity",
        "recency",
        "source_breadth",
        "confidence",
        "discovery_relevance",
        "actionability",
    }

    metrics = (
        await db_session.scalars(select(ThemeMetric).where(ThemeMetric.theme_id == theme.id))
    ).all()
    metric_keys = {m.metric_key for m in metrics}
    assert "record_count" in metric_keys
    assert "opportunity_score" in metric_keys
    assert "source_distribution" in metric_keys


async def test_low_relevance_theme_type_scores_lower_discovery_relevance(db_session) -> None:
    theme, theme_set = await _seed_theme_with_n_records(
        db_session, n=2, theme_type=ThemeType.SERVICE_QUALITY, severities=[1, 1]
    )

    await compute_theme_metrics_and_scores(db_session, theme_set_id=theme_set.id)

    refreshed = await db_session.get(Theme, theme.id)
    assert refreshed.discovery_relevance_score == pytest.approx(0.5)
