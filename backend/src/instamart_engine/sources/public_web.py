"""Public web / forum connector: direct HTTP extraction for ordinary pages.

architecture.md §10.2. Playwright (rendered pages) and Apify (crawler
fallback) are documented as pluggable alternatives but out of scope for
Phase 1 — this connector only handles plain server-rendered HTML.

The connector returns one `article_passage` item per fetched URL without
making a relevance/quality judgement about it (architecture.md §10 — "A
connector returns source-native items without applying research
classifications"); an empty or unextractable page still produces an item so
downstream normalization (feedback pipeline) can mark it
`insufficient_content` rather than the connector silently dropping it.
"""

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import trafilatura

from instamart_engine.sources.base import (
    CollectionRequest,
    ConnectorCheckpoint,
    RawSourceItem,
    SourceConfig,
)
from instamart_engine.sources.exceptions import (
    SourceAuthError,
    SourceBlockedContentError,
    SourceConfigError,
    SourceRateLimitedError,
    SourceTransientError,
    SourceUnavailableError,
)
from instamart_engine.sources.ssrf import validate_public_url

# ING-013 — best-effort, not a guarantee: if a page is challenge-gated we
# stop rather than attempt any automated bypass.
_CHALLENGE_MARKERS = ("g-recaptcha", "cf-challenge", "captcha-delivery", "id=\"challenge-running\"")


class PublicWebConnector:
    source_name = "public_web"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "instamart-discovery-engine-research-bot/0.1"},
        )
        self._last_checkpoint: ConnectorCheckpoint | None = None

    def _urls_from_config(self, config: SourceConfig) -> list[str]:
        urls: list[str] = []
        if config.target_identifier:
            urls.append(config.target_identifier)
        urls.extend(config.configuration.get("urls", []))
        seen: set[str] = set()
        deduped = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    def validate_config(self, config: SourceConfig) -> None:
        urls = self._urls_from_config(config)
        if not urls:
            raise SourceConfigError(
                "public_web requires target_identifier or configuration['urls']"
            )
        allow_http = bool(config.configuration.get("allow_http", False))
        for url in urls:
            validate_public_url(url, allow_http=allow_http)  # SRC-012/013

    def collect(self, request: CollectionRequest) -> Iterator[RawSourceItem]:
        config = request.config
        self.validate_config(config)
        urls = self._urls_from_config(config)

        if request.checkpoint is not None and request.checkpoint.is_terminal:
            self._last_checkpoint = request.checkpoint
            return

        start_index = 0
        if request.checkpoint is not None:
            start_index = request.checkpoint.checkpoint_value.get("next_index", 0)

        limit = config.record_limit or len(urls)
        fetched = 0
        index = start_index

        while index < len(urls) and fetched < limit:
            url = urls[index]
            index += 1
            yield self._fetch_one(url)
            fetched += 1

        is_terminal = index >= len(urls)
        self._last_checkpoint = ConnectorCheckpoint(
            checkpoint_type="url_index",
            checkpoint_value={"next_index": index},
            is_terminal=is_terminal,
        )

    def checkpoint(self) -> ConnectorCheckpoint | None:
        return self._last_checkpoint

    def _fetch_one(self, url: str) -> RawSourceItem:
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SourceTransientError(f"Timeout fetching {url!r}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429:
                retry_after = exc.response.headers.get("retry-after")
                raise SourceRateLimitedError(
                    f"Rate limited fetching {url!r}",
                    retry_after_seconds=float(retry_after) if retry_after else None,
                ) from exc
            if status in (401, 403):
                raise SourceAuthError(f"Access denied fetching {url!r}: {status}") from exc
            if status == 404:
                raise SourceUnavailableError(f"Not found: {url!r}") from exc
            if 500 <= status < 600:
                raise SourceTransientError(f"Server error {status} fetching {url!r}") from exc
            raise SourceUnavailableError(f"Unexpected status {status} fetching {url!r}") from exc
        except httpx.HTTPError as exc:
            raise SourceTransientError(f"Network error fetching {url!r}: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type:
            # ING-015 — unexpected content type; retain metadata, don't parse it as HTML.
            return RawSourceItem(
                external_id=self._external_id_for(url),
                record_type="article_passage",
                body=None,
                source_url=url,
                source_metadata={
                    "content_type": content_type,
                    "extraction_status": "wrong_content_type",
                },
            )

        if any(marker in response.text for marker in _CHALLENGE_MARKERS):
            raise SourceBlockedContentError(f"Challenge/CAPTCHA content detected at {url!r}")

        extracted_json = trafilatura.extract(
            response.text,
            url=url,
            include_comments=False,
            favor_recall=False,
            with_metadata=True,
            output_format="json",
        )

        title: str | None = None
        body: str | None = None
        published_at: datetime | None = None
        site_name: str | None = None
        author: str | None = None
        extraction_status = "ok"

        if extracted_json:
            data = json.loads(extracted_json)
            title = data.get("title") or None
            body = (data.get("text") or "").strip() or None
            site_name = data.get("sitename") or None
            author = data.get("author") or None
            published_at = self._parse_date(data.get("date"))
        else:
            extraction_status = "no_extractable_content"

        if not body:
            extraction_status = "empty"

        return RawSourceItem(
            external_id=self._external_id_for(url),
            record_type="article_passage",
            title=title,
            body=body,
            source_url=url,
            published_at=published_at,
            source_metadata={
                "site_name": site_name,
                "author_display_name": author,  # not hashed: byline, not a commenting user
                "extraction_status": extraction_status,
            },
        )

    def _external_id_for(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                continue
        return None
