"""Raw artifact storage contract. architecture.md §10.4.

Every collected response or source item is preserved in immutable raw
storage before normalization. The filesystem backend is used for local dev
(RAW_STORAGE_BACKEND=filesystem); Supabase Storage is used for hosted
environments (RAW_STORAGE_BACKEND=supabase, architecture.md §34.4). Use
`storage.factory.build_raw_artifact_storage` to select the configured
implementation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    storage_backend: str
    storage_key: str
    sha256: str
    byte_size: int


class RawArtifactStorage(Protocol):
    def save(
        self,
        *,
        source_key: str,
        ingestion_run_id: str,
        item_key: str,
        captured_at: datetime,
        content: bytes,
        content_type: str = "application/json",
        extension: str | None = None,
    ) -> StoredArtifact: ...

    def read(self, storage_key: str) -> bytes: ...

    def verify_checksum(self, storage_key: str, expected_sha256: str) -> bool: ...
