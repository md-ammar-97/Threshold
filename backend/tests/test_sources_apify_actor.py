"""Unit tests for the shared Apify-actor connector base class. Uses
httpx.MockTransport — no real network access, no Apify token needed."""

import httpx
import pytest

from instamart_engine.sources.apify_actor import ApifyActorConnector
from instamart_engine.sources.base import CollectionRequest, RawSourceItem, SourceConfig
from instamart_engine.sources.exceptions import (
    SourceAuthError,
    SourceRateLimitedError,
    SourceTransientError,
    SourceUnavailableError,
)


class _FakeActorConnector(ApifyActorConnector):
    source_name = "fake_actor"
    actor_id = "someuser/some-actor"

    def _build_actor_input(self, config: SourceConfig) -> dict:
        return {"query": config.target_identifier}

    def _to_raw_item(self, item: dict) -> RawSourceItem | None:
        if "skip" in item:
            return None
        return RawSourceItem(external_id=item["id"], record_type="other", body=item.get("body"))


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.apify.com/v2")


def test_constructor_rejects_missing_token() -> None:
    with pytest.raises(SourceAuthError):
        _FakeActorConnector(api_token="")


def test_actor_path_url_encodes_slash() -> None:
    connector = _FakeActorConnector(
        api_token="tok", client=_client_for(lambda r: httpx.Response(200, json=[]))
    )
    assert connector._actor_path() == "someuser~some-actor"


def test_collect_maps_dataset_items_and_skips_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "someuser~some-actor" in str(request.url)
        return httpx.Response(200, json=[{"id": "1", "body": "hello"}, {"skip": True}])

    connector = _FakeActorConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="query"))

    items = list(connector.collect(request))

    assert len(items) == 1
    assert items[0].external_id == "1"
    assert items[0].body == "hello"

    checkpoint = connector.checkpoint()
    assert checkpoint is not None
    assert checkpoint.is_terminal is True


def test_collect_respects_record_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": str(i)} for i in range(5)])

    connector = _FakeActorConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="query", record_limit=2))

    items = list(connector.collect(request))

    assert len(items) == 2


def test_collect_ignores_prior_terminal_checkpoint_and_collects_again() -> None:
    """Apify calls are always single-shot with no continuation token — a
    terminal checkpoint from an earlier run must not block later re-runs of
    the same collection config (unlike paginated connectors)."""
    from instamart_engine.sources.base import ConnectorCheckpoint

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "1", "body": "hello"}])

    connector = _FakeActorConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(
        config=SourceConfig(target_identifier="query"),
        checkpoint=ConnectorCheckpoint(
            checkpoint_type="apify_run", checkpoint_value={}, is_terminal=True
        ),
    )

    items = list(connector.collect(request))
    assert len(items) == 1
    assert items[0].external_id == "1"


@pytest.mark.parametrize(
    "status,expected_exception",
    [
        (401, SourceAuthError),
        (403, SourceAuthError),
        (429, SourceRateLimitedError),
        (500, SourceTransientError),
        (404, SourceUnavailableError),
    ],
)
def test_collect_maps_http_errors(status: int, expected_exception: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "boom"})

    connector = _FakeActorConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="query"))

    with pytest.raises(expected_exception):
        list(connector.collect(request))


def test_collect_maps_network_error_as_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    connector = _FakeActorConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="query"))

    with pytest.raises(SourceTransientError):
        list(connector.collect(request))
