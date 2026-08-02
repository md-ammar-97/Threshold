"""DB access for the reporting domain. datamodel.md Part IX (§53-56)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.reports.models import (
    Report,
    ReportEvidenceLink,
    ReportEvidenceType,
    ReportExport,
    ReportExportFormat,
    ReportExportStatus,
    ReportSection,
    ReportSectionType,
    ReportStatus,
)


async def create_report(
    session: AsyncSession,
    *,
    title: str,
    analysis_run_id: UUID,
    theme_set_id: UUID,
    subtitle: str | None = None,
    insight_set_id: UUID | None = None,
    report_configuration: dict[str, Any] | None = None,
) -> Report:
    report = Report(
        title=title,
        subtitle=subtitle,
        analysis_run_id=analysis_run_id,
        theme_set_id=theme_set_id,
        insight_set_id=insight_set_id,
        report_configuration=report_configuration or {},
    )
    session.add(report)
    await session.flush()
    return report


async def get_report(session: AsyncSession, *, report_id: UUID) -> Report | None:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        return None
    return report


async def list_reports(session: AsyncSession) -> list[Report]:
    return list(
        (
            await session.scalars(
                select(Report).where(Report.deleted_at.is_(None)).order_by(Report.created_at.desc())
            )
        ).all()
    )


async def update_report_status(
    session: AsyncSession, *, report: Report, status: ReportStatus
) -> Report:
    report.status = status
    if status == ReportStatus.PUBLISHED and report.published_at is None:
        report.published_at = datetime.now()
    await session.flush()
    return report


async def get_max_section_position(session: AsyncSession, *, report_id: UUID) -> int:
    positions = await session.scalars(
        select(ReportSection.position).where(ReportSection.report_id == report_id)
    )
    values = positions.all()
    return max(values) if values else 0


async def add_section(
    session: AsyncSession,
    *,
    report_id: UUID,
    section_type: ReportSectionType,
    title: str,
    content: dict[str, Any],
    position: int | None = None,
    narrative_text: str | None = None,
) -> ReportSection:
    if position is None:
        position = await get_max_section_position(session, report_id=report_id) + 1
    section = ReportSection(
        report_id=report_id,
        section_type=section_type,
        position=position,
        title=title,
        content=content,
        narrative_text=narrative_text,
    )
    session.add(section)
    await session.flush()
    return section


async def get_section(session: AsyncSession, *, section_id: UUID) -> ReportSection | None:
    return await session.get(ReportSection, section_id)


async def get_sections_for_report(session: AsyncSession, *, report_id: UUID) -> list[ReportSection]:
    return list(
        (
            await session.scalars(
                select(ReportSection)
                .where(ReportSection.report_id == report_id)
                .order_by(ReportSection.position)
            )
        ).all()
    )


async def update_section(
    session: AsyncSession,
    *,
    section: ReportSection,
    title: str | None = None,
    content: dict[str, Any] | None = None,
    narrative_text: str | None = None,
    is_locked: bool | None = None,
) -> ReportSection:
    if title is not None:
        section.title = title
    if content is not None:
        section.content = content
    if narrative_text is not None:
        section.narrative_text = narrative_text
    if is_locked is not None:
        section.is_locked = is_locked
    await session.flush()
    return section


_REORDER_TEMP_POSITION_OFFSET = 1_000_000  # comfortably above any real section count


async def reorder_sections(
    session: AsyncSession, *, report_id: UUID, ordered_section_ids: list[UUID]
) -> list[ReportSection]:
    """Reassigns 1..N positions in the given order. Two-phase (temp
    far-out-of-range positions, then final) so the `UNIQUE(report_id,
    position)` constraint never sees a transient collision mid-reorder — a
    plain one-pass update can hit "position 2 is already taken" while
    section A is still sitting on the position section B is about to move
    into. `CHECK(position > 0)` rules out negative temp positions, hence
    the large positive offset instead."""
    sections = await get_sections_for_report(session, report_id=report_id)
    by_id = {section.id: section for section in sections}

    for offset, section_id in enumerate(ordered_section_ids, start=1):
        by_id[section_id].position = _REORDER_TEMP_POSITION_OFFSET + offset
    await session.flush()

    for position, section_id in enumerate(ordered_section_ids, start=1):
        by_id[section_id].position = position
    await session.flush()

    return await get_sections_for_report(session, report_id=report_id)


async def delete_section(session: AsyncSession, *, section: ReportSection) -> None:
    await session.delete(section)
    await session.flush()


async def add_evidence_link(
    session: AsyncSession,
    *,
    report_section_id: UUID,
    object_type: ReportEvidenceType,
    object_id: UUID,
    snapshot: dict[str, Any],
    display_order: int | None = None,
) -> ReportEvidenceLink:
    if display_order is None:
        existing = await session.scalars(
            select(ReportEvidenceLink.display_order).where(
                ReportEvidenceLink.report_section_id == report_section_id
            )
        )
        values = existing.all()
        display_order = (max(values) if values else 0) + 1
    link = ReportEvidenceLink(
        report_section_id=report_section_id,
        object_type=object_type,
        object_id=object_id,
        display_order=display_order,
        snapshot=snapshot,
    )
    session.add(link)
    await session.flush()
    return link


async def get_evidence_links_for_section(
    session: AsyncSession, *, report_section_id: UUID
) -> list[ReportEvidenceLink]:
    return list(
        (
            await session.scalars(
                select(ReportEvidenceLink)
                .where(ReportEvidenceLink.report_section_id == report_section_id)
                .order_by(ReportEvidenceLink.display_order)
            )
        ).all()
    )


async def remove_evidence_link(session: AsyncSession, *, link: ReportEvidenceLink) -> None:
    await session.delete(link)
    await session.flush()


async def create_export(
    session: AsyncSession,
    *,
    report_id: UUID,
    export_format: ReportExportFormat,
    export_configuration: dict[str, Any] | None = None,
) -> ReportExport:
    export = ReportExport(
        report_id=report_id,
        export_format=export_format,
        status=ReportExportStatus.RENDERING,
        export_configuration=export_configuration or {},
        started_at=datetime.now(),
    )
    session.add(export)
    await session.flush()
    return export


async def finalize_export(
    session: AsyncSession,
    *,
    export: ReportExport,
    status: ReportExportStatus,
    storage_backend: str | None = None,
    storage_key: str | None = None,
    sha256: str | None = None,
    byte_size: int | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> ReportExport:
    export.status = status
    export.storage_backend = storage_backend
    export.storage_key = storage_key
    export.sha256 = sha256
    export.byte_size = byte_size
    export.failure_code = failure_code
    export.failure_message = failure_message
    export.completed_at = datetime.now()
    await session.flush()
    return export


async def get_export(session: AsyncSession, *, export_id: UUID) -> ReportExport | None:
    return await session.get(ReportExport, export_id)


async def get_exports_for_report(session: AsyncSession, *, report_id: UUID) -> list[ReportExport]:
    return list(
        (
            await session.scalars(
                select(ReportExport)
                .where(ReportExport.report_id == report_id)
                .order_by(ReportExport.created_at.desc())
            )
        ).all()
    )
