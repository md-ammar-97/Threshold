"""Generic web crawler for community forums and consumer-review platforms
that have no official API (`docs/problemstatement.md`'s "Forums and
product-review sites" row — MouthShut, Quora, PissedConsumer-style sites).

Unlike `public_web.py` (fetches a fixed, caller-supplied URL list), this
connector discovers same-domain links from each page it fetches and
traverses them up to a bounded depth/page count, using `trafilatura`'s own
comment-region heuristics (`include_comments=True`) as the realistic route
to per-thread content without a bespoke parser per site. It does not
implement `ApifyActorConnector`: that base class's `collect()` is always a
single terminal remote call with no real pagination, which doesn't fit a
crawl's need to fetch many pages and follow links between them.

Every `collect()` call performs one full bounded crawl from the seed URLs —
the same single-shot-per-call model as the Apify connectors (see the
`apify_actor.py` fix from this same phase: a prior run's checkpoint must not
gate whether this run is allowed to happen, since a re-crawl can legitimately
surface new threads/comments each time).
"""

import hashlib
import json
from collections import deque
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import lxml.etree
import lxml.html
import trafilatura

from instamart_engine.sources.base import (
    CollectionRequest,
    ConnectorCheckpoint,
    RawSourceItem,
    RecordType,
    SourceConfig,
)
from instamart_engine.sources.crawl_safety import CrawlBudget, RateLimiter, RobotsChecker
from instamart_engine.sources.exceptions import (
    SourceAuthError,
    SourceBlockedContentError,
    SourceConfigError,
    SourceRateLimitedError,
    SourceTransientError,
    SourceUnavailableError,
)
from instamart_engine.sources.ssrf import validate_public_url

_CHALLENGE_MARKERS = ("g-recaptcha", "cf-challenge", "captcha-delivery", 'id="challenge-running"')
# Deliberately not "...research-bot..." like public_web.py's UA: verified
# live against a real robots.txt (mouthshut.com) that "research" contains
# "es", which coincidentally substring-matched an old blocked-bot entry
# named "es" — `urllib.robotparser` matches user-agents by substring, not
# exact token, so a real word fragment can accidentally trip an unrelated
# block. This name was checked against that file's blocklist before use.
_USER_AGENT = "InstamartDiscoveryCrawler/0.1"
_SKIPPABLE_FETCH_ERRORS = (
    SourceAuthError,
    SourceBlockedContentError,
    SourceRateLimitedError,
    SourceTransientError,
    SourceUnavailableError,
)


class WebCrawlerConnector:
    """Implements `instamart_engine.sources.base.SourceConnector`."""

    def __init__(
        self,
        *,
        source_name: str,
        seed_urls: list[str],
        record_type: RecordType,
        max_depth: int = 2,
        max_pages: int = 30,
        same_domain_only: bool = True,
        rate_limit_seconds: float = 1.0,
        client: httpx.Client | None = None,
        robots_checker: RobotsChecker | None = None,
    ) -> None:
        self.source_name = source_name
        self._seed_urls = seed_urls
        self._record_type = record_type
        self._max_depth = max_depth
        self._max_pages = max_pages
        self._same_domain_only = same_domain_only
        self._client = client or httpx.Client(
            timeout=15.0, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
        )
        self._rate_limiter = RateLimiter(min_interval_seconds=rate_limit_seconds)
        self._robots = robots_checker or RobotsChecker(user_agent=_USER_AGENT)
        self._last_checkpoint: ConnectorCheckpoint | None = None

    def validate_config(self, config: SourceConfig) -> None:
        if not self._seed_urls:
            raise SourceConfigError(f"{self.source_name}: at least one seed URL is required")
        for url in self._seed_urls:
            validate_public_url(url)

    def collect(self, request: CollectionRequest) -> Iterator[RawSourceItem]:
        config = request.config
        self.validate_config(config)

        budget = CrawlBudget(
            seed_urls=self._seed_urls,
            max_depth=self._max_depth,
            max_pages=self._max_pages,
            same_domain_only=self._same_domain_only,
        )
        limit = config.record_limit or self._max_pages
        queue: deque[tuple[str, int]] = deque((url, 0) for url in self._seed_urls)
        yielded = 0

        while queue and yielded < limit:
            url, depth = queue.popleft()
            if not budget.should_visit(url, depth=depth):
                continue
            budget.mark_visited(url)

            if not self._robots.is_allowed(url):
                continue

            self._rate_limiter.wait()

            try:
                item, discovered_links = self._fetch_and_extract(url, depth=depth)
            except _SKIPPABLE_FETCH_ERRORS:
                continue

            if item is not None:
                yield item
                yielded += 1

            if depth < self._max_depth:
                for link in discovered_links:
                    if budget.should_visit(link, depth=depth + 1):
                        queue.append((link, depth + 1))

        self._last_checkpoint = ConnectorCheckpoint(
            checkpoint_type="crawl_run",
            checkpoint_value={"pages_visited": budget.visited_count},
            is_terminal=True,
        )

    def checkpoint(self) -> ConnectorCheckpoint | None:
        return self._last_checkpoint

    def _fetch_and_extract(
        self, url: str, *, depth: int
    ) -> tuple[RawSourceItem | None, list[str]]:
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
            return None, []

        if any(marker in response.text for marker in _CHALLENGE_MARKERS):
            raise SourceBlockedContentError(f"Challenge/CAPTCHA content detected at {url!r}")

        links = self._extract_links(response.text, base_url=url) if depth < self._max_depth else []
        item = self._extract_item(response.text, url=url)
        return item, links

    def _extract_links(self, html: str, *, base_url: str) -> list[str]:
        try:
            tree = lxml.html.fromstring(html)
            tree.make_links_absolute(base_url)
        except (lxml.etree.LxmlError, ValueError):
            return []
        hrefs = {link for _el, attr, link, _pos in tree.iterlinks() if attr == "href"}
        return [href for href in hrefs if href.startswith("http")]

    def _extract_item(self, html: str, *, url: str) -> RawSourceItem | None:
        extracted_json = trafilatura.extract(
            html,
            url=url,
            include_comments=True,
            favor_recall=True,
            with_metadata=True,
            output_format="json",
        )
        if not extracted_json:
            return None

        data = json.loads(extracted_json)
        body = (data.get("text") or "").strip() or None
        if not body:
            return None

        return RawSourceItem(
            external_id=self._external_id_for(url),
            record_type=self._record_type,
            title=data.get("title") or None,
            body=body,
            source_url=url,
            published_at=self._parse_date(data.get("date")),
            source_metadata={
                "site_name": data.get("sitename") or None,
                "author_display_name": data.get("author") or None,  # byline, not a commenting user
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
