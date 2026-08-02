"""Unit tests for the Reddit connector. Uses httpx.MockTransport with a
real sample shape captured from a live Apify run during development — no
network access, no Apify token needed here."""

import httpx
import pytest

from instamart_engine.sources.base import CollectionRequest, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError
from instamart_engine.sources.reddit import RedditApifyConnector
from instamart_engine.sources.search_terms import INSTAMART_SEARCH_TERMS

SAMPLE_COMMENT = {
    "id": "t1_ozbe7bq",
    "parsedId": "ozbe7bq",
    "url": "https://www.reddit.com/r/GadgetsIndia/comments/1v49zct/suggest_me_a_phone/ozbe7bq/",
    "username": "nishit94",
    "communityName": "r/GadgetsIndia",
    "body": "If you order from Swiggy Instamart you will get a good deal.",
    "createdAt": "2026-07-23T16:56:56.000Z",
    "dataType": "comment",
}

SAMPLE_POST = {
    "id": "t3_1v4lv7n",
    "parsedId": "1v4lv7n",
    "url": "https://www.reddit.com/r/CreditCardsIndia/comments/1v4lv7n/rate_my_cards/",
    "username": "DietCokeIsLove",
    "title": "Rate my card collection!!",
    "communityName": "r/CreditCardsIndia",
    "body": "Offers 10% on Swiggy/Instamart and 5% on top online merchants.",
    "createdAt": "2026-07-23T18:13:22.000Z",
    "dataType": "post",
}


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.apify.com/v2")


def test_validate_config_rejects_empty_searches_list() -> None:
    connector = RedditApifyConnector(api_token="tok", client=_client_for(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(SourceConfigError):
        connector.validate_config(SourceConfig(target_identifier="x", configuration={"searches": []}))


def test_build_actor_input_defaults_to_shared_search_terms() -> None:
    connector = RedditApifyConnector(api_token="tok", client=_client_for(lambda r: httpx.Response(200, json=[])))
    actor_input = connector._build_actor_input(SourceConfig(target_identifier="x"))
    assert actor_input["searches"] == INSTAMART_SEARCH_TERMS
    assert actor_input["searchPosts"] is True
    assert actor_input["searchComments"] is True


def test_collect_maps_post_and_comment_with_parent_linkage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[SAMPLE_COMMENT, SAMPLE_POST])

    connector = RedditApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="x", configuration={"searches": ["Instamart"]}))

    items = {item.record_type: item for item in connector.collect(request)}

    comment = items["forum_comment"]
    assert comment.external_id == "t1_ozbe7bq"
    assert comment.external_parent_id == "t3_1v49zct"  # derived from the comment's own URL
    assert "Swiggy Instamart" in comment.body
    assert comment.author_external_id_hash is not None
    assert comment.author_external_id_hash != "nishit94"
    assert comment.published_at is not None

    post = items["forum_post"]
    assert post.external_id == "t3_1v4lv7n"
    assert post.external_parent_id is None
    assert post.title == "Rate my card collection!!"
    assert post.source_metadata["community_name"] == "r/CreditCardsIndia"


def test_collect_skips_non_content_dataset_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"dataType": "community"}, SAMPLE_POST])

    connector = RedditApifyConnector(api_token="tok", client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="x"))

    items = list(connector.collect(request))
    assert len(items) == 1
    assert items[0].record_type == "forum_post"
