"""Taxonomy v2 content: adds `topic_main`/`topic_sub`, a subject-matter
taxonomy of what feedback is *about* (Delivery experience, Payments,
Refunds, Trust and transparency, ...), alongside v1's analytical-lens
dimensions (journey stage, behavioural driver, exploration barrier,
frustration, unmet need — "why"/"what stage" rather than "what topic").

v1's dimensions are reused verbatim (imported, not copied) so there is a
single source of truth for their content; only the two new dimensions are
defined here. `topic_sub` labels carry a `parent_key` pointing at their
owning `topic_main` label — `load_taxonomy_v2` resolves that into a real
`parent_label_id` once the `topic_main` labels are inserted and flushed.
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
from instamart_engine.taxonomy.seed_v1 import DimensionSeed, LabelSeed, _labels

TAXONOMY_VERSION_KEY = "2026-07-v2"


TOPIC_MAIN = DimensionSeed(
    key="topic_main",
    display_name="Topic (Main Theme)",
    description="The primary subject-matter category the feedback is about — "
    "independent of the journey/behavioural/barrier/frustration/unmet-need lenses above.",
    cardinality=TaxonomyCardinality.MULTIPLE,
    labels=_labels(
        ("delivery_experience", "The delivery process itself: timing, route, or delivery method."),
        ("order_accuracy", "Whether the order received matched what was ordered."),
        ("product_quality", "The physical condition or freshness of the product received."),
        (
            "inventory_and_availability",
            "Whether items were actually in stock and available as shown.",
        ),
        ("pricing_and_value", "Price levels, fees, and overall value for money."),
        ("offers_and_promotions", "Coupons, discounts, cashback, and promotional offers."),
        ("payments", "The payment process itself: failures, charges, and payment methods."),
        ("refunds_and_cancellations", "The refund or cancellation process and its outcome."),
        ("customer_support", "Interactions with customer support, human or automated."),
        (
            "app_and_technical_experience",
            "App stability, performance, and technical functionality.",
        ),
        (
            "user_experience_and_usability",
            "How easy or difficult the app is to use and navigate.",
        ),
        ("packaging", "How the order was packaged for delivery."),
        (
            "delivery_partner_experience",
            "The delivery partner's (rider's) conduct and interaction with the user.",
        ),
        (
            "trust_and_transparency",
            "Whether the platform's fees, pricing, availability, or offers were "
            "honestly represented.",
        ),
        ("safety_and_hygiene", "Product or delivery safety, hygiene, and contamination concerns."),
        ("product_assortment", "The range and variety of products and brands offered."),
        (
            "account_and_membership",
            "Account status and paid membership programs (e.g. Swiggy One).",
        ),
        ("feature_request", "A specific feature or capability the user wants added."),
        ("positive_experience", "Unprompted praise or satisfaction with the service."),
        ("competitor_comparison", "Explicit comparison to a competing platform or local store."),
        (
            "brand_perception",
            "General sentiment or opinion about the brand itself, beyond a specific transaction.",
        ),
        (
            "social_media_engagement",
            "Social-media interaction patterns not tied to a specific service complaint "
            "or compliment.",
        ),
    ),
)

# Keyed by topic_main label key. Subtheme keys are unique across the whole
# topic_sub dimension (not just within their group) — note e.g.
# "positive_*" prefixes on positive_experience's subthemes to avoid
# colliding with similarly-named subthemes elsewhere (fast_delivery vs
# positive_fast_delivery).
TOPIC_SUB_BY_PARENT: dict[str, list[LabelSeed]] = {
    "delivery_experience": _labels(
        ("late_delivery", "Complaint that delivery took longer than expected or promised."),
        ("fast_delivery", "Praise for delivery arriving faster than expected."),
        ("incorrect_eta", "The estimated delivery time shown was inaccurate."),
        ("rider_behaviour", "Comment about the delivery rider's conduct during the delivery."),
        ("delivery_cancellation", "The delivery itself was cancelled after being placed."),
        ("contactless_delivery", "Comment about contactless or no-contact delivery."),
        (
            "location_issues",
            "Delivery went to the wrong location or the rider couldn't find the address.",
        ),
    ),
    "order_accuracy": _labels(
        ("missing_items", "One or more ordered items were missing from the delivery."),
        ("wrong_items", "An item different from what was ordered was delivered."),
        ("incorrect_quantity", "The quantity delivered didn't match what was ordered."),
        (
            "substituted_products",
            "An ordered item was replaced with a different product without being requested.",
        ),
        ("partial_order", "Only part of the order was delivered."),
    ),
    "product_quality": _labels(
        ("damaged_items", "A received item arrived physically damaged."),
        ("expired_products", "A received item was past its expiry date."),
        ("stale_food", "Received food was stale or not fresh."),
        (
            "poor_packaging",
            "The product's own packaging (not the delivery packaging) was of poor quality.",
        ),
        ("melted_frozen_products", "A frozen product arrived melted or thawed."),
        ("leakage", "A product leaked during transit."),
        ("freshness", "General comment about the freshness of a received product."),
    ),
    "inventory_and_availability": _labels(
        ("out_of_stock", "A desired item was out of stock."),
        (
            "item_shown_but_unavailable",
            "An item shown as available in the app was actually unavailable.",
        ),
        ("limited_selection", "Complaint that the available selection is too limited."),
        ("frequent_substitutions", "Complaint about substitutions happening too often."),
        ("restocking_requests", "A request for a specific item to be restocked."),
    ),
    "pricing_and_value": _labels(
        ("high_prices", "Complaint that prices are too high."),
        ("price_differences", "Price shown differed from price charged or from another source."),
        (
            "inflated_mrp",
            "The MRP shown appeared inflated relative to the actual retail price.",
        ),
        ("delivery_charges", "Complaint about the delivery fee charged."),
        ("handling_fees", "Complaint about a handling fee charged."),
        ("platform_fees", "Complaint about a platform fee charged."),
        ("value_for_money", "General comment about whether the price paid was worth it."),
    ),
    "offers_and_promotions": _labels(
        ("coupon_not_working", "A coupon code failed to apply or work as expected."),
        ("misleading_discount", "A discount was presented in a way that felt misleading."),
        ("cashback_missing", "Promised cashback was not received."),
        ("eligibility_confusion", "Confusion about whether an offer applied to the user's order."),
        ("promotional_appreciation", "Positive comment about an offer or promotion."),
    ),
    "payments": _labels(
        ("payment_failure", "A payment attempt failed."),
        (
            "amount_debited_but_order_not_placed",
            "Money was deducted but the order was not placed.",
        ),
        ("duplicate_charge", "The user was charged more than once for the same order."),
        ("cod_issues", "A problem with cash-on-delivery payment."),
        ("wallet_or_upi_problems", "A problem with a wallet or UPI payment method."),
    ),
    "refunds_and_cancellations": _labels(
        ("delayed_refund", "A refund took longer than expected to arrive."),
        ("partial_refund", "Only part of the expected refund amount was received."),
        ("cancellation_rejected", "A cancellation request was rejected or not honored."),
        ("refund_amount_incorrect", "The refund amount received was incorrect."),
        ("refund_experience", "General comment about the refund process itself."),
    ),
    "customer_support": _labels(
        ("bot_experience", "Comment about interacting with an automated support bot."),
        ("difficulty_reaching_an_agent", "Difficulty getting through to a human support agent."),
        ("unhelpful_support", "Support was contacted but didn't resolve the issue."),
        ("repeated_responses", "Support gave the same repeated response without progress."),
        ("issue_resolution", "Comment about whether the underlying issue was actually resolved."),
        ("good_support", "Praise for a positive support interaction."),
    ),
    "app_and_technical_experience": _labels(
        ("app_crashes", "The app crashed or force-closed."),
        ("slow_loading", "The app or a page within it loaded slowly."),
        ("login_issues", "Difficulty logging into the app or account."),
        ("search_problems", "The in-app search didn't work as expected."),
        ("cart_reset", "The shopping cart was unexpectedly emptied or reset."),
        ("address_issues", "Problem saving, selecting, or editing a delivery address."),
        (
            "notification_problems",
            "Problem with app notifications (missing, excessive, or incorrect).",
        ),
    ),
    "user_experience_and_usability": _labels(
        ("difficult_navigation", "Difficulty finding things while navigating the app."),
        ("confusing_checkout", "The checkout flow was confusing."),
        ("poor_filters", "Product filters were inadequate or hard to use."),
        ("reorder_experience", "Comment about the experience of reordering a past order."),
        ("accessibility", "Comment about the app's accessibility for users with disabilities."),
        ("excessive_steps", "Complaint that a task required too many steps to complete."),
    ),
    "packaging": _labels(
        ("excessive_packaging", "Complaint that an order was over-packaged."),
        ("damaged_packaging", "The delivery packaging itself arrived damaged."),
        (
            "poor_segregation",
            "Items were not properly separated or segregated within the package.",
        ),
        ("eco_friendly_packaging", "Comment about eco-friendly or sustainable packaging."),
        ("tamper_concerns", "Concern that a package appeared tampered with."),
    ),
    "delivery_partner_experience": _labels(
        ("politeness", "Comment about the delivery partner's politeness."),
        ("professionalism", "Comment about the delivery partner's professionalism."),
        ("unsafe_behaviour", "The delivery partner behaved unsafely (e.g. reckless driving)."),
        ("refusal_to_deliver", "The delivery partner refused to complete the delivery."),
        ("tip_requests", "The delivery partner requested a tip."),
        ("communication", "Comment about the delivery partner's communication with the user."),
    ),
    "trust_and_transparency": _labels(
        ("hidden_fees", "A fee was charged that wasn't clearly disclosed upfront."),
        ("misleading_eta", "The delivery time estimate felt deliberately misleading."),
        (
            "fake_availability",
            "An item appeared available when it likely wasn't, to induce a purchase.",
        ),
        (
            "manipulated_discounts",
            "A discount appeared to be artificially inflated before being discounted.",
        ),
        ("unexplained_cancellation", "An order was cancelled without a clear explanation."),
    ),
    "safety_and_hygiene": _labels(
        ("open_packaging", "A package arrived already open."),
        ("contamination", "A product appeared contaminated."),
        ("unsafe_delivery", "The delivery itself was carried out in an unsafe manner."),
        ("hygiene_complaints", "General complaint about hygiene standards."),
        ("counterfeit_products", "A received product appeared to be counterfeit."),
    ),
    "product_assortment": _labels(
        ("missing_brands", "A desired brand is not available on the platform."),
        ("demand_for_new_products", "A request for a new product category or item to be added."),
        (
            "local_product_availability",
            "A request for locally relevant products to be available.",
        ),
        ("category_variety", "General comment about the variety within a product category."),
    ),
    "account_and_membership": _labels(
        ("swiggy_one_benefits", "Comment about the benefits of a paid membership program."),
        ("membership_pricing", "Comment about the price of a paid membership program."),
        (
            "free_delivery_eligibility",
            "Confusion or complaint about free-delivery eligibility criteria.",
        ),
        ("account_suspension", "A user account was suspended or restricted."),
        ("loyalty_concerns", "Concern about a loyalty program's value or fairness."),
    ),
    "feature_request": _labels(
        ("scheduled_delivery", "Request for the ability to schedule a delivery in advance."),
        ("better_filters", "Request for improved filtering options."),
        ("wishlist", "Request for a wishlist or saved-items feature."),
        ("product_alerts", "Request for alerts when a product becomes available."),
        ("easier_refunds", "Request for a simpler refund process."),
        ("dark_mode", "Request for a dark-mode appearance option."),
    ),
    "positive_experience": _labels(
        ("positive_fast_delivery", "Praise for a fast delivery experience."),
        ("positive_fresh_products", "Praise for receiving fresh products."),
        ("positive_good_offers", "Praise for a good offer or deal."),
        ("positive_helpful_rider", "Praise for a helpful delivery rider."),
        ("positive_smooth_refund", "Praise for a smooth, easy refund experience."),
        ("positive_reliable_service", "General praise for reliable service."),
    ),
    "competitor_comparison": _labels(
        ("blinkit_comparison", "Comparison to Blinkit."),
        ("zepto_comparison", "Comparison to Zepto."),
        ("bigbasket_comparison", "Comparison to BigBasket."),
        ("amazon_fresh_comparison", "Comparison to Amazon Fresh."),
        ("local_store_comparison", "Comparison to a local or offline store."),
    ),
    "brand_perception": _labels(
        ("brand_trust", "Statement of trust or distrust in the brand."),
        ("brand_loyalty", "Statement of loyalty to the brand."),
        ("brand_disappointment", "Expression of disappointment with the brand."),
        ("brand_praise", "General praise for the brand."),
        ("boycott_calls", "A call to boycott or stop using the platform."),
        ("viral_jokes_and_memes", "A joke or meme about the brand that has spread widely."),
    ),
    "social_media_engagement": _labels(
        ("questions", "A question directed at the brand on social media."),
        ("tagging_friends", "Tagging friends in a brand-related post or comment."),
        ("humour", "Humorous content referencing the brand, not necessarily a meme."),
        ("trends", "Participation in a social-media trend referencing the brand."),
        ("influencer_mentions", "An influencer mentioning the brand."),
        (
            "unrelated_brand_chatter",
            "Brand-adjacent chatter not tied to a specific product or service opinion.",
        ),
    ),
}


def _schema_definition() -> dict[str, Any]:
    dimensions = [
        {
            "key": dim.key,
            "cardinality": dim.cardinality.value,
            "labels": [label.key for label in dim.labels],
        }
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
    return {"dimensions": dimensions}


def _checksum() -> str:
    payload = json.dumps(_schema_definition(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def _insert_dimension(
    session: AsyncSession, *, version_id: UUID, dim_seed: DimensionSeed, sort_order: int
) -> dict[str, UUID]:
    """Inserts a dimension and its flat labels; returns {label_key: label_id}
    for callers (topic_sub) that need to resolve parent labels afterward."""
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


async def load_taxonomy_v2(session: AsyncSession) -> TaxonomyVersion:
    """Idempotent: returns the existing version if already loaded. Complete
    reseed, not additive — `get_published_taxonomy()` picks exactly one
    most-recent PUBLISHED version, so v2 carries v1's 5 dimensions forward
    verbatim alongside the 2 new topic dimensions."""
    existing = await session.scalar(
        select(TaxonomyVersion).where(TaxonomyVersion.version_key == TAXONOMY_VERSION_KEY)
    )
    if existing is not None:
        return existing

    version = TaxonomyVersion(
        version_key=TAXONOMY_VERSION_KEY,
        name="Instamart Discovery Research Taxonomy v2",
        description="v1's journey/behavioural-driver/exploration-barrier/frustration/"
        "unmet-need dimensions, plus topic_main/topic_sub — a subject-matter taxonomy "
        "of what feedback is about, independent of the analytical lenses above.",
        schema_definition=_schema_definition(),
        source_file_checksum=_checksum(),
        status=TaxonomyStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    session.add(version)
    await session.flush()

    sort_order = 0
    for dim_seed in V1_DIMENSIONS:
        await _insert_dimension(
            session, version_id=version.id, dim_seed=dim_seed, sort_order=sort_order
        )
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
    return version
