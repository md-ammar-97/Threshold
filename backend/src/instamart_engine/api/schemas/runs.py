"""Response DTOs for the (minimal, read-only) runs surface. architecture.md
§20.2/§20.3 describe fuller ingestion/analysis-run management APIs; only a
unified read list is implemented here (design.md §34)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RunSummaryResponse(BaseModel):
    id: UUID
    run_type: str  # "ingestion" | "analysis"
    name: str
    status: str
    record_counts: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RunListResponse(BaseModel):
    runs: list[RunSummaryResponse]
