"""Insight generation via the AI gateway: theme -> insight. architecture.md
§16.2. Deterministic theme metrics (already computed in Phase 3,
`themes.metrics`) are snapshotted onto the insight rather than recomputed or
invented by the model (architecture.md §16.2/§16.4, edgecases.md INS-004,
INS-015) — the model only writes finding/interpretation/evidence citations
over the excerpts and counts it is given.
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai import repository as ai_repo
from instamart_engine.ai.exceptions import AIGatewayError
from instamart_engine.ai.gateway import AIGateway
from instamart_engine.ai.models import ModelConfiguration, PromptVersion
from instamart_engine.ai.prompt_safety import delimit_untrusted_content
from instamart_engine.analysis.demographic_guard import contains_demographic_inference
from instamart_engine.core.config import get_settings
from instamart_engine.core.logging import get_logger
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.insights import repository as insight_repo
from instamart_engine.insights.causal_guard import contains_causal_overclaim
from instamart_engine.insights.models import (
    ConfidenceLevel,
    EvidenceRole,
    InsightSetStatus,
    InsightThemeRelationship,
    InsightType,
)
from instamart_engine.insights.publishability import check_publishability
from instamart_engine.insights.schemas import InsightGenerationOutput
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import ThemeSet

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "insights"
TASK_KEY = "insight_generation"
PROMPT_VERSION_KEY = "v1"
MODEL_CONFIGURATION_NAME = "insight-generation-v1"
MAX_EXCERPT_CHARS = 500
_REDACTED_PLACEHOLDER = "[removed: content violated a generation guardrail]"


@dataclass(frozen=True, slots=True)
class InsightGenerationSummary:
    themes_total: int
    generated: int
    failed: int
    published: int
    blocked: int


async def _ensure_prompt_and_model(
    session: AsyncSession,
) -> tuple[PromptVersion, ModelConfiguration]:
    settings = get_settings()
    system_prompt = (_PROMPTS_DIR / "v1_system.md").read_text(encoding="utf-8")
    user_prompt_template = (_PROMPTS_DIR / "v1_user.md").read_text(encoding="utf-8")

    template = await ai_repo.get_or_create_prompt_template(
        session,
        task_key=TASK_KEY,
        name="Insight Generation",
        description="Synthesizes one research insight from a theme's evidence and metrics.",
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
        model_name=settings.LLM_MODEL_SYNTHESIS,
        task_type="insight_generation",
        temperature=0.2,
        max_output_tokens=1536,
        timeout_seconds=30,
        max_retries=settings.MODEL_MAX_RETRIES,
    )
    return prompt_version, model_configuration


def _build_excerpt_block(
    representatives: list[FeedbackRecord], counterexample: FeedbackRecord | None
) -> str:
    lines = []
    for i, record in enumerate(representatives, start=1):
        excerpt = record.redacted_text[:MAX_EXCERPT_CHARS]
        lines.append(f"[{i}] {excerpt}")
    if counterexample is not None:
        excerpt = counterexample.redacted_text[:MAX_EXCERPT_CHARS]
        lines.append(f"[0 / counterexample] {excerpt}")
    return "\n".join(lines)


def _find_offsets(text: str, excerpt: str) -> tuple[int, int] | None:
    """Mirrors analysis.classify._find_evidence_offsets (edgecases.md CLS-006 /
    INS-016) — reject an unresolved citation rather than store a bad span."""
    if not excerpt:
        return None
    start = text.find(excerpt)
    if start == -1:
        return None
    return start, start + len(excerpt)


def _redact_if_unsafe(field_name: str, text: str | None, *, theme_id: UUID) -> str | None:
    if text is None:
        return None
    if contains_demographic_inference(text):
        logger.warning(
            "insight_demographic_inference_removed", theme_id=str(theme_id), field=field_name
        )
        return _REDACTED_PLACEHOLDER
    if contains_causal_overclaim(text):
        logger.warning(
            "insight_causal_overclaim_detected", theme_id=str(theme_id), field=field_name
        )
    return text


async def generate_insights_for_theme_set(
    session: AsyncSession, *, theme_set_id: UUID, gateway: AIGateway | None = None
) -> InsightGenerationSummary:
    theme_set = await session.get(ThemeSet, theme_set_id)
    if theme_set is None:
        raise ValueError(f"theme_set {theme_set_id} not found")

    prompt_version, model_configuration = await _ensure_prompt_and_model(session)
    gateway = gateway or AIGateway()

    themes = await theme_repo.get_themes_for_set(session, theme_set_id=theme_set_id)
    if not themes:
        return InsightGenerationSummary(
            themes_total=0, generated=0, failed=0, published=0, blocked=0
        )

    insight_set = await insight_repo.create_insight_set(
        session,
        theme_set_id=theme_set_id,
        analysis_run_id=theme_set.analysis_run_id,
        model_configuration_id=model_configuration.id,
        prompt_version_id=prompt_version.id,
    )
    await session.commit()

    generated = 0
    failed = 0
    published = 0
    blocked = 0

    for theme in themes:
        representatives, counterexample = await theme_repo.get_theme_evidence(
            session, theme_id=theme.id
        )
        if not representatives:
            # INS-001 backstop: nothing to cite, so generating would only
            # produce an unpublishable insight — skip rather than waste a call.
            continue

        record_count = await theme_repo.get_theme_membership_count(session, theme_id=theme.id)
        excerpt_block = _build_excerpt_block(representatives, counterexample)

        user_prompt = (
            prompt_version.user_prompt_template.replace("{{THEME_NAME}}", theme.name)
            .replace("{{THEME_SUMMARY}}", theme.short_summary)
            .replace("{{RECORD_COUNT}}", str(record_count))
            .replace(
                "{{OPPORTUNITY_SCORE}}",
                f"{theme.opportunity_score:.2f}"
                if theme.opportunity_score is not None
                else "not yet scored",
            )
            .replace("{{UNTRUSTED_CONTENT}}", delimit_untrusted_content(excerpt_block))
        )

        try:
            parsed, model_call = await gateway.call_structured(
                session,
                prompt_version_id=prompt_version.id,
                prompt_version_key=prompt_version.version_key,
                system_prompt=prompt_version.system_prompt,
                user_prompt=user_prompt,
                model_configuration=model_configuration,
                output_format=InsightGenerationOutput,
                task_type="insight_generation",
                input_object_type="theme",
                input_object_ids=[theme.id],
            )
        except AIGatewayError as exc:
            failed += 1
            logger.warning("insight_generation_failed", theme_id=str(theme.id), error=str(exc))
            continue

        finding = _redact_if_unsafe("finding", parsed.finding, theme_id=theme.id)
        interpretation = _redact_if_unsafe(
            "interpretation", parsed.interpretation, theme_id=theme.id
        )
        affected_context = _redact_if_unsafe(
            "affected_context", parsed.affected_context, theme_id=theme.id
        )
        product_implication = _redact_if_unsafe(
            "product_implication", parsed.product_implication, theme_id=theme.id
        )

        insight = await insight_repo.create_insight(
            session,
            insight_set_id=insight_set.id,
            insight_type=InsightType(parsed.insight_type),
            title=parsed.title,
            finding=finding or parsed.finding,
            interpretation=interpretation or parsed.interpretation,
            affected_context=affected_context,
            product_implication=product_implication,
            validation_recommendation=parsed.validation_recommendation,
            confidence_level=ConfidenceLevel(parsed.confidence_level),
            confidence_score=parsed.confidence_score,
            # Snapshot, not recomputed — datamodel.md §64 "deterministic score
            # snapshot", edgecases.md INS-004/INS-015.
            opportunity_score=theme.opportunity_score,
            score_components=theme.score_components,
            model_call_id=model_call.id,
        )

        await insight_repo.add_insight_theme(
            session,
            insight_id=insight.id,
            theme_id=theme.id,
            relationship_type=InsightThemeRelationship.PRIMARY,
            relevance_score=(
                float(theme.confidence_score) if theme.confidence_score is not None else None
            ),
        )

        records_by_index: dict[int, FeedbackRecord] = dict(enumerate(representatives, start=1))
        if counterexample is not None:
            records_by_index[0] = counterexample

        supporting_evidence_count = 0
        for citation in parsed.evidence:
            record = records_by_index.get(citation.excerpt_number)
            if record is None:
                # INS-016 — the model cited an excerpt number that wasn't offered.
                logger.warning(
                    "insight_evidence_unresolved",
                    theme_id=str(theme.id),
                    excerpt_number=citation.excerpt_number,
                )
                continue
            excerpt = record.redacted_text[:MAX_EXCERPT_CHARS]
            offsets = _find_offsets(record.redacted_text, excerpt)
            evidence_role = EvidenceRole(citation.role)
            await insight_repo.add_insight_evidence(
                session,
                insight_id=insight.id,
                feedback_record_id=record.id,
                evidence_role=evidence_role,
                relevance_score=citation.relevance_score,
                start_offset=offsets[0] if offsets else None,
                end_offset=offsets[1] if offsets else None,
                excerpt_snapshot=excerpt,
            )
            if evidence_role == EvidenceRole.SUPPORTING:
                supporting_evidence_count += 1

        result = check_publishability(
            insight, has_theme_link=True, supporting_evidence_count=supporting_evidence_count
        )
        if result.publishable:
            published += 1
        else:
            blocked += 1
            logger.warning(
                "insight_blocked_from_publication",
                theme_id=str(theme.id),
                insight_id=str(insight.id),
                violated_rules=result.violated_rules,
            )

        await session.commit()
        generated += 1

    # INS-018 — a run with any per-theme failure, or that skipped themes
    # lacking evidence, is a partial result: keep the set as a draft holding
    # only the completed insights rather than marking it as the final,
    # ready-for-review set.
    if generated == 0:
        final_status = InsightSetStatus.REJECTED
    elif failed > 0 or generated < len(themes):
        final_status = InsightSetStatus.DRAFT
    else:
        final_status = InsightSetStatus.READY_FOR_REVIEW

    await insight_repo.finalize_insight_set(
        session, insight_set=insight_set, insight_count=generated, status=final_status
    )
    await session.commit()

    return InsightGenerationSummary(
        themes_total=len(themes),
        generated=generated,
        failed=failed,
        published=published,
        blocked=blocked,
    )
