"""Report export rendering. design.md §33.5 (Markdown preview, evidence
footnotes) — Markdown and JSON only; PDF is a documented, deferred
`ReportExportFormat` member (see `reports/models.py`'s docstring)."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from instamart_engine.reports.models import Report, ReportEvidenceLink, ReportSection


def _evidence_label(link: ReportEvidenceLink) -> str:
    snapshot = link.snapshot
    return (
        snapshot.get("title")
        or snapshot.get("name")
        or (snapshot.get("finding") or "")[:80]
        or (snapshot.get("excerpt") or "")[:80]
        or (snapshot.get("answer_text") or "")[:80]
        or str(link.object_id)
    )


def render_markdown(
    report: Report,
    sections: list[ReportSection],
    evidence_by_section: dict[UUID, list[ReportEvidenceLink]],
) -> str:
    lines = [f"# {report.title}"]
    if report.subtitle:
        lines.append(f"*{report.subtitle}*")
    lines.append("")

    for section in sections:
        lines.append(f"## {section.title}")
        lines.append("")
        if section.narrative_text:
            lines.append(section.narrative_text)
        elif section.content:
            # content is structured JSON (design.md §33.3) — a readable
            # fallback for sections without a human/generated narrative yet.
            lines.append(f"```json\n{json.dumps(section.content, indent=2)}\n```")
        else:
            lines.append("_(no content yet)_")

        evidence = evidence_by_section.get(section.id, [])
        if evidence:
            lines.append("")
            lines.append("**Evidence:**")
            for link in evidence:
                lines.append(f"- [{link.object_type.value}] {_evidence_label(link)}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Generated {datetime.now(UTC).isoformat()}_")
    return "\n".join(lines)


def render_json(
    report: Report,
    sections: list[ReportSection],
    evidence_by_section: dict[UUID, list[ReportEvidenceLink]],
) -> dict[str, Any]:
    return {
        "id": str(report.id),
        "title": report.title,
        "subtitle": report.subtitle,
        "status": report.status.value,
        "sections": [
            {
                "id": str(section.id),
                "section_type": section.section_type.value,
                "position": section.position,
                "title": section.title,
                "content": section.content,
                "narrative_text": section.narrative_text,
                "is_locked": section.is_locked,
                "evidence": [
                    {
                        "object_type": link.object_type.value,
                        "object_id": str(link.object_id),
                        "snapshot": link.snapshot,
                    }
                    for link in evidence_by_section.get(section.id, [])
                ],
            }
            for section in sections
        ],
        "generated_at": datetime.now(UTC).isoformat(),
    }
