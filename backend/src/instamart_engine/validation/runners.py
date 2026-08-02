"""Evaluation run orchestration. ai_evals.md §10-11; edgecases.md
EVAL-001/005/007/009.

Runs the deterministic grader tiers over every item in a dataset, resolving
each item's candidate_output from the real, currently-persisted database
row it points to — never from a re-generated or cached copy (edgecases.md
EVAL-010). `generated_answer` (grounding and retrieval quality — retrieval
graders run against the same candidate shape, since citations/findings
*are* the retrieved evidence package), `feedback_record` (classification
quality), and `theme` (theme quality) all have resolvers. `research_question`
has none yet and still raises `NotImplementedError`, which the per-item
try/except below turns into a counted failure (EVAL-009) rather than
crashing the whole run.
"""

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import AnalysisEvidenceSpan, AnalysisLabel, FeedbackAnalysis
from instamart_engine.core.logging import get_logger
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.insights.models import Insight, InsightSet
from instamart_engine.research.models import AnswerCitation, AnswerFinding, GeneratedAnswer
from instamart_engine.sources.models import SourceConnectorModel
from instamart_engine.taxonomy.models import TaxonomyDimension
from instamart_engine.themes.models import Theme, ThemeMembership, ThemeMetric, ThemeSet
from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.graders.base import EvalGrader, GraderResult
from instamart_engine.validation.models import (
    EvaluationDataset,
    EvaluationDatasetItem,
    EvaluationObjectType,
    EvaluationRun,
    EvaluationRunStatus,
)

logger = get_logger(__name__)

CALCULATION_VERSION = "v1"

_CitationObjectModel = type[FeedbackRecord] | type[Theme] | type[ThemeMetric] | type[Insight]

_CITATION_OBJECT_MODELS: dict[str, _CitationObjectModel] = {
    "feedback_record": FeedbackRecord,
    "theme": Theme,
    "theme_metric": ThemeMetric,
    "insight": Insight,
}


class EmptyDatasetError(Exception):
    """EVAL-001 — an evaluation run needs at least one item."""


async def _build_grounding_candidate_output(
    session: AsyncSession, *, generated_answer_id: UUID
) -> dict[str, Any] | None:
    answer = await session.get(GeneratedAnswer, generated_answer_id)
    if answer is None:
        # EVAL-005 — the gold item references a deleted/unavailable object.
        return None

    findings = (
        await session.scalars(
            select(AnswerFinding)
            .where(AnswerFinding.generated_answer_id == answer.id)
            .order_by(AnswerFinding.position)
        )
    ).all()

    findings_payload = []
    for finding in findings:
        citations = (
            await session.scalars(
                select(AnswerCitation).where(AnswerCitation.answer_finding_id == finding.id)
            )
        ).all()
        findings_payload.append(
            {
                "position": finding.position,
                "statement": finding.statement,
                "finding_type": finding.finding_type.value,
                "citations": [
                    {
                        "citation_label": c.citation_label,
                        "object_type": c.object_type.value,
                        "object_id": str(c.object_id),
                    }
                    for c in citations
                ],
            }
        )

    return {
        "answer_text": answer.answer_text,
        "citation_count": answer.citation_count,
        "warning_count": answer.warning_count,
        "findings": findings_payload,
    }


async def _build_classification_candidate_output(
    session: AsyncSession, *, feedback_record_id: UUID
) -> dict[str, Any] | None:
    record = await session.get(FeedbackRecord, feedback_record_id)
    if record is None:
        # EVAL-005 — the gold item references a deleted/unavailable object.
        return None

    analysis = await session.scalar(
        select(FeedbackAnalysis)
        .where(FeedbackAnalysis.feedback_record_id == feedback_record_id)
        .order_by(FeedbackAnalysis.created_at.desc())
        .limit(1)
    )
    if analysis is None:
        return None

    labels = (
        await session.scalars(
            select(AnalysisLabel).where(AnalysisLabel.feedback_analysis_id == analysis.id)
        )
    ).all()

    labels_payload = []
    for label in labels:
        dimension = await session.get(TaxonomyDimension, label.taxonomy_dimension_id)
        evidence_span = await session.scalar(
            select(AnalysisEvidenceSpan)
            .where(AnalysisEvidenceSpan.analysis_label_id == label.id)
            .limit(1)
        )
        labels_payload.append(
            {
                "dimension_key": dimension.key if dimension else None,
                "confidence": float(label.confidence),
                # datamodel.md §67 invariant #1: a label must belong to the
                # SAME taxonomy version as its own feedback_analysis — not
                # necessarily the currently-published one. A record
                # classified under an older, still-valid taxonomy version
                # is not "unsupported"; a label whose dimension belongs to
                # a *different* version than its own analysis row would be
                # a real integrity violation (e.g. a taxonomy migration bug).
                "belongs_to_own_taxonomy_version": (
                    dimension is not None
                    and dimension.taxonomy_version_id == analysis.taxonomy_version_id
                ),
                "evidence_excerpt": evidence_span.excerpt_snapshot if evidence_span else "",
            }
        )

    return {
        "feedback_record_id": str(record.id),
        "analysis_status": analysis.status.value,
        "labels": labels_payload,
    }


async def _build_theme_candidate_output(
    session: AsyncSession, *, theme_id: UUID
) -> dict[str, Any] | None:
    theme = await session.get(Theme, theme_id)
    if theme is None or theme.deleted_at is not None:
        # EVAL-005 — the gold item references a deleted/unavailable object.
        return None

    memberships = (
        await session.scalars(select(ThemeMembership).where(ThemeMembership.theme_id == theme_id))
    ).all()

    source_rows = await session.execute(
        select(SourceConnectorModel.key, func.count())
        .select_from(ThemeMembership)
        .join(FeedbackRecord, FeedbackRecord.id == ThemeMembership.feedback_record_id)
        .join(SourceConnectorModel, SourceConnectorModel.id == FeedbackRecord.source_connector_id)
        .where(ThemeMembership.theme_id == theme_id)
        .group_by(SourceConnectorModel.key)
    )

    return {
        "name": theme.name,
        "short_summary": theme.short_summary,
        "coherence_score": (
            float(theme.coherence_score) if theme.coherence_score is not None else None
        ),
        "member_count": len(memberships),
        "has_representative_evidence": any(m.is_representative for m in memberships),
        "source_counts": dict(source_rows.all()),
    }


async def _resolve_candidate_output(
    session: AsyncSession, item: EvaluationDatasetItem
) -> dict[str, Any] | None:
    if item.object_type == EvaluationObjectType.GENERATED_ANSWER:
        return await _build_grounding_candidate_output(
            session, generated_answer_id=item.object_id
        )
    if item.object_type == EvaluationObjectType.FEEDBACK_RECORD:
        return await _build_classification_candidate_output(
            session, feedback_record_id=item.object_id
        )
    if item.object_type == EvaluationObjectType.THEME:
        return await _build_theme_candidate_output(session, theme_id=item.object_id)
    raise NotImplementedError(
        f"No candidate-output resolver implemented for object_type={item.object_type.value!r}"
    )


async def _resolve_existing_object_ids(
    session: AsyncSession, candidate_output: dict[str, Any]
) -> set[str]:
    ids_by_type: dict[str, set[UUID]] = defaultdict(set)
    for finding in candidate_output.get("findings", []):
        for citation in finding.get("citations", []):
            object_type = citation.get("object_type")
            object_id = citation.get("object_id")
            if object_type in _CITATION_OBJECT_MODELS and object_id:
                ids_by_type[object_type].add(UUID(object_id))

    existing: set[str] = set()
    for object_type, ids in ids_by_type.items():
        model = _CITATION_OBJECT_MODELS[object_type]
        for object_id in ids:
            row = await session.get(model, object_id)
            if row is not None:
                existing.add(str(object_id))
    return existing


async def _analysis_run_id_for_citation_object(
    session: AsyncSession, *, object_type: str, row: Any
) -> UUID | None:
    if object_type == "feedback_record":
        analysis = await session.scalar(
            select(FeedbackAnalysis)
            .where(FeedbackAnalysis.feedback_record_id == row.id)
            .order_by(FeedbackAnalysis.created_at.desc())
            .limit(1)
        )
        return analysis.analysis_run_id if analysis else None
    if object_type == "theme":
        theme_set = await session.get(ThemeSet, row.theme_set_id)
        return theme_set.analysis_run_id if theme_set else None
    if object_type == "insight":
        insight_set = await session.get(InsightSet, row.insight_set_id)
        return insight_set.analysis_run_id if insight_set else None
    return None


async def _resolve_citation_object_details(
    session: AsyncSession, candidate_output: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Retrieval-quality graders (cross-version contamination, deleted-
    object retrieval) need more than existence — whether a cited object is
    soft-deleted and which `analysis_run_id` it traces back to. Batched by
    distinct object like `_resolve_existing_object_ids`, one extra lookup
    per object for its analysis lineage."""
    ids_by_type: dict[str, set[UUID]] = defaultdict(set)
    for finding in candidate_output.get("findings", []):
        for citation in finding.get("citations", []):
            object_type = citation.get("object_type")
            object_id = citation.get("object_id")
            if object_type in _CITATION_OBJECT_MODELS and object_id:
                ids_by_type[object_type].add(UUID(object_id))

    details: dict[str, dict[str, Any]] = {}
    for object_type, ids in ids_by_type.items():
        model = _CITATION_OBJECT_MODELS[object_type]
        for object_id in ids:
            row = await session.get(model, object_id)
            if row is None:
                details[str(object_id)] = {
                    "exists": False,
                    "deleted_at": None,
                    "analysis_run_id": None,
                }
                continue
            analysis_run_id = await _analysis_run_id_for_citation_object(
                session, object_type=object_type, row=row
            )
            deleted_at = getattr(row, "deleted_at", None)
            details[str(object_id)] = {
                "exists": True,
                "deleted_at": deleted_at.isoformat() if deleted_at else None,
                "analysis_run_id": str(analysis_run_id) if analysis_run_id else None,
            }
    return details


async def run_evaluation(
    session: AsyncSession,
    *,
    dataset: EvaluationDataset,
    graders: list[EvalGrader],
    analysis_run_id: UUID | None = None,
    model_configuration_id: UUID | None = None,
    prompt_version_id: UUID | None = None,
) -> EvaluationRun:
    items = await validation_repo.get_dataset_items(session, evaluation_dataset_id=dataset.id)
    if not items:
        raise EmptyDatasetError(f"evaluation_dataset {dataset.id} has no items")

    run = await validation_repo.create_evaluation_run(
        session,
        evaluation_dataset_id=dataset.id,
        configuration_snapshot={"grader_keys": [grader.key for grader in graders]},
        analysis_run_id=analysis_run_id,
        model_configuration_id=model_configuration_id,
        prompt_version_id=prompt_version_id,
    )
    await session.commit()

    results_by_grader: dict[str, list[GraderResult]] = defaultdict(list)
    items_evaluated = 0
    items_failed = 0

    for item in items:
        try:
            candidate_output = await _resolve_candidate_output(session, item)
            if candidate_output is None:
                items_failed += 1
                continue

            context = {
                "existing_citation_object_ids": await _resolve_existing_object_ids(
                    session, candidate_output
                ),
                "citation_object_details": await _resolve_citation_object_details(
                    session, candidate_output
                ),
            }
            for grader in graders:
                result = grader.grade(
                    item.input_snapshot, candidate_output, item.gold_output, context
                )
                results_by_grader[grader.key].append(result)
            items_evaluated += 1
        except Exception as exc:  # noqa: BLE001 — one bad item must not abort the run (EVAL-009)
            items_failed += 1
            logger.warning("evaluation_item_failed", item_id=str(item.id), error=str(exc))

    for grader_key, results in results_by_grader.items():
        sample_count = len(results)
        if sample_count == 0:
            # EVAL-007 — nothing to divide by; skip rather than record a
            # metric with an undefined denominator.
            continue

        pass_rate = sum(1 for r in results if r.passed) / sample_count
        hard_failure_count = sum(1 for r in results if r.hard_failure)
        await validation_repo.set_evaluation_metric(
            session,
            evaluation_run_id=run.id,
            metric_key=f"{grader_key}_pass_rate",
            numeric_value=pass_rate,
            sample_count=sample_count,
            calculation_version=CALCULATION_VERSION,
        )
        await validation_repo.set_evaluation_metric(
            session,
            evaluation_run_id=run.id,
            metric_key=f"{grader_key}_hard_failure_count",
            numeric_value=float(hard_failure_count),
            sample_count=sample_count,
            calculation_version=CALCULATION_VERSION,
        )
        scores = [r.score for r in results if r.score is not None]
        if scores:
            await validation_repo.set_evaluation_metric(
                session,
                evaluation_run_id=run.id,
                metric_key=f"{grader_key}_mean_score",
                numeric_value=sum(scores) / len(scores),
                sample_count=len(scores),
                calculation_version=CALCULATION_VERSION,
            )

    if items_evaluated == 0:
        final_status = EvaluationRunStatus.FAILED
    elif items_failed > 0:
        final_status = EvaluationRunStatus.COMPLETED_WITH_WARNINGS
    else:
        final_status = EvaluationRunStatus.COMPLETED

    await validation_repo.finalize_evaluation_run(
        session,
        run=run,
        status=final_status,
        items_evaluated=items_evaluated,
        items_failed=items_failed,
    )
    await session.commit()
    return run
