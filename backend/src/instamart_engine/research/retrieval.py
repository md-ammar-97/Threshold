"""Hybrid evidence retrieval for a research question. architecture.md §17.3.

Retrieval order (all deterministic, no LLM):

1. structured filters (source/date/taxonomy, from the validated query plan);
2. matching themes/insights (top by opportunity_score in the session's
   theme_set/insight_set);
3. hybrid record search (pgvector cosine similarity + Postgres full-text
   search, both restricted to the structured-filtered population);
4. rerank (weighted combination of vector + keyword scores);
5. source-diversity balancing (cap per-source-connector concentration);
6. contradiction retrieval (force-include a counterexample if one exists
   and wasn't already selected);
7. context-size control (hard caps on themes/insights/records).

Every candidate considered is persisted to `retrieval_result`, advancing
through `retrieval_stage`, so the funnel is auditable end to end
(datamodel.md §42).
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.embed import embed_query_text, get_current_embedding_configuration
from instamart_engine.analysis.embedding_models import Embedding
from instamart_engine.analysis.models import AnalysisLabel, FeedbackAnalysis
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.insights.models import Insight
from instamart_engine.research import repository as research_repo
from instamart_engine.research.models import RetrievalObjectType, RetrievalStage
from instamart_engine.sources.models import SourceConnectorModel
from instamart_engine.taxonomy.models import TaxonomyDimension, TaxonomyLabel
from instamart_engine.themes.models import Theme, ThemeMembership

MAX_RECORD_CANDIDATES = 40
MAX_SELECTED_RECORDS = 12
MAX_SELECTED_THEMES = 3
MAX_SELECTED_INSIGHTS = 3
MAX_RECORDS_PER_SOURCE = 6
VECTOR_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4
EXCERPT_MAX_CHARS = 500

_EMBEDDABLE_QUALITY = (QualityStatus.USABLE, QualityStatus.LOW_INFORMATION)
_SKIPPED_RELEVANCE = (RelevanceStatus.INSUFFICIENT_CONTENT, RelevanceStatus.SPAM_OR_PROMOTION)


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    label: str
    object_type: RetrievalObjectType
    object_id: UUID
    title: str
    excerpt: str
    metadata: dict


@dataclass(frozen=True, slots=True)
class EvidencePackage:
    themes: list[EvidenceItem]
    insights: list[EvidenceItem]
    records: list[EvidenceItem]

    def is_empty(self) -> bool:
        return not (self.themes or self.insights or self.records)

    def all_items(self) -> list[EvidenceItem]:
        return [*self.themes, *self.insights, *self.records]

    def resolve(self, label: str) -> EvidenceItem | None:
        for item in self.all_items():
            if item.label == label:
                return item
        return None


def _base_record_filters(effective_filters: dict[str, str]) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        FeedbackRecord.quality_status.in_(_EMBEDDABLE_QUALITY),
        FeedbackRecord.relevance_status.not_in(_SKIPPED_RELEVANCE),
        FeedbackRecord.deleted_at.is_(None),
    ]
    if "date_from" in effective_filters:
        conditions.append(FeedbackRecord.published_at >= effective_filters["date_from"])
    if "date_to" in effective_filters:
        conditions.append(FeedbackRecord.published_at <= effective_filters["date_to"])
    return conditions


async def _select_themes(
    session: AsyncSession, *, research_question_id: UUID, theme_set_id: UUID
) -> list[EvidenceItem]:
    themes = (
        await session.scalars(
            select(Theme)
            .where(Theme.theme_set_id == theme_set_id, Theme.deleted_at.is_(None))
            .order_by(Theme.opportunity_score.desc().nulls_last())
            .limit(MAX_SELECTED_THEMES)
        )
    ).all()

    items: list[EvidenceItem] = []
    for rank, theme in enumerate(themes, start=1):
        label = f"T{rank}"
        await research_repo.upsert_retrieval_result(
            session,
            research_question_id=research_question_id,
            object_type=RetrievalObjectType.THEME,
            object_id=theme.id,
            retrieval_stage=RetrievalStage.SELECTED,
            structured_filter_score=1.0,
            final_rank=rank,
            selection_reason={"stage": "theme_insight_match", "label": label},
        )
        items.append(
            EvidenceItem(
                label=label,
                object_type=RetrievalObjectType.THEME,
                object_id=theme.id,
                title=theme.name,
                excerpt=theme.short_summary,
                metadata={
                    "theme_type": theme.theme_type.value,
                    "opportunity_score": float(theme.opportunity_score)
                    if theme.opportunity_score is not None
                    else None,
                },
            )
        )
    return items


async def _select_insights(
    session: AsyncSession, *, research_question_id: UUID, insight_set_id: UUID | None
) -> list[EvidenceItem]:
    if insight_set_id is None:
        return []

    insights = (
        await session.scalars(
            select(Insight)
            .where(Insight.insight_set_id == insight_set_id, Insight.deleted_at.is_(None))
            .order_by(Insight.opportunity_score.desc().nulls_last())
            .limit(MAX_SELECTED_INSIGHTS)
        )
    ).all()

    items: list[EvidenceItem] = []
    for rank, insight in enumerate(insights, start=1):
        label = f"I{rank}"
        await research_repo.upsert_retrieval_result(
            session,
            research_question_id=research_question_id,
            object_type=RetrievalObjectType.INSIGHT,
            object_id=insight.id,
            retrieval_stage=RetrievalStage.SELECTED,
            structured_filter_score=1.0,
            final_rank=rank,
            selection_reason={"stage": "theme_insight_match", "label": label},
        )
        items.append(
            EvidenceItem(
                label=label,
                object_type=RetrievalObjectType.INSIGHT,
                object_id=insight.id,
                title=insight.title,
                excerpt=insight.finding,
                metadata={
                    "insight_type": insight.insight_type.value,
                    "opportunity_score": float(insight.opportunity_score)
                    if insight.opportunity_score is not None
                    else None,
                },
            )
        )
    return items


async def _hybrid_record_candidates(
    session: AsyncSession,
    *,
    analysis_run_id: UUID,
    question_text: str,
    effective_filters: dict[str, str],
    provider: str | None = None,
) -> list[tuple[FeedbackRecord, float, float]]:
    """Returns (record, similarity[0-1], keyword_rank) sorted by vector
    similarity — the population retrieval draws its candidates from.
    `provider` defaults to settings.EMBEDDING_PROVIDER; pass it explicitly to
    pin a provider (e.g. in tests that must stay offline)."""
    embedding_configuration = await get_current_embedding_configuration(session, provider=provider)
    if embedding_configuration is None:
        return []

    query_vector = await embed_query_text(question_text, provider=provider)

    # Always scoped to this session's own analysis_run — retrieving a
    # record analyzed under a different dataset/taxonomy version would be
    # cross-version contamination (edgecases.md ANS-017; ai_evals.md §24.2
    # "cross-version contamination 0%"), even when no taxonomy filter is set.
    stmt = (
        select(
            FeedbackRecord,
            Embedding.embedding_vector.cosine_distance(query_vector).label("distance"),
            func.ts_rank_cd(
                func.to_tsvector(
                    "simple",
                    func.coalesce(FeedbackRecord.original_title, "")
                    + " "
                    + FeedbackRecord.redacted_text,
                ),
                func.plainto_tsquery("simple", question_text),
            ).label("keyword_rank"),
        )
        .join(
            Embedding,
            (Embedding.object_id == FeedbackRecord.id)
            & (Embedding.object_type == "feedback_record")
            & (Embedding.embedding_configuration_id == embedding_configuration.id),
        )
        .join(FeedbackAnalysis, FeedbackAnalysis.feedback_record_id == FeedbackRecord.id)
        .where(
            FeedbackAnalysis.analysis_run_id == analysis_run_id,
            *_base_record_filters(effective_filters),
        )
    )

    if "source_connector_key" in effective_filters:
        stmt = stmt.join(
            SourceConnectorModel, SourceConnectorModel.id == FeedbackRecord.source_connector_id
        ).where(SourceConnectorModel.key == effective_filters["source_connector_key"])

    if "taxonomy_dimension_key" in effective_filters or "taxonomy_label_key" in effective_filters:
        stmt = stmt.join(AnalysisLabel, AnalysisLabel.feedback_analysis_id == FeedbackAnalysis.id)
        if "taxonomy_dimension_key" in effective_filters:
            stmt = stmt.join(
                TaxonomyDimension, TaxonomyDimension.id == AnalysisLabel.taxonomy_dimension_id
            ).where(TaxonomyDimension.key == effective_filters["taxonomy_dimension_key"])
        if "taxonomy_label_key" in effective_filters:
            stmt = stmt.join(
                TaxonomyLabel, TaxonomyLabel.id == AnalysisLabel.taxonomy_label_id
            ).where(TaxonomyLabel.key == effective_filters["taxonomy_label_key"])

    stmt = stmt.order_by("distance").limit(MAX_RECORD_CANDIDATES)

    result = await session.execute(stmt)
    return [
        (row[0], max(0.0, 1.0 - float(row[1])), float(row[2] or 0.0)) for row in result.all()
    ]


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [1.0 for _ in values]
    return [(v - low) / (high - low) for v in values]


async def _select_records(
    session: AsyncSession,
    *,
    research_question_id: UUID,
    theme_set_id: UUID,
    analysis_run_id: UUID,
    question_text: str,
    effective_filters: dict[str, str],
) -> list[EvidenceItem]:
    candidates = await _hybrid_record_candidates(
        session,
        analysis_run_id=analysis_run_id,
        question_text=question_text,
        effective_filters=effective_filters,
    )
    if not candidates:
        return []

    keyword_ranks = _normalize([rank for _, _, rank in candidates])
    scored = [
        (
            record,
            similarity,
            keyword_ranks[i],
            VECTOR_WEIGHT * similarity + KEYWORD_WEIGHT * keyword_ranks[i],
        )
        for i, (record, similarity, _) in enumerate(candidates)
    ]

    for record, similarity, keyword_rank, rerank_score in scored:
        await research_repo.upsert_retrieval_result(
            session,
            research_question_id=research_question_id,
            object_type=RetrievalObjectType.FEEDBACK_RECORD,
            object_id=record.id,
            retrieval_stage=RetrievalStage.RERANKED,
            vector_score=similarity,
            keyword_score=keyword_rank,
            structured_filter_score=1.0,
            rerank_score=rerank_score,
        )

    scored.sort(key=lambda row: row[3], reverse=True)

    selected: list[tuple[FeedbackRecord, float, float, float]] = []
    per_source_count: dict[UUID, int] = {}
    excluded: list[tuple[FeedbackRecord, float, float, float, str]] = []

    for record, similarity, keyword_rank, rerank_score in scored:
        if len(selected) >= MAX_SELECTED_RECORDS:
            excluded.append((record, similarity, keyword_rank, rerank_score, "context_size_cap"))
            continue
        source_count = per_source_count.get(record.source_connector_id, 0)
        if source_count >= MAX_RECORDS_PER_SOURCE:
            excluded.append(
                (record, similarity, keyword_rank, rerank_score, "source_concentration_cap")
            )
            continue
        selected.append((record, similarity, keyword_rank, rerank_score))
        per_source_count[record.source_connector_id] = source_count + 1

    # INS/MET-style contradiction pass (§17.3 step 6): if a known
    # counterexample for one of the in-scope themes exists among the
    # candidates but didn't survive reranking/diversity, force it in.
    selected_ids = {record.id for record, *_ in selected}
    counterexample_ids = set(
        (
            await session.scalars(
                select(ThemeMembership.feedback_record_id).where(
                    ThemeMembership.theme_id.in_(
                        select(Theme.id)
                        .where(Theme.theme_set_id == theme_set_id)
                        .order_by(Theme.opportunity_score.desc().nulls_last())
                        .limit(MAX_SELECTED_THEMES)
                    ),
                    ThemeMembership.is_counterexample.is_(True),
                )
            )
        ).all()
    )
    if counterexample_ids and not (counterexample_ids & selected_ids):
        for record, similarity, keyword_rank, rerank_score, _reason in excluded:
            if record.id in counterexample_ids:
                selected.append((record, similarity, keyword_rank, rerank_score))
                excluded = [row for row in excluded if row[0].id != record.id]
                break

    for record, similarity, keyword_rank, rerank_score, reason in excluded:
        await research_repo.upsert_retrieval_result(
            session,
            research_question_id=research_question_id,
            object_type=RetrievalObjectType.FEEDBACK_RECORD,
            object_id=record.id,
            retrieval_stage=RetrievalStage.EXCLUDED,
            vector_score=similarity,
            keyword_score=keyword_rank,
            rerank_score=rerank_score,
            selection_reason={"reason": reason},
        )

    items: list[EvidenceItem] = []
    for rank, (record, similarity, keyword_rank, rerank_score) in enumerate(selected, start=1):
        label = f"E{rank}"
        is_counterexample = record.id in counterexample_ids
        await research_repo.upsert_retrieval_result(
            session,
            research_question_id=research_question_id,
            object_type=RetrievalObjectType.FEEDBACK_RECORD,
            object_id=record.id,
            retrieval_stage=RetrievalStage.SELECTED,
            vector_score=similarity,
            keyword_score=keyword_rank,
            rerank_score=rerank_score,
            final_rank=rank,
            selection_reason={"label": label, "forced_contradiction": is_counterexample},
        )
        items.append(
            EvidenceItem(
                label=label,
                object_type=RetrievalObjectType.FEEDBACK_RECORD,
                object_id=record.id,
                title=f"Feedback record ({record.record_type.value})",
                excerpt=record.redacted_text[:EXCERPT_MAX_CHARS],
                metadata={
                    "is_counterexample": is_counterexample,
                    "published_at": record.published_at.isoformat()
                    if record.published_at
                    else None,
                },
            )
        )
    return items


async def retrieve_evidence(
    session: AsyncSession,
    *,
    research_question_id: UUID,
    theme_set_id: UUID,
    insight_set_id: UUID | None,
    analysis_run_id: UUID,
    question_text: str,
    effective_filters: dict[str, str],
) -> EvidencePackage:
    themes = await _select_themes(
        session, research_question_id=research_question_id, theme_set_id=theme_set_id
    )
    insights = await _select_insights(
        session, research_question_id=research_question_id, insight_set_id=insight_set_id
    )
    records = await _select_records(
        session,
        research_question_id=research_question_id,
        theme_set_id=theme_set_id,
        analysis_run_id=analysis_run_id,
        question_text=question_text,
        effective_filters=effective_filters,
    )
    return EvidencePackage(themes=themes, insights=insights, records=records)
