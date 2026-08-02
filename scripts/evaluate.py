#!/usr/bin/env python
"""CLI entry point for Phase 6 validation — builds evaluation datasets from
real, already-persisted data (generated answers, classified feedback
records, themes) and runs the deterministic grader chain against each,
printing the release-gate decision. "Pipeline mode" per architecture.md
§6.1.

Four suites, all deterministic/no-gold (tiers 1 and 3 —
`validation/graders/base.py`'s own docstring explains why tier 2/gold-
comparison isn't built: `data/evaluation/` is empty by design):
- grounding: citation integrity, demographic inference, causal overclaim,
  insufficient-evidence policy — against real `generated_answer` rows.
- retrieval: cross-version contamination, deleted-object retrieval,
  duplicate evidence — against the same `generated_answer` rows (citations
  *are* the retrieved evidence package).
- classification: unsupported-label rate, demographic inference, low-
  confidence rate — against real classified `feedback_record` rows.
- theme: naming integrity, representative-evidence presence, source
  concentration (per-theme) plus coverage/outlier/overlap/duplicate-
  inflation (theme-set-level, attached to the same run).

Usage:
    python scripts/evaluate.py --limit 50
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from instamart_engine.analysis.models import (  # noqa: E402
    FeedbackAnalysis,
    FeedbackAnalysisStatus,
)
from instamart_engine.core.database import get_session_factory  # noqa: E402
from instamart_engine.research.models import GeneratedAnswer  # noqa: E402
from instamart_engine.themes import repository as theme_repo  # noqa: E402
from instamart_engine.themes.models import Theme  # noqa: E402
from instamart_engine.validation import datasets  # noqa: E402
from instamart_engine.validation import repository as validation_repo  # noqa: E402
from instamart_engine.validation.graders.base import EvalGrader  # noqa: E402
from instamart_engine.validation.graders.citations import CitationIntegrityGrader  # noqa: E402
from instamart_engine.validation.graders.classification import (  # noqa: E402
    DemographicInferenceGrader as ClassificationDemographicInferenceGrader,
)
from instamart_engine.validation.graders.classification import (  # noqa: E402
    LowConfidenceRateGrader,
    UnsupportedLabelGrader,
)
from instamart_engine.validation.graders.grounding import (  # noqa: E402
    CausalOverclaimGrader,
    InsufficientEvidencePolicyGrader,
)
from instamart_engine.validation.graders.privacy import DemographicInferenceGrader  # noqa: E402
from instamart_engine.validation.graders.retrieval import (  # noqa: E402
    CrossVersionContaminationGrader,
    DeletedObjectRetrievalGrader,
    DuplicateEvidenceGrader,
)
from instamart_engine.validation.graders.schema import SchemaIntegrityGrader  # noqa: E402
from instamart_engine.validation.graders.theme_quality import (  # noqa: E402
    RepresentativeEvidenceGrader,
    SourceConcentrationGrader,
    ThemeNamingIntegrityGrader,
)
from instamart_engine.validation.models import EvaluationObjectType, EvaluationType  # noqa: E402
from instamart_engine.validation.release_gates import (  # noqa: E402
    CONFIG_DIR,
    evaluate_release_gates,
    load_release_gate_config,
)
from instamart_engine.validation.runners import run_evaluation  # noqa: E402

_RELEASE_GATE_CONFIG_PATH = CONFIG_DIR / "mvp-v1.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the deterministic evaluation suites.")
    parser.add_argument("--limit", type=int, default=50)
    return parser.parse_args()


async def _run_suite(
    session: AsyncSession,
    *,
    suite_name: str,
    evaluation_type: EvaluationType,
    object_type: EvaluationObjectType,
    object_ids: list,
    input_snapshot_key: str,
    graders: list[EvalGrader],
) -> None:
    print(f"\n=== {suite_name} ===")
    if not object_ids:
        print(f"No real {object_type.value} rows found — skipping.")
        return

    version_key = f"cli-{suite_name}-{datetime.now(UTC):%Y%m%dT%H%M%S%f}"
    dataset = await datasets.create_dataset(
        session,
        version_key=version_key,
        name=f"CLI {suite_name} evaluation",
        evaluation_type=evaluation_type,
        partition="development",
    )
    for object_id in object_ids:
        await datasets.add_item(
            session,
            dataset=dataset,
            object_type=object_type,
            object_id=object_id,
            input_snapshot={input_snapshot_key: str(object_id)},
        )
    await session.commit()
    print(f"[DATASET] id={dataset.id} items={dataset.item_count}")

    run = await run_evaluation(session, dataset=dataset, graders=graders)
    print(
        f"[RUN] id={run.id} status={run.status.value} "
        f"evaluated={run.items_evaluated} failed={run.items_failed}"
    )

    metrics = await validation_repo.get_metrics_for_run(session, evaluation_run_id=run.id)
    for metric in metrics:
        print(f"[METRIC] {metric.metric_key}={metric.numeric_value} (n={metric.sample_count})")

    if suite_name == "theme":
        await _attach_theme_set_metrics(session, run_id=run.id, theme_ids=object_ids)
        metrics = await validation_repo.get_metrics_for_run(session, evaluation_run_id=run.id)

    config = load_release_gate_config(_RELEASE_GATE_CONFIG_PATH)
    decision = evaluate_release_gates(config, metrics)
    print(
        f"[RELEASE GATE] profile={config.release_profile} status={decision.status} "
        f"zero_tolerance_failures={list(decision.zero_tolerance_failures)} "
        f"metric_failures={list(decision.metric_failures)}"
    )


async def _attach_theme_set_metrics(session: AsyncSession, *, run_id, theme_ids: list) -> None:
    """ai_evals.md §30's set-wide numbers (coverage, outlier rate, overlap
    rate, duplicate-inflation) don't fit the per-item grader loop — computed
    once per distinct theme_set among the evaluated themes and attached to
    the same run as the per-theme grader metrics."""
    theme_set_ids: set = set()
    for theme_id in theme_ids:
        theme = await session.get(Theme, theme_id)
        if theme is not None:
            theme_set_ids.add(theme.theme_set_id)

    for theme_set_id in theme_set_ids:
        set_metrics = await theme_repo.compute_theme_set_quality_metrics(
            session, theme_set_id=theme_set_id
        )
        for metric_key, value in (
            ("theme_set_eligible_record_coverage", set_metrics.eligible_record_coverage),
            ("theme_set_outlier_rate", set_metrics.outlier_rate),
            ("theme_set_overlap_rate", set_metrics.overlap_rate),
            ("theme_set_duplicate_inflation_rate", set_metrics.duplicate_inflation_rate),
        ):
            if value is None:
                continue
            await validation_repo.set_evaluation_metric(
                session,
                evaluation_run_id=run_id,
                metric_key=metric_key,
                dimension_key=str(theme_set_id),
                numeric_value=value,
                sample_count=1,
                calculation_version="v1",
            )
    await session.commit()


async def main() -> None:
    args = parse_args()
    session_factory = get_session_factory()

    async with session_factory() as session:
        answer_ids = list(
            (await session.scalars(select(GeneratedAnswer.id).limit(args.limit))).all()
        )
        await _run_suite(
            session,
            suite_name="grounding",
            evaluation_type=EvaluationType.GROUNDING,
            object_type=EvaluationObjectType.GENERATED_ANSWER,
            object_ids=answer_ids,
            input_snapshot_key="generated_answer_id",
            graders=[
                SchemaIntegrityGrader(required_keys=("answer_text", "citation_count")),
                CitationIntegrityGrader(),
                DemographicInferenceGrader(),
                CausalOverclaimGrader(),
                InsufficientEvidencePolicyGrader(),
            ],
        )

        await _run_suite(
            session,
            suite_name="retrieval",
            evaluation_type=EvaluationType.RETRIEVAL,
            object_type=EvaluationObjectType.GENERATED_ANSWER,
            object_ids=answer_ids,
            input_snapshot_key="generated_answer_id",
            graders=[
                CrossVersionContaminationGrader(),
                DeletedObjectRetrievalGrader(),
                DuplicateEvidenceGrader(),
            ],
        )

        classified_record_ids = list(
            (
                await session.scalars(
                    select(FeedbackAnalysis.feedback_record_id)
                    .where(FeedbackAnalysis.status == FeedbackAnalysisStatus.SUCCEEDED)
                    .limit(args.limit)
                )
            ).all()
        )
        await _run_suite(
            session,
            suite_name="classification",
            evaluation_type=EvaluationType.CLASSIFICATION,
            object_type=EvaluationObjectType.FEEDBACK_RECORD,
            object_ids=classified_record_ids,
            input_snapshot_key="feedback_record_id",
            graders=[
                UnsupportedLabelGrader(),
                ClassificationDemographicInferenceGrader(),
                LowConfidenceRateGrader(),
            ],
        )

        theme_ids = list(
            (
                await session.scalars(
                    select(Theme.id).where(Theme.deleted_at.is_(None)).limit(args.limit)
                )
            ).all()
        )
        await _run_suite(
            session,
            suite_name="theme",
            evaluation_type=EvaluationType.THEME,
            object_type=EvaluationObjectType.THEME,
            object_ids=theme_ids,
            input_snapshot_key="theme_id",
            graders=[
                ThemeNamingIntegrityGrader(),
                RepresentativeEvidenceGrader(),
                SourceConcentrationGrader(),
            ],
        )


if __name__ == "__main__":
    asyncio.run(main())
