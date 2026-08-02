"""Media pipeline Phase 1: OCR on images, speech-to-text on video/audio.

Runs after `process_unprocessed_items` and before `classify_unclassified_records`
(architecture.md §11 order, extended): a record with a captured `media_url`
gets its media downloaded, OCR'd or transcribed, and the resulting text
folded into `normalized_text`/`redacted_text` so the existing classification
pipeline picks it up with zero changes of its own. Phase 2 (a
vision-language model for images OCR/captions can't fully describe — damaged
products, contamination, etc.) is a deliberately separate, later addition.

Every record is processed independently and failures never abort the batch
(mirrors `analysis/classify.py`'s per-record try/except) — some source
platforms (Instagram especially) are known to block unauthenticated media
fetches.
"""

import io
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import httpx
import openai
import pytesseract
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.core.config import get_settings
from instamart_engine.core.logging import get_logger
from instamart_engine.feedback import repository as repo
from instamart_engine.feedback.language import detect_language
from instamart_engine.feedback.models import FeedbackRecord, MediaType, QualityEventSeverity
from instamart_engine.feedback.normalize import normalize_text
from instamart_engine.feedback.privacy import redact
from instamart_engine.feedback.relevance import assess_quality, assess_relevance
from instamart_engine.storage.base import RawArtifactStorage

logger = get_logger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_OCR_LANGUAGES = "eng+hin"  # matches the app's expected English/Hindi code-mixed content
_DOWNLOAD_TIMEOUT_SECONDS = 20.0
_FFMPEG_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class MediaExtractionSummary:
    selected: int
    extracted: int
    failed: int


class MediaExtractionError(Exception):
    """Raised for any recoverable per-record failure (download, OCR, demux,
    transcription) — always caught per-record, never propagates out of
    `extract_media_for_pending_records`."""


def download_media(url: str, *, timeout: float = _DOWNLOAD_TIMEOUT_SECONDS) -> bytes:
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MediaExtractionError(f"Failed to download media from {url!r}: {exc}") from exc
    return response.content


def extract_text_from_image(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image, lang=_OCR_LANGUAGES).strip()
    except Exception as exc:  # noqa: BLE001 — pytesseract/PIL raise several distinct types
        raise MediaExtractionError(f"OCR failed: {exc}") from exc


def extract_audio_track(video_bytes: bytes) -> bytes:
    """Demuxes the audio track from a video file via ffmpeg (shelled out —
    a single fixed command doesn't need a Python binding)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / "input.mp4"
        output_path = Path(tmp_dir) / "output.mp3"
        input_path.write_bytes(video_bytes)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(input_path),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    str(output_path),
                ],
                capture_output=True,
                timeout=_FFMPEG_TIMEOUT_SECONDS,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise MediaExtractionError(f"ffmpeg audio extraction failed: {exc}") from exc
        return output_path.read_bytes()


async def transcribe_audio(audio_bytes: bytes, *, filename: str = "audio.mp3") -> str:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise MediaExtractionError("GROQ_API_KEY is not configured — cannot transcribe audio")

    client = openai.AsyncOpenAI(api_key=settings.GROQ_API_KEY, base_url=_GROQ_BASE_URL)
    try:
        response = await client.audio.transcriptions.create(
            model=settings.LLM_MODEL_TRANSCRIPTION,
            file=(filename, audio_bytes),
        )
    except openai.OpenAIError as exc:
        raise MediaExtractionError(f"Groq transcription failed: {exc}") from exc
    return response.text.strip()


def _combine_text(original_text: str, extracted_media_text: str) -> str:
    if not extracted_media_text:
        return original_text
    if not original_text:
        return extracted_media_text
    return f"{original_text}\n\n[Extracted from media]\n{extracted_media_text}"


async def _process_one(
    session: AsyncSession, record: FeedbackRecord, *, storage: RawArtifactStorage
) -> None:
    assert record.media_url is not None and record.media_type is not None

    media_bytes = download_media(record.media_url)

    if record.media_type == MediaType.IMAGE:
        extracted_media_text = extract_text_from_image(media_bytes)
        content_type, extension = "image/jpeg", "jpg"
    else:
        audio_bytes = extract_audio_track(media_bytes)
        extracted_media_text = await transcribe_audio(audio_bytes)
        content_type, extension = "video/mp4", "mp4"

    combined_text = _combine_text(record.original_text or "", extracted_media_text)
    normalized = normalize_text(combined_text)
    redacted_text, redaction_events = redact(normalized)

    # Re-assess against the now-combined text — a media-only post with a
    # thin caption may have been marked LOW_INFORMATION/INSUFFICIENT_CONTENT
    # before extraction ran, which would otherwise permanently exclude it
    # from get_unclassified_feedback_records' quality_status filter.
    language_result = detect_language(normalized)
    new_relevance_status = assess_relevance(normalized)
    new_quality_status = assess_quality(
        original_text=combined_text,
        normalized_text=normalized,
        language_code=language_result.language_code,
        is_code_mixed=language_result.is_code_mixed,
        is_supported_language=language_result.is_supported,
    )

    await repo.update_feedback_record_media_extraction(
        session,
        record=record,
        extracted_media_text=extracted_media_text or "",
        normalized_text=normalized,
        redacted_text=redacted_text,
        quality_status=new_quality_status,
        relevance_status=new_relevance_status,
    )
    if redaction_events:
        await repo.insert_redaction_events(
            session, feedback_record_id=record.id, events=redaction_events
        )

    # Best-effort: preserve the downloaded media itself in raw storage,
    # same as raw_source_item's JSON artifacts, for evidence integrity.
    try:
        storage.save(
            source_key=str(record.source_connector_id),
            ingestion_run_id=str(record.raw_source_item_id),
            item_key=str(record.id),
            captured_at=record.ingested_at,
            content=media_bytes,
            content_type=content_type,
            extension=extension,
        )
    except Exception as exc:  # noqa: BLE001 — media storage is best-effort, not required for the run to count as a success
        logger.warning(
            "media_artifact_storage_failed", feedback_record_id=str(record.id), error=str(exc)
        )


async def extract_media_for_pending_records(
    session: AsyncSession,
    *,
    storage: RawArtifactStorage,
    source_connector_id: UUID | None = None,
    limit: int = 50,
) -> MediaExtractionSummary:
    records = await repo.get_feedback_records_pending_media_extraction(
        session, source_connector_id=source_connector_id, limit=limit
    )
    if not records:
        return MediaExtractionSummary(selected=0, extracted=0, failed=0)

    extracted = 0
    failed = 0

    for record in records:
        try:
            await _process_one(session, record, storage=storage)
        except MediaExtractionError as exc:
            failed += 1
            logger.warning(
                "media_extraction_failed", feedback_record_id=str(record.id), error=str(exc)
            )
            await repo.mark_feedback_record_media_extraction_failed(session, record=record)
            await repo.insert_quality_event(
                session,
                feedback_record_id=record.id,
                event_type="media_extraction_failed",
                severity=QualityEventSeverity.WARNING,
                stage="media_extraction",
                message=str(exc),
            )
            await session.commit()
            continue

        await session.commit()
        extracted += 1

    return MediaExtractionSummary(selected=len(records), extracted=extracted, failed=failed)
