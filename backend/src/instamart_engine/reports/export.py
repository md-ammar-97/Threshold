"""Report export rendering. design.md §33.5 (Markdown preview, evidence
footnotes) — Markdown, JSON, and PDF."""

import json
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import UUID

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

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


def _pdf_escape(text: str) -> str:
    """`Paragraph` bodies use a small XML-like markup — user/model-generated
    text must be entity-escaped or a stray `<`/`&` breaks rendering. Also
    swaps the rupee sign for "Rs." — the base-14 PDF fonts reportlab uses
    here have no glyph for U+20B9, so it would otherwise render as a
    black box in feedback text (this dataset is India-focused)."""
    return (
        text.replace("₹", "Rs. ")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_pdf(
    report: Report,
    sections: list[ReportSection],
    evidence_by_section: dict[UUID, list[ReportEvidenceLink]],
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        title=report.title,
    )
    styles = getSampleStyleSheet()
    evidence_style = ParagraphStyle(
        "Evidence", parent=styles["Normal"], leftIndent=18, spaceAfter=2, alignment=TA_LEFT
    )

    story: list[Any] = [Paragraph(_pdf_escape(report.title), styles["Title"])]
    if report.subtitle:
        story.append(Paragraph(_pdf_escape(report.subtitle), styles["Italic"]))
    story.append(Spacer(1, 0.25 * inch))

    for section in sections:
        story.append(Paragraph(_pdf_escape(section.title), styles["Heading2"]))
        if section.narrative_text:
            for paragraph in section.narrative_text.split("\n\n"):
                if paragraph.strip():
                    story.append(Paragraph(_pdf_escape(paragraph), styles["BodyText"]))
        elif section.content:
            content_json = _pdf_escape(json.dumps(section.content, indent=2))
            story.append(
                Paragraph(f"<font face='Courier' size=8>{content_json}</font>", styles["Normal"])
            )
        else:
            story.append(Paragraph("<i>(no content yet)</i>", styles["Normal"]))

        evidence = evidence_by_section.get(section.id, [])
        if evidence:
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph("<b>Evidence:</b>", styles["Normal"]))
            for link in evidence:
                story.append(
                    Paragraph(
                        f"• [{link.object_type.value}] {_pdf_escape(_evidence_label(link))}",
                        evidence_style,
                    )
                )
        story.append(Spacer(1, 0.2 * inch))

    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph(
            f"<i>Generated {datetime.now(UTC).isoformat()}</i>", styles["Normal"]
        )
    )

    doc.build(story)
    return buffer.getvalue()


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
