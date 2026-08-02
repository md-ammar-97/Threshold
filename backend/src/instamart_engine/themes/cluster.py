"""Theme discovery: cluster embeddings, store provisional memberships, and
select representative/contradictory evidence. architecture.md §15.2.

Naming/summarization (the LLM step) is a separate pass — see
`themes/synthesize.py` — so a `theme_set` can exist in a
`ready_for_review` state with real cluster assignments before any paid
model call happens.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import numpy as np
from sklearn.cluster import HDBSCAN
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.embed import get_current_embedding_configuration
from instamart_engine.analysis.embedding_repository import get_embedded_feedback_records
from instamart_engine.core.logging import get_logger
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import ThemeSetStatus

logger = get_logger(__name__)

CLUSTERING_VERSION = "sklearn-hdbscan-v1"
# THM-002 — below this many eligible records, HDBSCAN's density assumptions
# aren't meaningful; fall back to "no clusters, all outliers" rather than
# force a low-quality result.
MIN_RECORDS_FOR_CLUSTERING = 10
DEFAULT_MIN_CLUSTER_SIZE = 3
MAX_REPRESENTATIVE_PER_THEME = 5


@dataclass(frozen=True, slots=True)
class ClusteringSummary:
    theme_set_id: UUID | None
    eligible_record_count: int
    clustered_record_count: int
    outlier_record_count: int
    theme_count: int


async def discover_themes(
    session: AsyncSession,
    *,
    analysis_run_id: UUID,
    source_connector_id: UUID | None = None,
    min_cluster_size: int | None = None,
    limit: int = 5000,
    provider: str | None = None,
) -> ClusteringSummary:
    # Must resolve the same way embed_unembedded_records wrote its rows —
    # a hardcoded provider/version_key here previously caused clustering to
    # silently read a different (empty) embedding configuration than the one
    # actually populated under the default EMBEDDING_PROVIDER=hosted (F-8).
    # `provider` defaults to settings.EMBEDDING_PROVIDER; pass it explicitly
    # to pin a provider (e.g. in tests that must stay offline — same pattern
    # as embed_unembedded_records/embed_query_text).
    embedding_config = await get_current_embedding_configuration(session, provider=provider)
    if embedding_config is None:
        # Distinct from "no eligible records" below — this means no
        # embeddings exist yet at all under the active provider, not that
        # eligible records exist but aren't embedded.
        logger.warning("theme_discovery_skipped_no_embedding_configuration")
        return ClusteringSummary(
            theme_set_id=None,
            eligible_record_count=0,
            clustered_record_count=0,
            outlier_record_count=0,
            theme_count=0,
        )

    records_and_vectors = await get_embedded_feedback_records(
        session,
        embedding_configuration_id=embedding_config.id,
        source_connector_id=source_connector_id,
        limit=limit,
    )
    eligible_count = len(records_and_vectors)

    if eligible_count == 0:
        # THM-001 — do not run clustering at all.
        logger.warning("theme_discovery_skipped_no_eligible_records")
        return ClusteringSummary(
            theme_set_id=None,
            eligible_record_count=0,
            clustered_record_count=0,
            outlier_record_count=0,
            theme_count=0,
        )

    records = [record for record, _ in records_and_vectors]
    vectors = np.array([vector for _, vector in records_and_vectors], dtype=np.float32)

    if eligible_count < MIN_RECORDS_FOR_CLUSTERING:
        labels = np.full(eligible_count, -1)
        algorithm = "small_data_fallback"
        effective_min_cluster_size = None
    else:
        effective_min_cluster_size = min_cluster_size or max(
            2, min(DEFAULT_MIN_CLUSTER_SIZE, eligible_count // 5)
        )
        # copy=True: guarantees HDBSCAN never mutates `vectors` in place,
        # which we still read afterwards to compute cluster centroids.
        clusterer = HDBSCAN(
            min_cluster_size=effective_min_cluster_size, metric="euclidean", copy=True
        )
        labels = clusterer.fit_predict(vectors)
        algorithm = "hdbscan"

    theme_set = await theme_repo.create_theme_set(
        session,
        analysis_run_id=analysis_run_id,
        name=f"theme-set-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}",
        clustering_algorithm=algorithm,
        clustering_configuration={
            "min_cluster_size": effective_min_cluster_size,
            "version": CLUSTERING_VERSION,
            "embedding_version": embedding_config.version_key,
        },
        eligible_record_count=eligible_count,
    )
    await session.commit()

    outlier_count = int((labels == -1).sum())
    clustered_count = eligible_count - outlier_count
    unique_labels = sorted(int(label) for label in set(labels.tolist()) if label != -1)

    theme_count = 0
    for cluster_label in unique_labels:
        member_indices = [i for i, label in enumerate(labels) if label == cluster_label]
        member_vectors = vectors[member_indices]
        centroid = member_vectors.mean(axis=0)
        centroid_unit = centroid / (np.linalg.norm(centroid) + 1e-9)
        similarities = member_vectors @ centroid_unit
        order = np.argsort(-similarities)

        theme = await theme_repo.create_provisional_theme(
            session,
            theme_set_id=theme_set.id,
            theme_key=f"cluster_{cluster_label}",
            placeholder_name=f"Unnamed cluster {cluster_label}",
            representative_record_count=len(member_indices),
        )

        top_k = min(MAX_REPRESENTATIVE_PER_THEME, len(member_indices))
        for rank, local_idx in enumerate(order.tolist(), start=1):
            record = records[member_indices[local_idx]]
            score = float(max(0.0, min(1.0, similarities[local_idx])))
            is_representative = rank <= top_k
            is_counterexample = rank == len(order) and not is_representative
            await theme_repo.add_theme_membership(
                session,
                theme_id=theme.id,
                feedback_record_id=record.id,
                membership_score=score,
                assignment_method=CLUSTERING_VERSION,
                is_representative=is_representative,
                is_counterexample=is_counterexample,
                rank_within_theme=rank,
            )
        await session.commit()
        theme_count += 1

    await theme_repo.finalize_theme_set(
        session,
        theme_set=theme_set,
        clustered_record_count=clustered_count,
        outlier_record_count=outlier_count,
        theme_count=theme_count,
        status=ThemeSetStatus.READY_FOR_REVIEW if theme_count > 0 else ThemeSetStatus.REJECTED,
    )
    await session.commit()

    return ClusteringSummary(
        theme_set_id=theme_set.id,
        eligible_record_count=eligible_count,
        clustered_record_count=clustered_count,
        outlier_record_count=outlier_count,
        theme_count=theme_count,
    )
