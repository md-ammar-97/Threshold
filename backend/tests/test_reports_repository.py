"""Integration tests for the reporting domain repository against the live
Postgres. datamodel.md Part IX (§53-56)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from instamart_engine.analysis.models import AnalysisRun, AnalysisRunStatus
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.reports import evidence as evidence_resolver
from instamart_engine.reports import repository as report_repo
from instamart_engine.reports.models import ReportEvidenceType, ReportSectionType, ReportStatus
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel
from instamart_engine.themes import repository as theme_repo
from instamart_engine.themes.models import ThemeSet, ThemeSetStatus, ThemeType

pytestmark = pytest.mark.asyncio


async def _seed_report_dependencies(db_session):
    connector = SourceConnectorModel(
        key=f"test-reports-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    analysis_run = AnalysisRun(
        name="test-run",
        status=AnalysisRunStatus.RUNNING,
        dataset_snapshot={},
        taxonomy_version_id=uuid.uuid4(),
        classification_model_configuration_id=uuid.uuid4(),
    )
    db_session.add(analysis_run)
    await db_session.flush()

    theme_set = ThemeSet(
        analysis_run_id=analysis_run.id,
        version_number=1,
        name="test-theme-set",
        status=ThemeSetStatus.READY_FOR_REVIEW,
        clustering_algorithm="hdbscan",
        clustering_configuration={},
        eligible_record_count=1,
    )
    db_session.add(theme_set)
    await db_session.flush()

    theme = await theme_repo.create_provisional_theme(
        db_session,
        theme_set_id=theme_set.id,
        theme_key="cluster_0",
        placeholder_name="Delivery delays",
        representative_record_count=1,
    )
    theme.theme_type = ThemeType.FRUSTRATION
    theme.short_summary = "Users report delivery delays."
    await db_session.flush()

    body = "Delivery was very late again."
    artifact = RawArtifact(
        ingestion_run_id=uuid.uuid4(),
        storage_backend="filesystem",
        storage_key=f"raw/test/{uuid.uuid4()}.json",
        media_type="application/json",
        byte_size=len(body),
        sha256="0" * 64,
        captured_at=datetime.now(UTC),
    )
    db_session.add(artifact)
    await db_session.flush()

    raw_item = RawSourceItem(
        raw_artifact_id=artifact.id,
        ingestion_run_id=artifact.ingestion_run_id,
        source_connector_id=connector.id,
        external_id=str(uuid.uuid4()),
        record_type="app_review",
        body=body,
        payload_checksum="1" * 64,
    )
    db_session.add(raw_item)
    await db_session.flush()

    record = FeedbackRecord(
        raw_source_item_id=raw_item.id,
        source_connector_id=connector.id,
        record_type="app_review",
        ingested_at=datetime.now(UTC),
        published_at=datetime.now(UTC) - timedelta(days=1),
        original_text=body,
        normalized_text=body,
        redacted_text=body,
        content_hash=str(uuid.uuid4()),
        normalized_length=len(body),
        relevance_status=RelevanceStatus.UNREVIEWED,
        quality_status=QualityStatus.USABLE,
    )
    db_session.add(record)
    await db_session.flush()

    return analysis_run, theme_set, theme, record


async def test_create_report_defaults_and_get(db_session) -> None:
    analysis_run, theme_set, _theme, _record = await _seed_report_dependencies(db_session)

    report = await report_repo.create_report(
        db_session,
        title="Q3 Discovery Findings",
        analysis_run_id=analysis_run.id,
        theme_set_id=theme_set.id,
    )
    await db_session.commit()

    fetched = await report_repo.get_report(db_session, report_id=report.id)
    assert fetched is not None
    assert fetched.title == "Q3 Discovery Findings"
    assert fetched.status == ReportStatus.DRAFT


async def test_add_section_auto_increments_position(db_session) -> None:
    analysis_run, theme_set, _theme, _record = await _seed_report_dependencies(db_session)
    report = await report_repo.create_report(
        db_session, title="R", analysis_run_id=analysis_run.id, theme_set_id=theme_set.id
    )

    first = await report_repo.add_section(
        db_session,
        report_id=report.id,
        section_type=ReportSectionType.EXECUTIVE_SUMMARY,
        title="Executive Summary",
        content={},
    )
    second = await report_repo.add_section(
        db_session,
        report_id=report.id,
        section_type=ReportSectionType.KEY_THEME,
        title="Key Theme",
        content={},
    )
    await db_session.commit()

    assert first.position == 1
    assert second.position == 2


async def test_reorder_sections_avoids_unique_constraint_collision(db_session) -> None:
    analysis_run, theme_set, _theme, _record = await _seed_report_dependencies(db_session)
    report = await report_repo.create_report(
        db_session, title="R", analysis_run_id=analysis_run.id, theme_set_id=theme_set.id
    )
    a = await report_repo.add_section(
        db_session,
        report_id=report.id,
        section_type=ReportSectionType.EXECUTIVE_SUMMARY,
        title="A",
        content={},
    )
    b = await report_repo.add_section(
        db_session,
        report_id=report.id,
        section_type=ReportSectionType.KEY_THEME,
        title="B",
        content={},
    )
    c = await report_repo.add_section(
        db_session,
        report_id=report.id,
        section_type=ReportSectionType.LIMITATION,
        title="C",
        content={},
    )
    await db_session.commit()
    assert [s.position for s in (a, b, c)] == [1, 2, 3]

    reordered = await report_repo.reorder_sections(
        db_session, report_id=report.id, ordered_section_ids=[c.id, a.id, b.id]
    )
    await db_session.commit()

    by_id = {s.id: s.position for s in reordered}
    assert by_id[c.id] == 1
    assert by_id[a.id] == 2
    assert by_id[b.id] == 3


async def test_evidence_link_snapshot_and_lookup(db_session) -> None:
    analysis_run, theme_set, theme, record = await _seed_report_dependencies(db_session)
    report = await report_repo.create_report(
        db_session, title="R", analysis_run_id=analysis_run.id, theme_set_id=theme_set.id
    )
    section = await report_repo.add_section(
        db_session,
        report_id=report.id,
        section_type=ReportSectionType.KEY_THEME,
        title="Delivery delays",
        content={},
    )

    theme_snapshot = await evidence_resolver.resolve_evidence_snapshot(
        db_session, object_type=ReportEvidenceType.THEME, object_id=theme.id
    )
    assert theme_snapshot is not None
    assert theme_snapshot["name"] == theme.name

    record_snapshot = await evidence_resolver.resolve_evidence_snapshot(
        db_session, object_type=ReportEvidenceType.FEEDBACK_RECORD, object_id=record.id
    )
    assert record_snapshot is not None
    assert "Delivery was very late" in record_snapshot["excerpt"]

    link = await report_repo.add_evidence_link(
        db_session,
        report_section_id=section.id,
        object_type=ReportEvidenceType.THEME,
        object_id=theme.id,
        snapshot=theme_snapshot,
    )
    await db_session.commit()

    links = await report_repo.get_evidence_links_for_section(
        db_session, report_section_id=section.id
    )
    assert len(links) == 1
    assert links[0].id == link.id
    assert links[0].snapshot["name"] == theme.name


async def test_evidence_snapshot_returns_none_for_missing_object(db_session) -> None:
    snapshot = await evidence_resolver.resolve_evidence_snapshot(
        db_session, object_type=ReportEvidenceType.THEME, object_id=uuid.uuid4()
    )
    assert snapshot is None


async def test_update_report_status_sets_published_at(db_session) -> None:
    analysis_run, theme_set, _theme, _record = await _seed_report_dependencies(db_session)
    report = await report_repo.create_report(
        db_session, title="R", analysis_run_id=analysis_run.id, theme_set_id=theme_set.id
    )
    await db_session.commit()
    assert report.published_at is None

    await report_repo.update_report_status(db_session, report=report, status=ReportStatus.PUBLISHED)
    await db_session.commit()

    assert report.status == ReportStatus.PUBLISHED
    assert report.published_at is not None


async def test_delete_section_removes_it(db_session) -> None:
    analysis_run, theme_set, _theme, _record = await _seed_report_dependencies(db_session)
    report = await report_repo.create_report(
        db_session, title="R", analysis_run_id=analysis_run.id, theme_set_id=theme_set.id
    )
    section = await report_repo.add_section(
        db_session,
        report_id=report.id,
        section_type=ReportSectionType.APPENDIX,
        title="Appendix",
        content={},
    )
    await db_session.commit()

    await report_repo.delete_section(db_session, section=section)
    await db_session.commit()

    remaining = await report_repo.get_sections_for_report(db_session, report_id=report.id)
    assert remaining == []
