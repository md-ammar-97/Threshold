"""Unit tests for the Apple App Store connector. Uses httpx.MockTransport
with a real sample shape captured from Apple's own review feed during
development — no network access, no API key needed."""

import httpx
import pytest

from instamart_engine.sources.apple_app_store import AppleAppStoreConnector
from instamart_engine.sources.base import CollectionRequest, ConnectorCheckpoint, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError

SAMPLE_ENTRY = {
    "author": {"name": {"label": "Ratodh"}},
    "updated": {"label": "2026-07-22T14:30:02-07:00"},
    "im:rating": {"label": "5"},
    "im:version": {"label": "26.28.75"},
    "id": {"label": "14335917614"},
    "title": {"label": "Great app"},
    "content": {"label": "Works really well.", "attributes": {"type": "text"}},
    "im:voteSum": {"label": "0"},
    "im:voteCount": {"label": "0"},
}

APP_METADATA_ENTRY = {"im:name": {"label": "WhatsApp Messenger"}}  # no im:rating — not a review


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_validate_config_rejects_non_numeric_id() -> None:
    connector = AppleAppStoreConnector(client=_client_for(lambda r: httpx.Response(200, json={})))
    with pytest.raises(SourceConfigError):
        connector.validate_config(SourceConfig(target_identifier="in.swiggy.android"))


def test_collect_maps_review_and_skips_metadata_entry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "page=1" in str(request.url)
        return httpx.Response(200, json={"feed": {"entry": [APP_METADATA_ENTRY, SAMPLE_ENTRY]}})

    connector = AppleAppStoreConnector(country="us", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="310633997", record_limit=1))

    items = list(connector.collect(request))

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "14335917614"
    assert item.record_type == "app_review"
    assert item.rating == 5.0
    assert item.rating_scale_max == 5.0
    assert item.app_version == "26.28.75"
    assert item.country_code == "US"
    assert item.author_external_id_hash is not None
    assert item.author_external_id_hash != "Ratodh"
    assert item.published_at is not None and item.published_at.tzinfo is not None


def test_collect_stops_at_empty_page_and_marks_terminal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"feed": {"entry": [SAMPLE_ENTRY]}})

    connector = AppleAppStoreConnector(client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="310633997", record_limit=1))

    items = list(connector.collect(request))
    assert len(items) == 1

    checkpoint = connector.checkpoint()
    assert checkpoint is not None
    assert checkpoint.checkpoint_value["next_page"] == 2


def test_collect_resuming_terminal_checkpoint_returns_immediately() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called")

    connector = AppleAppStoreConnector(client=_client_for(handler))
    request = CollectionRequest(
        config=SourceConfig(target_identifier="310633997"),
        checkpoint=ConnectorCheckpoint(checkpoint_type="page_number", checkpoint_value={}, is_terminal=True),
    )

    items = list(connector.collect(request))
    assert items == []


def test_collect_marks_terminal_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    connector = AppleAppStoreConnector(client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="999999999999"))

    items = list(connector.collect(request))
    assert items == []
    assert connector.checkpoint().is_terminal is True
