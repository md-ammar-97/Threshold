"""Theme-quality graders. ai_evals.md §27-31's rubric (coherence,
distinctness, naming accuracy, actionability) is a human-rated 1-5 scale
(§29) that needs a reviewer, not something to fabricate — same "no
fabricated gold/rubric" reasoning as `classification.py`/`retrieval.py`.
These are the deterministic per-theme checks from §30.1's provisional
release gates that don't need a human rater: "misleading or causal theme
names: 0", "themes without representative evidence: 0", and a
source-concentration check feeding "source-concentrated theme share".

Candidate output comes from `runners.py::_build_theme_candidate_output` —
one theme's name/summary/coherence/membership shape. Theme-*set*-level
metrics (coverage, outlier rate, overlap rate — §30's set-wide numbers that
don't fit a per-theme grader) are computed separately in `scripts/evaluate.py`,
not here."""

from typing import Any

from instamart_engine.insights.causal_guard import contains_causal_overclaim
from instamart_engine.validation.graders.base import GraderResult

DEFAULT_SOURCE_CONCENTRATION_THRESHOLD = 0.9


class ThemeNamingIntegrityGrader:
    """ai_evals.md §30.1 "misleading or causal theme names: 0" — reuses the
    exact detector `insights/causal_guard.py` already applies to answer
    findings, against a theme's `name` + `short_summary` instead."""

    key = "theme_naming_integrity"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        text = f"{candidate_output.get('name', '')} {candidate_output.get('short_summary', '')}"
        violated = contains_causal_overclaim(text)
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=not violated,
            score=0.0 if violated else 1.0,
            hard_failure=violated,
            failure_codes=("causal_overclaim_theme_name",) if violated else (),
        )


class RepresentativeEvidenceGrader:
    """ai_evals.md §30.1 "themes without representative evidence: 0" — a
    theme with no member marked `is_representative` gives a researcher
    nothing concrete to read, regardless of how the name/summary read."""

    key = "representative_evidence"
    version = "v1"

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        has_representative = bool(candidate_output.get("has_representative_evidence"))
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=has_representative,
            score=1.0 if has_representative else 0.0,
            hard_failure=not has_representative,
            failure_codes=() if has_representative else ("no_representative_evidence",),
        )


class SourceConcentrationGrader:
    """Feeds ai_evals.md §30's "source-concentrated theme share" — flags a
    theme whose members come almost entirely from one source connector,
    which usually means the theme reflects one platform's quirks (or one
    connector's over-representation in the corpus) rather than a genuine
    cross-source pattern. Informational, not a hard failure on its own —
    §30.1 gates on the *share of themes* concentrated like this across a
    theme set, computed separately in `scripts/evaluate.py`."""

    key = "source_concentration"
    version = "v1"

    def __init__(self, *, threshold: float = DEFAULT_SOURCE_CONCENTRATION_THRESHOLD) -> None:
        self._threshold = threshold

    def grade(
        self,
        input_snapshot: dict[str, Any],
        candidate_output: dict[str, Any],
        gold_output: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> GraderResult:
        source_counts: dict[str, int] = candidate_output.get("source_counts", {})
        total = sum(source_counts.values())
        if total == 0:
            return GraderResult(
                grader_key=self.key,
                grader_version=self.version,
                passed=True,
                score=None,
                hard_failure=False,
                details={"max_source_share": None},
            )

        max_share = max(source_counts.values()) / total
        concentrated = max_share >= self._threshold
        return GraderResult(
            grader_key=self.key,
            grader_version=self.version,
            passed=not concentrated,
            score=1 - max_share,
            hard_failure=False,
            failure_codes=("source_concentrated",) if concentrated else (),
            details={"max_source_share": max_share, "source_counts": source_counts},
        )
