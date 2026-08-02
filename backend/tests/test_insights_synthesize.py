"""Integration tests for insight generation against the live Postgres, with a
mocked Groq/OpenRouter (openai-SDK-shaped) client (no API key needed).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from instamart_engine.ai.gateway import AIGateway
from instamart_engine.analysis.models import AnalysisRun, AnalysisRunStatus
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.insights.models import (
    Insight,
    InsightEvidence,
    InsightSet,
    InsightSetStatus,
    InsightTheme,
    InsightThemeRelationship,
    InsightType,
)
from instamart_engine.insights.schemas import InsightEvidenceCitation, InsightGenerationOutput
from instamart_engine.insights.synthesize import generate_insights_for_theme_set
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import Theme, ThemeSet, ThemeSetStatus, ThemeType

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


async def _seed_theme_with_evidence(
    db_session, *, with_counterexample: bool = True, with_representatives: bool = True
) -> Theme:
    connector = SourceConnectorModel(
        key=f"test-insight-{uuid.uuid4()}",
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
        eligible_record_count=3,
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
    theme.name = "Missing freshness information blocks trial"
    theme.short_summary = "Users avoid new produce because freshness info is missing."
    theme.theme_type = ThemeType.INFORMATION_NEED
    theme.confidence_score = 0.8
    theme.opportunity_score = 42.5
    theme.score_components = {
        "frequency": 0.5,
        "severity": 0.4,
        "recency": 0.3,
        "source_breadth": 0.2,
        "confidence": 0.8,
        "discovery_relevance": 0.9,
        "actionability": 0.6,
    }
    await db_session.flush()

    async def _add_record(body: str, *, representative: bool, counterexample: bool, rank) -> None:
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
            is_representative=representative,
            is_counterexample=counterexample,
            rank_within_theme=rank,
        )

    if with_representatives:
        await _add_record(
            "I could not find freshness information before buying vegetables.",
            representative=True,
            counterexample=False,
            rank=1,
        )
        await _add_record(
            "There was no detail about how fresh the produce was.",
            representative=True,
            counterexample=False,
            rank=2,
        )
    if with_counterexample:
        await _add_record(
            "The freshness label was clearly shown and it matched what arrived.",
            representative=False,
            counterexample=True,
            rank=None,
        )

    await db_session.commit()
    return theme


async def test_generate_insights_creates_insight_theme_link_and_evidence(db_session) -> None:
    theme = await _seed_theme_with_evidence(db_session)

    fake_output = InsightGenerationOutput(
        insight_type=InsightType.SYNTHESIZED_INSIGHT.value,
        title="Missing freshness info discourages produce trial",
        finding="Two of the reviewed excerpts report no freshness or expiry information "
        "shown before purchase.",
        interpretation="This pattern is associated with hesitation to try unfamiliar produce, "
        "though one excerpt shows the label displaying correctly, so the gap may be "
        "inconsistent rather than universal.",
        affected_context="Produce category product detail page",
        product_implication="Worth testing whether adding a visible freshness/expiry badge "
        "increases produce add-to-cart rate.",
        validation_recommendation=None,
        confidence_level="medium",
        confidence_score=0.7,
        evidence=[
            InsightEvidenceCitation(excerpt_number=1, role="supporting", relevance_score=0.9),
            InsightEvidenceCitation(excerpt_number=2, role="supporting", relevance_score=0.8),
            InsightEvidenceCitation(excerpt_number=0, role="contradictory", relevance_score=0.6),
        ],
    )
    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(fake_output))
    gateway = AIGateway(client=fake_client)

    summary = await generate_insights_for_theme_set(
        db_session, theme_set_id=theme.theme_set_id, gateway=gateway
    )

    assert summary.themes_total == 1
    assert summary.generated == 1
    assert summary.failed == 0
    assert summary.published == 1
    assert summary.blocked == 0

    insight = await db_session.scalar(
        select(Insight).where(Insight.title == "Missing freshness info discourages produce trial")
    )
    assert insight is not None
    assert insight.insight_type == InsightType.SYNTHESIZED_INSIGHT
    assert float(insight.opportunity_score) == pytest.approx(42.5)
    assert insight.score_components == theme.score_components
    assert insight.model_call_id is not None

    theme_link = await db_session.scalar(
        select(InsightTheme).where(InsightTheme.insight_id == insight.id)
    )
    assert theme_link is not None
    assert theme_link.theme_id == theme.id
    assert theme_link.relationship_type == InsightThemeRelationship.PRIMARY

    evidence_rows = (
        await db_session.scalars(
            select(InsightEvidence).where(InsightEvidence.insight_id == insight.id)
        )
    ).all()
    assert len(evidence_rows) == 3
    assert all(row.start_offset is not None and row.end_offset is not None for row in evidence_rows)

    theme_set_refreshed = await db_session.get(ThemeSet, theme.theme_set_id)
    assert theme_set_refreshed is not None  # sanity: theme_set untouched by insight generation


async def test_generate_insights_product_hypothesis_without_recommendation_is_blocked(
    db_session,
) -> None:
    theme = await _seed_theme_with_evidence(db_session, with_counterexample=False)

    fake_output = InsightGenerationOutput(
        insight_type=InsightType.PRODUCT_HYPOTHESIS.value,
        title="A visible freshness badge could increase produce trial",
        finding="Two excerpts report no freshness information before purchase.",
        interpretation="Users may be hesitant to try unfamiliar produce without this signal.",
        affected_context="Produce category product detail page",
        product_implication="Worth testing a freshness badge.",
        validation_recommendation=None,  # missing -> INS-010
        confidence_level="low",
        confidence_score=0.4,
        evidence=[
            InsightEvidenceCitation(excerpt_number=1, role="supporting", relevance_score=0.7),
        ],
    )
    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(fake_output))
    gateway = AIGateway(client=fake_client)

    summary = await generate_insights_for_theme_set(
        db_session, theme_set_id=theme.theme_set_id, gateway=gateway
    )

    assert summary.generated == 1
    assert summary.published == 0
    assert summary.blocked == 1

    insight = await db_session.scalar(
        select(Insight)
        .join(InsightTheme, InsightTheme.insight_id == Insight.id)
        .where(
            Insight.insight_type == InsightType.PRODUCT_HYPOTHESIS,
            InsightTheme.theme_id == theme.id,
        )
    )
    assert insight is not None
    assert insight.validation_recommendation is None


async def test_generate_insights_redacts_demographic_inference(db_session) -> None:
    theme = await _seed_theme_with_evidence(db_session, with_counterexample=False)

    fake_output = InsightGenerationOutput(
        insight_type=InsightType.OBSERVED_EVIDENCE.value,
        title="Freshness info gap",
        finding="A young professional reported missing freshness information.",
        interpretation="This may reduce trust among these users.",
        affected_context=None,
        product_implication=None,
        validation_recommendation=None,
        confidence_level="low",
        confidence_score=0.3,
        evidence=[
            InsightEvidenceCitation(excerpt_number=1, role="illustrative", relevance_score=0.5),
        ],
    )
    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(return_value=_FakeResponse(fake_output))
    gateway = AIGateway(client=fake_client)

    await generate_insights_for_theme_set(
        db_session, theme_set_id=theme.theme_set_id, gateway=gateway
    )

    insight = await db_session.scalar(
        select(Insight).where(Insight.title == "Freshness info gap")
    )
    assert insight is not None
    assert "young professional" not in insight.finding
    assert "removed" in insight.finding


async def test_generate_insights_skips_theme_without_representatives(db_session) -> None:
    theme = await _seed_theme_with_evidence(
        db_session, with_representatives=False, with_counterexample=False
    )

    fake_client = AsyncMock()
    gateway = AIGateway(client=fake_client)

    summary = await generate_insights_for_theme_set(
        db_session, theme_set_id=theme.theme_set_id, gateway=gateway
    )

    assert summary.themes_total == 1
    assert summary.generated == 0
    fake_client.beta.chat.completions.parse.assert_not_called()

    insight_set = await db_session.scalar(
        select(InsightSet).where(InsightSet.theme_set_id == theme.theme_set_id)
    )
    assert insight_set is not None
    assert insight_set.insight_count == 0
    assert insight_set.status == InsightSetStatus.REJECTED

    remaining_insights = (
        await db_session.scalars(
            select(Insight).where(Insight.insight_set_id == insight_set.id)
        )
    ).all()
    assert remaining_insights == []


async def test_generate_insights_with_no_themes_returns_empty_summary(db_session) -> None:
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

    summary = await generate_insights_for_theme_set(
        db_session, theme_set_id=theme_set.id, gateway=gateway
    )

    assert summary.themes_total == 0
    fake_client.beta.chat.completions.parse.assert_not_called()
