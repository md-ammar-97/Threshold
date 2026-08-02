#!/usr/bin/env python
"""CLI wrapper for `validation/gold_loader.py` — loads real, human-authored
gold annotations from a JSONL file into the evaluation dataset / two-
annotator adjudication system. Infrastructure only: this repo ships no gold
data. See `data/evaluation/README.md` for the file format.

Usage:
    python scripts/load_gold_dataset.py data/evaluation/my_gold_set.jsonl \
        --dataset-version 2026-08-v1 \
        --dataset-name "Discovery-mechanism classification gold set" \
        --evaluation-type classification
"""

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from instamart_engine.core.database import get_session_factory  # noqa: E402
from instamart_engine.validation.gold_loader import (  # noqa: E402
    GoldDatasetFormatError,
    load_gold_dataset_from_file,
)
from instamart_engine.validation.models import EvaluationType  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load a gold-annotation JSONL file.")
    parser.add_argument("file_path", help="Path to the JSONL gold dataset file")
    parser.add_argument(
        "--dataset-version",
        required=True,
        help="version_key for the evaluation_dataset (get-or-create by this key)",
    )
    parser.add_argument(
        "--dataset-name",
        required=True,
        help="Human-readable name, only used if the dataset doesn't already exist",
    )
    parser.add_argument(
        "--evaluation-type",
        required=True,
        choices=[t.value for t in EvaluationType],
        help="Only used if the dataset doesn't already exist",
    )
    parser.add_argument(
        "--partition",
        default="validation",
        choices=["development", "validation", "blind_test"],
        help="ai_evals.md §6.1 partition; only used if the dataset doesn't already exist",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            loaded = await load_gold_dataset_from_file(
                session,
                file_path=args.file_path,
                dataset_version=args.dataset_version,
                dataset_name=args.dataset_name,
                evaluation_type=EvaluationType(args.evaluation_type),
                partition=args.partition,
            )
        except GoldDatasetFormatError as exc:
            print(f"[FAILED] {exc}")
            raise SystemExit(1) from exc

        print(f"[OK] loaded {loaded} gold item(s) into dataset_version={args.dataset_version!r}")


if __name__ == "__main__":
    asyncio.run(main())
