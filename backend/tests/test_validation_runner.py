"""Integration test for the evaluation runner against the live Postgres.

Builds a real `grounding`-type evaluation dataset from real `generated_answer`
rows (one with citations that genuinely resolve to a real `feedback_record`
and `theme`, one with a citation pointing at a UUID that was never created,
and one dataset item pointing at a `generated_answer` that doesn't exist at
all) so the citation-integrity grader's existence check and the runner's
EVAL-005/EVAL-009 handling run against real database lookups, not mocks.
"""

import uuid
from datetime import UTC, datetime

import pytest

from instamart_engine.analysis.models import AnalysisRun, AnalysisRunStatus
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.insights.models import ConfidenceLevel, EvidenceRole, InsightType
from instamart_engine.research import repository as research_repo
from instamart_engine.research.models import (
    CitationObjectType,
    FindingSupportStatus,
    GroundingStatus,
)
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import Theme, ThemeSet, ThemeSetStatus, ThemeType
from instamart_engine.validation import datasets
from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.graders.citations import CitationIntegrityGrader
from instamart_engine.validation.graders.grounding import InsufficientEvidencePolicyGrader
from instamart_engine.validation.graders.privacy import DemographicInferenceGrader
from instamart_engine.validation.graders.schema import SchemaIntegrityGrader
from instamart_engine.validation.models import (
    EvaluationObjectType,
    EvaluationRunStatus,
    EvaluationType,
)
from instamart_engine.validation.release_gates import (
    CONFIG_DIR,
    evaluate_release_gates,
    load_release_gate_config,
)
from instamart_engine.validation.runners import EmptyDatasetError, run_evaluation

pytestmark = pytest.mark.asyncio

_GRADERS = [
    SchemaIntegrityGrader(required_keys=("answer_text", "citation_count")),
    CitationIntegrityGrader(),
    DemographicInferenceGrader(),
    InsufficientEvidencePolicyGrader(),
]


async def _seed_real_record_and_theme(db_session) -> tuple[FeedbackRecord, Theme]:
    connector = SourceConnectorModel(
        key=f"test-eval-{uuid.uuid4()}",
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
        byte_size=10,
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
        body="Missing freshness info before purchase.",
        payload_checksum="1" * 64,
    )
    db_session.add(raw_item)
    await db_session.flush()

    record = FeedbackRecord(
        raw_source_item_id=raw_item.id,
        source_connector_id=connector.id,
        record_type="app_review",
        ingested_at=datetime.now(UTC),
        original_text="Missing freshness info before purchase.",
        normalized_text="Missing freshness info before purchase.",
        redacted_text="Missing freshness info before purchase.",
        content_hash=str(uuid.uuid4()),
        normalized_length=40,
        relevance_status=RelevanceStatus.UNREVIEWED,
        quality_status=QualityStatus.USABLE,
    )
    db_session.add(record)
    await db_session.flush()

    analysis_run = AnalysisRun(
        name="test-eval-run",
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
        name="test-eval-theme-set",
        status=ThemeSetStatus.PUBLISHED,
        clustering_algorithm="hdbscan",
        clustering_configuration={},
        eligible_record_count=1,
    )
    db_session.add(theme_set)
    await db_session.flush()

    theme = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_0",
        placeholder_name="Freshness info theme",
        representative_record_count=1,
    )
    theme.theme_type = ThemeType.INFORMATION_NEED
    await db_session.flush()

    return record, theme


async def _create_generated_answer_with_citation(
    db_session, *, object_type: CitationObjectType, object_id, citation_count: int
):
    answer = await research_repo.create_generated_answer(
        db_session,
        research_question_id=uuid.uuid4(),
        model_call_id=None,
        answer_text="Users report missing freshness information before purchase.",
        answer_schema={},
        grounding_status=GroundingStatus.PENDING,
        grounding_score=None,
        citation_count=citation_count,
        warning_count=0,
        observed_evidence_count=0,
        synthesized_insight_count=1,
        product_hypothesis_count=0,
        limitations=[],
        suggested_validations=[],
    )
    finding = await research_repo.create_answer_finding(
        db_session,
        generated_answer_id=answer.id,
        position=1,
        finding_type=InsightType.SYNTHESIZED_INSIGHT,
        statement="Users report missing freshness information.",
        confidence_level=ConfidenceLevel.MEDIUM,
        confidence_score=0.7,
        support_status=FindingSupportStatus.SUPPORTED,
    )
    await research_repo.create_answer_citation(
        db_session,
        answer_finding_id=finding.id,
        citation_label="E1",
        object_type=object_type,
        object_id=object_id,
        evidence_role=EvidenceRole.SUPPORTING,
        excerpt_snapshot="Missing freshness info before purchase.",
        supports_claim=True,
    )
    await db_session.commit()
    return answer


@pytest.mark.p0_adversarial
async def test_run_evaluation_against_real_and_fabricated_citations(db_session) -> None:
    record, theme = await _seed_real_record_and_theme(db_session)

    good_answer = await _create_generated_answer_with_citation(
        db_session,
        object_type=CitationObjectType.FEEDBACK_RECORD,
        object_id=record.id,
        citation_count=1,
    )
    bad_answer = await _create_generated_answer_with_citation(
        db_session,
        object_type=CitationObjectType.FEEDBACK_RECORD,
        object_id=uuid.uuid4(),  # never created -> fabricated citation
        citation_count=1,
    )
    ghost_answer_id = uuid.uuid4()  # EVAL-005 -- references a nonexistent object

    dataset = await datasets.create_dataset(
        db_session,
        version_key=f"test-grounding-{uuid.uuid4()}",
        name="Grounding smoke dataset",
        evaluation_type=EvaluationType.GROUNDING,
        partition="development",
    )
    for answer_id in (good_answer.id, bad_answer.id, ghost_answer_id):
        await datasets.add_item(
            db_session,
            dataset=dataset,
            object_type=EvaluationObjectType.GENERATED_ANSWER,
            object_id=answer_id,
            input_snapshot={"generated_answer_id": str(answer_id)},
        )
    await db_session.commit()
    assert dataset.item_count == 3

    run = await run_evaluation(db_session, dataset=dataset, graders=_GRADERS)

    assert run.items_evaluated == 2
    assert run.items_failed == 1
    assert run.status == EvaluationRunStatus.COMPLETED_WITH_WARNINGS

    metric_rows = await validation_repo.get_metrics_for_run(db_session, evaluation_run_id=run.id)
    metrics = {m.metric_key: m for m in metric_rows}
    assert metrics["citation_integrity_pass_rate"].numeric_value == pytest.approx(0.5)
    assert metrics["citation_integrity_hard_failure_count"].numeric_value == 1.0
    assert metrics["schema_integrity_pass_rate"].numeric_value == pytest.approx(1.0)

    config = load_release_gate_config(CONFIG_DIR / "mvp-v1.yaml")
    decision = evaluate_release_gates(config, list(metrics.values()))
    assert decision.status == "fail"
    assert "citation_integrity" in decision.zero_tolerance_failures


async def test_run_evaluation_on_empty_dataset_raises(db_session) -> None:
    dataset = await datasets.create_dataset(
        db_session,
        version_key=f"test-empty-{uuid.uuid4()}",
        name="Empty dataset",
        evaluation_type=EvaluationType.GROUNDING,
        partition="development",
    )
    await db_session.commit()

    with pytest.raises(EmptyDatasetError):
        await run_evaluation(db_session, dataset=dataset, graders=_GRADERS)
