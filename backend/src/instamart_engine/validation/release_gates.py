"""Release-gate configuration and decision. ai_evals.md §51/§85/§86.

Loads a versioned, version-controlled YAML config (`backend/config/release_gates/`)
and decides `pass` / `pass_with_conditions` / `fail` from a run's persisted
`evaluation_metric` rows (never from live/recomputed numbers — the decision
must be reproducible from what was actually stored). A zero-tolerance
category failing always means `fail`, regardless of how every other metric
looks (ai_evals.md §2.6/§51) — this is deliberately not overridable by a
non-critical metric passing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from instamart_engine.validation.models import EvaluationMetric

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "release_gates"


@dataclass(frozen=True, slots=True)
class ReleaseGateConfig:
    release_profile: str
    zero_tolerance: tuple[str, ...]
    metrics: dict[str, dict[str, float]]


def load_release_gate_config(path: Path) -> ReleaseGateConfig:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ReleaseGateConfig(
        release_profile=data["release_profile"],
        zero_tolerance=tuple(data.get("zero_tolerance", [])),
        metrics=dict(data.get("metrics") or {}),
    )


@dataclass(frozen=True, slots=True)
class ReleaseGateDecision:
    status: str  # "pass" | "pass_with_conditions" | "fail"
    zero_tolerance_failures: tuple[str, ...]
    metric_failures: tuple[str, ...]


def evaluate_release_gates(
    config: ReleaseGateConfig, metrics: list[EvaluationMetric]
) -> ReleaseGateDecision:
    by_key = {metric.metric_key: metric for metric in metrics if metric.dimension_key is None}

    zero_tolerance_failures = []
    for category in config.zero_tolerance:
        # A zero-tolerance category maps to the grader of the same key; a
        # nonzero hard-failure count or a sub-1.0 pass rate disqualifies
        # the release outright, regardless of every other metric.
        hard_failure_metric = by_key.get(f"{category}_hard_failure_count")
        if hard_failure_metric is not None and (hard_failure_metric.numeric_value or 0) > 0:
            zero_tolerance_failures.append(category)
            continue
        pass_rate_metric = by_key.get(f"{category}_pass_rate")
        if pass_rate_metric is not None and float(pass_rate_metric.numeric_value or 0) < 1.0:
            zero_tolerance_failures.append(category)

    metric_failures = []
    for metric_key, bounds in config.metrics.items():
        metric = by_key.get(metric_key)
        if metric is None or metric.numeric_value is None:
            # EVAL-007-style — not applicable for this run, not a failure.
            continue
        value = float(metric.numeric_value)
        minimum = bounds.get("minimum")
        maximum = bounds.get("maximum")
        if minimum is not None and value < minimum:
            metric_failures.append(metric_key)
        if maximum is not None and value > maximum:
            metric_failures.append(metric_key)

    if zero_tolerance_failures:
        status = "fail"
    elif metric_failures:
        status = "pass_with_conditions"
    else:
        status = "pass"

    return ReleaseGateDecision(
        status=status,
        zero_tolerance_failures=tuple(zero_tolerance_failures),
        metric_failures=tuple(metric_failures),
    )
