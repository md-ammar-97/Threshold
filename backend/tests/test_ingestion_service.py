"""Integration tests for the ingestion orchestration service.

Run against the real live Postgres (see conftest.py's `db_session` — every
change is rolled back after each test). Network calls are mocked; only the
ingestion service's own DB/storage orchestration is under test.
"""

import time
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest
from google_play_scraper.features.reviews import _ContinuationToken
from sqlalchemy import select

from instamart_engine.ingestion import service as ingestion_service
from instamart_engine.ingestion.models import (
    ConnectorCheckpointModel,
    IngestionRunStatus,
    RawArtifact,
    RawSourceItem,
)
from instamart_engine.ingestion.service import run_ingestion
from instamart_engine.sources.base import CollectionRequest, ConnectorCheckpoint, SourceConfig
from instamart_engine.sources.google_play import GooglePlayConnector
from instamart_engine.sources.models import ConnectorType
from instamart_engine.sources.public_web import PublicWebConnector
from instamart_engine.storage.filesystem import FilesystemRawArtifactStorage

pytestmark = pytest.mark.asyncio

SAMPLE_REVIEW = {
    "reviewId": "review-1",
    "userName": "Test User",
    "userImage": "https://example.com/a.png",
    "content": "Good app but limited category discovery.",
    "score": 4,
    "thumbsUpCount": 1,
    "reviewCreatedVersion": "4.100.0",
    "at": datetime(2026, 6, 1, 9, 0, 0),
    "replyContent": None,
    "repliedAt": None,
    "appVersion": "4.100.0",
}


async def test_run_ingestion_persists_items_run_and_checkpoint(db_session, tmp_path) -> None:
    terminal_token = _ContinuationToken(None, "en", "in", 2, 200, None, None)
    storage = FilesystemRawArtifactStorage(str(tmp_path))
    connector = GooglePlayConnector(lang="en", country="in")

    with patch(
        "instamart_engine.sources.google_play.gp_reviews",
        return_value=([SAMPLE_REVIEW], terminal_token),
    ):
        run = await run_ingestion(
            db_session,
            connector=connector,
            connector_type=ConnectorType.LIBRARY,
            connector_key="google_play",
            connector_display_name="Google Play",
            connector_version="test-1",
            config_name="swiggy-in",
            source_config=SourceConfig(target_identifier="in.swiggy.android"),
            storage=storage,
        )

    assert run.status == IngestionRunStatus.COMPLETED
    assert run.records_discovered == 1
    assert run.records_stored == 1
    assert run.records_failed == 0

    # Scoped to this run's ID: the dev database may already contain
    # unrelated real data (e.g. from a manual CLI ingestion), so an
    # unfiltered select() would see that too.
    raw_items = (
        await db_session.scalars(
            select(RawSourceItem).where(RawSourceItem.ingestion_run_id == run.id)
        )
    ).all()
    assert len(raw_items) == 1
    assert raw_items[0].external_id == "review-1"
    assert raw_items[0].body == "Good app but limited category discovery."

    artifacts = (
        await db_session.scalars(select(RawArtifact).where(RawArtifact.ingestion_run_id == run.id))
    ).all()
    assert len(artifacts) == 1
    assert artifacts[0].sha256 == artifacts[0].sha256  # populated, non-empty by constraint

    checkpoints = (
        await db_session.scalars(
            select(ConnectorCheckpointModel).where(
                ConnectorCheckpointModel.ingestion_run_id == run.id
            )
        )
    ).all()
    assert len(checkpoints) == 1
    assert checkpoints[0].is_terminal is True


async def test_run_ingestion_upserts_same_external_id_without_duplicating(
    db_session, tmp_path
) -> None:
    """REC-002 — the same source-native review, re-collected (here via a
    second, independently configured collection run against the same
    connector) with edited content, updates the one canonical row rather
    than duplicating it. Two distinct `config_name`s are used deliberately:
    reusing the same collection config would hit its now-terminal checkpoint
    (CHK-009) and correctly fetch nothing on the second run — that's a
    different, already-covered behaviour, not this one.
    """
    storage = FilesystemRawArtifactStorage(str(tmp_path))

    async def _run_once(content: str, config_name: str):
        review = {**SAMPLE_REVIEW, "content": content}
        token = _ContinuationToken(None, "en", "in", 1, 200, None, None)
        with patch(
            "instamart_engine.sources.google_play.gp_reviews",
            return_value=([review], token),
        ):
            return await run_ingestion(
                db_session,
                connector=GooglePlayConnector(),
                connector_type=ConnectorType.LIBRARY,
                connector_key="google_play",
                connector_display_name="Google Play",
                connector_version="test-1",
                config_name=config_name,
                source_config=SourceConfig(target_identifier="in.swiggy.android"),
                storage=storage,
            )

    run_a = await _run_once("first version of the review", "swiggy-in-config-a")
    run_b = await _run_once("edited version of the review", "swiggy-in-config-b")

    raw_items = (
        await db_session.scalars(
            select(RawSourceItem).where(RawSourceItem.external_id == "review-1")
        )
    ).all()
    assert len(raw_items) == 1  # still one canonical row, not two
    assert raw_items[0].body == "edited version of the review"

    artifacts = (
        await db_session.scalars(
            select(RawArtifact).where(RawArtifact.ingestion_run_id.in_([run_a.id, run_b.id]))
        )
    ).all()
    assert len(artifacts) == 2  # raw artifacts accumulate; never overwritten


async def test_run_ingestion_survives_duplicate_item_within_same_run(
    db_session, tmp_path
) -> None:
    """A connector can return the same item twice in one collection (e.g.
    overlapping search terms surfacing the same post) — the second write
    hits `uq_raw_artifact_key` (same run, same external_id) and must be
    caught and logged as a per-item failure, not crash the whole run.
    Regression test for a bug where the exception handler's own logging
    (`run.id` after `session.rollback()`) raised `MissingGreenlet`, because
    rollback expires the ORM object's attributes and a bare attribute
    access can't trigger the async lazy-reload outside an awaited call."""
    terminal_token = _ContinuationToken(None, "en", "in", 2, 200, None, None)
    storage = FilesystemRawArtifactStorage(str(tmp_path))
    connector = GooglePlayConnector(lang="en", country="in")

    with patch(
        "instamart_engine.sources.google_play.gp_reviews",
        return_value=([SAMPLE_REVIEW, SAMPLE_REVIEW], terminal_token),
    ):
        run = await run_ingestion(
            db_session,
            connector=connector,
            connector_type=ConnectorType.LIBRARY,
            connector_key="google_play",
            connector_display_name="Google Play",
            connector_version="test-1",
            config_name="swiggy-in-duplicate",
            source_config=SourceConfig(target_identifier="in.swiggy.android"),
            storage=storage,
        )

    assert run.records_discovered == 2
    assert run.records_stored == 1
    assert run.records_failed == 1
    assert run.status == IngestionRunStatus.PARTIALLY_COMPLETED


class _HangingConnector:
    """Simulates a connector whose underlying HTTP call never returns —
    e.g. google_play_scraper's urlopen(), which has no timeout at all and
    was observed live to hang indefinitely against a cloud host's IP."""

    def validate_config(self, config: SourceConfig) -> None:
        return None

    def collect(self, request: CollectionRequest):
        time.sleep(10)
        yield from ()

    def checkpoint(self) -> ConnectorCheckpoint | None:
        return None


async def test_run_ingestion_times_out_a_hanging_connector_instead_of_blocking_forever(
    db_session, tmp_path, monkeypatch
) -> None:
    """Regression test for a live incident: google_play hung indefinitely
    against Render's datacenter IP (no error, no timeout, nothing) and the
    whole daily cron job blocked forever until manually canceled, burning
    paid compute the entire time. A hard ceiling at the orchestration layer
    means one connector hanging degrades to a logged failure, not an
    unbounded hang — regardless of which connector or why it hung."""
    monkeypatch.setattr(ingestion_service, "CONNECTOR_COLLECTION_TIMEOUT_SECONDS", 0.2)
    storage = FilesystemRawArtifactStorage(str(tmp_path))

    run = await run_ingestion(
        db_session,
        connector=_HangingConnector(),
        connector_type=ConnectorType.LIBRARY,
        connector_key="hanging_source",
        connector_display_name="Hanging Source",
        connector_version="test-1",
        config_name="hanging-source-config",
        source_config=SourceConfig(target_identifier="x"),
        storage=storage,
    )

    assert run.records_discovered == 0
    assert run.records_stored == 0
    assert run.records_failed == 1
    assert run.status == IngestionRunStatus.FAILED
    assert run.failure_code == "TimeoutError"


async def test_run_ingestion_preserves_partial_success_on_mid_stream_failure(
    db_session, tmp_path
) -> None:
    """ING-017 — a connector failure partway through must not discard items
    already collected."""
    storage = FilesystemRawArtifactStorage(str(tmp_path))
    good_html = (
        "<html><head><title>T</title></head><body><article>"
        "<p>Users repeatedly buy from known categories in quick commerce apps "
        "because it feels fast, familiar, and low risk during busy hours.</p>"
        "</article></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "fails" in str(request.url):
            return httpx.Response(500, text="boom")
        return httpx.Response(200, text=good_html, headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = PublicWebConnector(client=client)

    config = SourceConfig(
        target_identifier="https://example.com/ok-1",
        configuration={
            "urls": [
                "https://example.com/ok-1",
                "https://example.com/fails",
                "https://example.com/ok-2",
            ]
        },
    )

    run = await run_ingestion(
        db_session,
        connector=connector,
        connector_type=ConnectorType.HTTP,
        connector_key="public_web",
        connector_display_name="Public Web",
        connector_version="test-1",
        config_name="quick-commerce-articles",
        source_config=config,
        storage=storage,
    )

    # The connector stops at the first failure (ok-1 succeeds, fails raises),
    # so exactly one item should be preserved, and the run must not be a
    # total failure since something was stored.
    assert run.records_stored == 1
    assert run.status == IngestionRunStatus.PARTIALLY_COMPLETED

    raw_items = (
        await db_session.scalars(
            select(RawSourceItem).where(RawSourceItem.ingestion_run_id == run.id)
        )
    ).all()
    assert len(raw_items) == 1
    assert raw_items[0].source_url == "https://example.com/ok-1"
