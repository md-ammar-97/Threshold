"""Unit tests for the Instagram connector. Uses httpx.MockTransport with a
real sample shape captured from a live Apify run during development."""

import httpx
import pytest

from instamart_engine.sources.base import CollectionRequest, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError
from instamart_engine.sources.instagram import DEFAULT_HASHTAGS, InstagramApifyConnector

SAMPLE_POST = {
    "id": "123456789",
    "shortCode": "Cxxxxxx",
    "caption": "Loving the fast delivery from Instamart! #swiggyinstamart",
    "ownerUsername": "some_user",
    "ownerFullName": "Some User",
    "timestamp": "2026-07-20T10:00:00.000Z",
    "url": "https://www.instagram.com/p/Cxxxxxx/",
    "likesCount": 42,
    "commentsCount": 5,
    "type": "Image",
    "hashtags": ["swiggyinstamart", "instamart"],
}


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.apify.com/v2")


def test_validate_config_rejects_empty_hashtags_list() -> None:
    connector = InstagramApifyConnector(
        api_token="tok", client=_client_for(lambda r: httpx.Response(200, json=[]))
    )
    with pytest.raises(SourceConfigError):
        connector.validate_config(
            SourceConfig(target_identifier="x", configuration={"hashtags": []})
        )


def test_build_actor_input_defaults_to_default_hashtags() -> None:
    connector = InstagramApifyConnector(
        api_token="tok", client=_client_for(lambda r: httpx.Response(200, json=[]))
    )
    actor_input = connector._build_actor_input(SourceConfig(target_identifier="x"))
    assert actor_input["hashtags"] == DEFAULT_HASHTAGS


def test_collect_maps_post_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[SAMPLE_POST])

    connector = InstagramApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(
        config=SourceConfig(target_identifier="x", configuration={"hashtags": ["swiggyinstamart"]})
    )

    items = list(connector.collect(request))

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "123456789"
    assert item.record_type == "social_post"
    assert "Instamart" in item.body
    assert item.engagement_count == 42
    assert item.reply_count == 5
    assert item.published_at is not None
    assert item.author_external_id_hash is not None
    assert item.author_external_id_hash != "some_user"


def test_collect_treats_negative_counts_as_unknown() -> None:
    """Instagram uses -1 to mean "count hidden by the poster" — a real
    value observed live, and not a valid non-negative engagement_count."""
    hidden_counts_post = {**SAMPLE_POST, "likesCount": -1, "commentsCount": -1}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[hidden_counts_post])

    connector = InstagramApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="x"))

    items = list(connector.collect(request))
    assert items[0].engagement_count is None
    assert items[0].reply_count is None


def test_collect_falls_back_to_shortcode_when_id_missing() -> None:
    item_without_id = {**SAMPLE_POST, "id": None}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[item_without_id])

    connector = InstagramApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="x"))

    items = list(connector.collect(request))
    assert items[0].external_id == "Cxxxxxx"
