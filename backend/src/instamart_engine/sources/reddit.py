"""Reddit connector via Apify. architecture.md §10.2/§34.4 (open decision:
Apify actor vs. official OAuth through PRAW — Apify chosen; no Reddit
developer app/OAuth needed). Posts and comments are stored as separate
records; a comment's parent post id is derived from the comment's own
`url` (the actor's output has no direct `parentId` field) — verified live
against real sample output before writing this mapping.
"""

import hashlib
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from instamart_engine.sources.apify_actor import ApifyActorConnector
from instamart_engine.sources.base import RawSourceItem, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError
from instamart_engine.sources.search_terms import INSTAMART_SEARCH_TERMS

# Reddit comment URLs look like .../comments/{post_id}/{slug}/{comment_id}/ —
# the post's own `id` field uses the "t3_" fullname prefix.
_COMMENT_URL_PATTERN = re.compile(r"/comments/([a-z0-9]+)/")


class RedditApifyConnector(ApifyActorConnector):
    """Implements `instamart_engine.sources.base.SourceConnector`."""

    source_name = "reddit"
    actor_id = "trudax/reddit-scraper-lite"

    def validate_config(self, config: SourceConfig) -> None:
        searches = config.configuration.get("searches")
        if searches is not None and not searches:
            raise SourceConfigError("reddit: 'searches' must be a non-empty list if provided")

    def _build_actor_input(self, config: SourceConfig) -> dict[str, Any]:
        searches = config.configuration.get("searches") or INSTAMART_SEARCH_TERMS
        return {
            "searches": searches,
            "searchPosts": True,
            "searchComments": True,
            "maxItems": config.record_limit or 100,
            "maxComments": config.configuration.get("max_comments", 20),
            "sort": config.configuration.get("sort", "relevance"),
            # Without this, trudax/reddit-scraper-lite's fast RSS-feed mode
            # omits imageUrls/videoUrls entirely (per its documented input
            # schema) — needed to capture media at all.
            "includeMediaLinks": True,
        }

    def _to_raw_item(self, item: dict[str, Any]) -> RawSourceItem | None:
        data_type = item.get("dataType")
        if data_type not in ("post", "comment"):
            return None  # defensive: skip any non-content dataset row

        published_at = None
        created_raw = item.get("createdAt")
        if created_raw:
            published_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))

        parent_id = None
        if data_type == "comment":
            match = _COMMENT_URL_PATTERN.search(item.get("url", ""))
            if match:
                parent_id = f"t3_{match.group(1)}"

        # Field names per trudax/reddit-scraper-lite's documented output
        # schema (imageUrls/videoUrls, only populated with
        # includeMediaLinks=True set above) — not yet verified against a
        # live run, spot-check once APIFY_TOKEN is configured.
        video_urls = item.get("videoUrls") or []
        image_urls = item.get("imageUrls") or []
        media_url = (video_urls[0] if video_urls else None) or (
            image_urls[0] if image_urls else None
        )
        media_type = "video" if video_urls else ("image" if image_urls else None)

        return RawSourceItem(
            external_id=item["id"],
            external_parent_id=parent_id,
            record_type="forum_post" if data_type == "post" else "forum_comment",
            title=item.get("title"),
            body=item.get("body"),
            source_url=item.get("url"),
            published_at=published_at,
            author_external_id_hash=_hash(item.get("username")),
            media_url=media_url,
            media_type=media_type,
            source_metadata={"community_name": item.get("communityName")},
        )


def _hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
