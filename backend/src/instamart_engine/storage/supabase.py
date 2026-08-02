"""Supabase Storage-backed raw artifact storage (RAW_STORAGE_BACKEND=supabase).

Talks to Supabase Storage's own REST API (not the S3-compatible protocol) —
this only requires the project's `service_role` secret key, with no separate
S3 access-key pair to provision. Key pattern and checksum-on-write behavior
mirror `storage.filesystem.FilesystemRawArtifactStorage` exactly (RAW-006,
RAW-011); see that module's docstring for the rationale.
"""

import hashlib
from datetime import datetime

import httpx

MAX_ARTIFACT_BYTES = 10 * 1024 * 1024  # RAW-006 — matches the storage bucket's file_size_limit
MAX_MEDIA_ARTIFACT_BYTES = 50 * 1024 * 1024  # images/short video clips need more headroom


class RawArtifactStorageError(Exception):
    """Raised on upload failure, checksum mismatch, or oversized content."""


class SupabaseRawArtifactStorage:
    """Implements `instamart_engine.storage.base.RawArtifactStorage`."""

    def __init__(
        self, *, base_url: str, service_role_key: str, bucket: str, timeout: float = 30.0
    ) -> None:
        self._bucket = bucket
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/storage/v1",
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "apikey": service_role_key,
            },
            timeout=timeout,
        )

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
        sha256 = hashlib.sha256(content).hexdigest()

        response = self._client.post(
            f"/object/{self._bucket}/{storage_key}",
            content=content,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        if response.status_code not in (200, 201):
            raise RawArtifactStorageError(
                f"Supabase Storage upload failed for {storage_key!r}: "
                f"{response.status_code} {response.text}"
            )

        # RAW-003 — verify immediately after write rather than trusting the API call.
        if not self.verify_checksum(storage_key, sha256):
            try:
                self._client.delete(f"/object/{self._bucket}/{storage_key}")
            except httpx.HTTPError:
                pass  # best-effort cleanup — the mismatch itself is the reportable error
            raise RawArtifactStorageError(
                f"Checksum mismatch immediately after uploading {storage_key!r}; artifact discarded"
            )

        return StoredArtifact(
            storage_backend="supabase",
            storage_key=storage_key,
            sha256=sha256,
            byte_size=len(content),
        )

    def read(self, storage_key: str) -> bytes:
        response = self._client.get(f"/object/{self._bucket}/{storage_key}")
        response.raise_for_status()
        return response.content

    def verify_checksum(self, storage_key: str, expected_sha256: str) -> bool:
        try:
            content = self.read(storage_key)
        except httpx.HTTPStatusError:
            return False
        return hashlib.sha256(content).hexdigest() == expected_sha256
