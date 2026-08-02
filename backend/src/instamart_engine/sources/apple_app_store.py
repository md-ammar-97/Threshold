"""Apple App Store reviews connector via Apple's own public review feed.
architecture.md §10.2; problemstatement.md's App Store row.

problemstatement.md notes (mid-2026) that "the old RSS feed is no longer
reliable and may return empty results" and recommends an Apify actor
instead. A live check this session found the opposite: Apple's own feed
(`itunes.apple.com/.../rss/customerreviews/.../json`) returned real, current
reviews for a heavily-reviewed test app, while the two leading Apify
App-Store-review actors both returned zero results for the same app. Since
Apple's feed is official, free, and carries no ToS risk, it's used directly
rather than a scraping actor.

Capped at Apple's own feed depth (10 pages x 50 reviews = 500 most-recent
reviews per app/country) — this is a platform limit, not a connector one.
"""

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from instamart_engine.sources.base import (
    CollectionRequest,
    ConnectorCheckpoint,
    RawSourceItem,
    SourceConfig,
)
from instamart_engine.sources.exceptions import (
    SourceConfigError,
    SourceTransientError,
    SourceUnavailableError,
)

REVIEWS_URL_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/"
    "id={app_id}/sortBy=mostRecent/json"
)
MAX_PAGES = 10
DEFAULT_PAGE_SIZE = 50


class AppleAppStoreConnector:
    """Implements `instamart_engine.sources.base.SourceConnector`."""

    source_name = "apple_app_store"

    def __init__(self, country: str = "us", client: httpx.Client | None = None) -> None:
        self._country = country
        self._client = client or httpx.Client(timeout=15.0)
        self._last_checkpoint: ConnectorCheckpoint | None = None

    def validate_config(self, config: SourceConfig) -> None:
        if not config.target_identifier.isdigit():
            raise SourceConfigError(
                f"{config.target_identifier!r} does not look like an Apple App Store "
                "numeric app id (find it in the App Store page URL, e.g. "
                "apps.apple.com/us/app/.../id310633997 -> 310633997)"
            )

    def collect(self, request: CollectionRequest) -> Iterator[RawSourceItem]:
        config = request.config
        self.validate_config(config)

        if request.checkpoint is not None and request.checkpoint.is_terminal:
            self._last_checkpoint = request.checkpoint
            return

        start_page = 1
        if request.checkpoint is not None:
            start_page = request.checkpoint.checkpoint_value.get("next_page", 1)

        limit = config.record_limit or DEFAULT_PAGE_SIZE
        yielded = 0
        page = start_page
        is_terminal = False

        while yielded < limit and page <= MAX_PAGES:
            url = REVIEWS_URL_TEMPLATE.format(
                country=self._country, page=page, app_id=config.target_identifier
            )
            try:
                response = self._client.get(url)
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise SourceTransientError(
                    f"Timeout fetching Apple reviews page {page}: {exc}"
                ) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 404:
                    is_terminal = True
                    break
                if 500 <= status < 600:
                    raise SourceTransientError(f"Apple reviews server error {status}") from exc
                raise SourceUnavailableError(
                    f"Apple reviews request failed ({status})"
                ) from exc
            except httpx.HTTPError as exc:
                raise SourceTransientError(f"Network error fetching Apple reviews: {exc}") from exc

            # Page 1's first "entry" is sometimes app metadata rather than a
            # review (no im:rating) — skip non-review entries defensively.
            entries = [
                e for e in response.json().get("feed", {}).get("entry", []) if "im:rating" in e
            ]
            if not entries:
                is_terminal = True
                break

            for entry in entries:
                if yielded >= limit:
                    break
                yield self._to_raw_item(entry, app_id=config.target_identifier)
                yielded += 1

            page += 1

        if page > MAX_PAGES:
            is_terminal = True

        self._last_checkpoint = ConnectorCheckpoint(
            checkpoint_type="page_number",
            checkpoint_value={"next_page": page},
            is_terminal=is_terminal,
        )

    def checkpoint(self) -> ConnectorCheckpoint | None:
        return self._last_checkpoint

    def _to_raw_item(self, entry: dict[str, Any], *, app_id: str) -> RawSourceItem:
        author_name = entry.get("author", {}).get("name", {}).get("label")
        author_hash = (
            hashlib.sha256(author_name.encode("utf-8")).hexdigest() if author_name else None
        )
        rating = entry.get("im:rating", {}).get("label")

        published_at = None
        published_raw = entry.get("updated", {}).get("label")
        if published_raw:
            published_at = datetime.fromisoformat(published_raw).astimezone(UTC)

        return RawSourceItem(
            external_id=entry.get("id", {}).get("label", ""),
            record_type="app_review",
            title=entry.get("title", {}).get("label"),
            body=entry.get("content", {}).get("label"),
            source_url=f"https://itunes.apple.com/{self._country}/review?id={app_id}&type=Purple%20Software",
            published_at=published_at,
            author_external_id_hash=author_hash,
            rating=float(rating) if rating else None,
            rating_scale_max=5.0,
            app_version=entry.get("im:version", {}).get("label"),
            country_code=self._country.upper()[:2],
            source_metadata={
                "vote_sum": entry.get("im:voteSum", {}).get("label"),
                "vote_count": entry.get("im:voteCount", {}).get("label"),
            },
        )
