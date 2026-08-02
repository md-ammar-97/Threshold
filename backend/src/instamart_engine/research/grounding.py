"""Deterministic grounding validation for generated answers.
edgecases.md ANS-001/004/006/019/024, CIT-001/002; architecture.md §17.4-17.6.

Citation labels are resolved against the exact evidence package built for
this question moments earlier in the same request — a label the model
invents or misremembers simply fails to resolve and is dropped. This is
what prevents CIT-001 ("citation points to wrong object") structurally,
the same way Phase 4's insight generation resolves excerpt numbers rather
than trusting model-supplied record IDs (edgecases.md INS-016).
"""

from dataclasses import dataclass

from instamart_engine.analysis.demographic_guard import contains_demographic_inference
from instamart_engine.feedback.models import QualityEventSeverity
from instamart_engine.insights.causal_guard import contains_causal_overclaim
from instamart_engine.insights.models import EvidenceRole
from instamart_engine.research.models import (
    CitationObjectType,
    FindingSupportStatus,
    RetrievalObjectType,
)
from instamart_engine.research.retrieval import EvidenceItem, EvidencePackage
from instamart_engine.research.schemas import AnswerFindingOutput

_RETRIEVAL_TO_CITATION_OBJECT_TYPE = {
    RetrievalObjectType.FEEDBACK_RECORD: CitationObjectType.FEEDBACK_RECORD,
    RetrievalObjectType.THEME: CitationObjectType.THEME,
    RetrievalObjectType.INSIGHT: CitationObjectType.INSIGHT,
}


@dataclass(frozen=True, slots=True)
class ResolvedCitation:
    label: str
    item: EvidenceItem
    object_type: CitationObjectType
    evidence_role: EvidenceRole


@dataclass(frozen=True, slots=True)
class GroundingWarning:
    warning_type: str
    severity: QualityEventSeverity
    message: str
    details: dict


@dataclass(frozen=True, slots=True)
class ValidatedFinding:
    statement: str
    finding_type: str
    confidence_level: str
    confidence_score: float | None
    support_status: FindingSupportStatus
    citations: list[ResolvedCitation]
    dropped_labels: list[str]
    redacted: bool


def _resolve_citations(
    finding: AnswerFindingOutput, evidence_package: EvidencePackage
) -> tuple[list[ResolvedCitation], list[str]]:
    resolved: list[ResolvedCitation] = []
    dropped: list[str] = []
    for label in finding.citation_labels:
        item = evidence_package.resolve(label)
        if item is None:
            dropped.append(label)
            continue
        role = (
            EvidenceRole.CONTRADICTORY
            if item.metadata.get("is_counterexample")
            else EvidenceRole.SUPPORTING
        )
        resolved.append(
            ResolvedCitation(
                label=label,
                item=item,
                object_type=_RETRIEVAL_TO_CITATION_OBJECT_TYPE[item.object_type],
                evidence_role=role,
            )
        )
    return resolved, dropped


def validate_finding(
    finding: AnswerFindingOutput, evidence_package: EvidencePackage
) -> tuple[ValidatedFinding, list[GroundingWarning]]:
    warnings: list[GroundingWarning] = []
    citations, dropped_labels = _resolve_citations(finding, evidence_package)

    if dropped_labels:
        warnings.append(
            GroundingWarning(
                warning_type="unresolvable_citation",
                severity=QualityEventSeverity.WARNING,
                message=f"Dropped {len(dropped_labels)} citation(s) not present in the "
                "evidence package.",
                details={"dropped_labels": dropped_labels, "statement": finding.statement},
            )
        )

    statement = finding.statement
    redacted = False
    if contains_demographic_inference(statement):
        # ANS-019 — an inferred demographic claim presented as fact is a
        # hard-failure category; reject the finding, don't just warn.
        warnings.append(
            GroundingWarning(
                warning_type="possible_demographic_inference",
                severity=QualityEventSeverity.ERROR,
                message="A finding was removed for containing an unsupported demographic "
                "inference.",
                details={"original_statement": statement},
            )
        )
        redacted = True
    elif contains_causal_overclaim(statement):
        warnings.append(
            GroundingWarning(
                warning_type="causal_overclaim",
                severity=QualityEventSeverity.WARNING,
                message="A finding used causal language stronger than public feedback "
                "can support.",
                details={"statement": statement},
            )
        )

    if redacted:
        support_status = FindingSupportStatus.UNSUPPORTED
    elif not citations:
        # ANS-004 — a finding without any resolvable citation is unsupported.
        support_status = FindingSupportStatus.UNSUPPORTED
        warnings.append(
            GroundingWarning(
                warning_type="insufficient_evidence",
                severity=QualityEventSeverity.WARNING,
                message="A finding had no resolvable citations and is marked unsupported.",
                details={"statement": statement},
            )
        )
    else:
        support_status = FindingSupportStatus.SUPPORTED

    validated = ValidatedFinding(
        statement=statement,
        finding_type=finding.finding_type,
        confidence_level=finding.confidence_level,
        confidence_score=finding.confidence_score,
        support_status=support_status,
        citations=citations,
        dropped_labels=dropped_labels,
        redacted=redacted,
    )
    return validated, warnings


def evidence_package_prompt_block(evidence_package: EvidencePackage) -> str:
    """Renders the evidence package as the labelled reference block the
    answer-generation prompt cites against (architecture.md §17.4)."""
    lines: list[str] = []

    def _render(items: list[EvidenceItem], heading: str) -> None:
        if not items:
            return
        lines.append(f"{heading}:")
        for item in items:
            marker = " [counterexample]" if item.metadata.get("is_counterexample") else ""
            lines.append(f"[{item.label}]{marker} {item.title}: {item.excerpt}")

    _render(evidence_package.themes, "Themes")
    _render(evidence_package.insights, "Insights")
    _render(evidence_package.records, "Feedback records")
    return "\n".join(lines)
