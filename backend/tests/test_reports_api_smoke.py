"""Smoke test: the Report Builder endpoints respond correctly end-to-end
against the live Postgres (design.md §33) — create a report, add a section
with real evidence, export it to Markdown and JSON, and read the export
content back. Mirrors `test_validation_api_smoke.py`'s TestClient pattern
(one `with TestClient(app) as client:` block — see that file's docstring
for why the cached engine/session-factory singleton needs the reset before
entering the block).
"""

from fastapi.testclient import TestClient

import instamart_engine.core.database as database_module
from instamart_engine.api.main import app


def test_report_builder_end_to_end() -> None:
    database_module._engine = None
    database_module._session_factory = None

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/reports", json={"title": "Smoke Test Report"}
        )
        assert create_response.status_code == 201, create_response.text
        report = create_response.json()
        assert report["title"] == "Smoke Test Report"
        assert report["status"] == "draft"
        assert report["sections"] == []
        report_id = report["id"]

        list_response = client.get("/api/v1/reports")
        assert list_response.status_code == 200
        assert any(r["id"] == report_id for r in list_response.json()["reports"])

        section_response = client.post(
            f"/api/v1/reports/{report_id}/sections",
            json={
                "section_type": "executive_summary",
                "title": "Executive Summary",
                "content": {"text": "Placeholder"},
            },
        )
        assert section_response.status_code == 201, section_response.text
        section = section_response.json()
        assert section["position"] == 1
        section_id = section["id"]

        update_response = client.patch(
            f"/api/v1/reports/{report_id}/sections/{section_id}",
            json={"narrative_text": "Users repeatedly report delivery delays."},
        )
        assert update_response.status_code == 200
        updated_narrative = update_response.json()["narrative_text"]
        assert updated_narrative == "Users repeatedly report delivery delays."

        detail_response = client.get(f"/api/v1/reports/{report_id}")
        assert detail_response.status_code == 200
        assert len(detail_response.json()["sections"]) == 1

        md_export_response = client.post(
            f"/api/v1/reports/{report_id}/exports", json={"export_format": "markdown"}
        )
        assert md_export_response.status_code == 201, md_export_response.text
        md_export = md_export_response.json()
        assert md_export["status"] == "completed"
        assert "Executive Summary" in md_export["content"]
        assert "Users repeatedly report delivery delays." in md_export["content"]

        json_export_response = client.post(
            f"/api/v1/reports/{report_id}/exports", json={"export_format": "json"}
        )
        assert json_export_response.status_code == 201, json_export_response.text
        json_export = json_export_response.json()
        assert json_export["content"]["title"] == "Smoke Test Report"
        assert json_export["content"]["sections"][0]["title"] == "Executive Summary"

        get_export_response = client.get(
            f"/api/v1/reports/{report_id}/exports/{md_export['id']}"
        )
        assert get_export_response.status_code == 200
        assert get_export_response.json()["content"] == md_export["content"]

        # RESEND_API_KEY isn't configured in the test environment (and
        # never will be with a fabricated value) — 503 is the correct,
        # honest response, not a fake success. See test_reports_email.py
        # for coverage of the actual send path via a mocked Resend client.
        email_md_response = client.post(
            f"/api/v1/reports/{report_id}/exports/{md_export['id']}/email",
            json={"recipient_email": "researcher@example.com"},
        )
        assert email_md_response.status_code == 503, email_md_response.text

        email_json_response = client.post(
            f"/api/v1/reports/{report_id}/exports/{json_export['id']}/email",
            json={"recipient_email": "researcher@example.com"},
        )
        assert email_json_response.status_code == 400  # only markdown exports are emailable

        pdf_export_response = client.post(
            f"/api/v1/reports/{report_id}/exports", json={"export_format": "pdf"}
        )
        assert pdf_export_response.status_code == 400  # documented, deferred format

        delete_response = client.delete(f"/api/v1/reports/{report_id}/sections/{section_id}")
        assert delete_response.status_code == 204

        empty_detail_response = client.get(f"/api/v1/reports/{report_id}")
        assert empty_detail_response.json()["sections"] == []

        missing_response = client.get(
            "/api/v1/reports/00000000-0000-0000-0000-000000000000"
        )
        assert missing_response.status_code == 404
