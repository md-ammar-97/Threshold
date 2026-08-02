"""DB access for the embedding domain. architecture.md §8.4."""

from typing import cast
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.embedding_models import Embedding, EmbeddingConfiguration
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus

_EMBEDDABLE_QUALITY = (QualityStatus.USABLE, QualityStatus.LOW_INFORMATION)
_SKIPPED_RELEVANCE = (RelevanceStatus.INSUFFICIENT_CONTENT, RelevanceStatus.SPAM_OR_PROMOTION)


async def get_or_create_embedding_configuration(
    session: AsyncSession,
    *,
    version_key: str,
    provider: str,
    model_name: str,
    dimension: int,
    normalization_strategy: str,
    distance_metric: str = "cosine",
) -> EmbeddingConfiguration:
    existing = await session.scalar(
        select(EmbeddingConfiguration).where(EmbeddingConfiguration.version_key == version_key)
    )
    if existing is not None:
        return existing

    config = EmbeddingConfiguration(
        version_key=version_key,
        provider=provider,
        model_name=model_name,
        dimension=dimension,
        distance_metric=distance_metric,
        normalization_strategy=normalization_strategy,
    )
    session.add(config)
    await session.flush()
    return config


async def get_embedding_configuration_by_version_key(
    session: AsyncSession, *, version_key: str
) -> EmbeddingConfiguration | None:
    return await session.scalar(
        select(EmbeddingConfiguration).where(EmbeddingConfiguration.version_key == version_key)
    )


async def get_unembedded_feedback_records(
    session: AsyncSession,
    *,
    embedding_configuration_id: UUID,
    source_connector_id: UUID | None = None,
    limit: int = 500,
) -> list[FeedbackRecord]:
    already_embedded = select(Embedding.object_id).where(
        Embedding.embedding_configuration_id == embedding_configuration_id,
        Embedding.object_type == "feedback_record",
    )
    stmt = (
        select(FeedbackRecord)
        .where(
            FeedbackRecord.id.not_in(already_embedded),
            FeedbackRecord.quality_status.in_(_EMBEDDABLE_QUALITY),
            FeedbackRecord.relevance_status.not_in(_SKIPPED_RELEVANCE),
            FeedbackRecord.deleted_at.is_(None),
        )
        .order_by(FeedbackRecord.created_at)
        .limit(limit)
    )
    if source_connector_id is not None:
        stmt = stmt.where(FeedbackRecord.source_connector_id == source_connector_id)
    return list((await session.scalars(stmt)).all())


async def upsert_embedding(
    session: AsyncSession,
    *,
    embedding_configuration_id: UUID,
    object_type: str,
    object_id: UUID,
    text_variant: str,
    text_checksum: str,
    vector: list[float],
    token_count: int | None = None,
) -> UUID:
    table = cast(Table, Embedding.__table__)
    stmt = (
        pg_insert(table)
        .values(
            embedding_configuration_id=embedding_configuration_id,
            object_type=object_type,
            object_id=object_id,
            text_variant=text_variant,
            text_checksum=text_checksum,
            embedding_vector=vector,
            token_count=token_count,
        )
        .on_conflict_do_nothing(
            index_elements=[
                "embedding_configuration_id",
                "object_type",
                "object_id",
                "text_checksum",
            ]
        )
        .returning(table.c.id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is not None:
        return row[0]

    existing_id = await session.scalar(
        select(table.c.id).where(
            table.c.embedding_configuration_id == embedding_configuration_id,
            table.c.object_type == object_type,
            table.c.object_id == object_id,
            table.c.text_checksum == text_checksum,
        )
    )
    assert existing_id is not None
    return existing_id


async def get_embedded_feedback_records(
    session: AsyncSession,
    *,
    embedding_configuration_id: UUID,
    source_connector_id: UUID | None = None,
    limit: int = 5000,
) -> list[tuple[FeedbackRecord, list[float]]]:
    """Eligible records that already have a current-configuration embedding
    — the input population for clustering."""
    stmt = (
        select(FeedbackRecord, Embedding.embedding_vector)
        .join(
            Embedding,
            (Embedding.object_id == FeedbackRecord.id)
            & (Embedding.object_type == "feedback_record")
            & (Embedding.embedding_configuration_id == embedding_configuration_id),
        )
        .where(
            FeedbackRecord.quality_status.in_(_EMBEDDABLE_QUALITY),
            FeedbackRecord.relevance_status.not_in(_SKIPPED_RELEVANCE),
            FeedbackRecord.deleted_at.is_(None),
        )
        .order_by(FeedbackRecord.created_at)
        .limit(limit)
    )
    if source_connector_id is not None:
        stmt = stmt.where(FeedbackRecord.source_connector_id == source_connector_id)
    result = await session.execute(stmt)
    return [(row[0], list(row[1])) for row in result.all()]


async def get_embeddings_for_records(
    session: AsyncSession, *, embedding_configuration_id: UUID, feedback_record_ids: list[UUID]
) -> dict[UUID, list[float]]:
    if not feedback_record_ids:
        return {}
    stmt = select(Embedding.object_id, Embedding.embedding_vector).where(
        Embedding.embedding_configuration_id == embedding_configuration_id,
        Embedding.object_type == "feedback_record",
        Embedding.object_id.in_(feedback_record_ids),
    )
    result = await session.execute(stmt)
    return {row[0]: list(row[1]) for row in result.all()}
