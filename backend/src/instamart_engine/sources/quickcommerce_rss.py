"""Quick-commerce industry commentary via RSS. `docs/problemstatement.md`'s
"Quick-commerce industry commentary" row names Entrackr, Inc42, YourStory,
and Moneycontrol as ordinary public pages best reached via direct HTTP
fetching or an RSS reader. Verified live during implementation: Entrackr
(`https://entrackr.com/rss`) and Inc42/YourStory (`/feed`) all serve real
RSS 2.0; Moneycontrol's RSS endpoints now redirect through a login-consent
gate and its old feed index returns 410 — no working public feed there
currently, so it's left out of the default seed list rather than guessed at.

Uses `ConnectorType.RSS` (already defined in `sources/models.py`, unused by
any connector until now).
"""

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from time import struct_time

import feedparser
import lxml.html

from instamart_engine.sources.base import (
    CollectionRequest,
    ConnectorCheckpoint,
    RawSourceItem,
    SourceConfig,
)
from instamart_engine.sources.exceptions import SourceConfigError

DEFAULT_FEED_URLS = [
    "https://entrackr.com/rss",
    "https://inc42.com/feed/",
    "https://yourstory.com/feed",
]


class QuickCommerceRSSConnector:
    """Implements `instamart_engine.sources.base.SourceConnector`. One RSS
    feed per `feed_urls` entry; incremental by published-timestamp
    checkpoint per feed."""

    source_name = "quickcommerce"

    def __init__(self, *, feed_urls: list[str] | None = None) -> None:
        # `None` means "use the defaults"; an explicit `[]` means "no feeds"
        # and must still fail `validate_config` rather than silently falling
        # back to defaults.
        self._feed_urls = DEFAULT_FEED_URLS if feed_urls is None else feed_urls
        self._last_checkpoint: ConnectorCheckpoint | None = None

    def validate_config(self, config: SourceConfig) -> None:
        if not self._feed_urls:
            raise SourceConfigError("quickcommerce: at least one feed URL is required")

    def collect(self, request: CollectionRequest) -> Iterator[RawSourceItem]:
        config = request.config
        self.validate_config(config)

        last_seen: dict[str, str] = {}
        if request.checkpoint is not None:
            last_seen = request.checkpoint.checkpoint_value.get("last_seen_per_feed", {})

        limit = config.record_limit
        yielded = 0
        new_last_seen = dict(last_seen)

        for feed_url in self._feed_urls:
            if limit is not None and yielded >= limit:
                break
            parsed = feedparser.parse(feed_url)
            if parsed.bozo and not parsed.entries:
                # Malformed/unreachable feed — skip it, don't abort the
                # whole run over one bad outlet.
                continue

            feed_high_water_mark = last_seen.get(feed_url)
            newest_seen_this_run: str | None = None

            for entry in parsed.entries:
                if limit is not None and yielded >= limit:
                    break
                published_iso = _published_iso(entry)
                if (
                    feed_high_water_mark is not None
                    and published_iso is not None
                    and published_iso <= feed_high_water_mark
                ):
                    continue

                mapped = self._to_raw_item(entry, feed_url=feed_url)
                if mapped is None:
                    continue
                yield mapped
                yielded += 1

                if published_iso is not None and (
                    newest_seen_this_run is None or published_iso > newest_seen_this_run
                ):
                    newest_seen_this_run = published_iso

            if newest_seen_this_run is not None:
                new_last_seen[feed_url] = newest_seen_this_run

        self._last_checkpoint = ConnectorCheckpoint(
            checkpoint_type="rss_last_seen",
            checkpoint_value={"last_seen_per_feed": new_last_seen},
            is_terminal=True,
        )

    def checkpoint(self) -> ConnectorCheckpoint | None:
        return self._last_checkpoint

    def _to_raw_item(
        self, entry: "feedparser.FeedParserDict", *, feed_url: str
    ) -> RawSourceItem | None:
        link = entry.get("link")
        if not link:
            return None

        body = _strip_html(entry.get("summary") or entry.get("description"))
        published_at = _entry_datetime(entry)

        return RawSourceItem(
            external_id=self._external_id_for(link),
            record_type="article_passage",
            title=entry.get("title") or None,
            body=body,
            source_url=link,
            published_at=published_at,
            source_metadata={
                "feed_url": feed_url,
                "author_display_name": entry.get("author") or None,
            },
        )

    def _external_id_for(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _strip_html(value: str | None) -> str | None:
    """RSS `summary`/`description` fields are frequently HTML fragments
    (e.g. WordPress excerpts with an inline `<img>`), unlike every other
    connector's `body`, which is always plain text — strip markup so
    downstream classification isn't fed raw tags."""
    if not value or not value.strip():
        return None
    text = lxml.html.fromstring(value).text_content().strip()
    return text or None


def _entry_datetime(entry: "feedparser.FeedParserDict") -> datetime | None:
    parsed_time: struct_time | None = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time is None:
        return None
    try:
        return datetime(*parsed_time[:6], tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def _published_iso(entry: "feedparser.FeedParserDict") -> str | None:
    parsed = _entry_datetime(entry)
    return parsed.isoformat() if parsed else None
