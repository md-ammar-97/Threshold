"""Smoke test: the Report Builder endpoints respond correctly end-to-end
against the live Postgres (design.md §33) — create a report, add a section
with real evidence, export it to Markdown and JSON, and read the export
content back. Mirrors `test_validation_api_smoke.py`'s TestClient pattern
(one `with TestClient(app) as client:` block — see that file's docstring
for why the cached engine/session-factory singleton needs the reset before
entering the block).

Unlike `test_validation_api_smoke.py` (which only asserts structure, since
it explicitly tolerates the shared dev DB having no data), report creation
defaults `analysis_run_id`/`theme_set_id` from the *latest* theme_set when
not given explicitly — which doesn't exist on a genuinely empty database
(e.g. a fresh CI run). So this test seeds its own minimal AnalysisRun/
ThemeSet first (committed for real, not the rolled-back `db_session`
fixture, since the TestClient's requests need to actually see it) and
passes both ids explicitly, making the test self-contained regardless of
what else is in the database.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

import instamart_engine.core.database as database_module
from instamart_engine.analysis.models import AnalysisRun, AnalysisRunStatus
from instamart_engine.api.main import app
from instamart_engine.core.config import get_settings
from instamart_engine.themes.models import ThemeSet, ThemeSetStatus


async def _seed_minimal_theme_set() -> tuple[uuid.UUID, uuid.UUID]:
    engine = create_async_engine(get_settings().DATABASE_URL)
    try:
        async with engine.begin() as connection:
            from sqlalchemy.ext.asyncio import AsyncSession

            session = AsyncSession(bind=connection, expire_on_commit=False)
            analysis_run = AnalysisRun(
                name=f"smoke-test-{uuid.uuid4()}",
                status=AnalysisRunStatus.RUNNING,
                dataset_snapshot={},
                taxonomy_version_id=uuid.uuid4(),
                classification_model_configuration_id=uuid.uuid4(),
            )
            session.add(analysis_run)
            await session.flush()

            theme_set = ThemeSet(
                analysis_run_id=analysis_run.id,
                version_number=1,
                name="smoke-test-theme-set",
                status=ThemeSetStatus.READY_FOR_REVIEW,
                clustering_algorithm="hdbscan",
                clustering_configuration={},
                eligible_record_count=0,
            )
            session.add(theme_set)
            await session.flush()
            return analysis_run.id, theme_set.id
    finally:
        await engine.dispose()


def test_report_builder_end_to_end() -> None:
    database_module._engine = None
    database_module._session_factory = None
    analysis_run_id, theme_set_id = asyncio.run(_seed_minimal_theme_set())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/reports",
            json={
                "title": "Smoke Test Report",
                "analysis_run_id": str(analysis_run_id),
                "theme_set_id": str(theme_set_id),
            },
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
