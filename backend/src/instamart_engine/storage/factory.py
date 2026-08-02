"""Selects the configured `RawArtifactStorage` implementation. architecture.md §10.4."""

from instamart_engine.core.config import Settings
from instamart_engine.storage.base import RawArtifactStorage
from instamart_engine.storage.filesystem import FilesystemRawArtifactStorage
from instamart_engine.storage.supabase import SupabaseRawArtifactStorage


def build_raw_artifact_storage(settings: Settings) -> RawArtifactStorage:
    if settings.RAW_STORAGE_BACKEND == "filesystem":
        return FilesystemRawArtifactStorage(settings.RAW_STORAGE_PATH)

    if settings.RAW_STORAGE_BACKEND == "supabase":
        if not (
            settings.SUPABASE_URL
            and settings.SUPABASE_SERVICE_ROLE_KEY
            and settings.SUPABASE_STORAGE_BUCKET
        ):
            raise RuntimeError(
                "RAW_STORAGE_BACKEND=supabase requires SUPABASE_URL, "
                "SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_STORAGE_BUCKET to be set"
            )
        return SupabaseRawArtifactStorage(
            base_url=settings.SUPABASE_URL,
            service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            bucket=settings.SUPABASE_STORAGE_BUCKET,
        )

    raise RuntimeError(f"Unsupported RAW_STORAGE_BACKEND: {settings.RAW_STORAGE_BACKEND!r}")
