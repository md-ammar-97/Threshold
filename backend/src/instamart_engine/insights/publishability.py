"""Insight publishability rules. datamodel.md §64; edgecases.md INS-001,
INS-010, INS-015.

Enforced at the service layer, not the DB layer, per `insights.models.Insight`
— an insight can exist in draft/unreviewed form without yet meeting these
rules; a caller (report export, research answer generation) must re-check
before treating an insight as citable.
"""

from dataclasses import dataclass

from instamart_engine.insights.models import Insight, InsightType


@dataclass(frozen=True, slots=True)
class PublishabilityResult:
    publishable: bool
    violated_rules: tuple[str, ...]


def check_publishability(
    insight: Insight,
    *,
    has_theme_link: bool,
    supporting_evidence_count: int,
) -> PublishabilityResult:
    violations: list[str] = []

    has_any_link = has_theme_link or supporting_evidence_count > 0
    if not has_any_link:
        violations.append("INS-001")

    if (
        insight.insight_type == InsightType.SYNTHESIZED_INSIGHT
        and supporting_evidence_count == 0
    ):
        violations.append("INS-001")

    if insight.insight_type == InsightType.PRODUCT_HYPOTHESIS and not (
        insight.validation_recommendation and insight.validation_recommendation.strip()
    ):
        violations.append("INS-010")

    if insight.opportunity_score is not None and not insight.score_components:
        violations.append("INS-015")

    return PublishabilityResult(publishable=not violations, violated_rules=tuple(violations))
