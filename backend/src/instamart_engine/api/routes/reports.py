"""Report Builder endpoints. design.md §33. Backend/DB for this domain
(`report`/`report_section`/`report_evidence_link`/`report_export`) didn't
exist at all before this — Reports was a fully unimplemented Phase 8
feature (frontend showed a static "not available yet" empty state)."""

import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.api.schemas.reports import (
    CreateExportRequest,
    CreateReportRequest,
    CreateSectionRequest,
    EmailExportRequest,
    EmailExportResponse,
    EvidenceRefRequest,
    ReorderSectionsRequest,
    ReportDetailResponse,
    ReportEvidenceLinkResponse,
    ReportExportResponse,
    ReportListResponse,
    ReportSectionResponse,
    ReportSummaryResponse,
    UpdateReportRequest,
    UpdateSectionRequest,
)
from instamart_engine.core.config import get_settings
from instamart_engine.core.database import get_db_session
from instamart_engine.reports import email as report_email
from instamart_engine.reports import evidence as evidence_resolver
from instamart_engine.reports import export as export_render
from instamart_engine.reports import repository as report_repo
from instamart_engine.reports.models import (
    Report,
    ReportEvidenceType,
    ReportExport,
    ReportExportFormat,
    ReportExportStatus,
    ReportSection,
    ReportSectionType,
    ReportStatus,
)
from instamart_engine.storage.base import RawArtifactStorage
from instamart_engine.storage.factory import build_raw_artifact_storage
from instamart_engine.themes import repository as theme_repo

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

_RENDERABLE_FORMATS = {ReportExportFormat.MARKDOWN, ReportExportFormat.JSON}


def _storage() -> RawArtifactStorage:
    return build_raw_artifact_storage(get_settings())


def _to_summary(report: Report) -> ReportSummaryResponse:
    return ReportSummaryResponse(
        id=report.id,
        title=report.title,
        subtitle=report.subtitle,
        status=report.status.value,
        analysis_run_id=report.analysis_run_id,
        theme_set_id=report.theme_set_id,
        insight_set_id=report.insight_set_id,
        created_at=report.created_at.isoformat(),
        updated_at=report.updated_at.isoformat(),
        published_at=report.published_at.isoformat() if report.published_at else None,
    )


def _to_section_response(
    section: ReportSection, evidence_links: list
) -> ReportSectionResponse:
    return ReportSectionResponse(
        id=section.id,
        section_type=section.section_type.value,
        position=section.position,
        title=section.title,
        content=section.content,
        narrative_text=section.narrative_text,
        is_locked=section.is_locked,
        evidence=[
            ReportEvidenceLinkResponse(
                id=link.id,
                object_type=link.object_type.value,
                object_id=link.object_id,
                display_order=link.display_order,
                snapshot=link.snapshot,
            )
            for link in evidence_links
        ],
    )


async def _get_report_or_404(session: AsyncSession, report_id: UUID) -> Report:
    report = await report_repo.get_report(session, report_id=report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


async def _get_section_or_404(
    session: AsyncSession, *, report_id: UUID, section_id: UUID
) -> ReportSection:
    section = await report_repo.get_section(session, section_id=section_id)
    if section is None or section.report_id != report_id:
        raise HTTPException(status_code=404, detail="report section not found")
    return section


@router.post("", response_model=ReportDetailResponse, status_code=201)
async def create_report(body: CreateReportRequest, session: DbSession) -> ReportDetailResponse:
    analysis_run_id = body.analysis_run_id
    theme_set_id = body.theme_set_id
    if analysis_run_id is None or theme_set_id is None:
        latest_theme_set = await theme_repo.get_latest_theme_set(session)
        if latest_theme_set is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No theme_set exists yet to default analysis_run_id/theme_set_id from — "
                    "pass them explicitly or run analysis first"
                ),
            )
        analysis_run_id = analysis_run_id or latest_theme_set.analysis_run_id
        theme_set_id = theme_set_id or latest_theme_set.id

    report = await report_repo.create_report(
        session,
        title=body.title,
        subtitle=body.subtitle,
        analysis_run_id=analysis_run_id,
        theme_set_id=theme_set_id,
        insight_set_id=body.insight_set_id,
    )
    await session.commit()
    return ReportDetailResponse(**_to_summary(report).model_dump(), sections=[])


@router.get("", response_model=ReportListResponse)
async def list_reports(session: DbSession) -> ReportListResponse:
    reports = await report_repo.list_reports(session)
    return ReportListResponse(reports=[_to_summary(report) for report in reports])


@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(report_id: UUID, session: DbSession) -> ReportDetailResponse:
    report = await _get_report_or_404(session, report_id)
    sections = await report_repo.get_sections_for_report(session, report_id=report.id)
    section_responses = []
    for section in sections:
        evidence_links = await report_repo.get_evidence_links_for_section(
            session, report_section_id=section.id
        )
        section_responses.append(_to_section_response(section, evidence_links))
    return ReportDetailResponse(**_to_summary(report).model_dump(), sections=section_responses)


@router.patch("/{report_id}", response_model=ReportDetailResponse)
async def update_report(
    report_id: UUID, body: UpdateReportRequest, session: DbSession
) -> ReportDetailResponse:
    report = await _get_report_or_404(session, report_id)
    if body.title is not None:
        report.title = body.title
    if body.subtitle is not None:
        report.subtitle = body.subtitle
    if body.status is not None:
        try:
            status = ReportStatus(body.status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Unknown status: {body.status}") from exc
        await report_repo.update_report_status(session, report=report, status=status)
    await session.commit()
    return await get_report(report_id, session)


@router.post("/{report_id}/sections", response_model=ReportSectionResponse, status_code=201)
async def add_section(
    report_id: UUID, body: CreateSectionRequest, session: DbSession
) -> ReportSectionResponse:
    await _get_report_or_404(session, report_id)
    try:
        section_type = ReportSectionType(body.section_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown section_type: {body.section_type}"
        ) from exc

    section = await report_repo.add_section(
        session,
        report_id=report_id,
        section_type=section_type,
        title=body.title,
        content=body.content,
        position=body.position,
        narrative_text=body.narrative_text,
    )

    evidence_links = []
    for ref in body.evidence:
        try:
            object_type = ReportEvidenceType(ref.object_type)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Unknown evidence object_type: {ref.object_type}"
            ) from exc
        snapshot = await evidence_resolver.resolve_evidence_snapshot(
            session, object_type=object_type, object_id=ref.object_id
        )
        if snapshot is None:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot link evidence — {object_type.value} {ref.object_id} not found",
            )
        evidence_links.append(
            await report_repo.add_evidence_link(
                session,
                report_section_id=section.id,
                object_type=object_type,
                object_id=ref.object_id,
                snapshot=snapshot,
            )
        )

    await session.commit()
    return _to_section_response(section, evidence_links)


@router.patch(
    "/{report_id}/sections/{section_id}", response_model=ReportSectionResponse
)
async def update_section(
    report_id: UUID, section_id: UUID, body: UpdateSectionRequest, session: DbSession
) -> ReportSectionResponse:
    section = await _get_section_or_404(session, report_id=report_id, section_id=section_id)
    if section.is_locked and (body.title is not None or body.content is not None):
        # design.md §33.4 "lock manually edited sections" — a locked
        # section's substantive content is protected; is_locked itself can
        # still be toggled (to unlock) via this same endpoint.
        raise HTTPException(
            status_code=409, detail="section is locked; unlock it before editing content"
        )
    await report_repo.update_section(
        session,
        section=section,
        title=body.title,
        content=body.content,
        narrative_text=body.narrative_text,
        is_locked=body.is_locked,
    )
    evidence_links = await report_repo.get_evidence_links_for_section(
        session, report_section_id=section.id
    )
    await session.commit()
    return _to_section_response(section, evidence_links)


@router.delete("/{report_id}/sections/{section_id}", status_code=204)
async def delete_section(report_id: UUID, section_id: UUID, session: DbSession) -> None:
    section = await _get_section_or_404(session, report_id=report_id, section_id=section_id)
    await report_repo.delete_section(session, section=section)
    await session.commit()


@router.post("/{report_id}/sections/reorder", response_model=list[ReportSectionResponse])
async def reorder_sections(
    report_id: UUID, body: ReorderSectionsRequest, session: DbSession
) -> list[ReportSectionResponse]:
    await _get_report_or_404(session, report_id)
    existing = await report_repo.get_sections_for_report(session, report_id=report_id)
    existing_ids = {section.id for section in existing}
    if set(body.section_ids) != existing_ids:
        raise HTTPException(
            status_code=400,
            detail="section_ids must be exactly the report's current section ids, reordered",
        )
    reordered = await report_repo.reorder_sections(
        session, report_id=report_id, ordered_section_ids=body.section_ids
    )
    await session.commit()
    responses = []
    for section in reordered:
        evidence_links = await report_repo.get_evidence_links_for_section(
            session, report_section_id=section.id
        )
        responses.append(_to_section_response(section, evidence_links))
    return responses


@router.post(
    "/{report_id}/sections/{section_id}/evidence",
    response_model=ReportEvidenceLinkResponse,
    status_code=201,
)
async def add_evidence(
    report_id: UUID,
    section_id: UUID,
    body: EvidenceRefRequest,
    session: DbSession,
) -> ReportEvidenceLinkResponse:
    await _get_section_or_404(session, report_id=report_id, section_id=section_id)
    try:
        object_type = ReportEvidenceType(body.object_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown evidence object_type: {body.object_type}"
        ) from exc

    snapshot = await evidence_resolver.resolve_evidence_snapshot(
        session, object_type=object_type, object_id=body.object_id
    )
    if snapshot is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot link evidence — {object_type.value} {body.object_id} not found",
        )
    link = await report_repo.add_evidence_link(
        session,
        report_section_id=section_id,
        object_type=object_type,
        object_id=body.object_id,
        snapshot=snapshot,
    )
    await session.commit()
    return ReportEvidenceLinkResponse(
        id=link.id,
        object_type=link.object_type.value,
        object_id=link.object_id,
        display_order=link.display_order,
        snapshot=link.snapshot,
    )


@router.delete(
    "/{report_id}/sections/{section_id}/evidence/{link_id}", status_code=204
)
async def remove_evidence(
    report_id: UUID, section_id: UUID, link_id: UUID, session: DbSession
) -> None:
    await _get_section_or_404(session, report_id=report_id, section_id=section_id)
    links = await report_repo.get_evidence_links_for_section(session, report_section_id=section_id)
    link = next((link for link in links if link.id == link_id), None)
    if link is None:
        raise HTTPException(status_code=404, detail="evidence link not found")
    await report_repo.remove_evidence_link(session, link=link)
    await session.commit()


@router.post("/{report_id}/exports", response_model=ReportExportResponse, status_code=201)
async def create_export(
    report_id: UUID, body: CreateExportRequest, session: DbSession
) -> ReportExportResponse:
    report = await _get_report_or_404(session, report_id)
    try:
        export_format = ReportExportFormat(body.export_format)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown export_format: {body.export_format}"
        ) from exc
    if export_format not in _RENDERABLE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"{export_format.value} export isn't supported yet (markdown/json only)",
        )

    sections = await report_repo.get_sections_for_report(session, report_id=report.id)
    evidence_by_section = {
        section.id: await report_repo.get_evidence_links_for_section(
            session, report_section_id=section.id
        )
        for section in sections
    }

    export = await report_repo.create_export(
        session, report_id=report.id, export_format=export_format
    )
    await session.commit()

    try:
        if export_format == ReportExportFormat.MARKDOWN:
            rendered = export_render.render_markdown(report, sections, evidence_by_section)
            content_bytes = rendered.encode("utf-8")
            extension = "md"
        else:
            rendered_json = export_render.render_json(report, sections, evidence_by_section)
            content_bytes = json.dumps(rendered_json, indent=2).encode("utf-8")
            extension = "json"

        stored = _storage().save(
            source_key="reports",
            ingestion_run_id=str(report.id),
            item_key=str(export.id),
            captured_at=datetime.now(UTC),
            content=content_bytes,
            content_type="application/json" if extension == "json" else "text/markdown",
            extension=extension,
        )
        await report_repo.finalize_export(
            session,
            export=export,
            status=ReportExportStatus.COMPLETED,
            storage_backend=stored.storage_backend,
            storage_key=stored.storage_key,
            sha256=stored.sha256,
            byte_size=stored.byte_size,
        )
    except Exception as exc:  # noqa: BLE001 — a bad render must still record a failed export, not crash
        await report_repo.finalize_export(
            session,
            export=export,
            status=ReportExportStatus.FAILED,
            failure_code=type(exc).__name__,
            failure_message=str(exc),
        )
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    await session.commit()
    return await get_export(report_id, export.id, session)


@router.get("/{report_id}/exports", response_model=list[ReportExportResponse])
async def list_exports(report_id: UUID, session: DbSession) -> list[ReportExportResponse]:
    await _get_report_or_404(session, report_id)
    exports = await report_repo.get_exports_for_report(session, report_id=report_id)
    return [await _to_export_response(export) for export in exports]


@router.get("/{report_id}/exports/{export_id}", response_model=ReportExportResponse)
async def get_export(report_id: UUID, export_id: UUID, session: DbSession) -> ReportExportResponse:
    await _get_report_or_404(session, report_id)
    export = await report_repo.get_export(session, export_id=export_id)
    if export is None or export.report_id != report_id:
        raise HTTPException(status_code=404, detail="export not found")
    return await _to_export_response(export)


@router.post(
    "/{report_id}/exports/{export_id}/email",
    response_model=EmailExportResponse,
)
async def email_export(
    report_id: UUID, export_id: UUID, body: EmailExportRequest, session: DbSession
) -> EmailExportResponse:
    report = await _get_report_or_404(session, report_id)
    export = await report_repo.get_export(session, export_id=export_id)
    if export is None or export.report_id != report_id:
        raise HTTPException(status_code=404, detail="export not found")
    if export.status != ReportExportStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="export has not completed successfully")
    if export.export_format != ReportExportFormat.MARKDOWN:
        raise HTTPException(
            status_code=400, detail="only markdown exports can be emailed today"
        )

    # A COMPLETED export always has a storage_key — finalize_export() only
    # leaves it None on the failure path, guarded against above.
    assert export.storage_key is not None
    rendered_content = _storage().read(export.storage_key).decode("utf-8")
    try:
        message_id = report_email.send_report_export_email(
            report=report,
            export=export,
            rendered_content=rendered_content,
            recipient_email=body.recipient_email,
        )
    except report_email.EmailNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except report_email.EmailSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return EmailExportResponse(message_id=message_id, recipient_email=body.recipient_email)


async def _to_export_response(export: ReportExport) -> ReportExportResponse:
    content: str | dict | None = None
    if export.status == ReportExportStatus.COMPLETED and export.storage_key:
        raw = _storage().read(export.storage_key)
        if export.export_format == ReportExportFormat.JSON:
            content = json.loads(raw)
        else:
            content = raw.decode("utf-8")
    return ReportExportResponse(
        id=export.id,
        report_id=export.report_id,
        export_format=export.export_format.value,
        status=export.status.value,
        sha256=export.sha256,
        byte_size=export.byte_size,
        failure_code=export.failure_code,
        failure_message=export.failure_message,
        created_at=export.created_at.isoformat(),
        completed_at=export.completed_at.isoformat() if export.completed_at else None,
        content=content,
    )
