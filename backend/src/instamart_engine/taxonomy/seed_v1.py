"""Taxonomy v1 content, verbatim from context.md §12.

Definitions are intentionally concise placeholders for the classification
prompt to reference — context.md §18 Phase 2 explicitly expects them to be
"refined" after reviewing 100-200 sample outputs, so this is a deliberate
starting point, not a finished rubric.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.taxonomy.models import (
    TaxonomyCardinality,
    TaxonomyDimension,
    TaxonomyLabel,
    TaxonomyStatus,
    TaxonomyValueType,
    TaxonomyVersion,
)

TAXONOMY_VERSION_KEY = "2026-07-v1"


@dataclass(frozen=True, slots=True)
class LabelSeed:
    key: str
    display_name: str
    definition: str


@dataclass(frozen=True, slots=True)
class DimensionSeed:
    key: str
    display_name: str
    description: str
    cardinality: TaxonomyCardinality
    labels: list[LabelSeed]


def _labels(*pairs: tuple[str, str]) -> list[LabelSeed]:
    return [
        LabelSeed(key=key, display_name=key.replace("_", " ").title(), definition=definition)
        for key, definition in pairs
    ]


JOURNEY_STAGE = DimensionSeed(
    key="journey_stage",
    display_name="Journey Stage",
    description="Where in the shopping journey the text is describing (context.md §7.C, §12).",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("need_recognition", "User expresses realizing they need something."),
        ("app_entry", "User opens or returns to the app."),
        ("search", "User is actively searching for a product or category."),
        ("browse", "User is browsing categories or recommendations without a specific search."),
        ("product_evaluation", "User is comparing options, reading details, or judging fit."),
        ("cart_building", "User is adding items to cart or building an order."),
        ("checkout", "User is at payment or order confirmation."),
        ("fulfilment", "Order is being packed/dispatched from the seller's side."),
        ("delivery", "The delivery experience itself: timing, rider, packaging on arrival."),
        ("consumption_or_usage", "User describes using or consuming the product after delivery."),
        (
            "support_refund_or_complaint",
            "User is seeking support, a refund, or lodging a complaint.",
        ),
        ("repeat_purchase", "User describes reordering or habitual repurchase."),
    ),
)

BEHAVIOURAL_DRIVER = DimensionSeed(
    key="behavioural_driver",
    display_name="Behavioural Driver",
    description="Why the user describes buying/behaving the way they do (context.md §7.A, §12).",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("habit", "Repeated behaviour described as routine, without active deliberation."),
        ("convenience", "Ease or low effort is the stated motivation."),
        ("urgency", "An immediate, time-pressured need drives the action."),
        ("replenishment", "Restocking a regularly used item."),
        ("familiarity", "Preference for what is already known, not necessarily habitual."),
        ("loyalty", "Stated preference for a specific brand or the platform itself."),
        ("price_or_promotion", "A price point, discount, or offer is the stated driver."),
        ("availability", "The item being in stock or quickly available drives the choice."),
        ("speed", "Delivery or fulfilment speed is the stated driver."),
        ("perceived_quality", "A belief about product quality drives the choice."),
        ("low_effort", "Explicit preference for the option requiring least decision effort."),
        ("social_influence", "A recommendation from friends, family, or social media."),
        ("curiosity_or_novelty", "Trying something because it is new or unfamiliar."),
    ),
)

EXPLORATION_BARRIER = DimensionSeed(
    key="exploration_barrier",
    display_name="Exploration Barrier",
    description="What the text says stops the user from trying an unfamiliar category or product "
    "(context.md §7.B, §12).",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("weak_recommendation_relevance", "Recommendations shown felt irrelevant."),
        ("poor_search_or_navigation", "Difficulty finding things via search or category browsing."),
        ("insufficient_information", "Not enough product detail to decide."),
        ("price_uncertainty", "Unclear or unpredictable pricing."),
        ("quality_uncertainty", "Uncertainty about the product's actual quality."),
        ("freshness_or_expiry_concern", "Concern about freshness, expiry, or shelf life."),
        ("trust_or_authenticity_concern", "Doubt about authenticity or seller trustworthiness."),
        ("substitution_concern", "Fear of receiving an unwanted substituted item."),
        ("limited_assortment", "Desired options are not available on the platform at all."),
        ("preferred_brand_unavailable", "A specific known brand is missing."),
        ("out_of_stock", "The specific item was out of stock."),
        (
            "delivery_economics",
            "Delivery fees or minimum-order thresholds discourage the purchase.",
        ),
        ("prior_negative_experience", "A past bad experience discourages trying again."),
        ("time_pressure", "Not enough time to browse or evaluate new options."),
        ("excessive_choice", "Too many options create decision fatigue."),
        ("low_perceived_need", "The user simply doesn't feel a need for the category."),
    ),
)

FRUSTRATION = DimensionSeed(
    key="frustration",
    display_name="Frustration Family",
    description="Recurring complaint categories (context.md §7.B, §12).",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("product_quality", "Complaint about the physical quality of a received product."),
        ("missing_or_wrong_item", "An item was missing from the order or the wrong item arrived."),
        ("refund_or_support", "Complaint about the refund or customer-support process."),
        ("delivery_delay", "Complaint about delivery taking too long."),
        ("cancellation", "Complaint about an order being cancelled."),
        ("pricing_discrepancy", "The charged price differed from what was shown."),
        ("fees", "Complaint specifically about delivery or platform fees."),
        ("inventory_accuracy", "Item shown as available was actually unavailable."),
        ("search", "Complaint about search functionality itself."),
        ("recommendation", "Complaint about recommendations or personalization."),
        ("app_performance", "Complaint about app crashes, slowness, or bugs."),
        ("payment", "Complaint about the payment process."),
        ("packaging", "Complaint about how the order was packaged."),
        ("substitution", "Complaint about an unwanted item substitution that occurred."),
        (
            "dark_patterns_or_misleading_offers",
            "Complaint that an offer or UI pattern felt misleading.",
        ),
    ),
)

UNMET_NEED = DimensionSeed(
    key="unmet_need",
    display_name="Unmet-Need Family",
    description="What the user implies would help them, that isn't currently offered "
    "(context.md §7.B, §12).",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("richer_product_information", "Wants more detailed product information."),
        ("better_comparison", "Wants an easier way to compare similar products."),
        ("stronger_trust_signals", "Wants clearer trust/authenticity signals."),
        ("personalized_discovery", "Wants more relevant, personalized recommendations."),
        ("transparent_pricing", "Wants clearer, more predictable pricing."),
        ("reliable_stock_status", "Wants accurate real-time stock information."),
        ("controllable_substitutions", "Wants control over whether/how substitutions happen."),
        ("category_education", "Wants help understanding an unfamiliar category."),
        ("samples_or_trial_sizes", "Wants small trial sizes before committing to a full purchase."),
        ("bundles_or_starter_kits", "Wants curated bundles to ease first-time trial."),
        ("dietary_and_preference_filters", "Wants filters for dietary or personal preferences."),
        ("improved_post_purchase_resolution", "Wants a smoother post-purchase resolution process."),
    ),
)

ALL_DIMENSIONS: list[DimensionSeed] = [
    JOURNEY_STAGE,
    BEHAVIOURAL_DRIVER,
    EXPLORATION_BARRIER,
    FRUSTRATION,
    UNMET_NEED,
]


def _schema_definition() -> dict:
    return {
        "dimensions": [
            {
                "key": dim.key,
                "cardinality": dim.cardinality.value,
                "labels": [label.key for label in dim.labels],
            }
            for dim in ALL_DIMENSIONS
        ]
    }


def _checksum() -> str:
    payload = json.dumps(_schema_definition(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def load_taxonomy_v1(session: AsyncSession) -> TaxonomyVersion:
    """Idempotent: returns the existing version if already loaded."""
    from sqlalchemy import select

    existing = await session.scalar(
        select(TaxonomyVersion).where(TaxonomyVersion.version_key == TAXONOMY_VERSION_KEY)
    )
    if existing is not None:
        return existing

    version = TaxonomyVersion(
        version_key=TAXONOMY_VERSION_KEY,
        name="Instamart Discovery Research Taxonomy v1",
        description="Journey stages, behavioural drivers, exploration barriers, frustration "
        "families, and unmet-need families, per context.md §12.",
        schema_definition=_schema_definition(),
        source_file_checksum=_checksum(),
        status=TaxonomyStatus.PUBLISHED,
    )
    session.add(version)
    await session.flush()

    for sort_order, dim_seed in enumerate(ALL_DIMENSIONS):
        dimension = TaxonomyDimension(
            taxonomy_version_id=version.id,
            key=dim_seed.key,
            display_name=dim_seed.display_name,
            description=dim_seed.description,
            cardinality=dim_seed.cardinality,
            value_type=TaxonomyValueType.CATEGORICAL,
            sort_order=sort_order,
        )
        session.add(dimension)
        await session.flush()

        for label_sort_order, label_seed in enumerate(dim_seed.labels):
            session.add(
                TaxonomyLabel(
                    taxonomy_dimension_id=dimension.id,
                    key=label_seed.key,
                    display_name=label_seed.display_name,
                    definition=label_seed.definition,
                    sort_order=label_sort_order,
                )
            )

    await session.flush()
    return version
