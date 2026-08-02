"""Instagram connector via Apify's hashtag scraper. Not documented in
architecture.md/context.md (only Reddit/Twitter/Apple were), but the actor
supports genuine keyword-style discovery — `keywordSearch=True` searches by
keyword instead of a literal hashtag — so brand-mention monitoring is
feasible here, unlike Facebook (see `facebook.py`).
"""

import hashlib
from datetime import UTC, datetime
from typing import Any, Literal

from instamart_engine.sources.apify_actor import ApifyActorConnector
from instamart_engine.sources.base import RawSourceItem, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError

DEFAULT_HASHTAGS = ["instamart", "swiggyinstamart", "quickcommerceindia"]


class InstagramApifyConnector(ApifyActorConnector):
    """Implements `instamart_engine.sources.base.SourceConnector`."""

    source_name = "instagram"
    actor_id = "apify/instagram-hashtag-scraper"

    def validate_config(self, config: SourceConfig) -> None:
        hashtags = config.configuration.get("hashtags")
        if hashtags is not None and not hashtags:
            raise SourceConfigError("instagram: 'hashtags' must be a non-empty list if provided")

    def _build_actor_input(self, config: SourceConfig) -> dict[str, Any]:
        hashtags = config.configuration.get("hashtags") or DEFAULT_HASHTAGS
        return {
            "hashtags": hashtags,
            "resultsType": "posts",
            "resultsLimit": config.record_limit or 50,
            "keywordSearch": config.configuration.get("keyword_search", False),
        }

    def _to_raw_item(self, item: dict[str, Any]) -> RawSourceItem | None:
        post_id = item.get("id") or item.get("shortCode")
        if not post_id:
            return None

        published_at = None
        timestamp = item.get("timestamp")
        if timestamp:
            published_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)

        # Field names per apify/instagram-hashtag-scraper's documented output
        # schema (displayUrl = image/thumbnail, videoUrl = present only for
        # Video-type posts, type in {"Image","Video"}) — not yet verified
        # against a live run, spot-check once APIFY_TOKEN is configured.
        video_url = item.get("videoUrl")
        display_url = item.get("displayUrl")
        media_url = video_url or display_url
        media_type: Literal["image", "video"] | None = None
        if media_url:
            media_type = "video" if video_url else "image"

        return RawSourceItem(
            external_id=post_id,
            record_type="social_post",
            body=item.get("caption"),
            source_url=item.get("url"),
            published_at=published_at,
            author_external_id_hash=_hash(item.get("ownerUsername")),
            engagement_count=_non_negative(item.get("likesCount")),
            reply_count=_non_negative(item.get("commentsCount")),
            media_url=media_url,
            media_type=media_type,
            source_metadata={
                "hashtags": item.get("hashtags"),
                "post_type": item.get("type"),
            },
        )


def _hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _non_negative(value: int | None) -> int | None:
    """Instagram returns -1 for like/comment counts the poster has hidden —
    that's not a real count, so store it as unknown (NULL) rather than
    violating raw_source_item's non-negative check constraints."""
    if value is None or value < 0:
        return None
    return value
