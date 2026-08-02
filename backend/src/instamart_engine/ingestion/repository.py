"""DB access for the source/ingestion domain. Isolates SQLAlchemy usage from
`ingestion/service.py` per architecture.md §8.4."""

from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ingestion.models import (
    ConnectorCheckpointModel,
    IngestionRun,
    IngestionRunStatus,
    RawArtifact,
    RawSourceItem,
    SourceCollectionConfig,
)
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel


async def get_or_create_source_connector(
    session: AsyncSession,
    *,
    key: str,
    display_name: str,
    connector_type: ConnectorType,
    implementation_version: str,
    supports_incremental: bool = False,
    supports_thread_context: bool = False,
) -> SourceConnectorModel:
    existing = await session.scalar(
        select(SourceConnectorModel).where(SourceConnectorModel.key == key)
    )
    if existing is not None:
        return existing

    connector = SourceConnectorModel(
        key=key,
        display_name=display_name,
        connector_type=connector_type,
        implementation_version=implementation_version,
        supports_incremental=supports_incremental,
        supports_thread_context=supports_thread_context,
    )
    session.add(connector)
    await session.flush()
    return connector


async def get_or_create_collection_config(
    session: AsyncSession,
    *,
    source_connector_id: UUID,
    name: str,
    target_identifier: str,
    configuration: dict[str, Any] | None = None,
    default_record_limit: int | None = None,
    default_date_from: date | None = None,
    default_date_to: date | None = None,
) -> SourceCollectionConfig:
    existing = await session.scalar(
        select(SourceCollectionConfig).where(
            SourceCollectionConfig.source_connector_id == source_connector_id,
            SourceCollectionConfig.name == name,
            SourceCollectionConfig.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return existing

    config = SourceCollectionConfig(
        source_connector_id=source_connector_id,
        name=name,
        target_identifier=target_identifier,
        configuration=configuration or {},
        default_record_limit=default_record_limit,
        default_date_from=default_date_from,
        default_date_to=default_date_to,
    )
    session.add(config)
    await session.flush()
    return config


async def get_latest_checkpoint(
    session: AsyncSession, *, source_collection_config_id: UUID
) -> ConnectorCheckpointModel | None:
    return await session.scalar(
        select(ConnectorCheckpointModel)
        .where(ConnectorCheckpointModel.source_collection_config_id == source_collection_config_id)
        .order_by(ConnectorCheckpointModel.created_at.desc())
        .limit(1)
    )


async def create_ingestion_run(
    session: AsyncSession,
    *,
    source_collection_config_id: UUID,
    requested_record_limit: int | None,
    date_from: date | None,
    date_to: date | None,
    configuration_snapshot: dict[str, Any],
) -> IngestionRun:
    run = IngestionRun(
        source_collection_config_id=source_collection_config_id,
        requested_record_limit=requested_record_limit,
        date_from=date_from,
        date_to=date_to,
        configuration_snapshot=configuration_snapshot,
        status=IngestionRunStatus.RUNNING,
        started_at=datetime.now(),
    )
    session.add(run)
    await session.flush()
    return run


async def save_connector_checkpoint(
    session: AsyncSession,
    *,
    source_collection_config_id: UUID,
    ingestion_run_id: UUID,
    checkpoint_type: str,
    checkpoint_value: dict[str, Any],
    is_terminal: bool,
) -> ConnectorCheckpointModel:
    checkpoint = ConnectorCheckpointModel(
        source_collection_config_id=source_collection_config_id,
        ingestion_run_id=ingestion_run_id,
        checkpoint_type=checkpoint_type,
        checkpoint_value=checkpoint_value,
        is_terminal=is_terminal,
    )
    session.add(checkpoint)
    await session.flush()
    return checkpoint


async def insert_raw_artifact(
    session: AsyncSession,
    *,
    ingestion_run_id: UUID,
    storage_backend: str,
    storage_key: str,
    media_type: str,
    byte_size: int,
    sha256: str,
    captured_at: datetime,
    source_url: str | None = None,
) -> RawArtifact:
    artifact = RawArtifact(
        ingestion_run_id=ingestion_run_id,
        storage_backend=storage_backend,
        storage_key=storage_key,
        media_type=media_type,
        byte_size=byte_size,
        sha256=sha256,
        captured_at=captured_at,
        source_url=source_url,
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def upsert_raw_source_item(
    session: AsyncSession,
    *,
    raw_artifact_id: UUID,
    ingestion_run_id: UUID,
    source_connector_id: UUID,
    external_id: str,
    payload_checksum: str,
    fields: dict[str, Any],
) -> tuple[UUID, bool]:
    """Insert or update by (source_connector_id, external_id) (REC-002 — a
    source item that changes at the source gets its latest content, but the
    raw_artifact history is never overwritten, only accumulated).

    Returns (row_id, was_inserted).

    Deliberately targets `RawSourceItem.__table__` (Core), not the mapped
    class: `pg_insert(RawSourceItem)` triggers SQLAlchemy's ORM-enabled bulk
    DML-with-RETURNING sync, which partially populates the identity map
    (only the `.returning()` columns) and leaves any already-identity-mapped
    object's other attributes (e.g. `body`) stale on a subsequent upsert of
    the same row within the same session.
    """
    table = cast(Table, RawSourceItem.__table__)
    stmt = (
        pg_insert(table)
        .values(
            raw_artifact_id=raw_artifact_id,
            ingestion_run_id=ingestion_run_id,
            source_connector_id=source_connector_id,
            external_id=external_id,
            payload_checksum=payload_checksum,
            **fields,
        )
        .on_conflict_do_update(
            index_elements=["source_connector_id", "external_id"],
            set_={
                "raw_artifact_id": raw_artifact_id,
                "ingestion_run_id": ingestion_run_id,
                "payload_checksum": payload_checksum,
                **fields,
            },
            where=(table.c.payload_checksum != payload_checksum),
        )
        .returning(table.c.id, table.c.payload_checksum)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        # Conflict occurred but WHERE excluded it (checksum unchanged) — fetch existing.
        existing_id = await session.scalar(
            select(table.c.id).where(
                table.c.source_connector_id == source_connector_id,
                table.c.external_id == external_id,
            )
        )
        assert existing_id is not None
        return existing_id, False
    return row[0], True


async def finalize_ingestion_run(
    session: AsyncSession,
    *,
    run: IngestionRun,
    records_discovered: int,
    records_stored: int,
    records_skipped: int,
    records_failed: int,
    checkpoint_end: dict[str, Any] | None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> IngestionRun:
    run.records_discovered = records_discovered
    run.records_stored = records_stored
    run.records_skipped = records_skipped
    run.records_failed = records_failed
    run.checkpoint_end = checkpoint_end
    run.completed_at = datetime.now()

    if failure_code is not None:
        run.status = IngestionRunStatus.FAILED
        run.failure_code = failure_code
        run.failure_message = failure_message
    elif records_failed > 0 and records_stored > 0:
        run.status = IngestionRunStatus.PARTIALLY_COMPLETED
    elif records_failed > 0 and records_stored == 0:
        run.status = IngestionRunStatus.FAILED
        run.failure_code = "ALL_ITEMS_FAILED"
    else:
        run.status = IngestionRunStatus.COMPLETED

    await session.flush()
    return run
