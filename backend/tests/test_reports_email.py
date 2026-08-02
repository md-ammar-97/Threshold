"""Unit tests for `reports/email.py`. Mocks `resend.Emails.send` — no real
network call, no real API key needed, matching the AI-gateway-mocking
pattern already used in `test_analysis_classify.py` etc."""

import uuid
from datetime import datetime

import pytest

from instamart_engine.core.config import get_settings
from instamart_engine.reports import email as report_email
from instamart_engine.reports.models import (
    Report,
    ReportExport,
    ReportExportFormat,
    ReportExportStatus,
    ReportStatus,
)


def _fake_report() -> Report:
    return Report(
        id=uuid.uuid4(),
        title="Q3 Discovery Findings",
        subtitle=None,
        analysis_run_id=uuid.uuid4(),
        theme_set_id=uuid.uuid4(),
        status=ReportStatus.DRAFT,
        report_configuration={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _fake_export(
    *, export_format: ReportExportFormat = ReportExportFormat.MARKDOWN
) -> ReportExport:
    return ReportExport(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        export_format=export_format,
        status=ReportExportStatus.COMPLETED,
        export_configuration={},
    )


def test_send_report_export_email_raises_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(report_email.EmailNotConfiguredError):
            report_email.send_report_export_email(
                report=_fake_report(),
                export=_fake_export(),
                rendered_content="# Title\n\nBody text.",
                recipient_email="user@example.com",
            )
    finally:
        get_settings.cache_clear()


def test_send_report_export_email_rejects_non_markdown_format(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="markdown"):
            report_email.send_report_export_email(
                report=_fake_report(),
                export=_fake_export(export_format=ReportExportFormat.JSON),
                rendered_content="{}",
                recipient_email="user@example.com",
            )
    finally:
        get_settings.cache_clear()


def test_send_report_export_email_success(monkeypatch) -> None:
    captured_calls = []

    def fake_send(params):
        captured_calls.append(params)
        return {"id": "fake-message-id"}

    monkeypatch.setattr("instamart_engine.reports.email.resend.Emails.send", fake_send)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "reports@example.com")
    get_settings.cache_clear()
    try:
        message_id = report_email.send_report_export_email(
            report=_fake_report(),
            export=_fake_export(),
            rendered_content=(
                "# Q3 Discovery Findings\n\n## Executive Summary\n\nUsers report delays."
            ),
            recipient_email="researcher@example.com",
        )
    finally:
        get_settings.cache_clear()

    assert message_id == "fake-message-id"
    assert len(captured_calls) == 1
    call = captured_calls[0]
    assert call["from"] == "reports@example.com"
    assert call["to"] == ["researcher@example.com"]
    assert "Q3 Discovery Findings" in call["subject"]
    assert "<h1>" in call["html"] or "<h2>" in call["html"]
    assert "Users report delays." in call["html"]


def test_send_report_export_email_wraps_sdk_failure(monkeypatch) -> None:
    def fake_send(params):
        raise RuntimeError("Resend API returned 401")

    monkeypatch.setattr("instamart_engine.reports.email.resend.Emails.send", fake_send)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    get_settings.cache_clear()
    try:
        with pytest.raises(report_email.EmailSendError):
            report_email.send_report_export_email(
                report=_fake_report(),
                export=_fake_export(),
                rendered_content="# Title",
                recipient_email="user@example.com",
            )
    finally:
        get_settings.cache_clear()


def test_markdown_to_html_paragraphs_escapes_html() -> None:
    rendered = report_email._markdown_to_html_paragraphs("<script>alert(1)</script>")
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
