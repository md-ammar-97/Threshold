import uuid

from instamart_engine.validation.models import EvaluationMetric
from instamart_engine.validation.release_gates import (
    CONFIG_DIR,
    ReleaseGateConfig,
    evaluate_release_gates,
    load_release_gate_config,
)


def _metric(
    metric_key: str, numeric_value: float, dimension_key: str | None = None
) -> EvaluationMetric:
    return EvaluationMetric(
        id=uuid.uuid4(),
        evaluation_run_id=uuid.uuid4(),
        metric_key=metric_key,
        dimension_key=dimension_key,
        numeric_value=numeric_value,
        json_value=None,
        sample_count=10,
        calculation_version="v1",
    )


def _config(**overrides) -> ReleaseGateConfig:
    defaults = dict(
        release_profile="test-v1",
        zero_tolerance=("citation_integrity",),
        metrics={"schema_integrity_pass_rate": {"minimum": 1.0}},
    )
    defaults.update(overrides)
    return ReleaseGateConfig(**defaults)


def test_real_mvp_config_loads_and_parses() -> None:
    config = load_release_gate_config(CONFIG_DIR / "mvp-v1.yaml")
    assert config.release_profile == "mvp-v1"
    assert "citation_integrity" in config.zero_tolerance
    assert "demographic_inference" in config.zero_tolerance
    assert config.metrics["schema_integrity_pass_rate"]["minimum"] == 1.0


def test_pass_when_everything_meets_thresholds() -> None:
    metrics = [
        _metric("citation_integrity_hard_failure_count", 0),
        _metric("schema_integrity_pass_rate", 1.0),
    ]
    decision = evaluate_release_gates(_config(), metrics)
    assert decision.status == "pass"
    assert decision.zero_tolerance_failures == ()
    assert decision.metric_failures == ()


def test_fail_on_zero_tolerance_hard_failure() -> None:
    metrics = [
        _metric("citation_integrity_hard_failure_count", 2),
        _metric("schema_integrity_pass_rate", 1.0),
    ]
    decision = evaluate_release_gates(_config(), metrics)
    assert decision.status == "fail"
    assert "citation_integrity" in decision.zero_tolerance_failures


def test_fail_on_zero_tolerance_pass_rate_below_one() -> None:
    metrics = [
        _metric("citation_integrity_pass_rate", 0.98),
        _metric("schema_integrity_pass_rate", 1.0),
    ]
    decision = evaluate_release_gates(_config(), metrics)
    assert decision.status == "fail"
    assert "citation_integrity" in decision.zero_tolerance_failures


def test_pass_with_conditions_on_non_critical_metric_miss() -> None:
    metrics = [
        _metric("citation_integrity_hard_failure_count", 0),
        _metric("schema_integrity_pass_rate", 0.90),
    ]
    decision = evaluate_release_gates(_config(), metrics)
    assert decision.status == "pass_with_conditions"
    assert "schema_integrity_pass_rate" in decision.metric_failures


def test_missing_metric_is_not_applicable_not_a_failure() -> None:
    decision = evaluate_release_gates(_config(), metrics=[])
    assert decision.status == "pass"
    assert decision.metric_failures == ()
    assert decision.zero_tolerance_failures == ()


def test_zero_tolerance_always_wins_over_metric_pass() -> None:
    metrics = [
        _metric("citation_integrity_hard_failure_count", 1),
        _metric("schema_integrity_pass_rate", 1.0),
    ]
    decision = evaluate_release_gates(_config(), metrics)
    assert decision.status == "fail"
