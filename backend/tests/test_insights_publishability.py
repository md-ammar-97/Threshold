from instamart_engine.insights.models import ConfidenceLevel, Insight, InsightType
from instamart_engine.insights.publishability import check_publishability


def _base_insight(**overrides) -> Insight:
    defaults = dict(
        insight_type=InsightType.OBSERVED_EVIDENCE,
        title="t",
        finding="f",
        interpretation="i",
        confidence_level=ConfidenceLevel.LOW,
        confidence_score=0.3,
        opportunity_score=None,
        score_components=None,
        validation_recommendation=None,
    )
    defaults.update(overrides)
    return Insight(**defaults)


def test_no_theme_link_and_no_evidence_fails_ins_001() -> None:
    insight = _base_insight()
    result = check_publishability(insight, has_theme_link=False, supporting_evidence_count=0)
    assert result.publishable is False
    assert "INS-001" in result.violated_rules


def test_theme_link_alone_is_sufficient_for_observed_evidence() -> None:
    insight = _base_insight(insight_type=InsightType.OBSERVED_EVIDENCE)
    result = check_publishability(insight, has_theme_link=True, supporting_evidence_count=0)
    assert result.publishable is True


def test_synthesized_insight_requires_supporting_evidence_ins_001() -> None:
    insight = _base_insight(insight_type=InsightType.SYNTHESIZED_INSIGHT)
    result = check_publishability(insight, has_theme_link=True, supporting_evidence_count=0)
    assert result.publishable is False
    assert "INS-001" in result.violated_rules

    result_with_support = check_publishability(
        insight, has_theme_link=True, supporting_evidence_count=1
    )
    assert result_with_support.publishable is True


def test_product_hypothesis_without_validation_recommendation_fails_ins_010() -> None:
    insight = _base_insight(
        insight_type=InsightType.PRODUCT_HYPOTHESIS, validation_recommendation=None
    )
    result = check_publishability(insight, has_theme_link=True, supporting_evidence_count=0)
    assert result.publishable is False
    assert "INS-010" in result.violated_rules

    insight.validation_recommendation = "Run a controlled experiment with a freshness badge."
    result_with_recommendation = check_publishability(
        insight, has_theme_link=True, supporting_evidence_count=0
    )
    assert result_with_recommendation.publishable is True


def test_opportunity_score_without_components_fails_ins_015() -> None:
    insight = _base_insight(opportunity_score=42.0, score_components=None)
    result = check_publishability(insight, has_theme_link=True, supporting_evidence_count=0)
    assert result.publishable is False
    assert "INS-015" in result.violated_rules
