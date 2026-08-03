#!/usr/bin/env python
"""CLI entry point for Phase 1 ingestion — "pipeline mode" per
architecture.md §6.1: run collection directly for debugging, without going
through the API/worker.

Usage:
    python scripts/ingest.py google_play in.swiggy.android --limit 200 --process
    python scripts/ingest.py public_web https://example.com/article --process
    python scripts/ingest.py public_web https://example.com/a --urls https://example.com/b --process
    python scripts/ingest.py apple_app_store 310633997 --country us --limit 50
    python scripts/ingest.py reddit "quick commerce" --search-terms "quick commerce" "Instamart" --limit 50
    python scripts/ingest.py twitter "" --search-terms "Swiggy Instamart" --limit 50
    python scripts/ingest.py instagram "" --hashtags instamart swiggyinstamart --limit 50
    python scripts/ingest.py forum "" --urls https://example-forum.com/thread-1 --limit 20
    python scripts/ingest.py mouthshut "" --limit 20
    python scripts/ingest.py quickcommerce "" --limit 30

Every new source (apple_app_store, reddit, twitter, instagram) is genuinely
pay-per-result/metered except apple_app_store — keep --limit modest,
especially for twitter/instagram. forum/mouthshut are polite, rate-limited
crawls (see `sources/crawl_safety.py`); quickcommerce is a free RSS pull.
"""

import argparse
import asyncio
import socket
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

# Every connector's own HTTP client sets an explicit timeout (see
# sources/apify_actor.py, apple_app_store.py, public_web.py, web_crawler.py)
# except google_play.py, which goes through the google_play_scraper library's
# raw urlopen() call with no timeout at all. Confirmed live: from a cloud
# host's IP, Google Play silently black-holed the connection and the process
# hung indefinitely — asyncio.wait_for() around the collection call (see
# ingestion/service.py) unblocks the *application* logic correctly, but
# can't stop the underlying OS thread genuinely stuck in a blocking socket
# call, and Python's ThreadPoolExecutor waits for every worker thread to
# finish before the process can exit — so the whole `ingest.py` subprocess
# stayed hung even though the timeout fired internally. This process-wide
# default is the actual fix: it makes the stuck socket call itself raise
# rather than block forever, so the thread — and therefore the process —
# can actually finish. Safe to set globally here since each `ingest.py`
# invocation is a single-purpose, single-connector process (see this
# script's own docstring), and every other connector already manages its
# own httpx timeout independently of this socket-module default.
socket.setdefaulttimeout(120)

from instamart_engine.core.config import Settings, get_settings  # noqa: E402
from instamart_engine.core.database import get_session_factory  # noqa: E402
from instamart_engine.feedback.pipeline import process_unprocessed_items  # noqa: E402
from instamart_engine.ingestion.models import IngestionRunStatus  # noqa: E402
from instamart_engine.ingestion.service import run_ingestion  # noqa: E402
from instamart_engine.sources.apple_app_store import AppleAppStoreConnector  # noqa: E402
from instamart_engine.sources.base import SourceConfig  # noqa: E402
from instamart_engine.sources.google_play import GooglePlayConnector  # noqa: E402
from instamart_engine.sources.instagram import InstagramApifyConnector  # noqa: E402
from instamart_engine.sources.models import ConnectorType  # noqa: E402
from instamart_engine.sources.public_web import PublicWebConnector  # noqa: E402
from instamart_engine.sources.quickcommerce_rss import QuickCommerceRSSConnector  # noqa: E402
from instamart_engine.sources.reddit import RedditApifyConnector  # noqa: E402
from instamart_engine.sources.twitter import TwitterApifyConnector  # noqa: E402
from instamart_engine.sources.web_crawler import WebCrawlerConnector  # noqa: E402
from instamart_engine.storage.factory import build_raw_artifact_storage  # noqa: E402

# Verified live and relevant (real Swiggy Instamart complaint discussions)
# when this connector was built. consumercomplaints.in was tried first but
# its robots.txt genuinely disallows crawling this section, so it's not
# used. consumercourt.net's robots.txt permits it but its WAF 403s the
# actual page fetch regardless of user agent — kept as a second seed since
# the connector skips per-page failures gracefully rather than aborting.
_FORUM_DEFAULT_SEED_URLS = [
    "https://consumercomplaintscourt.com/tag/swiggy-instamart/",
    "https://consumercourt.net/threads/swiggy-instamart.2162/",
]
# The Swiggy reviews listing page on MouthShut, verified live; links to
# individual review pages the crawler discovers and follows.
_MOUTHSHUT_DEFAULT_SEED_URLS = [
    "https://www.mouthshut.com/websites/swiggy-reviews-925740914",
]


@dataclass(frozen=True, slots=True)
class SourceSetup:
    connector: Any
    connector_type: ConnectorType
    connector_key: str
    connector_display_name: str
    configuration: dict = field(default_factory=dict)
    supports_thread_context: bool = False


def _setup_google_play(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=GooglePlayConnector(lang=args.lang, country=args.country),
        connector_type=ConnectorType.LIBRARY,
        connector_key="google_play",
        connector_display_name="Google Play",
    )


def _setup_public_web(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=PublicWebConnector(),
        connector_type=ConnectorType.HTTP,
        connector_key="public_web",
        connector_display_name="Public Web",
        configuration={"urls": args.urls} if args.urls else {},
    )


def _setup_apple_app_store(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=AppleAppStoreConnector(country=args.country),
        connector_type=ConnectorType.DIRECT_API,
        connector_key="apple_app_store",
        connector_display_name="Apple App Store",
    )


def _setup_reddit(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=RedditApifyConnector(api_token=settings.APIFY_TOKEN or ""),
        connector_type=ConnectorType.APIFY,
        connector_key="reddit",
        connector_display_name="Reddit",
        configuration={"searches": args.search_terms} if args.search_terms else {},
        supports_thread_context=True,
    )


def _setup_twitter(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=TwitterApifyConnector(api_token=settings.APIFY_TOKEN or ""),
        connector_type=ConnectorType.APIFY,
        connector_key="twitter",
        connector_display_name="Twitter/X",
        configuration={"searchTerms": args.search_terms} if args.search_terms else {},
        supports_thread_context=True,
    )


def _setup_instagram(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=InstagramApifyConnector(api_token=settings.APIFY_TOKEN or ""),
        connector_type=ConnectorType.APIFY,
        connector_key="instagram",
        connector_display_name="Instagram",
        configuration={"hashtags": args.hashtags} if args.hashtags else {},
    )


def _setup_forum(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=WebCrawlerConnector(
            source_name="forum",
            seed_urls=args.urls or _FORUM_DEFAULT_SEED_URLS,
            record_type="forum_post",
        ),
        connector_type=ConnectorType.HTTP,
        connector_key="forum",
        connector_display_name="Community Forums",
    )


def _setup_mouthshut(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=WebCrawlerConnector(
            source_name="mouthshut",
            seed_urls=args.urls or _MOUTHSHUT_DEFAULT_SEED_URLS,
            record_type="product_review",
        ),
        connector_type=ConnectorType.HTTP,
        connector_key="mouthshut",
        connector_display_name="MouthShut",
    )


def _setup_quickcommerce(args: argparse.Namespace, settings: Settings) -> SourceSetup:
    return SourceSetup(
        connector=QuickCommerceRSSConnector(feed_urls=args.urls or None),
        connector_type=ConnectorType.RSS,
        connector_key="quickcommerce",
        connector_display_name="Quick-Commerce Industry Commentary",
    )


_SOURCE_REGISTRY: dict[str, Callable[[argparse.Namespace, Settings], SourceSetup]] = {
    "google_play": _setup_google_play,
    "public_web": _setup_public_web,
    "apple_app_store": _setup_apple_app_store,
    "reddit": _setup_reddit,
    "twitter": _setup_twitter,
    "instagram": _setup_instagram,
    "forum": _setup_forum,
    "mouthshut": _setup_mouthshut,
    "quickcommerce": _setup_quickcommerce,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Phase 1 ingestion collection.")
    parser.add_argument("source", choices=sorted(_SOURCE_REGISTRY))
    parser.add_argument(
        "target",
        help=(
            "Android package id (google_play), seed URL (public_web), numeric app id "
            "(apple_app_store) — leave blank ('') for reddit/twitter/instagram/forum/"
            "mouthshut/quickcommerce, which are driven by --search-terms/--hashtags/"
            "--urls instead"
        ),
    )
    parser.add_argument(
        "--urls",
        nargs="*",
        default=[],
        help=(
            "Extra URLs for public_web; crawl seed URLs for forum/mouthshut "
            "(defaults to a verified real seed if omitted); feed URLs for "
            "quickcommerce (defaults to Entrackr/Inc42/YourStory if omitted)"
        ),
    )
    parser.add_argument("--limit", type=int, default=None, help="Max records to collect")
    parser.add_argument("--lang", default="en", help="google_play only")
    parser.add_argument("--country", default="in", help="google_play / apple_app_store")
    parser.add_argument(
        "--search-terms",
        nargs="*",
        default=[],
        help="Override the default keyword list for reddit/twitter (default: INSTAMART_SEARCH_TERMS)",
    )
    parser.add_argument(
        "--hashtags",
        nargs="*",
        default=[],
        help="Hashtags for instagram (default: instamart/swiggyinstamart/quickcommerceindia)",
    )
    parser.add_argument(
        "--config-name", default=None, help="Collection config name (defaults to the target id)"
    )
    parser.add_argument(
        "--process",
        action="store_true",
        help="Also run the normalization pipeline on newly ingested raw items",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    storage = build_raw_artifact_storage(settings)
    session_factory = get_session_factory()

    setup = _SOURCE_REGISTRY[args.source](args, settings)

    config_name = args.config_name or args.target or args.source
    source_config = SourceConfig(
        target_identifier=args.target or args.source,
        configuration=setup.configuration,
        record_limit=args.limit,
    )

    async with session_factory() as session:
        run = await run_ingestion(
            session,
            connector=setup.connector,
            connector_type=setup.connector_type,
            connector_key=setup.connector_key,
            connector_display_name=setup.connector_display_name,
            connector_version="cli-1",
            config_name=config_name,
            source_config=source_config,
            storage=storage,
            supports_thread_context=setup.supports_thread_context,
        )

        status_icon = "OK" if run.status == IngestionRunStatus.COMPLETED else run.status.value.upper()
        print(f"[{status_icon}] ingestion_run={run.id}")
        print(
            f"  discovered={run.records_discovered} stored={run.records_stored} "
            f"failed={run.records_failed}"
        )
        if run.failure_message:
            print(f"  failure: {run.failure_code}: {run.failure_message}")

        if args.process:
            summary = await process_unprocessed_items(session)
            print(
                f"[PROCESSED] {summary.processed} record(s); "
                f"duplicates={summary.marked_duplicate} malformed={summary.marked_malformed}"
            )


if __name__ == "__main__":
    asyncio.run(main())
