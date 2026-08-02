"""Cross-cutting operational models: audit_event and cost_ledger_entry.

See datamodel.md §58 (`audit_event`) and §59 (`cost_ledger_entry`). `job_run`
lives in `instamart_engine.runs.models` since it is a per-job concept rather
than a cross-cutting one.
"""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class ActorType(enum.StrEnum):
    """datamodel.md §58 — actor_type enum."""

    USER = "user"
    SYSTEM = "system"
    WORKER = "worker"
    ADMINISTRATOR = "administrator"


actor_type_enum = Enum(ActorType, name="actor_type", values_callable=lambda e: [m.value for m in e])


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only record of important user/system/administrative actions.

    datamodel.md §58. Never updated or deleted; retained with anonymized
    target identifiers per the hard-deletion policy in datamodel.md §76.
    """

    __tablename__ = "audit_event"

    actor_type: Mapped[ActorType] = mapped_column(actor_type_enum, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_id: Mapped[UUID | None] = mapped_column(nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    before_snapshot: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    after_snapshot: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    audit_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class CostLedgerEntry(UUIDPrimaryKeyMixin, Base):
    """Estimated/actual provider and collection cost. datamodel.md §59."""

    __tablename__ = "cost_ledger_entry"
    __table_args__ = (
        CheckConstraint("estimated_cost_usd >= 0", name="ck_cost_ledger_estimated_nonneg"),
        CheckConstraint(
            "actual_cost_usd IS NULL OR actual_cost_usd >= 0",
            name="ck_cost_ledger_actual_nonneg",
        ),
    )

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    service_type: Mapped[str] = mapped_column(Text, nullable=False)
    business_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_object_id: Mapped[UUID | None] = mapped_column(nullable=True)
    model_call_id: Mapped[UUID | None] = mapped_column(nullable=True)
    ingestion_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_cost_usd: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False)
    actual_cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 6), nullable=True)
    pricing_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
