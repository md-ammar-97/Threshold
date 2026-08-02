"""DB access for the taxonomy domain."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.taxonomy.models import (
    TaxonomyDimension,
    TaxonomyLabel,
    TaxonomyStatus,
    TaxonomyVersion,
)


@dataclass(frozen=True, slots=True)
class TaxonomyLabelInfo:
    id: UUID
    key: str
    definition: str
    parent_label_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class TaxonomyDimensionInfo:
    id: UUID
    key: str
    display_name: str
    labels: list[TaxonomyLabelInfo]


async def get_published_taxonomy(session: AsyncSession) -> TaxonomyVersion:
    # nullslast(): Postgres's default DESC ordering puts NULL first, which
    # would make a version with no published_at set outrank a genuinely
    # newer one — nullslast() ensures a real timestamp always wins.
    version = await session.scalar(
        select(TaxonomyVersion)
        .where(TaxonomyVersion.status == TaxonomyStatus.PUBLISHED)
        .order_by(TaxonomyVersion.published_at.desc().nullslast())
        .limit(1)
    )
    if version is None:
        raise ValueError("No published taxonomy_version found — run load_taxonomy_v3 first")
    return version


async def get_dimensions_with_labels(
    session: AsyncSession, *, taxonomy_version_id: UUID
) -> list[TaxonomyDimensionInfo]:
    dimensions = (
        await session.scalars(
            select(TaxonomyDimension)
            .where(TaxonomyDimension.taxonomy_version_id == taxonomy_version_id)
            .order_by(TaxonomyDimension.sort_order)
        )
    ).all()

    result: list[TaxonomyDimensionInfo] = []
    for dimension in dimensions:
        labels = (
            await session.scalars(
                select(TaxonomyLabel)
                .where(
                    TaxonomyLabel.taxonomy_dimension_id == dimension.id,
                    TaxonomyLabel.is_active.is_(True),
                )
                .order_by(TaxonomyLabel.sort_order)
            )
        ).all()
        result.append(
            TaxonomyDimensionInfo(
                id=dimension.id,
                key=dimension.key,
                display_name=dimension.display_name,
                labels=[
                    TaxonomyLabelInfo(
                        id=label.id,
                        key=label.key,
                        definition=label.definition,
                        parent_label_id=label.parent_label_id,
                    )
                    for label in labels
                ],
            )
        )
    return result
