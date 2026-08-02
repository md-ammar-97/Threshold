"""Unit tests for the quick-commerce RSS connector. Feeds are parsed from
in-memory strings via `feedparser.parse(io.BytesIO(...))` — no real network
access, no monkeypatching of `feedparser` internals."""

import io

import feedparser
import pytest

from instamart_engine.sources.base import CollectionRequest, ConnectorCheckpoint, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError
from instamart_engine.sources.quickcommerce_rss import QuickCommerceRSSConnector

_FEED_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Test Outlet</title>
{items}
</channel></rss>
"""

_ITEM_TEMPLATE = """
<item>
<title>{title}</title>
<link>{link}</link>
<description>{description}</description>
<pubDate>{pub_date}</pubDate>
</item>
"""


def _feed_url(name: str) -> str:
    return f"memory://{name}"


# Captured before any monkeypatching below replaces `feedparser.parse` at
# module scope — the fakes below call this, not `feedparser.parse` directly,
# to avoid infinitely recursing into themselves.
_real_parse = feedparser.parse


def _install_feed(monkeypatch: pytest.MonkeyPatch, feeds: dict[str, str]) -> None:
    def fake_parse(url: str, *args: object, **kwargs: object) -> "feedparser.FeedParserDict":
        xml = feeds.get(url)
        if xml is None:
            return _real_parse(io.BytesIO(b""))
        return _real_parse(io.BytesIO(xml.encode("utf-8")))

    monkeypatch.setattr("instamart_engine.sources.quickcommerce_rss.feedparser.parse", fake_parse)


def test_validate_config_requires_feed_urls() -> None:
    connector = QuickCommerceRSSConnector(feed_urls=[])
    with pytest.raises(SourceConfigError):
        connector.validate_config(SourceConfig(target_identifier="quickcommerce"))


def test_collect_maps_entries_to_article_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = _feed_url("outlet-a")
    xml = _FEED_TEMPLATE.format(
        items=_ITEM_TEMPLATE.format(
            title="Quick commerce funding roundup",
            link="https://outlet-a.example/article-1",
            description="A roundup of quick-commerce funding news this week.",
            pub_date="Mon, 27 Jul 2026 10:00:00 GMT",
        )
    )
    _install_feed(monkeypatch, {feed_url: xml})

    connector = QuickCommerceRSSConnector(feed_urls=[feed_url])
    request = CollectionRequest(config=SourceConfig(target_identifier="quickcommerce"))

    items = list(connector.collect(request))

    assert len(items) == 1
    item = items[0]
    assert item.record_type == "article_passage"
    assert item.title == "Quick commerce funding roundup"
    assert item.source_url == "https://outlet-a.example/article-1"
    assert item.published_at is not None
    assert item.source_metadata["feed_url"] == feed_url

    checkpoint = connector.checkpoint()
    assert checkpoint is not None
    last_seen = checkpoint.checkpoint_value["last_seen_per_feed"][feed_url]
    assert last_seen == item.published_at.isoformat()


def test_collect_skips_entries_at_or_before_checkpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = _feed_url("outlet-b")
    xml = _FEED_TEMPLATE.format(
        items=(
            _ITEM_TEMPLATE.format(
                title="Older article",
                link="https://outlet-b.example/old",
                description="Old news.",
                pub_date="Mon, 20 Jul 2026 10:00:00 GMT",
            )
            + _ITEM_TEMPLATE.format(
                title="Newer article",
                link="https://outlet-b.example/new",
                description="Fresh news.",
                pub_date="Mon, 27 Jul 2026 10:00:00 GMT",
            )
        )
    )
    _install_feed(monkeypatch, {feed_url: xml})

    connector = QuickCommerceRSSConnector(feed_urls=[feed_url])
    checkpoint = ConnectorCheckpoint(
        checkpoint_type="rss_last_seen",
        checkpoint_value={"last_seen_per_feed": {feed_url: "2026-07-22T00:00:00+00:00"}},
        is_terminal=True,
    )
    request = CollectionRequest(
        config=SourceConfig(target_identifier="quickcommerce"), checkpoint=checkpoint
    )

    items = list(connector.collect(request))

    assert len(items) == 1
    assert items[0].source_url == "https://outlet-b.example/new"


def test_collect_skips_one_bad_feed_without_aborting_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good_url = _feed_url("outlet-good")
    bad_url = _feed_url("outlet-bad")
    good_xml = _FEED_TEMPLATE.format(
        items=_ITEM_TEMPLATE.format(
            title="Good article",
            link="https://outlet-good.example/a",
            description="Fine.",
            pub_date="Mon, 27 Jul 2026 10:00:00 GMT",
        )
    )

    def fake_parse(url: str, *args: object, **kwargs: object) -> "feedparser.FeedParserDict":
        if url == good_url:
            return _real_parse(io.BytesIO(good_xml.encode("utf-8")))
        return _real_parse(io.BytesIO(b"not xml at all"))

    monkeypatch.setattr("instamart_engine.sources.quickcommerce_rss.feedparser.parse", fake_parse)

    connector = QuickCommerceRSSConnector(feed_urls=[bad_url, good_url])
    request = CollectionRequest(config=SourceConfig(target_identifier="quickcommerce"))

    items = list(connector.collect(request))

    assert len(items) == 1
    assert items[0].source_url == "https://outlet-good.example/a"


def test_collect_respects_record_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = _feed_url("outlet-c")
    xml = _FEED_TEMPLATE.format(
        items="".join(
            _ITEM_TEMPLATE.format(
                title=f"Article {i}",
                link=f"https://outlet-c.example/{i}",
                description="Text.",
                pub_date="Mon, 27 Jul 2026 10:00:00 GMT",
            )
            for i in range(5)
        )
    )
    _install_feed(monkeypatch, {feed_url: xml})

    connector = QuickCommerceRSSConnector(feed_urls=[feed_url])
    request = CollectionRequest(
        config=SourceConfig(target_identifier="quickcommerce", record_limit=2)
    )

    items = list(connector.collect(request))
    assert len(items) == 2
