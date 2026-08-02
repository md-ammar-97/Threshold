"""Emails a completed report export via Resend (resend.com). Wraps the
`resend` SDK behind a small function so the API route and tests don't touch
the SDK directly — same shape as `storage/factory.py` wrapping a
third-party integration behind this codebase's own interface."""

import html
import re

import resend

from instamart_engine.core.config import get_settings
from instamart_engine.reports.models import Report, ReportExport, ReportExportFormat


class EmailNotConfiguredError(Exception):
    """RESEND_API_KEY is not set. Distinct from a Resend API failure so the
    caller can return a clear "not configured" response instead of a
    generic 502."""


class EmailSendError(Exception):
    """The Resend API call itself failed (bad key, rate limit, etc.)."""


def _markdown_to_html_paragraphs(markdown_text: str) -> str:
    """A minimal, dependency-free Markdown-to-HTML pass — good enough for
    the plain heading/paragraph/list shape `reports/export.py::render_markdown`
    actually produces, not a general Markdown renderer."""
    lines = markdown_text.split("\n")
    html_lines: list[str] = []
    for line in lines:
        escaped = html.escape(line)
        if line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip() == "---":
            html_lines.append("<hr>")
        elif line.strip() == "":
            html_lines.append("<br>")
        else:
            emphasized = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
            html_lines.append(f"<p>{emphasized}</p>")
    return "\n".join(html_lines)


def send_report_export_email(
    *,
    report: Report,
    export: ReportExport,
    rendered_content: str,
    recipient_email: str,
) -> str:
    """Sends `rendered_content` (already-rendered Markdown text) as an HTML
    email. Returns the Resend message id. Raises `EmailNotConfiguredError`
    if `RESEND_API_KEY` is unset, `EmailSendError` if the API call fails."""
    if export.export_format != ReportExportFormat.MARKDOWN:
        raise ValueError("Only markdown exports can be emailed today")

    settings = get_settings()
    if not settings.RESEND_API_KEY:
        raise EmailNotConfiguredError("RESEND_API_KEY is not configured")

    resend.api_key = settings.RESEND_API_KEY
    body_html = _markdown_to_html_paragraphs(rendered_content)

    try:
        response = resend.Emails.send(
            {
                "from": settings.RESEND_FROM_EMAIL,
                "to": [recipient_email],
                "subject": f"Report: {report.title}",
                "html": f"<div>{body_html}</div>",
            }
        )
    except Exception as exc:  # noqa: BLE001 — the resend SDK's own exception types aren't part of its stable public API
        raise EmailSendError(f"Resend API call failed: {exc}") from exc

    return response["id"]
