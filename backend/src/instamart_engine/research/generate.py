"""Grounded answer generation: evidence package -> generated_answer.
architecture.md §17.4-17.5. Deterministic grounding validation
(`research.grounding`) runs on every LLM finding before persistence — the
model proposes findings and citations, it never decides what counts as
supported.
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai import repository as ai_repo
from instamart_engine.ai.gateway import AIGateway
from instamart_engine.ai.models import ModelConfiguration, PromptVersion
from instamart_engine.ai.prompt_safety import delimit_untrusted_content
from instamart_engine.core.config import get_settings
from instamart_engine.feedback.models import QualityEventSeverity
from instamart_engine.insights.models import ConfidenceLevel, InsightType
from instamart_engine.research import grounding
from instamart_engine.research import repository as research_repo
from instamart_engine.research.models import GeneratedAnswer, GroundingStatus
from instamart_engine.research.retrieval import EvidencePackage
from instamart_engine.research.schemas import GeneratedAnswerOutput

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "research" / "answer"
TASK_KEY = "research_answer_generation"
PROMPT_VERSION_KEY = "v1"
MODEL_CONFIGURATION_NAME = "research-answer-v1"

_INSUFFICIENT_EVIDENCE_TEXT = (
    "There is not enough retrieved evidence in the current dataset to answer this "
    "question. Try broadening the question, removing filters, or expanding the "
    "analyzed dataset."
)


@dataclass(frozen=True, slots=True)
class AnswerResult:
    generated_answer: GeneratedAnswer
    grounding_status: GroundingStatus
    warning_count: int


async def _ensure_prompt_and_model(
    session: AsyncSession,
) -> tuple[PromptVersion, ModelConfiguration]:
    settings = get_settings()
    system_prompt = (_PROMPTS_DIR / "v1_system.md").read_text(encoding="utf-8")
    user_prompt_template = (_PROMPTS_DIR / "v1_user.md").read_text(encoding="utf-8")

    template = await ai_repo.get_or_create_prompt_template(
        session,
        task_key=TASK_KEY,
        name="Research Answer Generation",
        description="Generates a grounded, cited answer from a retrieved evidence package.",
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
        model_name=settings.LLM_MODEL_ANSWER,
        task_type="research_answer_generation",
        temperature=0.2,
        max_output_tokens=2048,
        timeout_seconds=45,
        max_retries=settings.MODEL_MAX_RETRIES,
    )
    return prompt_version, model_configuration


async def _persist_insufficient_evidence_answer(
    session: AsyncSession, *, research_question_id: UUID
) -> AnswerResult:
    answer = await research_repo.create_generated_answer(
        session,
        research_question_id=research_question_id,
        model_call_id=None,
        answer_text=_INSUFFICIENT_EVIDENCE_TEXT,
        answer_schema={"answer_text": _INSUFFICIENT_EVIDENCE_TEXT, "findings": []},
        grounding_status=GroundingStatus.PASSED_WITH_WARNINGS,
        grounding_score=None,
        citation_count=0,
        warning_count=1,
        observed_evidence_count=0,
        synthesized_insight_count=0,
        product_hypothesis_count=0,
        limitations=["No evidence matched this question in the current dataset."],
        suggested_validations=[],
    )
    await research_repo.create_answer_warning(
        session,
        generated_answer_id=answer.id,
        warning_type="insufficient_evidence",
        severity=QualityEventSeverity.WARNING,
        message="No evidence was retrieved for this question.",
        details={},
    )
    await session.commit()
    return AnswerResult(
        generated_answer=answer,
        grounding_status=GroundingStatus.PASSED_WITH_WARNINGS,
        warning_count=1,
    )


async def generate_answer(
    session: AsyncSession,
    *,
    research_question_id: UUID,
    question_text: str,
    query_intent: str,
    evidence_package: EvidencePackage,
    gateway: AIGateway | None = None,
) -> AnswerResult:
    if evidence_package.is_empty():
        # ANS-001 — no evidence supports the question: return a deterministic
        # insufficient-evidence answer without spending an LLM call on it.
        return await _persist_insufficient_evidence_answer(
            session, research_question_id=research_question_id
        )

    prompt_version, model_configuration = await _ensure_prompt_and_model(session)
    gateway = gateway or AIGateway()

    evidence_block = grounding.evidence_package_prompt_block(evidence_package)
    user_prompt = (
        prompt_version.user_prompt_template.replace("{{QUESTION_TEXT}}", question_text)
        .replace("{{QUERY_INTENT}}", query_intent)
        .replace("{{UNTRUSTED_CONTENT}}", delimit_untrusted_content(evidence_block))
    )

    parsed, model_call = await gateway.call_structured(
        session,
        prompt_version_id=prompt_version.id,
        prompt_version_key=prompt_version.version_key,
        system_prompt=prompt_version.system_prompt,
        user_prompt=user_prompt,
        model_configuration=model_configuration,
        output_format=GeneratedAnswerOutput,
        task_type="research_answer_generation",
        input_object_type="research_question",
        input_object_ids=[research_question_id],
    )

    answer = await research_repo.create_generated_answer(
        session,
        research_question_id=research_question_id,
        model_call_id=model_call.id,
        answer_text=parsed.answer_text,
        answer_schema=parsed.model_dump(mode="json"),
        grounding_status=GroundingStatus.PENDING,
        grounding_score=None,
        citation_count=0,
        warning_count=0,
        observed_evidence_count=0,
        synthesized_insight_count=0,
        product_hypothesis_count=0,
        limitations=parsed.limitations,
        suggested_validations=parsed.suggested_validations,
    )

    all_warnings: list[grounding.GroundingWarning] = []
    citation_total = 0
    type_counts = {member: 0 for member in InsightType}
    kept_position = 0

    for finding in parsed.findings:
        validated, finding_warnings = grounding.validate_finding(finding, evidence_package)
        all_warnings.extend(finding_warnings)
        if validated.redacted:
            # ANS-019 — a demographic-inference finding is dropped entirely,
            # not merely displayed with a warning label.
            continue

        kept_position += 1
        finding_type = InsightType(validated.finding_type)
        answer_finding = await research_repo.create_answer_finding(
            session,
            generated_answer_id=answer.id,
            position=kept_position,
            finding_type=finding_type,
            statement=validated.statement,
            confidence_level=ConfidenceLevel(validated.confidence_level),
            confidence_score=validated.confidence_score,
            support_status=validated.support_status,
        )
        type_counts[finding_type] += 1

        for citation in validated.citations:
            await research_repo.create_answer_citation(
                session,
                answer_finding_id=answer_finding.id,
                citation_label=citation.label,
                object_type=citation.object_type,
                object_id=citation.item.object_id,
                evidence_role=citation.evidence_role,
                excerpt_snapshot=citation.item.excerpt,
                supports_claim=True,
            )
            citation_total += 1

    for warning in all_warnings:
        await research_repo.create_answer_warning(
            session,
            generated_answer_id=answer.id,
            warning_type=warning.warning_type,
            severity=warning.severity,
            message=warning.message,
            details=warning.details,
        )

    has_error = any(w.severity == QualityEventSeverity.ERROR for w in all_warnings)
    findings_needing_evidence = sum(1 for f in parsed.findings if f.citation_labels)
    coverage_failed = kept_position == 0 and findings_needing_evidence > 0
    if has_error or coverage_failed:
        final_status = GroundingStatus.FAILED
    elif all_warnings:
        final_status = GroundingStatus.PASSED_WITH_WARNINGS
    else:
        final_status = GroundingStatus.PASSED

    # ANS-024 — citation_count/warning_count are always recomputed from the
    # actual persisted rows, never trusted from the model's own output.
    answer.grounding_status = final_status
    answer.citation_count = citation_total
    answer.warning_count = len(all_warnings)
    answer.observed_evidence_count = type_counts[InsightType.OBSERVED_EVIDENCE]
    answer.synthesized_insight_count = type_counts[InsightType.SYNTHESIZED_INSIGHT]
    answer.product_hypothesis_count = type_counts[InsightType.PRODUCT_HYPOTHESIS]
    await session.flush()
    await session.commit()

    return AnswerResult(
        generated_answer=answer, grounding_status=final_status, warning_count=len(all_warnings)
    )
