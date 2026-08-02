"""Minimal read-only runs endpoint for the Phase 7 Runs surface (design.md
§34), unifying ingestion_run and analysis_run into one list. architecture.md
§20.2/§20.3 describe fuller per-domain run management APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.analysis.models import AnalysisRun
from instamart_engine.api.schemas.runs import RunListResponse, RunSummaryResponse
from instamart_engine.core.database import get_db_session
from instamart_engine.ingestion.models import IngestionRun

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
DEFAULT_LIMIT = 25


def _ingestion_to_summary(run: IngestionRun) -> RunSummaryResponse:
    return RunSummaryResponse(
        id=run.id,
        run_type="ingestion",
        name=f"Ingestion {run.id.hex[:8]}",
        status=run.status.value,
        record_counts=f"{run.records_stored} stored / {run.records_discovered} discovered",
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


def _analysis_to_summary(run: AnalysisRun) -> RunSummaryResponse:
    return RunSummaryResponse(
        id=run.id,
        run_type="analysis",
        name=run.name,
        status=run.status.value,
        record_counts=f"{run.records_classified} classified / {run.records_selected} selected",
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


@router.get("", response_model=RunListResponse)
async def list_runs(
    session: DbSession, limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=100)
) -> RunListResponse:
    ingestion_runs = (
        await session.scalars(
            select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(limit)
        )
    ).all()
    analysis_runs = (
        await session.scalars(
            select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit)
        )
    ).all()

    combined = [_ingestion_to_summary(r) for r in ingestion_runs] + [
        _analysis_to_summary(r) for r in analysis_runs
    ]
    combined.sort(key=lambda r: r.created_at, reverse=True)

    return RunListResponse(runs=combined[:limit])
