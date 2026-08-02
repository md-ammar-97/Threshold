"""Request/response DTOs for the validation workspace API. architecture.md §20.7."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationMetricResponse(BaseModel):
    metric_key: str
    dimension_key: str | None
    numeric_value: float | None
    json_value: dict[str, Any] | None
    sample_count: int
    calculation_version: str


class ReleaseGateDecisionResponse(BaseModel):
    release_profile: str
    status: str
    zero_tolerance_failures: list[str]
    metric_failures: list[str]


class EvaluationRunResponse(BaseModel):
    id: UUID
    evaluation_dataset_id: UUID
    status: str
    items_evaluated: int
    items_failed: int
    created_at: datetime
    completed_at: datetime | None
    metrics: list[EvaluationMetricResponse]
    release_gate: ReleaseGateDecisionResponse | None


class EvaluationTypeSummaryResponse(BaseModel):
    evaluation_type: str
    latest_run: EvaluationRunResponse | None


class ValidationSummaryResponse(BaseModel):
    classification: EvaluationTypeSummaryResponse
    retrieval: EvaluationTypeSummaryResponse
    theme: EvaluationTypeSummaryResponse
    grounding: EvaluationTypeSummaryResponse


class SubmitReviewRequest(BaseModel):
    object_type: str
    object_id: UUID
    decision: str
    previous_snapshot: dict[str, Any]
    edited_snapshot: dict[str, Any] | None = None
    reviewer_actor_id: UUID | None = None
    reason_code: str | None = None
    notes: str | None = Field(default=None, max_length=4000)


class ReviewDecisionResponse(BaseModel):
    id: UUID
    object_type: str
    object_id: UUID
    decision: str
    reason_code: str | None
    notes: str | None
    created_at: datetime


class ReviewQueueItemResponse(BaseModel):
    object_type: str
    object_id: UUID
    excerpt: str
    dimension_key: str
    dimension_display_name: str
    label_key: str
    label_display_name: str
    confidence: float
    previous_snapshot: dict[str, Any]
    created_at: datetime


class ReviewQueueListResponse(BaseModel):
    total_matching: int
    limit: int
    offset: int
    items: list[ReviewQueueItemResponse]
