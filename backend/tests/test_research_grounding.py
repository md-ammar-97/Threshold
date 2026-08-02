import uuid

from instamart_engine.research.grounding import validate_finding
from instamart_engine.research.models import FindingSupportStatus, RetrievalObjectType
from instamart_engine.research.retrieval import EvidenceItem, EvidencePackage
from instamart_engine.research.schemas import AnswerFindingOutput


def _package() -> EvidencePackage:
    return EvidencePackage(
        themes=[
            EvidenceItem(
                label="T1",
                object_type=RetrievalObjectType.THEME,
                object_id=uuid.uuid4(),
                title="Missing freshness info",
                excerpt="Users report missing freshness info.",
                metadata={},
            )
        ],
        insights=[],
        records=[
            EvidenceItem(
                label="E1",
                object_type=RetrievalObjectType.FEEDBACK_RECORD,
                object_id=uuid.uuid4(),
                title="Feedback record",
                excerpt="I could not find freshness information before buying.",
                metadata={"is_counterexample": False},
            ),
            EvidenceItem(
                label="E2",
                object_type=RetrievalObjectType.FEEDBACK_RECORD,
                object_id=uuid.uuid4(),
                title="Feedback record",
                excerpt="The freshness label was clearly shown.",
                metadata={"is_counterexample": True},
            ),
        ],
    )


def _finding(**overrides) -> AnswerFindingOutput:
    defaults = dict(
        statement="Users report missing freshness information before purchase.",
        finding_type="synthesized_insight",
        confidence_level="medium",
        confidence_score=0.7,
        citation_labels=["E1"],
    )
    defaults.update(overrides)
    return AnswerFindingOutput(**defaults)


def test_valid_citation_resolves_and_is_supported() -> None:
    validated, warnings = validate_finding(_finding(), _package())
    assert validated.support_status == FindingSupportStatus.SUPPORTED
    assert len(validated.citations) == 1
    assert validated.citations[0].label == "E1"
    assert warnings == []


def test_counterexample_citation_resolves_as_contradictory() -> None:
    validated, _ = validate_finding(_finding(citation_labels=["E2"]), _package())
    assert validated.citations[0].evidence_role.value == "contradictory"


def test_unresolvable_citation_is_dropped_and_warned() -> None:
    validated, warnings = validate_finding(_finding(citation_labels=["E99"]), _package())
    assert validated.citations == []
    assert validated.dropped_labels == ["E99"]
    assert any(w.warning_type == "unresolvable_citation" for w in warnings)
    # No resolvable citations left -> unsupported (ANS-004).
    assert validated.support_status == FindingSupportStatus.UNSUPPORTED


def test_no_citations_is_unsupported() -> None:
    validated, warnings = validate_finding(_finding(citation_labels=[]), _package())
    assert validated.support_status == FindingSupportStatus.UNSUPPORTED
    assert any(w.warning_type == "insufficient_evidence" for w in warnings)


def test_demographic_inference_is_redacted() -> None:
    validated, warnings = validate_finding(
        _finding(statement="This is likely a young professional user segment."), _package()
    )
    assert validated.redacted is True
    assert validated.support_status == FindingSupportStatus.UNSUPPORTED
    assert any(w.warning_type == "possible_demographic_inference" for w in warnings)
    assert any(w.severity.value == "error" for w in warnings)


def test_causal_overclaim_warns_but_keeps_finding() -> None:
    validated, warnings = validate_finding(
        _finding(statement="Missing freshness info causes users to abandon their cart."),
        _package(),
    )
    assert validated.redacted is False
    assert validated.support_status == FindingSupportStatus.SUPPORTED
    assert any(w.warning_type == "causal_overclaim" for w in warnings)
