"""Integration tests for `validation/gold_loader.py` against the live
Postgres — confirms a loaded gold row is readable both ways it's written
(`EvaluationDatasetItem.gold_output`, used by `runners.py`'s grading
pipeline, and the adjudicated `Annotation`, used by
`annotations.get_gold_output()`), and that malformed input fails loudly
rather than partially loading."""

import json
import uuid
from pathlib import Path

import pytest

from instamart_engine.validation import annotations
from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.gold_loader import (
    GoldDatasetFormatError,
    load_gold_dataset_from_file,
)
from instamart_engine.validation.models import EvaluationObjectType, EvaluationType

pytestmark = pytest.mark.asyncio


def _write_jsonl(tmp_path: Path, rows: list[dict]) -> Path:
    file_path = tmp_path / "gold.jsonl"
    file_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return file_path


def _row(*, object_type: str, object_id: str, gold_output: dict, **extra) -> dict:
    return {
        "object_type": object_type,
        "object_id": object_id,
        "input_snapshot": {"question_text": "why do users keep buying the same categories?"},
        "gold_output": gold_output,
        **extra,
    }


async def test_load_creates_dataset_and_item_and_is_readable_both_ways(
    db_session, tmp_path: Path
) -> None:
    object_id = str(uuid.uuid4())
    version = f"test-gold-{uuid.uuid4()}"
    file_path = _write_jsonl(
        tmp_path,
        [_row(object_type="generated_answer", object_id=object_id, gold_output={"score": 1})],
    )

    loaded = await load_gold_dataset_from_file(
        db_session,
        file_path=file_path,
        dataset_version=version,
        dataset_name="Test gold set",
        evaluation_type=EvaluationType.GROUNDING,
    )
    assert loaded == 1

    dataset = await validation_repo.get_evaluation_dataset_by_version_key(
        db_session, version_key=version
    )
    assert dataset is not None
    assert dataset.item_count == 1

    item = await validation_repo.get_dataset_item_by_object(
        db_session,
        evaluation_dataset_id=dataset.id,
        object_type=EvaluationObjectType.GENERATED_ANSWER,
        object_id=uuid.UUID(object_id),
    )
    assert item is not None
    assert item.gold_output == {"score": 1}

    gold_via_annotation = await annotations.get_gold_output(
        db_session, evaluation_dataset_item_id=item.id
    )
    assert gold_via_annotation == {"score": 1}


async def test_reloading_same_object_updates_in_place_not_duplicated(
    db_session, tmp_path: Path
) -> None:
    object_id = str(uuid.uuid4())
    version = f"test-gold-{uuid.uuid4()}"
    first_file = _write_jsonl(
        tmp_path,
        [_row(object_type="generated_answer", object_id=object_id, gold_output={"score": 1})],
    )
    await load_gold_dataset_from_file(
        db_session,
        file_path=first_file,
        dataset_version=version,
        dataset_name="Test gold set",
        evaluation_type=EvaluationType.GROUNDING,
    )

    second_file = _write_jsonl(
        tmp_path,
        [_row(object_type="generated_answer", object_id=object_id, gold_output={"score": 5})],
    )
    loaded = await load_gold_dataset_from_file(
        db_session,
        file_path=second_file,
        dataset_version=version,
        dataset_name="Test gold set",
        evaluation_type=EvaluationType.GROUNDING,
    )
    assert loaded == 1

    dataset = await validation_repo.get_evaluation_dataset_by_version_key(
        db_session, version_key=version
    )
    assert dataset.item_count == 1  # updated, not duplicated

    item = await validation_repo.get_dataset_item_by_object(
        db_session,
        evaluation_dataset_id=dataset.id,
        object_type=EvaluationObjectType.GENERATED_ANSWER,
        object_id=uuid.UUID(object_id),
    )
    assert item.gold_output == {"score": 5}


async def test_invalid_json_line_raises_before_partial_load(db_session, tmp_path: Path) -> None:
    file_path = tmp_path / "gold.jsonl"
    file_path.write_text(
        json.dumps(
            _row(
                object_type="generated_answer",
                object_id=str(uuid.uuid4()),
                gold_output={"score": 1},
            )
        )
        + "\nnot valid json at all",
        encoding="utf-8",
    )

    with pytest.raises(GoldDatasetFormatError):
        await load_gold_dataset_from_file(
            db_session,
            file_path=file_path,
            dataset_version=f"test-gold-{uuid.uuid4()}",
            dataset_name="Test gold set",
            evaluation_type=EvaluationType.GROUNDING,
        )


async def test_missing_required_field_raises(db_session, tmp_path: Path) -> None:
    file_path = tmp_path / "gold.jsonl"
    file_path.write_text(
        json.dumps({"object_type": "generated_answer", "object_id": str(uuid.uuid4())}),
        encoding="utf-8",
    )

    with pytest.raises(GoldDatasetFormatError):
        await load_gold_dataset_from_file(
            db_session,
            file_path=file_path,
            dataset_version=f"test-gold-{uuid.uuid4()}",
            dataset_name="Test gold set",
            evaluation_type=EvaluationType.GROUNDING,
        )


async def test_unknown_object_type_raises(db_session, tmp_path: Path) -> None:
    file_path = _write_jsonl(
        tmp_path,
        [_row(object_type="not_a_real_type", object_id=str(uuid.uuid4()), gold_output={})],
    )

    with pytest.raises(GoldDatasetFormatError):
        await load_gold_dataset_from_file(
            db_session,
            file_path=file_path,
            dataset_version=f"test-gold-{uuid.uuid4()}",
            dataset_name="Test gold set",
            evaluation_type=EvaluationType.GROUNDING,
        )


async def test_invalid_uuid_raises(db_session, tmp_path: Path) -> None:
    file_path = _write_jsonl(
        tmp_path,
        [_row(object_type="generated_answer", object_id="not-a-uuid", gold_output={})],
    )

    with pytest.raises(GoldDatasetFormatError):
        await load_gold_dataset_from_file(
            db_session,
            file_path=file_path,
            dataset_version=f"test-gold-{uuid.uuid4()}",
            dataset_name="Test gold set",
            evaluation_type=EvaluationType.GROUNDING,
        )
