"""Twitter/X connector via Apify. context.md/problemstatement.md flag X as
optional/cost-sensitive ("used sparingly"); architecture.md §33 excludes
high-volume collection as an MVP goal — keep `record_limit` modest.

Uses `kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest`,
verified live to return real results for a common search term. The
originally-considered `apidojo/tweet-scraper` returned zero results even
for a very high-volume brand term during verification and appears
non-functional; swapped before writing this connector.
"""

import hashlib
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from instamart_engine.sources.apify_actor import ApifyActorConnector
from instamart_engine.sources.base import RawSourceItem, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError
from instamart_engine.sources.search_terms import INSTAMART_SEARCH_TERMS

# Twitter's actor returns this exact strftime-style format, e.g.
# "Fri Jul 24 03:11:47 +0000 2026" — confirmed against real sample output.
_CREATED_AT_FORMAT = "%a %b %d %H:%M:%S %z %Y"


class TwitterApifyConnector(ApifyActorConnector):
    """Implements `instamart_engine.sources.base.SourceConnector`."""

    source_name = "twitter"
    actor_id = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"

    def validate_config(self, config: SourceConfig) -> None:
        searches = config.configuration.get("searchTerms")
        if searches is not None and not searches:
            raise SourceConfigError("twitter: 'searchTerms' must be a non-empty list if provided")

    def _build_actor_input(self, config: SourceConfig) -> dict[str, Any]:
        search_terms = config.configuration.get("searchTerms") or INSTAMART_SEARCH_TERMS
        return {
            "searchTerms": search_terms,
            "maxItems": config.record_limit or 50,
            "queryType": config.configuration.get("queryType", "Latest"),
            "lang": config.configuration.get("lang", "en"),
        }

    def _to_raw_item(self, item: dict[str, Any]) -> RawSourceItem | None:
        if "id" not in item or "text" not in item:
            return None  # e.g. a noResults/error placeholder row

        published_at = None
        created_raw = item.get("createdAt")
        if created_raw:
            try:
                published_at = datetime.strptime(created_raw, _CREATED_AT_FORMAT)
            except ValueError:
                published_at = None

        author = item.get("author") or {}
        media_url, media_type = _extract_media(item)

        return RawSourceItem(
            external_id=item["id"],
            external_parent_id=item.get("inReplyToId"),
            record_type="social_post",
            body=item.get("text"),
            source_url=item.get("twitterUrl") or item.get("url"),
            published_at=published_at,
            author_external_id_hash=_hash(author.get("userName")),
            engagement_count=_non_negative(item.get("likeCount")),
            reply_count=_non_negative(item.get("replyCount")),
            language_hint=item.get("lang"),
            media_url=media_url,
            media_type=media_type,
            source_metadata={
                "retweet_count": item.get("retweetCount"),
                "view_count": item.get("viewCount"),
                "is_reply": item.get("isReply"),
            },
        )


def _extract_media(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Apify's docs confirm a top-level `media`/`extendedEntities` field
    exists on this actor's output but don't document the media object's
    internal shape — this follows the standard Twitter API v1.1 media-entity
    convention (`extendedEntities.media[]`, `type` in
    {"photo","video","animated_gif"}, `media_url_https`,
    `video_info.variants[]`), which `extendedEntities` being present at all
    strongly suggests this actor mirrors. NOT verified against a live run —
    spot-check once APIFY_TOKEN is configured, before relying on this."""
    extended_entities = item.get("extendedEntities") or {}
    media_list = extended_entities.get("media") or item.get("media") or []
    if not media_list:
        return None, None

    first = media_list[0]
    media_kind = first.get("type")
    if media_kind == "photo":
        return first.get("media_url_https") or first.get("media_url"), "image"
    if media_kind in ("video", "animated_gif"):
        variants = (first.get("video_info") or {}).get("variants") or []
        mp4_variants = [v for v in variants if v.get("content_type") == "video/mp4"]
        best = max(mp4_variants, key=lambda v: v.get("bitrate", 0), default=None)
        if best is not None:
            return best.get("url"), "video"
        if variants:
            return variants[0].get("url"), "video"
    return None, None


def _hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _non_negative(value: int | None) -> int | None:
    """Some platforms use -1 for hidden/unavailable counts — store as
    unknown (NULL) rather than violating raw_source_item's non-negative
    check constraints."""
    if value is None or value < 0:
        return None
    return value
