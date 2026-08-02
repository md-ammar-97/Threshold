#!/usr/bin/env python
"""CLI entry point for the Phase 1 media pipeline — OCR on images,
speech-to-text on video/audio — "pipeline mode" per architecture.md §6.1,
mirroring scripts/classify.py. Run after scripts/ingest.py's --process step
and before scripts/classify.py, so classification sees the combined text.

Usage:
    python scripts/extract_media.py --limit 50
    python scripts/extract_media.py --limit 50 --source-key instagram
"""

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from sqlalchemy import select  # noqa: E402

from instamart_engine.core.config import get_settings  # noqa: E402
from instamart_engine.core.database import get_session_factory  # noqa: E402
from instamart_engine.feedback.media_extraction import (  # noqa: E402
    extract_media_for_pending_records,
)
from instamart_engine.sources.models import SourceConnectorModel  # noqa: E402
from instamart_engine.storage.factory import build_raw_artifact_storage  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and OCR/transcribe media for pending feedback records."
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--source-key", default=None, help="Only process records from this connector key"
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    storage = build_raw_artifact_storage(settings)
    session_factory = get_session_factory()

    async with session_factory() as session:
        source_connector_id = None
        if args.source_key:
            connector = await session.scalar(
                select(SourceConnectorModel).where(SourceConnectorModel.key == args.source_key)
            )
            if connector is None:
                print(f"No source_connector found with key={args.source_key!r}")
                return
            source_connector_id = connector.id

        summary = await extract_media_for_pending_records(
            session, storage=storage, source_connector_id=source_connector_id, limit=args.limit
        )

        print(
            f"[MEDIA_EXTRACTED] selected={summary.selected} "
            f"extracted={summary.extracted} failed={summary.failed}"
        )


if __name__ == "__main__":
    asyncio.run(main())
