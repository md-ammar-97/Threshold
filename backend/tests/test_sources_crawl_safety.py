"""Unit tests for crawl hygiene primitives (`CrawlBudget`, `RateLimiter`).
`RobotsChecker` fetches `robots.txt` over the real network via `urllib` and
is exercised indirectly through `test_sources_web_crawler.py`'s injected
stub instead of tested directly here."""

import time

from instamart_engine.sources.crawl_safety import CrawlBudget, RateLimiter


def test_crawl_budget_rejects_urls_beyond_max_depth() -> None:
    budget = CrawlBudget(seed_urls=["https://forum.example/a"], max_depth=1, max_pages=100)
    assert budget.should_visit("https://forum.example/b", depth=1) is True
    assert budget.should_visit("https://forum.example/c", depth=2) is False


def test_crawl_budget_rejects_urls_beyond_max_pages() -> None:
    budget = CrawlBudget(seed_urls=["https://forum.example/a"], max_depth=5, max_pages=1)
    budget.mark_visited("https://forum.example/a")
    assert budget.should_visit("https://forum.example/b", depth=1) is False


def test_crawl_budget_dedupes_visited_urls() -> None:
    budget = CrawlBudget(seed_urls=["https://forum.example/a"], max_depth=5, max_pages=100)
    budget.mark_visited("https://forum.example/a")
    assert budget.should_visit("https://forum.example/a", depth=0) is False


def test_crawl_budget_rejects_off_domain_urls_when_same_domain_only() -> None:
    budget = CrawlBudget(
        seed_urls=["https://forum.example/a"], max_depth=5, max_pages=100, same_domain_only=True
    )
    assert budget.should_visit("https://other.example/b", depth=1) is False
    assert budget.should_visit("https://forum.example/b", depth=1) is True


def test_crawl_budget_allows_off_domain_urls_when_disabled() -> None:
    budget = CrawlBudget(
        seed_urls=["https://forum.example/a"], max_depth=5, max_pages=100, same_domain_only=False
    )
    assert budget.should_visit("https://other.example/b", depth=1) is True


def test_rate_limiter_waits_at_least_the_minimum_interval() -> None:
    limiter = RateLimiter(min_interval_seconds=0.05)
    limiter.wait()
    start = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.04  # small tolerance for scheduler jitter


def test_rate_limiter_does_not_wait_on_first_call() -> None:
    limiter = RateLimiter(min_interval_seconds=5.0)
    start = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed < 1.0
