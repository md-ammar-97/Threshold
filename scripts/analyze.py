#!/usr/bin/env python
"""CLI entry point for Phase 3/4 analysis — embed, cluster, (optionally)
synthesize themes, and (optionally) generate insights from them. "Pipeline
mode" per architecture.md §6.1.

Usage:
    python scripts/analyze.py --source-key google_play --limit 500
    python scripts/analyze.py --source-key google_play --synthesize
    python scripts/analyze.py --source-key google_play --synthesize --generate-insights
"""

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from sqlalchemy import select  # noqa: E402

from instamart_engine.ai.exceptions import AIGatewayError  # noqa: E402
from instamart_engine.analysis.classify import ensure_classification_prompt_and_model  # noqa: E402
from instamart_engine.analysis.embed import embed_unembedded_records  # noqa: E402
from instamart_engine.analysis.repository import create_analysis_run  # noqa: E402
from instamart_engine.core.database import get_session_factory  # noqa: E402
from instamart_engine.feedback.repository import (  # noqa: E402
    get_distinct_source_connector_count,
)
from instamart_engine.insights.synthesize import generate_insights_for_theme_set  # noqa: E402
from instamart_engine.sources.models import SourceConnectorModel  # noqa: E402
from instamart_engine.taxonomy.repository import get_published_taxonomy  # noqa: E402
from instamart_engine.taxonomy.seed_v3 import load_taxonomy_v3  # noqa: E402
from instamart_engine.themes.cluster import discover_themes  # noqa: E402
from instamart_engine.themes.metrics import compute_theme_metrics_and_scores  # noqa: E402
from instamart_engine.themes.synthesize import synthesize_theme_set  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed, cluster, and synthesize themes.")
    parser.add_argument("--source-key", default=None, help="Only analyze this connector's records")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-cluster-size", type=int, default=None)
    parser.add_argument(
        "--synthesize",
        action="store_true",
        help="Also call the LLM to name/summarize themes (requires GROQ_API_KEY)",
    )
    parser.add_argument(
        "--generate-insights",
        action="store_true",
        help="Also call the LLM to generate insights from synthesized themes "
        "(requires --synthesize and GROQ_API_KEY)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    session_factory = get_session_factory()

    async with session_factory() as session:
        await load_taxonomy_v3(session)
        taxonomy_version = await get_published_taxonomy(session)
        _prompt_version, model_configuration = await ensure_classification_prompt_and_model(session)
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

        embed_summary = await embed_unembedded_records(
            session, source_connector_id=source_connector_id, limit=args.limit
        )
        print(f"[EMBEDDED] selected={embed_summary.selected} embedded={embed_summary.embedded}")

        analysis_run = await create_analysis_run(
            session,
            name="theme-discovery",
            taxonomy_version_id=taxonomy_version.id,
            classification_model_configuration_id=model_configuration.id,
            dataset_snapshot={"source_key": args.source_key, "limit": args.limit},
        )
        await session.commit()

        cluster_summary = await discover_themes(
            session,
            analysis_run_id=analysis_run.id,
            source_connector_id=source_connector_id,
            min_cluster_size=args.min_cluster_size,
        )
        print(
            f"[CLUSTERED] eligible={cluster_summary.eligible_record_count} "
            f"clustered={cluster_summary.clustered_record_count} "
            f"outliers={cluster_summary.outlier_record_count} "
            f"themes={cluster_summary.theme_count}"
        )

        if cluster_summary.theme_set_id is None or cluster_summary.theme_count == 0:
            return

        if args.synthesize:
            try:
                synthesis_summary = await synthesize_theme_set(
                    session, theme_set_id=cluster_summary.theme_set_id
                )
                print(
                    f"[SYNTHESIZED] total={synthesis_summary.themes_total} "
                    f"synthesized={synthesis_summary.synthesized} "
                    f"failed={synthesis_summary.failed}"
                )
            except AIGatewayError as exc:
                print(f"[SYNTHESIS FAILED] {type(exc).__name__}: {exc}")

        total_source_connectors = await get_distinct_source_connector_count(session)
        metrics_results = await compute_theme_metrics_and_scores(
            session,
            theme_set_id=cluster_summary.theme_set_id,
            total_source_connectors=total_source_connectors,
        )
        for result in metrics_results:
            print(
                f"[METRICS] theme={result.theme_id} records={result.record_count} "
                f"opportunity_score={result.opportunity_score:.2f}"
            )

        if args.generate_insights:
            if not args.synthesize:
                print("[INSIGHTS SKIPPED] --generate-insights requires --synthesize")
            else:
                try:
                    insight_summary = await generate_insights_for_theme_set(
                        session, theme_set_id=cluster_summary.theme_set_id
                    )
                    print(
                        f"[INSIGHTS] total={insight_summary.themes_total} "
                        f"generated={insight_summary.generated} "
                        f"published={insight_summary.published} "
                        f"blocked={insight_summary.blocked} "
                        f"failed={insight_summary.failed}"
                    )
                except AIGatewayError as exc:
                    print(f"[INSIGHT GENERATION FAILED] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
