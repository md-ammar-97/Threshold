"""Source connector contract. architecture.md §10.1.

A connector returns source-native items without applying research
classifications — normalization, privacy, relevance, and dedup happen later
in the `feedback` pipeline (architecture.md §11).
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Protocol

RecordType = Literal[
    "app_review",
    "forum_post",
    "forum_comment",
    "social_post",
    "social_comment",
    "product_review",
    "article_passage",
    "other",
]


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """Mirrors the fields of `source_collection_config` needed to run a
    collection (datamodel.md §7)."""

    target_identifier: str
    configuration: dict[str, Any] = field(default_factory=dict)
    record_limit: int | None = None
    date_from: date | None = None
    date_to: date | None = None

    def __post_init__(self) -> None:
        # SRC-001/002 — required, non-blank target
        if not self.target_identifier or not self.target_identifier.strip():
            from instamart_engine.sources.exceptions import SourceConfigError

            raise SourceConfigError("target_identifier is required and cannot be blank")
        # SRC-006 — non-positive limit
        if self.record_limit is not None and self.record_limit <= 0:
            from instamart_engine.sources.exceptions import SourceConfigError

            raise SourceConfigError("record_limit must be positive")
        # SRC-008 — inverted date range
        if self.date_from and self.date_to and self.date_from > self.date_to:
            from instamart_engine.sources.exceptions import SourceConfigError

            raise SourceConfigError("date_from must be on or before date_to")


@dataclass(frozen=True, slots=True)
class ConnectorCheckpoint:
    """datamodel.md §11 — resumable connector state."""

    checkpoint_type: str
    checkpoint_value: dict[str, Any]
    is_terminal: bool = False


@dataclass(frozen=True, slots=True)
class CollectionRequest:
    config: SourceConfig
    checkpoint: ConnectorCheckpoint | None = None


@dataclass(frozen=True, slots=True)
class RawSourceItem:
    """One source-native record, pre-normalization. Field names mirror
    `raw_source_item` (datamodel.md §10) except `id`/`ingestion_run_id`,
    which the ingestion service assigns."""

    external_id: str
    record_type: RecordType
    body: str | None
    external_parent_id: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None
    edited_at: datetime | None = None
    title: str | None = None
    author_external_id_hash: str | None = None
    rating: float | None = None
    rating_scale_max: float | None = None
    engagement_count: int | None = None
    reply_count: int | None = None
    language_hint: str | None = None
    country_code: str | None = None
    app_version: str | None = None
    media_url: str | None = None
    media_type: Literal["image", "video"] | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)


class SourceConnector(Protocol):
    """architecture.md §10.1 connector contract."""

    source_name: str

    def validate_config(self, config: SourceConfig) -> None: ...

    def collect(self, request: CollectionRequest) -> Iterator[RawSourceItem]: ...

    def checkpoint(self) -> ConnectorCheckpoint | None: ...
