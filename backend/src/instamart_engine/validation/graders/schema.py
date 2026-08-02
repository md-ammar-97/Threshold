"""Grader 1 — schema/integrity. ai_evals.md §11. Deterministic; runs first
and is never overridden by a later grader."""

from typing import Any

from instamart_engine.validation.graders.base import GraderResult


class SchemaIntegrityGrader:
    key = "schema_integrity"
    version = "v1"

    def __init__(self, required_keys: tuple[str, ...]) -> None:
        self._required_keys = required_keys

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        missing = [key for key in self._required_keys if candidate_output.get(key) is None]
        passed = not missing
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=1.0 if passed else 0.0,
            hard_failure=not passed,
            failure_codes=tuple(f"missing_key:{key}" for key in missing),
            details={"missing_keys": missing},
        )
