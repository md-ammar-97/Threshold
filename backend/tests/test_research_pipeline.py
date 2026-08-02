"""End-to-end integration test for the research pipeline (plan -> retrieve
-> generate) against the live Postgres, with a mocked Anthropic client (no
API key needed). Feedback-record embeddings are synthetic fixed vectors —
same isolation rationale as test_themes_cluster.py: the embedding model
itself is validated for real elsewhere (test_analysis_embed.py), so this
test can focus on the retrieval/grounding/persistence logic without
depending on real semantic similarity. The question embedding still goes
through the real local model (retrieval.py has no injectable embedder),
which is fine here since none of the assertions depend on which specific
record ranks highest.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import numpy as np
import pytest
from sqlalchemy import select

from instamart_engine.ai.gateway import AIGateway
from instamart_engine.analysis import embedding_repository as embedding_repo
from instamart_engine.analysis.embed import EMBEDDING_VERSION_KEY_HOSTED
from instamart_engine.analysis.models import (
    AnalysisRun,
    AnalysisRunStatus,
    FeedbackAnalysis,
    FeedbackAnalysisStatus,
)
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.insights.models import (
    ConfidenceLevel,
    Insight,
    InsightSet,
    InsightSetStatus,
    InsightType,
)
from instamart_engine.research.models import (
    GeneratedAnswer,
    GroundingStatus,
    QueryPlan,
    ResearchQuestion,
    ResearchQuestionStatus,
    ResearchSession,
    RetrievalResult,
)
from instamart_engine.research.schemas import (
    AnswerFindingOutput,
    GeneratedAnswerOutput,
    QueryPlanOutput,
)
from instamart_engine.research.service import ask_question
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.taxonomy.repository import get_published_taxonomy
from instamart_engine.taxonomy.seed_v1 import load_taxonomy_v1
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import ThemeSet, ThemeSetStatus, ThemeType

pytestmark = pytest.mark.asyncio

VECTOR_DIM = 384


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


def _synthetic_vector(base_index: int, jitter_seed: int) -> list[float]:
    rng = np.random.default_rng(jitter_seed)
    vector = np.zeros(VECTOR_DIM, dtype=np.float32)
    vector[base_index] = 1.0
    vector += rng.normal(scale=0.02, size=VECTOR_DIM).astype(np.float32)
    norm = np.linalg.norm(vector)
    return (vector / norm).tolist()


@pytest.fixture(autouse=True)
def _stub_query_embedding(monkeypatch):
    """`retrieval.py` calls the real `embed_query_text` with no injectable
    override; this suite doesn't care which specific record ranks highest
    (see module docstring), so stub it to a fixed synthetic vector rather
    than depending on network access / EMBEDDING_PROVIDER=hosted."""

    async def _fake_embed_query_text(_text: str, *, provider: str | None = None) -> list[float]:
        return _synthetic_vector(base_index=0, jitter_seed=0)

    monkeypatch.setattr(
        "instamart_engine.research.retrieval.embed_query_text", _fake_embed_query_text
    )


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

    await embedding_repo.upsert_embedding(
        db_session,
        embedding_configuration_id=embedding_config_id,
        object_type="feedback_record",
        object_id=record.id,
        text_variant="normalized",
        text_checksum=uuid.uuid4().hex,
        vector=vector,
    )
    return record


async def _seed_research_session(db_session) -> ResearchSession:
    await load_taxonomy_v1(db_session)
    taxonomy_version = await get_published_taxonomy(db_session)

    connector = SourceConnectorModel(
        key=f"test-research-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    # settings.EMBEDDING_PROVIDER defaults to "hosted" and retrieval now
    # resolves its embedding configuration from that setting (not an
    # is_active/"most recent" heuristic) — seed under the matching version
    # key so retrieval actually finds these rows.
    embedding_config = await embedding_repo.get_or_create_embedding_configuration(
        db_session,
        version_key=EMBEDDING_VERSION_KEY_HOSTED,
        provider="hosted",
        model_name="test",
        dimension=VECTOR_DIM,
        normalization_strategy="l2_normalize",
    )

    analysis_run = AnalysisRun(
        name="test-research-run",
        status=AnalysisRunStatus.RUNNING,
        dataset_snapshot={},
        taxonomy_version_id=taxonomy_version.id,
        classification_model_configuration_id=uuid.uuid4(),
    )
    db_session.add(analysis_run)
    await db_session.flush()

    theme_set = ThemeSet(
        analysis_run_id=analysis_run.id,
        version_number=1,
        name="test-research-theme-set",
        status=ThemeSetStatus.PUBLISHED,
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
        placeholder_name="Missing freshness information",
        representative_record_count=2,
    )
    theme.name = "Missing freshness information blocks trial"
    theme.short_summary = "Users avoid new produce because freshness info is missing."
    theme.theme_type = ThemeType.INFORMATION_NEED
    theme.confidence_score = 0.8
    theme.opportunity_score = 51.6
    theme.score_components = {"frequency": 0.5, "severity": 0.4}
    await db_session.flush()

    bodies = [
        "I could not find freshness information before buying vegetables.",
        "There was no detail about how fresh the produce was.",
        "The freshness label was clearly shown and it matched what arrived.",
    ]
    records = []
    for i, body in enumerate(bodies):
        record = await _seed_record_with_embedding(
            db_session,
            connector_id=connector.id,
            embedding_config_id=embedding_config.id,
            body=body,
            vector=_synthetic_vector(base_index=i, jitter_seed=i),
        )
        records.append(record)
        db_session.add(
            FeedbackAnalysis(
                feedback_record_id=record.id,
                analysis_run_id=analysis_run.id,
                taxonomy_version_id=taxonomy_version.id,
                status=FeedbackAnalysisStatus.SUCCEEDED,
            )
        )
        await db_session.flush()
        await theme_repo.add_theme_membership(
            db_session,
            theme_id=theme.id,
            feedback_record_id=record.id,
            membership_score=0.9,
            assignment_method="test",
            is_representative=(i < 2),
            is_counterexample=(i == 2),
            rank_within_theme=i + 1 if i < 2 else None,
        )

    insight_set = InsightSet(
        theme_set_id=theme_set.id,
        analysis_run_id=analysis_run.id,
        version_number=1,
        status=InsightSetStatus.READY_FOR_REVIEW,
        model_configuration_id=uuid.uuid4(),
        prompt_version_id=uuid.uuid4(),
        insight_count=1,
    )
    db_session.add(insight_set)
    await db_session.flush()

    insight = Insight(
        insight_set_id=insight_set.id,
        insight_type=InsightType.SYNTHESIZED_INSIGHT,
        title="Missing freshness info discourages produce trial",
        finding="Two reviewed excerpts report no freshness information shown before purchase.",
        interpretation="This pattern is associated with hesitation to try unfamiliar produce.",
        confidence_level=ConfidenceLevel.MEDIUM,
        confidence_score=0.7,
        opportunity_score=42.0,
        score_components={"frequency": 0.4},
    )
    db_session.add(insight)
    await db_session.flush()

    research_session = ResearchSession(
        title="Test research session",
        analysis_run_id=analysis_run.id,
        theme_set_id=theme_set.id,
        insight_set_id=insight_set.id,
    )
    db_session.add(research_session)
    await db_session.flush()
    await db_session.commit()
    return research_session


def _fake_gateway() -> AIGateway:
    plan_output = QueryPlanOutput(
        research_dimensions=["exploration_barrier"],
        query_intent="explain",
        structured_filters={},
        ambiguity_warnings=[],
        requires_deterministic_aggregation=False,
    )
    answer_output = GeneratedAnswerOutput(
        answer_text="Users report missing freshness information before purchase, though "
        "one review shows the label was shown correctly.",
        findings=[
            AnswerFindingOutput(
                statement="Multiple reviews report missing freshness information before "
                "purchase.",
                finding_type="synthesized_insight",
                confidence_level="medium",
                confidence_score=0.7,
                citation_labels=["E1", "T1"],
            )
        ],
        limitations=["Small sample size from one source."],
        suggested_validations=[],
    )
    outputs = iter([plan_output, answer_output])

    async def _fake_parse(**kwargs):
        return _FakeResponse(next(outputs))

    fake_client = AsyncMock()
    fake_client.beta.chat.completions.parse = AsyncMock(side_effect=_fake_parse)
    return AIGateway(client=fake_client)


async def test_ask_question_full_pipeline(db_session) -> None:
    research_session = await _seed_research_session(db_session)
    gateway = _fake_gateway()

    result = await ask_question(
        db_session,
        research_session_id=research_session.id,
        question_text="Why do users hesitate to try new produce categories?",
        gateway=gateway,
    )

    question = await db_session.get(ResearchQuestion, result.question.id)
    assert question.status in (
        ResearchQuestionStatus.COMPLETED,
        ResearchQuestionStatus.COMPLETED_WITH_WARNINGS,
    )
    assert question.answer_mode == "explain"

    query_plan = await db_session.scalar(
        select(QueryPlan).where(QueryPlan.research_question_id == question.id)
    )
    assert query_plan is not None
    assert query_plan.research_dimensions == ["exploration_barrier"]

    retrieval_rows = (
        await db_session.scalars(
            select(RetrievalResult).where(RetrievalResult.research_question_id == question.id)
        )
    ).all()
    assert len(retrieval_rows) >= 4  # 1 theme + 1 insight + 3 records (all small enough to fit)

    answer = await db_session.scalar(
        select(GeneratedAnswer).where(GeneratedAnswer.research_question_id == question.id)
    )
    assert answer is not None
    assert answer.grounding_status in (
        GroundingStatus.PASSED,
        GroundingStatus.PASSED_WITH_WARNINGS,
    )
    assert answer.citation_count == 2  # E1 and T1 both resolve
    assert answer.synthesized_insight_count == 1


async def test_ask_question_with_no_matching_evidence_is_insufficient(db_session) -> None:
    await load_taxonomy_v1(db_session)
    analysis_run = AnalysisRun(
        name="test-research-empty-run",
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
        name="test-research-empty-theme-set",
        status=ThemeSetStatus.PUBLISHED,
        clustering_algorithm="hdbscan",
        clustering_configuration={},
        eligible_record_count=0,
    )
    db_session.add(theme_set)
    await db_session.flush()

    research_session = ResearchSession(
        title="Empty test research session",
        analysis_run_id=analysis_run.id,
        theme_set_id=theme_set.id,
    )
    db_session.add(research_session)
    await db_session.flush()
    await db_session.commit()

    gateway = _fake_gateway()

    result = await ask_question(
        db_session,
        research_session_id=research_session.id,
        question_text="Why do users churn?",
        gateway=gateway,
    )

    answer = await db_session.scalar(
        select(GeneratedAnswer).where(GeneratedAnswer.research_question_id == result.question.id)
    )
    assert answer is not None
    assert answer.citation_count == 0
    assert "not enough" in answer.answer_text.lower()
