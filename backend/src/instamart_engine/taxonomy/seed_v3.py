"""Taxonomy v3 content: adds `discovery_mechanism` and
`experimentation_propensity`, from `docs/context.md` §7.C/§7.D verbatim —
the two dimensions research questions 3 ("How do users discover products
today?") and 7 ("Which user segments are more likely to experiment?") had no
taxonomy support for (audit-2026-07-31.md R-5/R-6). `ThemeType.DISCOVERY_
MECHANISM`/`ThemeType.EXPERIMENTATION_SIGNAL` already existed as enum values
with nothing able to populate them.

v1/v2's dimensions are reused verbatim (imported, not copied), same pattern
as seed_v2.py. Both new dimensions are flat (no parent/child labels), like
`frustration`/`unmet_need` — not hierarchical like v2's topic_main/topic_sub.

`experimentation_propensity`'s `household_role`/`city_or_region`/
`self_reported_usage_frequency` labels sit close to the demographic
boundary — context.md §7.D's own closing line is carried into their
definitions verbatim ("only when explicitly stated by the user, never
inferred"). No new guard code is needed: `_persist_labels_for_dimensions`
(analysis/classify.py) already runs `contains_demographic_inference()`
against every dimension's evidence excerpts dimension-agnostically, so this
new dimension inherits that backstop automatically.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.taxonomy.models import (
    TaxonomyCardinality,
    TaxonomyDimension,
    TaxonomyLabel,
    TaxonomyStatus,
    TaxonomyValueType,
    TaxonomyVersion,
)
from instamart_engine.taxonomy.seed_v1 import ALL_DIMENSIONS as V1_DIMENSIONS
from instamart_engine.taxonomy.seed_v1 import DimensionSeed, _labels
from instamart_engine.taxonomy.seed_v2 import TOPIC_MAIN, TOPIC_SUB_BY_PARENT

TAXONOMY_VERSION_KEY = "2026-07-v3"


DISCOVERY_MECHANISM = DimensionSeed(
    key="discovery_mechanism",
    display_name="Discovery Mechanism",
    description="How the user discovered the product or category being described "
    "(context.md §7.C).",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("search", "User discovers a product or category via active search."),
        ("home_page_recommendations", "User discovers via home-page recommendations."),
        (
            "category_browsing",
            "User discovers by browsing categories without a specific search.",
        ),
        ("offers_and_discounts", "User discovers via offers or discounts shown to them."),
        ("banners", "User discovers via a promotional banner."),
        ("trending_sections", "User discovers via a trending or popular-items section."),
        ("previous_orders", "User discovers via their own previous order history."),
        (
            "external_social_recommendations",
            "User discovers via a recommendation from external social media.",
        ),
        ("family_or_peer_suggestions", "User discovers via a suggestion from family or peers."),
        (
            "urgency_driven_need_states",
            "User discovers while in an urgent, time-pressured need state.",
        ),
        (
            "accidental_exposure",
            "User discovers by accident while buying something else.",
        ),
    ),
)

EXPERIMENTATION_PROPENSITY = DimensionSeed(
    key="experimentation_propensity",
    display_name="Experimentation Propensity",
    description="Behavioural signals indicating how likely the user is to try a new "
    "category (context.md §7.D) — behavioural only, never demographic. Segments must "
    "be inferred only from available evidence; never fabricate age, income, gender, "
    "occupation, or household attributes.",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("deal_seeking_behaviour", "User's language shows deal-seeking behaviour."),
        (
            "novelty_seeking_language",
            "User's language shows novelty-seeking, e.g. wanting to try something new.",
        ),
        (
            "premium_product_interest",
            "User expresses interest in premium or higher-end products.",
        ),
        (
            "convenience_dependence",
            "User's language shows reliance on convenience as the primary driver.",
        ),
        (
            "planned_versus_urgent_shopping",
            "User's language indicates whether this shopping was planned in advance "
            "or driven by urgency.",
        ),
        (
            "household_role",
            "User explicitly states their role within their household (e.g. primary "
            "shopper). Only apply when explicitly stated by the user, never inferred.",
        ),
        (
            "city_or_region",
            "User explicitly states their city or region. Only apply when explicitly "
            "stated by the user, never inferred.",
        ),
        (
            "category_context",
            "The category context surrounding the user's experimentation (e.g. trying "
            "a new category vs. staying within a familiar one).",
        ),
        (
            "prior_experience_valence",
            "User's language indicates a positive or negative prior experience shaping "
            "their willingness to experiment.",
        ),
        (
            "self_reported_usage_frequency",
            "User explicitly states how often they use quick-commerce. Only apply when "
            "explicitly stated by the user, never inferred.",
        ),
    ),
)

ALL_V3_DIMENSIONS: list[DimensionSeed] = [DISCOVERY_MECHANISM, EXPERIMENTATION_PROPENSITY]


def _schema_definition() -> dict[str, Any]:
    dimensions = [
        {"key": dim.key, "cardinality": dim.cardinality.value, "labels": [label.key for label in dim.labels]}
        for dim in V1_DIMENSIONS
    ]
    dimensions.append(
        {
            "key": TOPIC_MAIN.key,
            "cardinality": TOPIC_MAIN.cardinality.value,
            "labels": [label.key for label in TOPIC_MAIN.labels],
        }
    )
    dimensions.append(
        {
            "key": "topic_sub",
            "cardinality": TaxonomyCardinality.MULTIPLE.value,
            "labels": [
                label.key for labels in TOPIC_SUB_BY_PARENT.values() for label in labels
            ],
        }
    )
    for dim in ALL_V3_DIMENSIONS:
        dimensions.append(
            {"key": dim.key, "cardinality": dim.cardinality.value, "labels": [label.key for label in dim.labels]}
        )
    return {"dimensions": dimensions}


def _checksum() -> str:
    payload = json.dumps(_schema_definition(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def _insert_dimension(
    session: AsyncSession, *, version_id: UUID, dim_seed: DimensionSeed, sort_order: int
) -> dict[str, UUID]:
    dimension = TaxonomyDimension(
        taxonomy_version_id=version_id,
        key=dim_seed.key,
        display_name=dim_seed.display_name,
        description=dim_seed.description,
        cardinality=dim_seed.cardinality,
        value_type=TaxonomyValueType.CATEGORICAL,
        sort_order=sort_order,
    )
    session.add(dimension)
    await session.flush()

    label_objects: list[tuple[str, TaxonomyLabel]] = []
    for label_sort_order, label_seed in enumerate(dim_seed.labels):
        label = TaxonomyLabel(
            taxonomy_dimension_id=dimension.id,
            key=label_seed.key,
            display_name=label_seed.display_name,
            definition=label_seed.definition,
            sort_order=label_sort_order,
        )
        session.add(label)
        label_objects.append((label_seed.key, label))

    await session.flush()
    return {key: label.id for key, label in label_objects}


async def load_taxonomy_v3(session: AsyncSession) -> TaxonomyVersion:
    """Idempotent: returns the existing version if already loaded. Complete
    reseed (v1's 5 + v2's topic_main/topic_sub + these 2 new dimensions),
    not additive — `get_published_taxonomy()` picks exactly one most-recent
    PUBLISHED version."""
    existing = await session.scalar(
        select(TaxonomyVersion).where(TaxonomyVersion.version_key == TAXONOMY_VERSION_KEY)
    )
    if existing is not None:
        return existing

    version = TaxonomyVersion(
        version_key=TAXONOMY_VERSION_KEY,
        name="Instamart Discovery Research Taxonomy v3",
        description="v1's journey/behavioural-driver/exploration-barrier/frustration/"
        "unmet-need dimensions, v2's topic_main/topic_sub, plus discovery_mechanism "
        "and experimentation_propensity (context.md §7.C/§7.D) — answers research "
        "questions 3 and 7.",
        schema_definition=_schema_definition(),
        source_file_checksum=_checksum(),
        status=TaxonomyStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    session.add(version)
    await session.flush()

    sort_order = 0
    for dim_seed in V1_DIMENSIONS:
        await _insert_dimension(session, version_id=version.id, dim_seed=dim_seed, sort_order=sort_order)
        sort_order += 1

    topic_main_label_ids = await _insert_dimension(
        session, version_id=version.id, dim_seed=TOPIC_MAIN, sort_order=sort_order
    )
    sort_order += 1

    topic_sub_dimension = TaxonomyDimension(
        taxonomy_version_id=version.id,
        key="topic_sub",
        display_name="Topic (Subtheme)",
        description="A finer-grained subtheme within a topic_main category.",
        cardinality=TaxonomyCardinality.MULTIPLE,
        value_type=TaxonomyValueType.CATEGORICAL,
        sort_order=sort_order,
    )
    session.add(topic_sub_dimension)
    await session.flush()
    sort_order += 1

    label_sort_order = 0
    for main_key, sub_labels in TOPIC_SUB_BY_PARENT.items():
        parent_id = topic_main_label_ids[main_key]
        for label_seed in sub_labels:
            session.add(
                TaxonomyLabel(
                    taxonomy_dimension_id=topic_sub_dimension.id,
                    key=label_seed.key,
                    display_name=label_seed.display_name,
                    definition=label_seed.definition,
                    parent_label_id=parent_id,
                    sort_order=label_sort_order,
                )
            )
            label_sort_order += 1
    await session.flush()

    for dim_seed in ALL_V3_DIMENSIONS:
        await _insert_dimension(session, version_id=version.id, dim_seed=dim_seed, sort_order=sort_order)
        sort_order += 1

    return version
