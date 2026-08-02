"""extensions and shared operational tables

Migration order step 1 of datamodel.md §80: PostgreSQL extensions and the
shared enums/tables (job_run, audit_event, cost_ledger_entry) that every
later phase's migrations log into.

Revision ID: b454289024bc
Revises:
Create Date: 2026-07-20 02:18:32.294525

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b454289024bc"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # datamodel.md §3.1 — required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # create_type=False: the type is created explicitly below via .create().
    # Without this, op.create_table() would try to CREATE TYPE a second time
    # when it encounters these columns and fail with DuplicateObjectError.
    actor_type = postgresql.ENUM(
        "user", "system", "worker", "administrator", name="actor_type", create_type=False
    )
    postgresql.ENUM(
        "user", "system", "worker", "administrator", name="actor_type"
    ).create(op.get_bind(), checkfirst=True)

    job_status = postgresql.ENUM(
        "created",
        "queued",
        "running",
        "retrying",
        "partially_completed",
        "completed",
        "failed",
        "cancelled",
        "dead_lettered",
        name="job_status",
        create_type=False,
    )
    postgresql.ENUM(
        "created",
        "queued",
        "running",
        "retrying",
        "partially_completed",
        "completed",
        "failed",
        "cancelled",
        "dead_lettered",
        name="job_status",
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "job_run",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("queue_name", sa.Text(), nullable=False),
        sa.Column("parent_job_run_id", sa.Uuid(), nullable=True),
        sa.Column("business_object_type", sa.Text(), nullable=True),
        sa.Column("business_object_id", sa.Uuid(), nullable=True),
        sa.Column("status", job_status, nullable=False, server_default="created"),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("progress_current", sa.Integer(), nullable=True),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("progress_message", sa.Text(), nullable=True),
        sa.Column(
            "input_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "result_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("attempt_number > 0", name="ck_job_run_attempt_positive"),
        sa.CheckConstraint(
            "progress_current IS NULL OR progress_current >= 0",
            name="ck_job_run_progress_current_nonneg",
        ),
        sa.CheckConstraint(
            "progress_total IS NULL OR progress_total >= 0",
            name="ck_job_run_progress_total_nonneg",
        ),
        sa.CheckConstraint(
            "progress_current IS NULL OR progress_total IS NULL "
            "OR progress_current <= progress_total",
            name="ck_job_run_progress_current_le_total",
        ),
    )

    op.create_table(
        "audit_event",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=True),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "cost_ledger_entry",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("service_type", sa.Text(), nullable=False),
        sa.Column("business_object_type", sa.Text(), nullable=True),
        sa.Column("business_object_id", sa.Uuid(), nullable=True),
        sa.Column("model_call_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(14, 6), nullable=False),
        sa.Column("actual_cost_usd", sa.Numeric(14, 6), nullable=True),
        sa.Column("pricing_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "estimated_cost_usd >= 0", name="ck_cost_ledger_estimated_nonneg"
        ),
        sa.CheckConstraint(
            "actual_cost_usd IS NULL OR actual_cost_usd >= 0",
            name="ck_cost_ledger_actual_nonneg",
        ),
    )

    op.create_index(
        "idx_job_run_status_created", "job_run", ["status", "created_at"]
    )
    op.create_index(
        "idx_cost_ledger_business_object",
        "cost_ledger_entry",
        ["business_object_type", "business_object_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_cost_ledger_business_object", table_name="cost_ledger_entry")
    op.drop_index("idx_job_run_status_created", table_name="job_run")
    op.drop_table("cost_ledger_entry")
    op.drop_table("audit_event")
    op.drop_table("job_run")

    postgresql.ENUM(name="job_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="actor_type").drop(op.get_bind(), checkfirst=True)

    op.execute("DROP EXTENSION IF EXISTS citext")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
