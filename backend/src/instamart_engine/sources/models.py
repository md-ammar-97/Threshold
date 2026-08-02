"""`source_connector` — registered connector types. datamodel.md §6."""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from instamart_engine.core.database import Base, UUIDPrimaryKeyMixin


class ConnectorType(enum.StrEnum):
    DIRECT_API = "direct_api"
    LIBRARY = "library"
    PLAYWRIGHT = "playwright"
    APIFY = "apify"
    RSS = "rss"
    HTTP = "http"


connector_type_enum = Enum(
    ConnectorType, name="connector_type", values_callable=lambda e: [m.value for m in e]
)


class SourceConnectorModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_connector"
    __table_args__ = (
        UniqueConstraint("key", name="uq_source_connector_key"),
        CheckConstraint(
            "default_rate_limit_per_minute IS NULL OR default_rate_limit_per_minute > 0",
            name="ck_source_connector_rate_limit_positive",
        ),
    )

    key: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    connector_type: Mapped[ConnectorType] = mapped_column(connector_type_enum, nullable=False)
    implementation_version: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    supports_incremental: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    supports_thread_context: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )
    default_rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
