"""Grader 3 — rule-based semantic check: unsupported demographic inference.
ai_evals.md §11 "unsupported demographic detector"; edgecases.md ANS-019,
INS-003. Reuses the same narrow, high-precision detector already used at
generation time (analysis.demographic_guard) — this grader exists to catch
a regression that generation-time redaction missed, not to duplicate it.
"""

from typing import Any

from instamart_engine.analysis.demographic_guard import contains_demographic_inference
from instamart_engine.validation.graders.base import GraderResult

_TEXT_FIELDS = ("answer_text", "finding", "interpretation", "summary")


def collect_text_fields(candidate_output: dict[str, Any]) -> list[str]:
    texts = [
        candidate_output[field]
        for field in _TEXT_FIELDS
        if isinstance(candidate_output.get(field), str)
    ]
    for finding in candidate_output.get("findings", []):
        statement = finding.get("statement")
        if isinstance(statement, str):
            texts.append(statement)
    return texts


class DemographicInferenceGrader:
    key = "demographic_inference"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        violations = [
            text
            for text in collect_text_fields(candidate_output)
            if contains_demographic_inference(text)
        ]
        passed = not violations
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=1.0 if passed else 0.0,
            # ai_evals.md §41/§85 — unsupported demographic inference is a
            # zero-tolerance category, never a soft warning.
            hard_failure=not passed,
            failure_codes=tuple("unsupported_demographic_inference" for _ in violations),
            details={"violations": violations},
        )
