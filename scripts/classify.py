#!/usr/bin/env python
"""CLI entry point for Phase 2 classification — "pipeline mode" per
architecture.md §6.1, mirroring scripts/ingest.py.

Usage:
    python scripts/classify.py --limit 50
    python scripts/classify.py --limit 50 --source-key google_play
"""

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from sqlalchemy import select  # noqa: E402

from instamart_engine.ai.exceptions import AIGatewayError  # noqa: E402
from instamart_engine.analysis.classify import classify_unclassified_records  # noqa: E402
from instamart_engine.core.database import get_session_factory  # noqa: E402
from instamart_engine.sources.models import SourceConnectorModel  # noqa: E402
from instamart_engine.taxonomy.seed_v3 import load_taxonomy_v3  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify unclassified feedback records.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--source-key", default=None, help="Only classify records from this connector key"
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    session_factory = get_session_factory()

    async with session_factory() as session:
        await load_taxonomy_v3(session)
        await session.commit()

        source_connector_id = None
        if args.source_key:
            connector = await session.scalar(
                select(SourceConnectorModel).where(SourceConnectorModel.key == args.source_key)
            )
            if connector is None:
                print(f"No source_connector found with key={args.source_key!r}")
                return
            source_connector_id = connector.id

        try:
            summary = await classify_unclassified_records(
                session, limit=args.limit, source_connector_id=source_connector_id
            )
        except AIGatewayError as exc:
            print(f"[FAILED] {type(exc).__name__}: {exc}")
            raise SystemExit(1) from exc

        print(
            f"[CLASSIFIED] selected={summary.selected} "
            f"classified={summary.classified} failed={summary.failed}"
        )


if __name__ == "__main__":
    asyncio.run(main())
