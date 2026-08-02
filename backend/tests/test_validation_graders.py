import pytest

from instamart_engine.validation.graders.citations import CitationIntegrityGrader
from instamart_engine.validation.graders.classification import (
    DemographicInferenceGrader as ClassificationDemographicInferenceGrader,
)
from instamart_engine.validation.graders.classification import (
    LowConfidenceRateGrader,
    UnsupportedLabelGrader,
)
from instamart_engine.validation.graders.grounding import (
    CausalOverclaimGrader,
    InsufficientEvidencePolicyGrader,
)
from instamart_engine.validation.graders.privacy import DemographicInferenceGrader
from instamart_engine.validation.graders.retrieval import (
    CrossVersionContaminationGrader,
    DeletedObjectRetrievalGrader,
    DuplicateEvidenceGrader,
)
from instamart_engine.validation.graders.schema import SchemaIntegrityGrader
from instamart_engine.validation.graders.theme_quality import (
    RepresentativeEvidenceGrader,
    SourceConcentrationGrader,
    ThemeNamingIntegrityGrader,
)


def test_schema_grader_passes_when_all_required_keys_present() -> None:
    grader = SchemaIntegrityGrader(required_keys=("answer_text", "citation_count"))
    result = grader.grade({}, {"answer_text": "x", "citation_count": 0}, None, {})
    assert result.passed is True
    assert result.hard_failure is False


def test_schema_grader_fails_on_missing_key() -> None:
    grader = SchemaIntegrityGrader(required_keys=("answer_text", "citation_count"))
    result = grader.grade({}, {"answer_text": "x"}, None, {})
    assert result.passed is False
    assert result.hard_failure is True
    assert "missing_key:citation_count" in result.failure_codes


def test_citation_grader_passes_when_all_citations_resolve() -> None:
    grader = CitationIntegrityGrader()
    candidate = {
        "citation_count": 1,
        "findings": [
            {"statement": "x", "citations": [{"citation_label": "E1", "object_id": "abc"}]}
        ],
    }
    result = grader.grade({}, candidate, None, {"existing_citation_object_ids": {"abc"}})
    assert result.passed is True
    assert result.hard_failure is False
    assert result.score == 1.0


@pytest.mark.p0_adversarial
def test_citation_grader_flags_fabricated_citation() -> None:
    grader = CitationIntegrityGrader()
    candidate = {
        "citation_count": 1,
        "findings": [
            {"statement": "x", "citations": [{"citation_label": "E1", "object_id": "ghost"}]}
        ],
    }
    result = grader.grade({}, candidate, None, {"existing_citation_object_ids": set()})
    assert result.passed is False
    assert result.hard_failure is True
    assert any("fabricated_citation" in code for code in result.failure_codes)


def test_citation_grader_flags_count_mismatch() -> None:
    grader = CitationIntegrityGrader()
    candidate = {
        "citation_count": 5,
        "findings": [
            {"statement": "x", "citations": [{"citation_label": "E1", "object_id": "abc"}]}
        ],
    }
    result = grader.grade({}, candidate, None, {"existing_citation_object_ids": {"abc"}})
    assert "citation_count_mismatch" in result.failure_codes


def test_citation_grader_flags_uncovered_finding() -> None:
    grader = CitationIntegrityGrader()
    candidate = {"citation_count": 0, "findings": [{"statement": "x", "citations": []}]}
    result = grader.grade({}, candidate, None, {"existing_citation_object_ids": set()})
    assert result.details["uncovered_findings"] == 1
    assert result.score == 0.0


@pytest.mark.p0_adversarial
def test_demographic_inference_grader_flags_violation() -> None:
    grader = DemographicInferenceGrader()
    candidate = {"answer_text": "This is likely a young professional user."}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is False
    assert result.hard_failure is True


def test_demographic_inference_grader_passes_clean_text() -> None:
    grader = DemographicInferenceGrader()
    candidate = {"answer_text": "Users reported a delivery delay."}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True
    assert result.hard_failure is False


def test_causal_overclaim_grader_warns_but_not_hard_failure() -> None:
    grader = CausalOverclaimGrader()
    candidate = {"answer_text": "Missing freshness info causes users to abandon carts."}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is False
    assert result.hard_failure is False


@pytest.mark.p0_adversarial
def test_insufficient_evidence_policy_grader_flags_confident_empty_answer() -> None:
    grader = InsufficientEvidencePolicyGrader()
    candidate = {"citation_count": 0, "answer_text": "Users love the freshness of produce."}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is False
    assert result.hard_failure is True


def test_insufficient_evidence_policy_grader_passes_when_disclosed() -> None:
    grader = InsufficientEvidencePolicyGrader()
    candidate = {"citation_count": 0, "answer_text": "There is not enough evidence to answer."}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True


def test_insufficient_evidence_policy_grader_passes_with_citations() -> None:
    grader = InsufficientEvidencePolicyGrader()
    candidate = {"citation_count": 2, "answer_text": "Users report freshness concerns."}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True


# --- Classification quality (validation/graders/classification.py) ---


def test_unsupported_label_grader_passes_when_all_labels_current() -> None:
    grader = UnsupportedLabelGrader()
    candidate = {
        "labels": [
            {"dimension_key": "frustration", "belongs_to_own_taxonomy_version": True},
            {"dimension_key": "journey_stage", "belongs_to_own_taxonomy_version": True},
        ]
    }
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True
    assert result.hard_failure is False
    assert result.score == 1.0


@pytest.mark.p0_adversarial
def test_unsupported_label_grader_flags_stale_taxonomy_version() -> None:
    grader = UnsupportedLabelGrader()
    candidate = {
        "labels": [
            {"dimension_key": "frustration", "belongs_to_own_taxonomy_version": True},
            {"dimension_key": "old_dimension", "belongs_to_own_taxonomy_version": False},
        ]
    }
    result = grader.grade({}, candidate, None, {})
    assert result.passed is False
    assert result.hard_failure is True
    assert "unsupported_label:old_dimension" in result.failure_codes


def test_classification_demographic_inference_grader_flags_violation() -> None:
    grader = ClassificationDemographicInferenceGrader()
    candidate = {
        "labels": [
            {"dimension_key": "household_role", "evidence_excerpt": "sounds like a working mother"}
        ]
    }
    result = grader.grade({}, candidate, None, {})
    assert result.passed is False
    assert result.hard_failure is True


def test_classification_demographic_inference_grader_passes_clean_excerpts() -> None:
    grader = ClassificationDemographicInferenceGrader()
    candidate = {
        "labels": [{"dimension_key": "frustration", "evidence_excerpt": "delivery was late"}]
    }
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True


def test_low_confidence_rate_grader_reports_rate_without_hard_failure() -> None:
    grader = LowConfidenceRateGrader(threshold=0.5)
    candidate = {"labels": [{"confidence": 0.3}, {"confidence": 0.9}]}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True
    assert result.hard_failure is False
    assert result.details["low_confidence_rate"] == 0.5


def test_low_confidence_rate_grader_handles_no_labels() -> None:
    grader = LowConfidenceRateGrader()
    result = grader.grade({}, {"labels": []}, None, {})
    assert result.passed is True
    assert result.score is None


# --- Retrieval quality (validation/graders/retrieval.py) ---


def _finding_with_citation(object_type: str, object_id: str, label: str = "E1") -> dict:
    return {
        "statement": "x",
        "citations": [
            {"citation_label": label, "object_type": object_type, "object_id": object_id}
        ],
    }


def test_cross_version_contamination_grader_passes_single_run() -> None:
    grader = CrossVersionContaminationGrader()
    candidate = {"findings": [_finding_with_citation("feedback_record", "r1")]}
    context = {"citation_object_details": {"r1": {"analysis_run_id": "run-a"}}}
    result = grader.grade({}, candidate, None, context)
    assert result.passed is True
    assert result.hard_failure is False


@pytest.mark.p0_adversarial
def test_cross_version_contamination_grader_flags_mixed_runs() -> None:
    grader = CrossVersionContaminationGrader()
    candidate = {
        "findings": [
            _finding_with_citation("feedback_record", "r1", "E1"),
            _finding_with_citation("theme", "t1", "T1"),
        ]
    }
    context = {
        "citation_object_details": {
            "r1": {"analysis_run_id": "run-a"},
            "t1": {"analysis_run_id": "run-b"},
        }
    }
    result = grader.grade({}, candidate, None, context)
    assert result.passed is False
    assert result.hard_failure is True
    assert set(result.details["distinct_analysis_run_ids"]) == {"run-a", "run-b"}


def test_deleted_object_retrieval_grader_flags_deleted_citation() -> None:
    grader = DeletedObjectRetrievalGrader()
    candidate = {"findings": [_finding_with_citation("feedback_record", "r1")]}
    context = {"citation_object_details": {"r1": {"deleted_at": "2026-01-01T00:00:00Z"}}}
    result = grader.grade({}, candidate, None, context)
    assert result.passed is False
    assert result.hard_failure is True
    assert "deleted_object_cited:E1" in result.failure_codes


def test_deleted_object_retrieval_grader_passes_live_objects() -> None:
    grader = DeletedObjectRetrievalGrader()
    candidate = {"findings": [_finding_with_citation("feedback_record", "r1")]}
    context = {"citation_object_details": {"r1": {"deleted_at": None}}}
    result = grader.grade({}, candidate, None, context)
    assert result.passed is True


def test_duplicate_evidence_grader_flags_repeated_citation() -> None:
    grader = DuplicateEvidenceGrader()
    candidate = {
        "findings": [
            _finding_with_citation("feedback_record", "r1", "E1"),
            _finding_with_citation("feedback_record", "r1", "E2"),
        ]
    }
    result = grader.grade({}, candidate, None, {})
    assert result.details["duplicate_rate"] == 0.5
    assert "duplicate_evidence:E2" in result.failure_codes


def test_duplicate_evidence_grader_passes_distinct_citations() -> None:
    grader = DuplicateEvidenceGrader()
    candidate = {
        "findings": [
            _finding_with_citation("feedback_record", "r1", "E1"),
            _finding_with_citation("feedback_record", "r2", "E2"),
        ]
    }
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True
    assert result.details["duplicate_rate"] == 0.0


# --- Theme quality (validation/graders/theme_quality.py) ---


def test_theme_naming_integrity_grader_passes_clean_name() -> None:
    grader = ThemeNamingIntegrityGrader()
    candidate = {"name": "Delivery delays", "short_summary": "Users report late deliveries."}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True
    assert result.hard_failure is False


@pytest.mark.p0_adversarial
def test_theme_naming_integrity_grader_flags_causal_name() -> None:
    grader = ThemeNamingIntegrityGrader()
    candidate = {
        "name": "Missing freshness info causes cart abandonment",
        "short_summary": "x",
    }
    result = grader.grade({}, candidate, None, {})
    assert result.passed is False
    assert result.hard_failure is True


def test_representative_evidence_grader_passes_when_present() -> None:
    grader = RepresentativeEvidenceGrader()
    result = grader.grade({}, {"has_representative_evidence": True}, None, {})
    assert result.passed is True
    assert result.hard_failure is False


def test_representative_evidence_grader_fails_when_absent() -> None:
    grader = RepresentativeEvidenceGrader()
    result = grader.grade({}, {"has_representative_evidence": False}, None, {})
    assert result.passed is False
    assert result.hard_failure is True
    assert "no_representative_evidence" in result.failure_codes


def test_source_concentration_grader_passes_diverse_sources() -> None:
    grader = SourceConcentrationGrader(threshold=0.9)
    candidate = {"source_counts": {"google_play": 5, "reddit": 5}}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is True
    assert result.details["max_source_share"] == 0.5


def test_source_concentration_grader_flags_single_source_domination() -> None:
    grader = SourceConcentrationGrader(threshold=0.9)
    candidate = {"source_counts": {"google_play": 19, "reddit": 1}}
    result = grader.grade({}, candidate, None, {})
    assert result.passed is False
    assert result.hard_failure is False  # informational, not a hard failure
    assert "source_concentrated" in result.failure_codes


def test_source_concentration_grader_handles_no_members() -> None:
    grader = SourceConcentrationGrader()
    result = grader.grade({}, {"source_counts": {}}, None, {})
    assert result.passed is True
    assert result.score is None
