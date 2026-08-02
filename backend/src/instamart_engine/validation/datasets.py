"""Evaluation dataset lifecycle. ai_evals.md §2.5/§6.1/§82; edgecases.md EVAL-003.

Locked datasets are immutable (datamodel.md §47) — this is the only place
new items are ever added, and it refuses once a dataset is locked rather
than relying on callers to check first.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.models import (
    EvaluationDataset,
    EvaluationDatasetItem,
    EvaluationDatasetStatus,
    EvaluationObjectType,
    EvaluationType,
)


class DatasetLockedError(Exception):
    """EVAL-003 — a locked evaluation dataset must not be mutated."""


async def create_dataset(
    session: AsyncSession,
    *,
    version_key: str,
    name: str,
    evaluation_type: EvaluationType,
    partition: str,
    description: str | None = None,
    taxonomy_version_id: UUID | None = None,
) -> EvaluationDataset:
    """`partition` is one of ai_evals.md §6.1's `development`/`validation`/
    `blind_test` — stored in `selection_method`, not a new enum column, per
    ai_evals.md §82 "store evaluation subtype in metadata rather than
    proliferating enums prematurely"."""
    return await validation_repo.create_evaluation_dataset(
        session,
        version_key=version_key,
        name=name,
        evaluation_type=evaluation_type,
        description=description,
        taxonomy_version_id=taxonomy_version_id,
        selection_method={"partition": partition},
    )


async def add_item(
    session: AsyncSession,
    *,
    dataset: EvaluationDataset,
    object_type: EvaluationObjectType,
    object_id: UUID,
    input_snapshot: dict[str, Any],
    gold_output: dict[str, Any] | None = None,
    item_metadata: dict[str, Any] | None = None,
) -> EvaluationDatasetItem:
    if dataset.status == EvaluationDatasetStatus.LOCKED:
        raise DatasetLockedError(
            f"evaluation_dataset {dataset.id} is locked and cannot accept new items"
        )
    return await validation_repo.add_evaluation_dataset_item(
        session,
        evaluation_dataset_id=dataset.id,
        object_type=object_type,
        object_id=object_id,
        input_snapshot=input_snapshot,
        gold_output=gold_output,
        item_metadata=item_metadata,
    )


async def lock_dataset(session: AsyncSession, *, dataset: EvaluationDataset) -> EvaluationDataset:
    if dataset.status == EvaluationDatasetStatus.LOCKED:
        return dataset
    return await validation_repo.lock_evaluation_dataset(session, dataset=dataset)


def partition_of(dataset: EvaluationDataset) -> str | None:
    return dataset.selection_method.get("partition")


def is_blind_test(dataset: EvaluationDataset) -> bool:
    """ai_evals.md §6.1 — the blind-test partition must never be usable as
    prompt/example content; callers building prompts should check this
    before pulling item text into a prompt template."""
    return partition_of(dataset) == "blind_test"
