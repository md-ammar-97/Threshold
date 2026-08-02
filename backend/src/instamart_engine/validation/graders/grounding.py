"""Grader 3 — rule-based semantic checks for grounding quality.
ai_evals.md §11 "causal phrase detector", "insufficient-evidence policy";
edgecases.md INS-002/ANS-020 (causal overclaim), ANS-001 (insufficient
evidence). Reuses the same detectors used at generation time
(insights.causal_guard) — a regression check, not a duplicate control.
"""

from typing import Any

from instamart_engine.insights.causal_guard import contains_causal_overclaim
from instamart_engine.validation.graders.base import GraderResult
from instamart_engine.validation.graders.privacy import collect_text_fields

_INSUFFICIENT_EVIDENCE_MARKER = "not enough"


class CausalOverclaimGrader:
    key = "causal_overclaim"
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
            if contains_causal_overclaim(text)
        ]
        passed = not violations
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=1.0 if passed else 0.0,
            # Soft signal, matching how causal_guard is used at generation
            # time (ai_evals.md §33 lists this as a hard failure for
            # egregious cases, but the deterministic phrase list here is
            # intentionally narrow/high-precision, so a hit is a strong
            # candidate for human review rather than an automatic block).
            hard_failure=False,
            failure_codes=tuple("causal_overclaim" for _ in violations),
            details={"violations": violations},
        )


class InsufficientEvidencePolicyGrader:
    key = "insufficient_evidence_policy"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        citation_count = candidate_output.get("citation_count", 0)
        answer_text = candidate_output.get("answer_text", "")
        states_insufficient = _INSUFFICIENT_EVIDENCE_MARKER in answer_text.lower()

        if citation_count == 0 and not states_insufficient:
            # ANS-001/ai_evals.md §39 — zero evidence must be disclosed as
            # insufficient, never presented as a confident answer.
            return GraderResult(
                grader_key=self.key,
                grader_version=self.version,
                passed=False,
                score=0.0,
                hard_failure=True,
                failure_codes=("confident_answer_without_evidence",),
                details={"citation_count": citation_count},
            )

        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=True,
            score=1.0,
            hard_failure=False,
            details={"citation_count": citation_count},
        )
