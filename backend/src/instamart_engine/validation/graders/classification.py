"""Classification-quality graders. ai_evals.md §13-14's release gates (macro
F1, Jaccard, exact-set match) need gold-comparison data we don't have —
`data/evaluation/` is empty by design (see `data/evaluation/README.md`), so
these are the same deterministic, no-gold tier the existing Grounding suite
uses (`validation/graders/base.py`'s own docstring: "tiers 1 and 3... tier 2
[gold comparison] is implemented per-suite once a gold dataset exists").

Candidate output comes from `runners.py::_build_classification_candidate_output`
— one `feedback_record`'s current `AnalysisLabel` set."""

from typing import Any

from instamart_engine.analysis.demographic_guard import contains_demographic_inference
from instamart_engine.validation.graders.base import GraderResult

DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.5


class UnsupportedLabelGrader:
    """ai_evals.md §14.4 "unsupported-label rate: 0%" — every applied label
    must belong to the SAME taxonomy version as its own `feedback_analysis`
    (datamodel.md §67 invariant #1). Deliberately not "the currently-
    published taxonomy version": a record classified under an older, still-
    valid taxonomy version isn't unsupported just because a newer version
    has since been published — that would flag more records "unsupported"
    every time the taxonomy grows, which isn't what this check means. A
    label whose dimension belongs to a *different* version than its own
    analysis row is the real integrity violation this catches (e.g. a
    taxonomy migration bug, or a label copied across analysis runs)."""

    key = "unsupported_label"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        labels = candidate_output.get("labels", [])
        unsupported = [
            label.get("dimension_key")
            for label in labels
            if not label.get("belongs_to_own_taxonomy_version")
        ]
        passed = not unsupported
        sample_count = len(labels)
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=1.0 if sample_count == 0 else 1 - (len(unsupported) / sample_count),
            hard_failure=not passed,
            failure_codes=tuple(f"unsupported_label:{key}" for key in unsupported),
            details={"unsupported_dimension_keys": unsupported, "label_count": sample_count},
        )


class DemographicInferenceGrader:
    """ai_evals.md §14.4 "explicit demographic-inference violations: 0" —
    reuses the exact detector already applied at generation time
    (`analysis/classify.py::_persist_labels_for_dimensions`) as a regression
    check, the same relationship `grounding.py::CausalOverclaimGrader` has to
    `insights/causal_guard.py`."""

    key = "classification_demographic_inference"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        labels = candidate_output.get("labels", [])
        violations = [
            label.get("dimension_key")
            for label in labels
            if contains_demographic_inference(label.get("evidence_excerpt", ""))
        ]
        passed = not violations
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=1.0 if passed else 0.0,
            hard_failure=not passed,
            failure_codes=tuple(f"demographic_inference:{key}" for key in violations),
            details={"violation_dimension_keys": violations},
        )


class LowConfidenceRateGrader:
    """Informational, not a hard failure — reports how much of a record's
    classification the model itself was unsure about. Useful as a review-
    queue signal (ai_evals.md §18 confidence calibration needs gold to
    check *correctness* of confidence; without gold this only reports the
    raw distribution)."""

    key = "low_confidence_rate"
    version = "v1"

    def __init__(self, *, threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD) -> None:
        self._threshold = threshold

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        labels = candidate_output.get("labels", [])
        if not labels:
            return GraderResult(
                grader_key=self.key,
                grader_version=self.version,
                passed=True,
                score=None,
                hard_failure=False,
                details={"label_count": 0},
            )
        low_confidence = [
            label for label in labels if label.get("confidence", 1.0) < self._threshold
        ]
        rate = len(low_confidence) / len(labels)
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=True,  # informational only — never a hard failure on its own
            score=1 - rate,
            hard_failure=False,
            details={"low_confidence_rate": rate, "threshold": self._threshold},
        )
