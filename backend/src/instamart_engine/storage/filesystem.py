"""Filesystem-backed raw artifact storage (RAW_STORAGE_BACKEND=filesystem).

Key pattern per architecture.md §10.4:
    raw/{source}/{yyyy}/{mm}/{dd}/{ingestion_run_id}/{source_item_id}.json

RAW-011 — the raw `item_key` (typically a source-native external_id, which
may contain arbitrary characters supplied by a third-party site) is never
used directly as a path component; it is hashed first.
"""

import hashlib
from datetime import datetime
from pathlib import Path

MAX_ARTIFACT_BYTES = 10 * 1024 * 1024  # RAW-006 — 10MB per item is generous for text feedback
MAX_MEDIA_ARTIFACT_BYTES = 50 * 1024 * 1024  # images/short video clips need more headroom


class RawArtifactStorageError(Exception):
    """Raised on write failure, checksum mismatch, or oversized content."""


class FilesystemRawArtifactStorage:
    """Implements `instamart_engine.storage.base.RawArtifactStorage`."""

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)

    def _safe_item_filename(self, item_key: str, extension: str = "json") -> str:
        digest = hashlib.sha256(item_key.encode("utf-8")).hexdigest()
        return f"{digest}.{extension}"

    def _key_for(
        self,
        source_key: str,
        ingestion_run_id: str,
        item_key: str,
        captured_at: datetime,
        extension: str = "json",
    ) -> str:
        # source_key/ingestion_run_id are our own UUIDs/slugs, not attacker
        # controlled, but we still avoid path separators defensively.
        safe_source = source_key.replace("/", "_").replace("\\", "_")
        safe_run = ingestion_run_id.replace("/", "_").replace("\\", "_")
        return "/".join(
            [
                "raw",
                safe_source,
                f"{captured_at.year:04d}",
                f"{captured_at.month:02d}",
                f"{captured_at.day:02d}",
                safe_run,
                self._safe_item_filename(item_key, extension),
            ]
        )

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
    ):
        from instamart_engine.storage.base import StoredArtifact

        max_bytes = (
            MAX_ARTIFACT_BYTES if content_type == "application/json" else MAX_MEDIA_ARTIFACT_BYTES
        )
        if len(content) > max_bytes:
            raise RawArtifactStorageError(
                f"Artifact for {item_key!r} is {len(content)} bytes, "
                f"exceeding the {max_bytes}-byte limit (RAW-006)"
            )

        resolved_extension = extension or "json"
        storage_key = self._key_for(
            source_key, ingestion_run_id, item_key, captured_at, resolved_extension
        )
        full_path = self._root / storage_key
        full_path.parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256(content).hexdigest()

        tmp_path = full_path.with_suffix(full_path.suffix + ".tmp")
        tmp_path.write_bytes(content)
        tmp_path.replace(full_path)  # atomic on same filesystem — avoids partial writes

        # RAW-003 — verify immediately after write rather than trusting the OS call.
        written = full_path.read_bytes()
        if hashlib.sha256(written).hexdigest() != sha256:
            full_path.unlink(missing_ok=True)
            raise RawArtifactStorageError(
                f"Checksum mismatch immediately after writing {storage_key!r}; artifact discarded"
            )

        return StoredArtifact(
            storage_backend="filesystem",
            storage_key=storage_key,
            sha256=sha256,
            byte_size=len(content),
        )

    def read(self, storage_key: str) -> bytes:
        return (self._root / storage_key).read_bytes()

    def verify_checksum(self, storage_key: str, expected_sha256: str) -> bool:
        try:
            content = self.read(storage_key)
        except FileNotFoundError:
            return False
        return hashlib.sha256(content).hexdigest() == expected_sha256
