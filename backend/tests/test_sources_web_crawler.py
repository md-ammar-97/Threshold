"""Unit tests for the generic web crawler connector. Uses httpx.MockTransport
— no real network access — and a stub RobotsChecker so robots.txt fetches
(which go through `urllib`, not the injected httpx client) don't hit the
network either."""

import httpx
import pytest

from instamart_engine.sources.base import CollectionRequest, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError
from instamart_engine.sources.web_crawler import WebCrawlerConnector

_LISTING_HTML = """
<html><body>
<a href="/thread-1">Thread 1</a>
<a href="/thread-2">Thread 2</a>
<a href="https://example.org/off-site">Off-site</a>
</body></html>
"""

_THREAD_HTML = """
<html><head><title>Delivery was late again</title></head>
<body><article>
<p>Users keep ordering the same snacks every week because trying something new
feels risky when delivery is already unpredictable. This complaint repeats
across many threads on this forum about quick-commerce delivery times.</p>
</article></body></html>
"""


class _AllowAllRobots:
    def is_allowed(self, url: str) -> bool:
        return True


class _DenyAllRobots:
    def is_allowed(self, url: str) -> bool:
        return False


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_validate_config_requires_seed_urls() -> None:
    connector = WebCrawlerConnector(
        source_name="forum",
        seed_urls=[],
        record_type="forum_post",
        client=_client_for(lambda r: httpx.Response(200)),
        robots_checker=_AllowAllRobots(),
    )
    with pytest.raises(SourceConfigError):
        connector.validate_config(SourceConfig(target_identifier="forum"))


def test_collect_discovers_and_follows_same_domain_links() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.com/listing":
            return httpx.Response(200, text=_LISTING_HTML, headers={"content-type": "text/html"})
        return httpx.Response(200, text=_THREAD_HTML, headers={"content-type": "text/html"})

    connector = WebCrawlerConnector(
        source_name="forum",
        seed_urls=["https://example.com/listing"],
        record_type="forum_post",
        rate_limit_seconds=0,
        client=_client_for(handler),
        robots_checker=_AllowAllRobots(),
    )
    request = CollectionRequest(config=SourceConfig(target_identifier="forum"))

    items = list(connector.collect(request))

    # The listing page itself and the two same-domain thread pages it
    # links to all yield a record. The off-site link is not followed
    # (same_domain_only=True, default) — 3 records, not 4.
    assert len(items) == 3
    assert all(item.record_type == "forum_post" for item in items)
    thread_items = [item for item in items if item.source_url != "https://example.com/listing"]
    assert len(thread_items) == 2
    assert all("quick-commerce" in (item.body or "") for item in thread_items)

    checkpoint = connector.checkpoint()
    assert checkpoint is not None
    assert checkpoint.is_terminal is True


def test_collect_respects_record_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.com/listing":
            return httpx.Response(200, text=_LISTING_HTML, headers={"content-type": "text/html"})
        return httpx.Response(200, text=_THREAD_HTML, headers={"content-type": "text/html"})

    connector = WebCrawlerConnector(
        source_name="forum",
        seed_urls=["https://example.com/listing"],
        record_type="forum_post",
        rate_limit_seconds=0,
        client=_client_for(handler),
        robots_checker=_AllowAllRobots(),
    )
    request = CollectionRequest(
        config=SourceConfig(target_identifier="forum", record_limit=1)
    )

    items = list(connector.collect(request))
    assert len(items) == 1


def test_collect_skips_pages_disallowed_by_robots_txt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called when robots.txt disallows the seed")

    connector = WebCrawlerConnector(
        source_name="forum",
        seed_urls=["https://example.com/listing"],
        record_type="forum_post",
        rate_limit_seconds=0,
        client=_client_for(handler),
        robots_checker=_DenyAllRobots(),
    )
    request = CollectionRequest(config=SourceConfig(target_identifier="forum"))

    items = list(connector.collect(request))
    assert items == []


def test_collect_continues_past_a_single_broken_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.com/listing":
            return httpx.Response(200, text=_LISTING_HTML, headers={"content-type": "text/html"})
        if str(request.url) == "https://example.com/thread-1":
            return httpx.Response(500)
        return httpx.Response(200, text=_THREAD_HTML, headers={"content-type": "text/html"})

    connector = WebCrawlerConnector(
        source_name="forum",
        seed_urls=["https://example.com/listing"],
        record_type="forum_post",
        rate_limit_seconds=0,
        client=_client_for(handler),
        robots_checker=_AllowAllRobots(),
    )
    request = CollectionRequest(config=SourceConfig(target_identifier="forum"))

    items = list(connector.collect(request))

    # thread-1 500s and is skipped; the listing page and thread-2 still
    # get collected.
    assert len(items) == 2
    assert {item.source_url for item in items} == {
        "https://example.com/listing",
        "https://example.com/thread-2",
    }


def test_ssrf_blocked_seed_url_is_rejected_before_any_request() -> None:
    connector = WebCrawlerConnector(
        source_name="forum",
        seed_urls=["http://127.0.0.1:8000/admin"],
        record_type="forum_post",
        client=_client_for(lambda r: httpx.Response(200)),
        robots_checker=_AllowAllRobots(),
    )
    request = CollectionRequest(config=SourceConfig(target_identifier="forum"))

    with pytest.raises(SourceConfigError):
        list(connector.collect(request))
