"""Theme naming and summarization via the AI gateway. architecture.md §15.2
steps "select representative/contradictory evidence" -> "LLM naming".
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai import repository as ai_repo
from instamart_engine.ai.exceptions import AIGatewayError
from instamart_engine.ai.gateway import AIGateway
from instamart_engine.ai.prompt_safety import delimit_untrusted_content
from instamart_engine.core.config import get_settings
from instamart_engine.core.logging import get_logger
from instamart_engine.feedback.models import FeedbackRecord
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import ThemeType
from instamart_engine.themes.schemas import THEME_TYPE_VALUES, ThemeSynthesisOutput

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "themes"
TASK_KEY = "theme_synthesis"
PROMPT_VERSION_KEY = "v1"
MODEL_CONFIGURATION_NAME = "theme-synthesis-v1"
MAX_EXCERPT_CHARS = 500


@dataclass(frozen=True, slots=True)
class SynthesisSummary:
    themes_total: int
    synthesized: int
    failed: int


async def _ensure_prompt_and_model(session: AsyncSession):
    settings = get_settings()
    system_prompt = (_PROMPTS_DIR / "v1_system.md").read_text(encoding="utf-8")
    user_prompt_template = (_PROMPTS_DIR / "v1_user.md").read_text(encoding="utf-8")

    template = await ai_repo.get_or_create_prompt_template(
        session,
        task_key=TASK_KEY,
        name="Theme Synthesis",
        description="Names and summarizes a cluster of similar feedback records.",
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
        task_type="theme_synthesis",
        temperature=0.2,
        max_output_tokens=1024,
        timeout_seconds=30,
        max_retries=settings.MODEL_MAX_RETRIES,
    )
    return prompt_version, model_configuration


def _build_evidence_block(
    representatives: list[FeedbackRecord], counterexample: FeedbackRecord | None
) -> str:
    lines = []
    for i, record in enumerate(representatives, start=1):
        excerpt = record.redacted_text[:MAX_EXCERPT_CHARS]
        lines.append(f"[{i}] {excerpt}")
    if counterexample is not None:
        excerpt = counterexample.redacted_text[:MAX_EXCERPT_CHARS]
        lines.append(f"[counterexample] {excerpt}")
    return "\n".join(lines)


async def synthesize_theme_set(
    session: AsyncSession, *, theme_set_id: UUID, gateway: AIGateway | None = None
) -> SynthesisSummary:
    prompt_version, model_configuration = await _ensure_prompt_and_model(session)
    gateway = gateway or AIGateway()

    themes = await theme_repo.get_themes_for_set(session, theme_set_id=theme_set_id)
    if not themes:
        return SynthesisSummary(themes_total=0, synthesized=0, failed=0)

    synthesized = 0
    failed = 0

    for theme in themes:
        representatives, counterexample = await theme_repo.get_theme_evidence(
            session, theme_id=theme.id
        )
        total_count = await theme_repo.get_theme_membership_count(session, theme_id=theme.id)
        evidence_block = _build_evidence_block(representatives, counterexample)

        user_prompt = (
            prompt_version.user_prompt_template.replace(
                "{{THEME_TYPES}}", ", ".join(THEME_TYPE_VALUES)
            )
            .replace("{{REPRESENTATIVE_COUNT}}", str(len(representatives)))
            .replace("{{TOTAL_COUNT}}", str(total_count))
            .replace("{{UNTRUSTED_CONTENT}}", delimit_untrusted_content(evidence_block))
        )

        try:
            parsed, model_call = await gateway.call_structured(
                session,
                prompt_version_id=prompt_version.id,
                prompt_version_key=prompt_version.version_key,
                system_prompt=prompt_version.system_prompt,
                user_prompt=user_prompt,
                model_configuration=model_configuration,
                output_format=ThemeSynthesisOutput,
                task_type="theme_synthesis",
                input_object_type="theme",
                input_object_ids=[theme.id],
            )
        except AIGatewayError as exc:
            failed += 1
            logger.warning("theme_synthesis_failed", theme_id=str(theme.id), error=str(exc))
            continue

        await theme_repo.update_theme_synthesis(
            session,
            theme=theme,
            name=parsed.name,
            short_summary=parsed.short_summary,
            long_summary=parsed.long_summary,
            theme_type=ThemeType(parsed.theme_type),
            confidence_score=parsed.confidence_score,
            model_call_id=model_call.id,
        )
        await session.commit()
        synthesized += 1

    return SynthesisSummary(themes_total=len(themes), synthesized=synthesized, failed=failed)
