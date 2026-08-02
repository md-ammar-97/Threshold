"""Classification orchestration: feedback_record -> feedback_analysis.

architecture.md §13 / context.md §13 Step 2. Uses only the supplied text;
the system prompt (prompts/classification/v1_system.md) forbids demographic
inference, and `demographic_guard` is the deterministic backstop (CLS-017).
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai import repository as ai_repo
from instamart_engine.ai.exceptions import AIGatewayError
from instamart_engine.ai.gateway import AIGateway
from instamart_engine.ai.models import ModelConfiguration, PromptVersion
from instamart_engine.ai.prompt_safety import delimit_untrusted_content
from instamart_engine.analysis import repository as analysis_repo
from instamart_engine.analysis.demographic_guard import contains_demographic_inference
from instamart_engine.analysis.models import AnalysisRun, FeedbackAnalysisStatus
from instamart_engine.analysis.schemas import (
    build_classification_output_model,
    build_topic_output_model,
    render_taxonomy_reference,
)
from instamart_engine.core.config import get_settings
from instamart_engine.core.logging import get_logger
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.taxonomy.repository import (
    TaxonomyDimensionInfo,
    get_dimensions_with_labels,
    get_published_taxonomy,
)

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "classification"
TASK_KEY = "feedback_classification"
PROMPT_VERSION_KEY = "v1"
MODEL_CONFIGURATION_NAME = "classification-v1"

# Topic classification (topic_main/topic_sub) runs as a separate, second
# call per record rather than being merged into the dimensions above — the
# topic taxonomy is large enough (~150 labels) that folding it into the
# primary call would roughly triple that call's prompt/schema size, and this
# system has already hit Groq's free-tier TPM rate limit on the smaller,
# original taxonomy. A second bounded call keeps the shipped classifier's
# size completely unchanged and isolates the new taxonomy's cost/risk.
_TOPIC_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "topics"
TOPIC_TASK_KEY = "feedback_topic_classification"
TOPIC_PROMPT_VERSION_KEY = "v1"
TOPIC_MODEL_CONFIGURATION_NAME = "topic-classification-v1"
_TOPIC_DIMENSION_KEYS = (
    "topic_main",
    "topic_sub",
    "discovery_mechanism",
    "experimentation_propensity",
)


@dataclass(frozen=True, slots=True)
class ClassificationSummary:
    selected: int
    classified: int
    failed: int


async def ensure_classification_prompt_and_model(
    session: AsyncSession,
) -> tuple[PromptVersion, ModelConfiguration]:
    settings = get_settings()
    system_prompt = (_PROMPTS_DIR / "v1_system.md").read_text(encoding="utf-8")
    user_prompt_template = (_PROMPTS_DIR / "v1_user.md").read_text(encoding="utf-8")

    template = await ai_repo.get_or_create_prompt_template(
        session,
        task_key=TASK_KEY,
        name="Feedback Classification",
        description="Classifies one feedback record against the research taxonomy.",
    )
    prompt_version = await ai_repo.get_or_create_prompt_version(
        session,
        prompt_template_id=template.id,
        version_key=PROMPT_VERSION_KEY,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
    )
    model_configuration = await ai_repo.get_or_create_model_configuration(
        session,
        name=MODEL_CONFIGURATION_NAME,
        provider=settings.LLM_PROVIDER,
        model_name=settings.LLM_MODEL_CLASSIFICATION,
        task_type="classification",
        temperature=0.0,
        max_output_tokens=2048,
        timeout_seconds=30,
        max_retries=settings.MODEL_MAX_RETRIES,
    )
    return prompt_version, model_configuration


async def ensure_topic_classification_prompt_and_model(
    session: AsyncSession,
) -> tuple[PromptVersion, ModelConfiguration]:
    settings = get_settings()
    system_prompt = (_TOPIC_PROMPTS_DIR / "v1_system.md").read_text(encoding="utf-8")
    user_prompt_template = (_TOPIC_PROMPTS_DIR / "v1_user.md").read_text(encoding="utf-8")

    template = await ai_repo.get_or_create_prompt_template(
        session,
        task_key=TOPIC_TASK_KEY,
        name="Feedback Topic Classification",
        description="Classifies one feedback record against the topic_main/topic_sub "
        "subject-matter taxonomy, separately from the main taxonomy dimensions.",
    )
    prompt_version = await ai_repo.get_or_create_prompt_version(
        session,
        prompt_template_id=template.id,
        version_key=TOPIC_PROMPT_VERSION_KEY,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
    )
    model_configuration = await ai_repo.get_or_create_model_configuration(
        session,
        name=TOPIC_MODEL_CONFIGURATION_NAME,
        provider=settings.LLM_PROVIDER,
        model_name=settings.LLM_MODEL_CLASSIFICATION,
        task_type="feedback_topic_classification",
        temperature=0.0,
        max_output_tokens=1024,
        timeout_seconds=30,
        max_retries=settings.MODEL_MAX_RETRIES,
    )
    return prompt_version, model_configuration


def _find_evidence_offsets(text: str, excerpt: str) -> tuple[int, int] | None:
    """CLS-006 — reject the span rather than store an invalid one."""
    if not excerpt:
        return None
    start = text.find(excerpt)
    if start == -1:
        return None
    return start, start + len(excerpt)


async def _persist_labels_for_dimensions(
    session: AsyncSession,
    *,
    record: FeedbackRecord,
    analysis_id: UUID,
    parsed: BaseModel,
    dimensions: list[TaxonomyDimensionInfo],
) -> None:
    """Inserts `analysis_label`/`evidence_span` rows for every dimension in
    `dimensions` against an existing `feedback_analysis` row. Shared by the
    primary classification call and the separate topic_main/topic_sub call
    so both label sets attach to the same analysis record."""
    data = parsed.model_dump()
    label_lookup = {
        dimension.key: {label.key: label.id for label in dimension.labels}
        for dimension in dimensions
    }
    dimension_id_lookup = {dimension.key: dimension.id for dimension in dimensions}

    for dimension_key, label_ids_by_key in label_lookup.items():
        for item in data.get(dimension_key, []):
            if contains_demographic_inference(item.get("evidence_excerpt", "")):
                logger.warning(
                    "demographic_inference_removed",
                    feedback_record_id=str(record.id),
                    stage=dimension_key,
                )
                continue

            label_key = item["label"]
            taxonomy_label_id = label_ids_by_key.get(label_key)
            if taxonomy_label_id is None:
                # TAX-007 — the schema should have already prevented this,
                # but never trust a label key that isn't in this taxonomy.
                logger.warning(
                    "unknown_label_rejected", feedback_record_id=str(record.id), label=label_key
                )
                continue

            analysis_label = await analysis_repo.insert_analysis_label(
                session,
                feedback_analysis_id=analysis_id,
                taxonomy_dimension_id=dimension_id_lookup[dimension_key],
                taxonomy_label_id=taxonomy_label_id,
                confidence=item["confidence"],
            )

            offsets = _find_evidence_offsets(
                record.normalized_text, item.get("evidence_excerpt", "")
            )
            if offsets is not None:
                await analysis_repo.insert_evidence_span(
                    session,
                    analysis_label_id=analysis_label.id,
                    feedback_record_id=record.id,
                    excerpt_snapshot=item["evidence_excerpt"],
                    start_offset=offsets[0],
                    end_offset=offsets[1],
                    support_strength=item["confidence"],
                )


async def _persist_classification(
    session: AsyncSession,
    *,
    record: FeedbackRecord,
    analysis_run_id: UUID,
    taxonomy_version_id: UUID,
    model_call_id: UUID,
    parsed: BaseModel,
    dimensions: list[TaxonomyDimensionInfo],
) -> UUID:
    data = parsed.model_dump()

    summary = data.get("summary", "")
    if contains_demographic_inference(summary):
        logger.warning(
            "demographic_inference_removed", feedback_record_id=str(record.id), stage="summary"
        )
        summary = "[summary removed: contained a possible demographic inference]"

    analysis = await analysis_repo.insert_feedback_analysis(
        session,
        feedback_record_id=record.id,
        analysis_run_id=analysis_run_id,
        taxonomy_version_id=taxonomy_version_id,
        model_call_id=model_call_id,
        status=FeedbackAnalysisStatus.SUCCEEDED,
        overall_confidence=data.get("overall_confidence"),
        sentiment_score=data.get("sentiment_score"),
        sentiment_confidence=data.get("sentiment_confidence"),
        severity_value=data.get("severity_value"),
        severity_confidence=data.get("severity_confidence"),
        summary=summary,
    )

    await _persist_labels_for_dimensions(
        session, record=record, analysis_id=analysis.id, parsed=parsed, dimensions=dimensions
    )
    return analysis.id


async def classify_unclassified_records(
    session: AsyncSession,
    *,
    limit: int = 50,
    gateway: AIGateway | None = None,
    source_connector_id: UUID | None = None,
    analysis_run: AnalysisRun | None = None,
) -> ClassificationSummary:
    taxonomy_version = await get_published_taxonomy(session)
    all_dimensions = await get_dimensions_with_labels(
        session, taxonomy_version_id=taxonomy_version.id
    )
    # Topic classification (topic_main/topic_sub) is a separate call — see
    # the module-level comment on _TOPIC_DIMENSION_KEYS — so it's excluded
    # from the primary call's dimensions/schema entirely.
    dimensions = [d for d in all_dimensions if d.key not in _TOPIC_DIMENSION_KEYS]
    topic_dimensions = [d for d in all_dimensions if d.key in _TOPIC_DIMENSION_KEYS]
    taxonomy_reference = render_taxonomy_reference(dimensions)
    output_model = build_classification_output_model(dimensions)

    prompt_version, model_configuration = await ensure_classification_prompt_and_model(session)
    topic_prompt_version: PromptVersion | None = None
    topic_model_configuration: ModelConfiguration | None = None
    topic_output_model: type[BaseModel] | None = None
    topic_taxonomy_reference = ""
    if topic_dimensions:
        topic_prompt_version, topic_model_configuration = (
            await ensure_topic_classification_prompt_and_model(session)
        )
        topic_output_model = build_topic_output_model(topic_dimensions)
        topic_taxonomy_reference = render_taxonomy_reference(topic_dimensions)

    records = await analysis_repo.get_unclassified_feedback_records(
        session, source_connector_id=source_connector_id, limit=limit
    )
    if not records:
        return ClassificationSummary(selected=0, classified=0, failed=0)

    # A caller running the full pipeline (scripts/pipeline.py) passes one
    # shared AnalysisRun through classify -> embed -> cluster so that
    # research retrieval's FeedbackAnalysis.analysis_run_id join (scoped to
    # the theme set's run) actually matches these classifications instead of
    # finding zero records (F-9). Standalone callers (scripts/classify.py)
    # still get their own run, unchanged.
    if analysis_run is None:
        analysis_run = await analysis_repo.create_analysis_run(
            session,
            name=f"classification-{taxonomy_version.version_key}",
            taxonomy_version_id=taxonomy_version.id,
            classification_model_configuration_id=model_configuration.id,
            dataset_snapshot={"record_count": len(records)},
        )
        await session.commit()

    gateway = gateway or AIGateway()
    classified = 0
    failed = 0

    # The taxonomy reference is the same for every record in this run; only
    # the untrusted feedback text changes per record.
    user_prompt_with_taxonomy = prompt_version.user_prompt_template.replace(
        "{{TAXONOMY_REFERENCE}}", taxonomy_reference
    )
    topic_user_prompt_with_taxonomy = (
        topic_prompt_version.user_prompt_template.replace(
            "{{TAXONOMY_REFERENCE}}", topic_taxonomy_reference
        )
        if topic_prompt_version is not None
        else None
    )

    for record in records:
        user_prompt = user_prompt_with_taxonomy.replace(
            "{{UNTRUSTED_CONTENT}}", delimit_untrusted_content(record.redacted_text)
        )

        try:
            parsed, model_call = await gateway.call_structured(
                session,
                prompt_version_id=prompt_version.id,
                prompt_version_key=prompt_version.version_key,
                system_prompt=prompt_version.system_prompt,
                user_prompt=user_prompt,
                model_configuration=model_configuration,
                output_format=output_model,
                task_type="classification",
                analysis_run_id=analysis_run.id,
                input_object_type="feedback_record",
                input_object_ids=[record.id],
            )
        except AIGatewayError as exc:
            failed += 1
            logger.warning(
                "classification_failed", feedback_record_id=str(record.id), error=str(exc)
            )
            await analysis_repo.insert_feedback_analysis(
                session,
                feedback_record_id=record.id,
                analysis_run_id=analysis_run.id,
                taxonomy_version_id=taxonomy_version.id,
                model_call_id=None,
                status=FeedbackAnalysisStatus.FAILED,
                overall_confidence=None,
                sentiment_score=None,
                sentiment_confidence=None,
                severity_value=None,
                severity_confidence=None,
                summary=None,
            )
            await session.commit()
            continue

        analysis_id = await _persist_classification(
            session,
            record=record,
            analysis_run_id=analysis_run.id,
            taxonomy_version_id=taxonomy_version.id,
            model_call_id=model_call.id,
            parsed=parsed,
            dimensions=dimensions,
        )
        await session.commit()
        classified += 1

        # Topic classification failing never undoes the primary
        # classification above — it's logged and skipped, not raised.
        if topic_dimensions and topic_user_prompt_with_taxonomy is not None:
            topic_user_prompt = topic_user_prompt_with_taxonomy.replace(
                "{{UNTRUSTED_CONTENT}}", delimit_untrusted_content(record.redacted_text)
            )
            try:
                topic_parsed, _topic_model_call = await gateway.call_structured(
                    session,
                    prompt_version_id=topic_prompt_version.id,
                    prompt_version_key=topic_prompt_version.version_key,
                    system_prompt=topic_prompt_version.system_prompt,
                    user_prompt=topic_user_prompt,
                    model_configuration=topic_model_configuration,
                    output_format=topic_output_model,
                    task_type=TOPIC_TASK_KEY,
                    analysis_run_id=analysis_run.id,
                    input_object_type="feedback_record",
                    input_object_ids=[record.id],
                )
            except AIGatewayError as exc:
                logger.warning(
                    "topic_classification_failed",
                    feedback_record_id=str(record.id),
                    error=str(exc),
                )
            else:
                await _persist_labels_for_dimensions(
                    session,
                    record=record,
                    analysis_id=analysis_id,
                    parsed=topic_parsed,
                    dimensions=topic_dimensions,
                )
                await session.commit()

    await analysis_repo.finalize_analysis_run(
        session,
        run=analysis_run,
        records_selected=len(records),
        records_classified=classified,
        records_failed=failed,
    )
    await session.commit()

    return ClassificationSummary(selected=len(records), classified=classified, failed=failed)
