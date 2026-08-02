"""Query planning: research_question -> query_plan. architecture.md §17.2.

The planner LLM proposes dimensions/intent/filters; `query_filters.validate_filters`
is the deterministic backstop that actually decides what retrieval is allowed
to use (QRY-010/011) — the model's raw output is stored too, so a rejected
filter is auditable, not silently lost.
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai import repository as ai_repo
from instamart_engine.ai.gateway import AIGateway
from instamart_engine.ai.models import ModelConfiguration, PromptVersion
from instamart_engine.ai.prompt_safety import delimit_untrusted_content
from instamart_engine.analysis.schemas import render_taxonomy_reference
from instamart_engine.core.config import get_settings
from instamart_engine.research import query_filters
from instamart_engine.research import repository as research_repo
from instamart_engine.research.models import QueryIntent, QueryPlan
from instamart_engine.research.schemas import QueryPlanOutput
from instamart_engine.sources.models import SourceConnectorModel
from instamart_engine.taxonomy.repository import get_dimensions_with_labels, get_published_taxonomy

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "research" / "planning"
TASK_KEY = "research_query_planning"
PROMPT_VERSION_KEY = "v1"
MODEL_CONFIGURATION_NAME = "research-planning-v1"


@dataclass(frozen=True, slots=True)
class QueryPlanResult:
    query_plan: QueryPlan
    effective_filters: dict[str, str]
    warnings: list[str]


async def _ensure_prompt_and_model(
    session: AsyncSession,
) -> tuple[PromptVersion, ModelConfiguration]:
    settings = get_settings()
    system_prompt = (_PROMPTS_DIR / "v1_system.md").read_text(encoding="utf-8")
    user_prompt_template = (_PROMPTS_DIR / "v1_user.md").read_text(encoding="utf-8")

    template = await ai_repo.get_or_create_prompt_template(
        session,
        task_key=TASK_KEY,
        name="Research Query Planning",
        description="Parses a research question into dimensions, intent, and filters.",
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
        task_type="research_query_planning",
        temperature=0.0,
        max_output_tokens=1024,
        timeout_seconds=30,
        max_retries=settings.MODEL_MAX_RETRIES,
    )
    return prompt_version, model_configuration


async def plan_question(
    session: AsyncSession, *, research_question_id: UUID, question_text: str, gateway: AIGateway
) -> QueryPlanResult:
    prompt_version, model_configuration = await _ensure_prompt_and_model(session)

    taxonomy_version = await get_published_taxonomy(session)
    dimensions = await get_dimensions_with_labels(
        session, taxonomy_version_id=taxonomy_version.id
    )
    taxonomy_reference = render_taxonomy_reference(dimensions)
    source_keys = (
        await session.scalars(
            select(SourceConnectorModel.key).where(SourceConnectorModel.is_enabled.is_(True))
        )
    ).all()

    user_prompt = (
        prompt_version.user_prompt_template.replace("{{SOURCE_KEYS}}", ", ".join(source_keys))
        .replace("{{TAXONOMY_REFERENCE}}", taxonomy_reference)
        .replace("{{UNTRUSTED_CONTENT}}", delimit_untrusted_content(question_text))
    )

    parsed, model_call = await gateway.call_structured(
        session,
        prompt_version_id=prompt_version.id,
        prompt_version_key=prompt_version.version_key,
        system_prompt=prompt_version.system_prompt,
        user_prompt=user_prompt,
        model_configuration=model_configuration,
        output_format=QueryPlanOutput,
        task_type="research_query_planning",
        input_object_type="research_question",
        input_object_ids=[research_question_id],
    )

    raw_filters = parsed.structured_filters.model_dump(exclude_none=True)
    effective_filters, warnings = query_filters.validate_filters(raw_filters)
    combined_warnings = list(parsed.ambiguity_warnings) + warnings

    query_plan = await research_repo.save_query_plan(
        session,
        research_question_id=research_question_id,
        model_call_id=model_call.id,
        research_dimensions=parsed.research_dimensions,
        query_intent=QueryIntent(parsed.query_intent),
        structured_filters=raw_filters,
        retrieval_strategy={
            "stages": [
                "structured_filters",
                "theme_insight_match",
                "hybrid_record_search",
                "rerank",
                "diversity_balance",
                "contradiction_retrieval",
                "context_size_control",
            ]
        },
        ambiguity_warnings=combined_warnings,
        requires_deterministic_aggregation=parsed.requires_deterministic_aggregation,
    )

    return QueryPlanResult(
        query_plan=query_plan, effective_filters=effective_filters, warnings=combined_warnings
    )
