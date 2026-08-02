"""Grader 1 — citation integrity. ai_evals.md §11/§36; edgecases.md
ANS-004/005/024, CIT-001.

Fabricated-citation and citation-count checks are deterministic and must
never be delegated to an LLM judge (ai_evals.md §12.2). Object existence is
resolved by the runner into `context["existing_citation_object_ids"]`
beforehand (one batch query) so this grader stays a pure function, matching
the `EvalGrader` protocol.
"""

from typing import Any

from instamart_engine.validation.graders.base import GraderResult


class CitationIntegrityGrader:
    key = "citation_integrity"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        findings = candidate_output.get("findings", [])
        existing_ids: set[str] = context.get("existing_citation_object_ids", set())
        declared_citation_count = candidate_output.get("citation_count")

        failure_codes: list[str] = []
        actual_citation_count = 0
        uncovered_findings = 0

        for finding in findings:
            citations = finding.get("citations", [])
            if not citations:
                uncovered_findings += 1
                continue
            for citation in citations:
                actual_citation_count += 1
                object_id = str(citation.get("object_id"))
                if object_id not in existing_ids:
                    # CIT-001 / ai_evals.md §41 "fabricated citation" — a
                    # citation whose object doesn't exist in this request's
                    # own resolved set is a hard, zero-tolerance failure.
                    failure_codes.append(f"fabricated_citation:{citation.get('citation_label')}")

        if (
            declared_citation_count is not None
            and declared_citation_count != actual_citation_count
        ):
            # ANS-024 — the declared count must equal the actual rows.
            failure_codes.append("citation_count_mismatch")

        coverage = (
            1.0 if not findings else (len(findings) - uncovered_findings) / len(findings)
        )
        hard_failure = any(code.startswith("fabricated_citation") for code in failure_codes)
        passed = not failure_codes

        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=coverage,
            hard_failure=hard_failure,
            failure_codes=tuple(failure_codes),
            details={
                "citation_coverage": coverage,
                "actual_citation_count": actual_citation_count,
                "uncovered_findings": uncovered_findings,
            },
        )
