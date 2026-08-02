"""Generic human review workflow. architecture.md §18.3; edgecases.md
REV-004/005/006.

`review_decision` rows are insert-only — nothing here ever mutates or
deletes the object being reviewed or a prior review row, so rejecting or
editing something always creates a new reviewed version rather than
destroying the original model output (REV-006).
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import AnalysisLabel, ReviewStatus
from instamart_engine.taxonomy.repository import get_dimensions_with_labels, get_published_taxonomy
from instamart_engine.validation import repository as validation_repo
from instamart_engine.validation.models import ReviewDecision, ReviewObjectType

# REV-004 — these decisions state a problem with the reviewed object, so a
# bare "no" without an explanation isn't an acceptable review outcome.
_DECISIONS_REQUIRING_REASON = (ReviewStatus.REJECTED, ReviewStatus.NEEDS_SECOND_REVIEW)


class ReviewReasonRequiredError(Exception):
    """REV-004 — a reject/needs-second-review decision must include a reason."""


class InvalidTaxonomyLabelError(Exception):
    """REV-005 — an edit must not introduce a label outside the current taxonomy."""


class MissingPreviousSnapshotError(Exception):
    """REV-006 — a review must capture what it is reviewing, not overwrite blind."""


async def _validate_analysis_label_edit(
    session: AsyncSession, edited_snapshot: dict[str, Any]
) -> None:
    label_key = edited_snapshot.get("label_key")
    dimension_key = edited_snapshot.get("dimension_key")
    if label_key is None or dimension_key is None:
        return

    taxonomy_version = await get_published_taxonomy(session)
    dimensions = await get_dimensions_with_labels(
        session, taxonomy_version_id=taxonomy_version.id
    )
    for dimension in dimensions:
        if dimension.key != dimension_key:
            continue
        if any(label.key == label_key for label in dimension.labels):
            return
        raise InvalidTaxonomyLabelError(
            f"{label_key!r} is not an active label in dimension {dimension_key!r}"
        )
    raise InvalidTaxonomyLabelError(f"{dimension_key!r} is not a taxonomy dimension")


async def submit_review(
    session: AsyncSession,
    *,
    object_type: ReviewObjectType,
    object_id: UUID,
    decision: ReviewStatus,
    previous_snapshot: dict[str, Any],
    edited_snapshot: dict[str, Any] | None = None,
    reviewer_actor_id: UUID | None = None,
    reason_code: str | None = None,
    notes: str | None = None,
) -> ReviewDecision:
    if not previous_snapshot:
        raise MissingPreviousSnapshotError(
            "previous_snapshot is required — a review must record what it evaluated"
        )

    if decision in _DECISIONS_REQUIRING_REASON and not reason_code:
        raise ReviewReasonRequiredError(
            f"reason_code is required when decision={decision.value!r}"
        )

    if (
        object_type == ReviewObjectType.ANALYSIS_LABEL
        and decision == ReviewStatus.EDITED
        and edited_snapshot is not None
    ):
        await _validate_analysis_label_edit(session, edited_snapshot)

    review = await validation_repo.create_review_decision(
        session,
        object_type=object_type,
        object_id=object_id,
        decision=decision,
        previous_snapshot=previous_snapshot,
        edited_snapshot=edited_snapshot,
        reviewer_actor_id=reviewer_actor_id,
        reason_code=reason_code,
        notes=notes,
    )

    # Object types that carry their own `review_status` column must be kept
    # in sync with the decision just recorded — otherwise a reviewed item
    # would never leave the pending-review listing (GET /validation/reviews).
    if object_type == ReviewObjectType.ANALYSIS_LABEL:
        label = await session.get(AnalysisLabel, object_id)
        if label is not None:
            label.review_status = decision
            await session.flush()

    return review
