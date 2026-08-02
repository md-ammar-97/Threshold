"""Integration test for theme synthesis against the live Postgres, with a
mocked Groq/OpenRouter (openai-SDK-shaped) client (no API key needed).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from instamart_engine.ai.gateway import AIGateway
from instamart_engine.analysis.models import AnalysisRun, AnalysisRunStatus
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import Theme, ThemeSet, ThemeSetStatus, ThemeStatus, ThemeType
from instamart_engine.themes.schemas import ThemeSynthesisOutput
from instamart_engine.themes.synthesize import synthesize_theme_set

pytestmark = pytest.mark.asyncio


class _FakeUsage:
    prompt_tokens = 30
    completion_tokens = 20


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


async def _seed_theme_with_evidence(db_session) -> Theme:
    connector = SourceConnectorModel(
        key=f"test-synth-{uuid.uuid4()}",
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
        status=ThemeSetStatus.PROCESSING,
        clustering_algorithm="hdbscan",
        clustering_configuration={},
        eligible_record_count=2,
    )
    db_session.add(theme_set)
    await db_session.flush()

    theme = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_0",
        placeholder_name="Unnamed cluster 0",
        representative_record_count=2,
    )

    for i, body in enumerate(
        [
            "I could not find freshness information before buying vegetables.",
            "There was no detail about how fresh the produce was.",
        ]
    ):
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

        await theme_repo.add_theme_membership(
            db_session,
            theme_id=theme.id,
            feedback_record_id=record.id,
            membership_score=0.9,
            assignment_method="test",
            is_representative=True,
            rank_within_theme=i + 1,
        )

    await db_session.commit()
    return theme


async def test_synthesize_theme_set_updates_theme_from_model_output(db_session) -> None:
    theme = await _seed_theme_with_evidence(db_session)

    fake_output = ThemeSynthesisOutput(
        name="Missing freshness information blocks trial",
        short_summary="Users avoid new produce because freshness info is missing.",
        long_summary="Multiple users report being unable to find freshness or expiry "
        "information before purchasing, which discourages trying unfamiliar produce.",
        theme_type=ThemeType.INFORMATION_NEED.value,
        confidence_score=0.8,
    )
    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(fake_output))
    gateway = AIGateway(client=fake_client)

    summary = await synthesize_theme_set(
        db_session, theme_set_id=theme.theme_set_id, gateway=gateway
    )

    assert summary.themes_total == 1
    assert summary.synthesized == 1
    assert summary.failed == 0

    refreshed = await db_session.get(Theme, theme.id)
    assert refreshed.name == "Missing freshness information blocks trial"
    assert refreshed.theme_type == ThemeType.INFORMATION_NEED
    assert refreshed.status == ThemeStatus.UNREVIEWED
    assert float(refreshed.confidence_score) == pytest.approx(0.8)
    assert refreshed.model_call_id is not None


async def test_synthesize_theme_set_with_no_themes_returns_empty_summary(db_session) -> None:
    analysis_run = AnalysisRun(
        name="test-run-empty",
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
        name="empty-set",
        status=ThemeSetStatus.REJECTED,
        clustering_algorithm="hdbscan",
        clustering_configuration={},
        eligible_record_count=0,
    )
    db_session.add(theme_set)
    await db_session.flush()
    await db_session.commit()

    fake_client = AsyncMock()
    gateway = AIGateway(client=fake_client)

    summary = await synthesize_theme_set(db_session, theme_set_id=theme_set.id, gateway=gateway)

    assert summary.themes_total == 0
    fake_client.beta.chat.completions.parse.assert_not_called()
