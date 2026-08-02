"""Grader interface. ai_evals.md §11 (hierarchy), §84 (interface).

Graders run in a fixed order: schema/integrity -> gold comparison ->
rule-based semantic checks -> human rubric -> LLM judge. An LLM judge must
never override a failed deterministic or adjudicated-human check
(ai_evals.md §2.2, §11) — this module (and the graders built on it) only
implements the deterministic tiers 1 and 3; tier 2 (gold comparison) is
implemented per-suite once a gold dataset exists, and tiers 4-5 (human
rubric, LLM judge) require a review workspace and a calibrated judge
prompt that don't exist yet (ai_evals.md §12.4) — deferred, same reasoning
as every prior phase's gold-set/rubric gaps.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class GraderResult:
    grader_key: str
    grader_version: str
    passed: bool
    score: float | None
    hard_failure: bool
    failure_codes: tuple[str, ...] = field(default_factory=tuple)
    details: dict[str, Any] = field(default_factory=dict)


class EvalGrader(Protocol):
    key: str
    version: str

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult: ...
