"""Integration tests for dataset lifecycle, annotation/adjudication, and
review-decision rules against the live Postgres.
"""

import uuid

import pytest

from instamart_engine.analysis.models import ReviewStatus
from instamart_engine.taxonomy.repository import get_dimensions_with_labels, get_published_taxonomy
from instamart_engine.taxonomy.seed_v1 import load_taxonomy_v1
from instamart_engine.validation import annotations, datasets
from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.models import (
    EvaluationObjectType,
    EvaluationType,
    ReviewObjectType,
)
from instamart_engine.validation.reviews import (
    InvalidTaxonomyLabelError,
    MissingPreviousSnapshotError,
    ReviewReasonRequiredError,
    submit_review,
)

pytestmark = pytest.mark.asyncio


async def test_add_item_to_locked_dataset_raises(db_session) -> None:
    dataset = await datasets.create_dataset(
        db_session,
        version_key=f"test-locked-{uuid.uuid4()}",
        name="Locked test dataset",
        evaluation_type=EvaluationType.GROUNDING,
        partition="development",
    )
    await datasets.lock_dataset(db_session, dataset=dataset)
    await db_session.commit()

    with pytest.raises(datasets.DatasetLockedError):
        await datasets.add_item(
            db_session,
            dataset=dataset,
            object_type=EvaluationObjectType.GENERATED_ANSWER,
            object_id=uuid.uuid4(),
            input_snapshot={"question": "why?"},
        )


async def test_add_item_before_lock_succeeds_and_increments_count(db_session) -> None:
    dataset = await datasets.create_dataset(
        db_session,
        version_key=f"test-draft-{uuid.uuid4()}",
        name="Draft test dataset",
        evaluation_type=EvaluationType.GROUNDING,
        partition="development",
    )
    await datasets.add_item(
        db_session,
        dataset=dataset,
        object_type=EvaluationObjectType.GENERATED_ANSWER,
        object_id=uuid.uuid4(),
        input_snapshot={"question": "why?"},
    )
    await db_session.commit()
    assert dataset.item_count == 1


async def test_submit_review_requires_reason_for_rejection(db_session) -> None:
    with pytest.raises(ReviewReasonRequiredError):
        await submit_review(
            db_session,
            object_type=ReviewObjectType.INSIGHT,
            object_id=uuid.uuid4(),
            decision=ReviewStatus.REJECTED,
            previous_snapshot={"title": "some insight"},
            reason_code=None,
        )


async def test_submit_review_requires_previous_snapshot(db_session) -> None:
    with pytest.raises(MissingPreviousSnapshotError):
        await submit_review(
            db_session,
            object_type=ReviewObjectType.INSIGHT,
            object_id=uuid.uuid4(),
            decision=ReviewStatus.ACCEPTED,
            previous_snapshot={},
        )


async def test_submit_review_rejects_invalid_taxonomy_label_edit(db_session) -> None:
    await load_taxonomy_v1(db_session)
    taxonomy_version = await get_published_taxonomy(db_session)
    dimensions = await get_dimensions_with_labels(
        db_session, taxonomy_version_id=taxonomy_version.id
    )
    real_dimension = dimensions[0]

    with pytest.raises(InvalidTaxonomyLabelError):
        await submit_review(
            db_session,
            object_type=ReviewObjectType.ANALYSIS_LABEL,
            object_id=uuid.uuid4(),
            decision=ReviewStatus.EDITED,
            previous_snapshot={"label_key": real_dimension.labels[0].key},
            edited_snapshot={
                "dimension_key": real_dimension.key,
                "label_key": "not_a_real_label_key",
            },
        )


async def test_submit_review_accepts_valid_taxonomy_label_edit(db_session) -> None:
    await load_taxonomy_v1(db_session)
    taxonomy_version = await get_published_taxonomy(db_session)
    dimensions = await get_dimensions_with_labels(
        db_session, taxonomy_version_id=taxonomy_version.id
    )
    real_dimension = dimensions[0]
    real_label = real_dimension.labels[1]

    review = await submit_review(
        db_session,
        object_type=ReviewObjectType.ANALYSIS_LABEL,
        object_id=uuid.uuid4(),
        decision=ReviewStatus.EDITED,
        previous_snapshot={"label_key": real_dimension.labels[0].key},
        edited_snapshot={"dimension_key": real_dimension.key, "label_key": real_label.key},
    )
    assert review.id is not None
    assert review.decision == ReviewStatus.EDITED


async def test_annotation_adjudication_flow(db_session) -> None:
    dataset = await datasets.create_dataset(
        db_session,
        version_key=f"test-annot-{uuid.uuid4()}",
        name="Annotation test dataset",
        evaluation_type=EvaluationType.CLASSIFICATION,
        partition="development",
    )
    item = await datasets.add_item(
        db_session,
        dataset=dataset,
        object_type=EvaluationObjectType.FEEDBACK_RECORD,
        object_id=uuid.uuid4(),
        input_snapshot={"text": "sample review"},
    )
    await db_session.commit()

    # EVAL-006 -- no gold output before adjudication.
    assert await annotations.get_gold_output(db_session, evaluation_dataset_item_id=item.id) is None

    await annotations.record_annotation(
        db_session,
        evaluation_dataset_item_id=item.id,
        annotation_round=1,
        annotation_output={"relevance": "relevant_user_feedback"},
    )
    await annotations.record_annotation(
        db_session,
        evaluation_dataset_item_id=item.id,
        annotation_round=1,
        annotation_output={"relevance": "irrelevant"},
    )
    await db_session.commit()

    assert await annotations.get_gold_output(db_session, evaluation_dataset_item_id=item.id) is None

    await annotations.adjudicate(
        db_session,
        evaluation_dataset_item_id=item.id,
        gold_output={"relevance": "relevant_user_feedback"},
    )
    await db_session.commit()

    gold = await annotations.get_gold_output(db_session, evaluation_dataset_item_id=item.id)
    assert gold == {"relevance": "relevant_user_feedback"}

    all_rounds = await validation_repo.get_annotations_for_item(
        db_session, evaluation_dataset_item_id=item.id
    )
    assert len(all_rounds) == 3  # 2 round-1 annotations + 1 adjudication
