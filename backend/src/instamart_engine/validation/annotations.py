"""Two-annotator + adjudication workflow. ai_evals.md §7; edgecases.md EVAL-006.

Round 1: independent annotators label the same item without seeing each
other's output. Round 2: disagreements are reviewed. Adjudication: a senior
reviewer's annotation is marked `is_adjudicated` and becomes the item's gold
output — until that happens, the item has no gold output and must be
excluded from gold-comparison metrics (EVAL-006), never silently guessed.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.models import Annotation


async def record_annotation(
    session: AsyncSession,
    *,
    evaluation_dataset_item_id: UUID,
    annotation_round: int,
    annotation_output: dict[str, Any],
    annotator_actor_id: UUID | None = None,
    confidence: float | None = None,
    notes: str | None = None,
) -> Annotation:
    return await validation_repo.create_annotation(
        session,
        evaluation_dataset_item_id=evaluation_dataset_item_id,
        annotation_round=annotation_round,
        annotation_output=annotation_output,
        annotator_actor_id=annotator_actor_id,
        confidence=confidence,
        is_adjudicated=False,
        notes=notes,
    )


async def adjudicate(
    session: AsyncSession,
    *,
    evaluation_dataset_item_id: UUID,
    gold_output: dict[str, Any],
    adjudicator_actor_id: UUID | None = None,
    notes: str | None = None,
) -> Annotation:
    """Records the senior reviewer's decision as the item's gold annotation.
    This does not overwrite Round 1/2 annotations — they remain for
    agreement calculation (ai_evals.md §7.5)."""
    rounds = await validation_repo.get_annotations_for_item(
        session, evaluation_dataset_item_id=evaluation_dataset_item_id
    )
    next_round = (max((a.annotation_round for a in rounds), default=0)) + 1
    return await validation_repo.create_annotation(
        session,
        evaluation_dataset_item_id=evaluation_dataset_item_id,
        annotation_round=next_round,
        annotation_output=gold_output,
        annotator_actor_id=adjudicator_actor_id,
        is_adjudicated=True,
        notes=notes,
    )


async def get_gold_output(
    session: AsyncSession, *, evaluation_dataset_item_id: UUID
) -> dict[str, Any] | None:
    """Returns the adjudicated gold output, or None if adjudication hasn't
    happened yet — callers must treat None as "exclude this item from
    gold-comparison metrics" (EVAL-006), not as an empty/negative label."""
    annotation = await validation_repo.get_adjudicated_annotation(
        session, evaluation_dataset_item_id=evaluation_dataset_item_id
    )
    return annotation.annotation_output if annotation is not None else None
