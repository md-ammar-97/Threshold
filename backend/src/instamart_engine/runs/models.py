"""`job_run` — the common operational record for Celery jobs. datamodel.md §57."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class JobStatus(enum.StrEnum):
    """datamodel.md §57 — job_status enum. Mirrors the ingestion/analysis run
    lifecycle in architecture.md §9.3 plus a terminal `dead_lettered` state."""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


job_status_enum = Enum(JobStatus, name="job_status", values_callable=lambda e: [m.value for m in e])


class JobRun(UUIDPrimaryKeyMixin, Base):
    """One execution attempt of one Celery task, across every queue."""

    __tablename__ = "job_run"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_job_run_attempt_positive"),
        CheckConstraint(
            "progress_current IS NULL OR progress_current >= 0",
            name="ck_job_run_progress_current_nonneg",
        ),
        CheckConstraint(
            "progress_total IS NULL OR progress_total >= 0",
            name="ck_job_run_progress_total_nonneg",
        ),
        CheckConstraint(
            "progress_current IS NULL OR progress_total IS NULL "
            "OR progress_current <= progress_total",
            name="ck_job_run_progress_current_le_total",
        ),
    )

    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    queue_name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_job_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    business_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_object_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, nullable=False, server_default=JobStatus.CREATED.value
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    progress_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    result_summary: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
