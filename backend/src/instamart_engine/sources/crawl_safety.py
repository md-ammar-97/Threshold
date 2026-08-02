"""Shared crawl hygiene for connectors that discover and traverse multiple
pages within a domain (`web_crawler.py`). Nothing else in this codebase
rate-limits, checks robots.txt, or bounds crawl depth/page count —
`public_web.py` only ever fetches a fixed, caller-supplied URL list with no
discovery, so it never needed any of this.
"""

import time
import urllib.robotparser
from urllib.parse import urlparse


class RateLimiter:
    """Enforces a minimum delay between successive requests."""

    def __init__(self, *, min_interval_seconds: float = 1.0) -> None:
        self._min_interval = min_interval_seconds
        self._last_request_at: float | None = None

    def wait(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self._min_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()


class RobotsChecker:
    """One `robots.txt` parser per domain, fetched lazily and cached for the
    connector's lifetime."""

    def __init__(self, *, user_agent: str) -> None:
        self._user_agent = user_agent
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._parsers:
            self._parsers[origin] = self._fetch_parser(origin)
        parser = self._parsers[origin]
        if parser is None:
            # No robots.txt / unreachable — treat as allow-all rather than
            # blocking a crawl over a transient fetch failure.
            return True
        return parser.can_fetch(self._user_agent, url)

    def _fetch_parser(self, origin: str) -> urllib.robotparser.RobotFileParser | None:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            parser.read()
        except OSError:
            return None
        return parser


class CrawlBudget:
    """Bounds one crawl: same-domain-only, max depth, max pages, visited-set
    dedup."""

    def __init__(
        self,
        *,
        seed_urls: list[str],
        max_depth: int = 2,
        max_pages: int = 30,
        same_domain_only: bool = True,
    ) -> None:
        self._seed_domains = {urlparse(u).netloc for u in seed_urls}
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.same_domain_only = same_domain_only
        self._visited: set[str] = set()

    def should_visit(self, url: str, *, depth: int) -> bool:
        if len(self._visited) >= self.max_pages:
            return False
        if depth > self.max_depth:
            return False
        if url in self._visited:
            return False
        if self.same_domain_only and urlparse(url).netloc not in self._seed_domains:
            return False
        return True

    def mark_visited(self, url: str) -> None:
        self._visited.add(url)

    @property
    def visited_count(self) -> int:
        return len(self._visited)
