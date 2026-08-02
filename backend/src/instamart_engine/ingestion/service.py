"""Ingestion orchestration: run a connector, persist raw artifacts and
source items, track checkpoints and run status. architecture.md §10, §11.1.

Connectors are synchronous generators (architecture.md §10.1's literal
protocol); the DB layer is async SQLAlchemy. `_collect_safely` iterates the
generator in a worker thread with a manual next()/try-except so that a
connector-level failure partway through (ING-017) still preserves every
item collected before it, instead of `list(generator)` discarding
everything collected so far on the first exception.
"""

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.core.logging import get_logger
from instamart_engine.ingestion import repository as repo
from instamart_engine.ingestion.models import IngestionRun
from instamart_engine.sources.base import (
    CollectionRequest,
    ConnectorCheckpoint,
    RawSourceItem,
    SourceConfig,
    SourceConnector,
)
from instamart_engine.sources.exceptions import SourceConnectorError
from instamart_engine.sources.models import ConnectorType
from instamart_engine.storage.base import RawArtifactStorage

logger = get_logger(__name__)


def _collect_safely(
    connector: SourceConnector, request: CollectionRequest
) -> list[tuple[RawSourceItem | None, Exception | None]]:
    """Runs entirely inside a worker thread (see `run_ingestion`)."""
    results: list[tuple[RawSourceItem | None, Exception | None]] = []
    iterator = iter(connector.collect(request))
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        except SourceConnectorError as exc:
            results.append((None, exc))
            break
        else:
            results.append((item, None))
    return results


def _item_to_db_fields(item: RawSourceItem) -> dict[str, Any]:
    # media_url/media_type have no dedicated raw_source_item column (kept
    # generic — the canonical, queryable home for them is feedback_record,
    # populated by the feedback pipeline); folded into source_metadata here
    # so raw capture still preserves them faithfully.
    source_metadata = item.source_metadata
    if item.media_url is not None:
        source_metadata = {
            **item.source_metadata,
            "media_url": item.media_url,
            "media_type": item.media_type,
        }
    return {
        "external_parent_id": item.external_parent_id,
        "record_type": item.record_type,
        "source_url": item.source_url,
        "published_at": item.published_at,
        "edited_at": item.edited_at,
        "author_external_id_hash": item.author_external_id_hash,
        "title": item.title,
        "body": item.body,
        "rating": item.rating,
        "rating_scale_max": item.rating_scale_max,
        "engagement_count": item.engagement_count,
        "reply_count": item.reply_count,
        "language_hint": item.language_hint,
        "country_code": item.country_code,
        "app_version": item.app_version,
        "source_metadata": source_metadata,
    }


def _serialize_for_storage(item: RawSourceItem) -> bytes:
    return json.dumps(asdict(item), default=str, sort_keys=True).encode("utf-8")


async def run_ingestion(
    session: AsyncSession,
    *,
    connector: SourceConnector,
    connector_type: ConnectorType,
    connector_key: str,
    connector_display_name: str,
    connector_version: str,
    config_name: str,
    source_config: SourceConfig,
    storage: RawArtifactStorage,
    supports_thread_context: bool = False,
) -> IngestionRun:
    connector_row = await repo.get_or_create_source_connector(
        session,
        key=connector_key,
        display_name=connector_display_name,
        connector_type=connector_type,
        implementation_version=connector_version,
        supports_thread_context=supports_thread_context,
    )

    collection_config = await repo.get_or_create_collection_config(
        session,
        source_connector_id=connector_row.id,
        name=config_name,
        target_identifier=source_config.target_identifier,
        configuration=source_config.configuration,
        default_record_limit=source_config.record_limit,
        default_date_from=source_config.date_from,
        default_date_to=source_config.date_to,
    )

    existing_checkpoint = await repo.get_latest_checkpoint(
        session, source_collection_config_id=collection_config.id
    )
    checkpoint: ConnectorCheckpoint | None = None
    if existing_checkpoint is not None:
        checkpoint = ConnectorCheckpoint(
            checkpoint_type=existing_checkpoint.checkpoint_type,
            checkpoint_value=existing_checkpoint.checkpoint_value,
            is_terminal=existing_checkpoint.is_terminal,
        )

    run = await repo.create_ingestion_run(
        session,
        source_collection_config_id=collection_config.id,
        requested_record_limit=source_config.record_limit,
        date_from=source_config.date_from,
        date_to=source_config.date_to,
        configuration_snapshot={
            "target_identifier": source_config.target_identifier,
            "configuration": source_config.configuration,
        },
    )
    await session.commit()
    # Cached before any commit/rollback below expires these objects'
    # attributes — a bare `.id` access after that point raises
    # `MissingGreenlet` (SQLAlchemy's async ORM can't lazy-refresh an
    # expired attribute outside an awaited session call), which previously
    # crashed the whole ingestion run on the first per-item failure instead
    # of just logging it and moving on.
    run_id = run.id
    collection_config_id = collection_config.id
    connector_row_id = connector_row.id

    request = CollectionRequest(config=source_config, checkpoint=checkpoint)
    results = await asyncio.to_thread(_collect_safely, connector, request)

    discovered = 0
    stored = 0
    failed = 0
    trailing_error: Exception | None = None

    for item, error in results:
        if error is not None:
            trailing_error = error
            continue

        assert item is not None
        discovered += 1
        try:
            content = _serialize_for_storage(item)
            stored_artifact = await asyncio.to_thread(
                storage.save,
                source_key=connector_key,
                ingestion_run_id=str(run_id),
                item_key=item.external_id,
                captured_at=datetime.now(UTC),
                content=content,
            )
            artifact_row = await repo.insert_raw_artifact(
                session,
                ingestion_run_id=run_id,
                storage_backend=stored_artifact.storage_backend,
                storage_key=stored_artifact.storage_key,
                media_type="application/json",
                byte_size=stored_artifact.byte_size,
                sha256=stored_artifact.sha256,
                captured_at=datetime.now(UTC),
                source_url=item.source_url,
            )
            payload_checksum = hashlib.sha256(content).hexdigest()
            await repo.upsert_raw_source_item(
                session,
                raw_artifact_id=artifact_row.id,
                ingestion_run_id=run_id,
                source_connector_id=connector_row_id,
                external_id=item.external_id,
                payload_checksum=payload_checksum,
                fields=_item_to_db_fields(item),
            )
            await session.commit()
            stored += 1
        except Exception as exc:  # noqa: BLE001 — one bad item must not abort the run
            await session.rollback()
            failed += 1
            logger.warning(
                "raw_item_persist_failed",
                external_id=item.external_id,
                run_id=str(run_id),
                error=str(exc),
            )

    if trailing_error is not None:
        failed += 1
        logger.warning(
            "connector_stopped_early",
            run_id=str(run_id),
            error=str(trailing_error),
            retryable=getattr(trailing_error, "retryable", False),
        )

    connector_checkpoint = connector.checkpoint()
    checkpoint_end_value: dict[str, Any] | None = None
    if connector_checkpoint is not None:
        await repo.save_connector_checkpoint(
            session,
            source_collection_config_id=collection_config_id,
            ingestion_run_id=run_id,
            checkpoint_type=connector_checkpoint.checkpoint_type,
            checkpoint_value=connector_checkpoint.checkpoint_value,
            is_terminal=connector_checkpoint.is_terminal,
        )
        checkpoint_end_value = connector_checkpoint.checkpoint_value

    # A total failure (nothing stored) is a run failure; a failure after
    # partial success is recorded as `partially_completed` by finalize_*.
    is_total_failure = trailing_error is not None and stored == 0

    await repo.finalize_ingestion_run(
        session,
        run=run,
        records_discovered=discovered,
        records_stored=stored,
        records_skipped=0,
        records_failed=failed,
        checkpoint_end=checkpoint_end_value,
        failure_code=type(trailing_error).__name__ if is_total_failure else None,
        failure_message=str(trailing_error) if is_total_failure else None,
    )
    await session.commit()
    return run
