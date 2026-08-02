"""Loads real, human-authored gold annotations from a JSONL file into the
existing two-annotator/adjudication system (`annotations.py`, `datasets.py`
— both fully built, previously idle because no gold data existed to load).

Infrastructure only: this module ships with no gold data of its own.
`data/evaluation/` stays empty until a human annotates real examples — see
that directory's README for the file format and why AI-generated "gold"
data would be circular (a model can't validate itself).

Writes gold in two places that must both be kept in sync — a pre-existing
split in this codebase, not introduced here: `EvaluationDatasetItem.gold_output`
(what `runners.py`'s actual grading pipeline reads via `item.gold_output`)
and an adjudicated `Annotation` row (what `annotations.get_gold_output()`
and the two-annotator audit trail read). Loading through this module keeps
both consistent; writing directly to just one silently breaks the other.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.validation import annotations
from instamart_engine.validation import datasets as dataset_service
from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.models import EvaluationObjectType, EvaluationType


class GoldDatasetFormatError(Exception):
    """A line in the input JSONL file is missing a required field or has an
    unrecognized `object_type`."""


_REQUIRED_FIELDS = ("object_type", "object_id", "input_snapshot", "gold_output")


async def load_gold_dataset_from_file(
    session: AsyncSession,
    *,
    file_path: str | Path,
    dataset_version: str,
    dataset_name: str,
    evaluation_type: EvaluationType,
    partition: str = "validation",
    adjudicator_actor_id: UUID | None = None,
) -> int:
    """Reads `file_path` (JSONL — see `data/evaluation/README.md`) and loads
    each row as a gold-annotated `EvaluationDatasetItem`, creating the
    evaluation dataset (get-or-create, by `dataset_version`) and item rows
    as needed. Returns the number of rows loaded.

    Raises `GoldDatasetFormatError` on the first malformed row rather than
    partially loading a bad file — a gold dataset must be trustworthy as a
    whole, not "load what parsed."
    """
    dataset = await validation_repo.get_evaluation_dataset_by_version_key(
        session, version_key=dataset_version
    )
    if dataset is None:
        dataset = await dataset_service.create_dataset(
            session,
            version_key=dataset_version,
            name=dataset_name,
            evaluation_type=evaluation_type,
            partition=partition,
        )

    loaded = 0
    with Path(file_path).open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            row = _parse_row(line, file_path=file_path, line_number=line_number)
            object_type = _parse_object_type(row, file_path=file_path, line_number=line_number)
            object_id = _parse_object_id(row, file_path=file_path, line_number=line_number)
            gold_output = row["gold_output"]
            input_snapshot = row["input_snapshot"]

            item = await validation_repo.get_dataset_item_by_object(
                session,
                evaluation_dataset_id=dataset.id,
                object_type=object_type,
                object_id=object_id,
            )
            if item is None:
                item = await dataset_service.add_item(
                    session,
                    dataset=dataset,
                    object_type=object_type,
                    object_id=object_id,
                    input_snapshot=input_snapshot,
                    gold_output=gold_output,
                    item_metadata=row.get("metadata"),
                )
            else:
                item = await validation_repo.set_dataset_item_gold_output(
                    session, item=item, gold_output=gold_output
                )

            await annotations.adjudicate(
                session,
                evaluation_dataset_item_id=item.id,
                gold_output=gold_output,
                adjudicator_actor_id=adjudicator_actor_id,
                notes=row.get("notes"),
            )
            loaded += 1

    await session.commit()
    return loaded


def _parse_row(line: str, *, file_path: str | Path, line_number: int) -> dict[str, Any]:
    try:
        row = json.loads(line)
    except json.JSONDecodeError as exc:
        raise GoldDatasetFormatError(f"{file_path}:{line_number}: invalid JSON: {exc}") from exc

    # input_snapshot/gold_output may legitimately be an empty dict ({}), so
    # this checks key presence, not truthiness.
    missing = [field for field in _REQUIRED_FIELDS if field not in row]
    if missing:
        raise GoldDatasetFormatError(
            f"{file_path}:{line_number}: missing required field(s): {', '.join(missing)}"
        )
    if not row["object_type"] or not row["object_id"]:
        raise GoldDatasetFormatError(
            f"{file_path}:{line_number}: object_type and object_id must be non-empty"
        )
    return row


def _parse_object_type(
    row: dict[str, Any], *, file_path: str | Path, line_number: int
) -> EvaluationObjectType:
    try:
        return EvaluationObjectType(row["object_type"])
    except ValueError as exc:
        valid = ", ".join(t.value for t in EvaluationObjectType)
        raise GoldDatasetFormatError(
            f"{file_path}:{line_number}: unknown object_type {row['object_type']!r} "
            f"(expected one of: {valid})"
        ) from exc


def _parse_object_id(row: dict[str, Any], *, file_path: str | Path, line_number: int) -> UUID:
    try:
        return UUID(row["object_id"])
    except (ValueError, AttributeError, TypeError) as exc:
        raise GoldDatasetFormatError(
            f"{file_path}:{line_number}: object_id {row['object_id']!r} is not a valid UUID"
        ) from exc
