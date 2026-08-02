"""Google Play reviews connector. architecture.md §10.2, context.md §10.

Still open with no auth required as of problemstatement.md's mid-2026
source survey. Uses the `google-play-scraper` PyPI package, which handles
its own internal pagination; we drive it with a single `count` per
`collect()` call and persist its opaque continuation token as our
checkpoint (CHK-002/CHK-009).
"""

import hashlib
import re
from collections.abc import Iterator
from datetime import UTC
from typing import Any

from google_play_scraper import Sort
from google_play_scraper import reviews as gp_reviews
from google_play_scraper.exceptions import NotFoundError

# Reaching into a private class is unavoidable: it's the only way to
# reconstruct a resumable continuation token for this library's API.
from google_play_scraper.features.reviews import _ContinuationToken

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

DEFAULT_COLLECTION_COUNT = 200
_PACKAGE_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")


class GooglePlayConnector:
    source_name = "google_play"

    def __init__(self, lang: str = "en", country: str = "in") -> None:
        self._lang = lang
        self._country = country
        self._last_checkpoint: ConnectorCheckpoint | None = None

    def validate_config(self, config: SourceConfig) -> None:
        # SRC-001/002/006/008 are already enforced by SourceConfig itself.
        if not _PACKAGE_ID_PATTERN.match(config.target_identifier):
            raise SourceConfigError(
                f"{config.target_identifier!r} does not look like an Android package id "
                "(expected dotted form like 'in.swiggy.android')"
            )

    def collect(self, request: CollectionRequest) -> Iterator[RawSourceItem]:
        config = request.config
        self.validate_config(config)

        # CHK-009 — resuming a terminal checkpoint returns immediately.
        if request.checkpoint is not None and request.checkpoint.is_terminal:
            self._last_checkpoint = request.checkpoint
            return

        token = None
        if request.checkpoint is not None:
            token = _ContinuationToken(**request.checkpoint.checkpoint_value)

        count = config.record_limit or DEFAULT_COLLECTION_COUNT

        try:
            items, next_token = gp_reviews(
                config.target_identifier,
                lang=self._lang,
                country=self._country,
                sort=Sort.NEWEST,
                count=count,
                continuation_token=token,
            )
        except NotFoundError as exc:
            raise SourceUnavailableError(
                f"Google Play app not found: {config.target_identifier}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 — library raises bare Exception on HTTP failure
            raise SourceTransientError(f"Google Play request failed: {exc}") from exc

        is_terminal = next_token.token is None
        self._last_checkpoint = ConnectorCheckpoint(
            checkpoint_type="continuation_token",
            checkpoint_value={
                "token": next_token.token,
                "lang": next_token.lang,
                "country": next_token.country,
                "sort": next_token.sort,
                "count": next_token.count,
                "filter_score_with": next_token.filter_score_with,
                "filter_device_with": next_token.filter_device_with,
            },
            is_terminal=is_terminal,
        )

        for item in items:
            yield self._to_raw_item(item, app_id=config.target_identifier)

    def checkpoint(self) -> ConnectorCheckpoint | None:
        return self._last_checkpoint

    def _to_raw_item(self, item: dict[str, Any], *, app_id: str) -> RawSourceItem:
        published_at = item.get("at")
        # REC-003/REC-005 — the library returns a naive datetime; the Play
        # Store API doesn't expose an explicit timezone, so we document the
        # UTC assumption here rather than silently mis-tagging it as local.
        if published_at is not None and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        username = item.get("userName")
        author_hash = (
            hashlib.sha256(username.encode("utf-8")).hexdigest() if username else None
        )

        score = item.get("score")
        app_version = item.get("appVersion") or item.get("reviewCreatedVersion")

        return RawSourceItem(
            external_id=item["reviewId"],
            record_type="app_review",
            body=item.get("content"),
            source_url=f"https://play.google.com/store/apps/details?id={app_id}&reviewId={item['reviewId']}",
            published_at=published_at,
            author_external_id_hash=author_hash,
            rating=float(score) if score is not None else None,
            rating_scale_max=5.0,
            engagement_count=item.get("thumbsUpCount"),
            language_hint=self._lang,
            country_code=self._country.upper()[:2],
            app_version=app_version,
            source_metadata={
                "has_developer_reply": bool(item.get("replyContent")),
            },
        )
