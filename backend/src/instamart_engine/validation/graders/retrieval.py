"""Retrieval-quality graders. ai_evals.md §24's release gates (Precision@K,
nDCG, Recall, MRR) need graded-relevance gold data we don't have — same
"no fabricated gold" reasoning as `classification.py`. These are the
deterministic checks computable from the retrieved evidence package alone:
`ai_evals.md` §24.2's "duplicate evidence < 5%", "cross-version
contamination 0%", and "deleted-object retrieval 0%" gates.

A `RETRIEVAL`-type evaluation dataset reuses the same `generated_answer`
candidate shape `GROUNDING` datasets use (`runners.py::_build_grounding_candidate_output`)
— citations/findings *are* the retrieved evidence package — so these
graders read `candidate_output["findings"][*]["citations"]`, same as
`citations.py`. `CrossVersionContaminationGrader`/`DeletedObjectRetrievalGrader`
additionally need `context["citation_object_details"]`
(`runners.py::_resolve_citation_object_details`)."""

from typing import Any

from instamart_engine.validation.graders.base import GraderResult


def _all_citations(candidate_output: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        citation
        for finding in candidate_output.get("findings", [])
        for citation in finding.get("citations", [])
    ]


class CrossVersionContaminationGrader:
    """ai_evals.md §24.2 "cross-version contamination: 0%"; datamodel.md
    §67 invariant #6 (a theme membership's record must have been eligible
    in that theme set's own dataset snapshot) generalizes here to: every
    citation in one answer package must trace back to the same
    `analysis_run_id`. Mixing evidence analyzed under two different
    pipeline runs (and potentially two different taxonomy versions) inside
    one answer is a real integrity problem regardless of which run is
    "correct"."""

    key = "cross_version_contamination"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        details_by_id: dict[str, dict[str, Any]] = context.get("citation_object_details", {})
        run_ids: set[str] = set()
        for citation in _all_citations(candidate_output):
            info = details_by_id.get(str(citation.get("object_id")))
            if info and info.get("analysis_run_id"):
                run_ids.add(info["analysis_run_id"])

        contaminated = len(run_ids) > 1
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=not contaminated,
            score=0.0 if contaminated else 1.0,
            hard_failure=contaminated,
            failure_codes=("cross_version_contamination",) if contaminated else (),
            details={"distinct_analysis_run_ids": sorted(run_ids)},
        )


class DeletedObjectRetrievalGrader:
    """ai_evals.md §24.2 "deleted-object retrieval: 0%" — a citation must
    never point at an object that has since been soft-deleted."""

    key = "deleted_object_retrieval"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        details_by_id: dict[str, dict[str, Any]] = context.get("citation_object_details", {})
        deleted_labels = []
        for citation in _all_citations(candidate_output):
            info = details_by_id.get(str(citation.get("object_id")))
            if info and info.get("deleted_at"):
                deleted_labels.append(citation.get("citation_label"))

        passed = not deleted_labels
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=1.0 if passed else 0.0,
            hard_failure=not passed,
            failure_codes=tuple(f"deleted_object_cited:{label}" for label in deleted_labels),
            details={"deleted_citation_labels": deleted_labels},
        )


class DuplicateEvidenceGrader:
    """ai_evals.md §24.2 "duplicate evidence in selected package < 5%" —
    purely structural (no DB lookup needed): the same object cited twice
    within one answer package adds bulk, not distinct support."""

    key = "duplicate_evidence"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        seen: set[tuple[str | None, str | None]] = set()
        duplicate_labels = []
        for citation in _all_citations(candidate_output):
            key = (citation.get("object_type"), citation.get("object_id"))
            if key in seen:
                duplicate_labels.append(citation.get("citation_label"))
            else:
                seen.add(key)

        total = len(seen) + len(duplicate_labels)
        rate = len(duplicate_labels) / total if total else 0.0
        passed = rate < 0.05
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=passed,
            score=1 - rate,
            hard_failure=False,
            failure_codes=tuple(f"duplicate_evidence:{label}" for label in duplicate_labels),
            details={"duplicate_rate": rate, "duplicate_citation_labels": duplicate_labels},
        )
