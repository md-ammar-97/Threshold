"""Unit tests for the Twitter/X connector. Uses httpx.MockTransport with a
real sample shape captured from a live Apify run during development."""

import httpx
import pytest

from instamart_engine.sources.base import CollectionRequest, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError
from instamart_engine.sources.search_terms import INSTAMART_SEARCH_TERMS
from instamart_engine.sources.twitter import TwitterApifyConnector

SAMPLE_TWEET = {
    "id": "2080491105024688326",
    "createdAt": "Fri Jul 24 03:11:47 +0000 2026",
    "text": "Swiggy Instamart appears to be following Eternal's footsteps.",
    "inReplyToId": None,
    "isReply": False,
    "lang": "en",
    "likeCount": 12,
    "retweetCount": 3,
    "replyCount": 1,
    "viewCount": 500,
    "url": "https://x.com/Ashish_shah72/status/2080491105024688326",
    "twitterUrl": "https://twitter.com/Ashish_shah72/status/2080491105024688326",
    "author": {"userName": "Ashish_shah72", "name": "ASHISH SHAH"},
}


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.apify.com/v2")


def test_validate_config_rejects_empty_search_terms_list() -> None:
    connector = TwitterApifyConnector(api_token="tok", client=_client_for(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(SourceConfigError):
        connector.validate_config(SourceConfig(target_identifier="x", configuration={"searchTerms": []}))


def test_build_actor_input_defaults_to_shared_search_terms() -> None:
    connector = TwitterApifyConnector(api_token="tok", client=_client_for(lambda r: httpx.Response(200, json=[])))
    actor_input = connector._build_actor_input(SourceConfig(target_identifier="x"))
    assert actor_input["searchTerms"] == INSTAMART_SEARCH_TERMS


def test_collect_maps_tweet_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[SAMPLE_TWEET])

    connector = TwitterApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="x", configuration={"searchTerms": ["Swiggy Instamart"]}))

    items = list(connector.collect(request))

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "2080491105024688326"
    assert item.record_type == "social_post"
    assert item.external_parent_id is None
    assert item.engagement_count == 12
    assert item.reply_count == 1
    assert item.language_hint == "en"
    assert item.published_at is not None and item.published_at.year == 2026
    assert item.author_external_id_hash is not None
    assert item.author_external_id_hash != "Ashish_shah72"


def test_collect_skips_no_results_placeholder_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"noResults": True}])

    connector = TwitterApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="x"))

    items = list(connector.collect(request))
    assert items == []


def test_collect_maps_reply_parent_id() -> None:
    reply = {**SAMPLE_TWEET, "id": "999", "inReplyToId": "2080491105024688326", "isReply": True}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[reply])

    connector = TwitterApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="x"))

    items = list(connector.collect(request))
    assert items[0].external_parent_id == "2080491105024688326"
