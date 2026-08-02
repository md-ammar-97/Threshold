"""Embedding generation. architecture.md §14.

Supports two providers (EMBEDDING_PROVIDER in .env.example):
- `local`: runs entirely on-CPU via `sentence-transformers`, no API key.
- `hosted` (default): calls the Hugging Face Inference API's
  feature-extraction endpoint for the same model, so no local model weights
  need to be downloaded/run in the app container — useful for a thin web
  deployment. Verified to produce the same normalized 384-dim vector space
  as the local model (mean-pooling + L2 normalization), so hosted and local
  embeddings are directly comparable and neither requires re-embedding the
  other's rows.

A text checksum is part of the embedding's identity (datamodel.md §29's
unique constraint), so a changed record produces a *new* vector rather than
silently overwriting the old one (EMB-005) — history is never rewritten.
"""

import asyncio
import hashlib
from dataclasses import dataclass
from uuid import UUID

import httpx
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession

from instamart_engine.ai.exceptions import ModelUnavailableError, ProviderConfigurationError
from instamart_engine.analysis import embedding_repository as embedding_repo
from instamart_engine.analysis.embedding_models import EmbeddingConfiguration
from instamart_engine.core.config import get_settings
from instamart_engine.core.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_VERSION_KEY = "all-MiniLM-L6-v2-v1"  # local provider
EMBEDDING_VERSION_KEY_HOSTED = "all-MiniLM-L6-v2-hf-v1"
EMBEDDING_DIMENSION = 384
DEFAULT_BATCH_SIZE = 32

HF_FEATURE_EXTRACTION_URL = (
    "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
)

_model_singleton: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model_singleton
    if _model_singleton is None:
        _model_singleton = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model_singleton


def _encode_batch_local(texts: list[str]) -> list[list[float]]:
    """Runs synchronously on CPU — always called via `asyncio.to_thread`."""
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]


async def _encode_batch_hosted(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.HF_API_TOKEN:
        # research/service.py::ask_question only catches AIGatewayError (and
        # its subclasses) to mark a question FAILED gracefully — a bare
        # RuntimeError here used to bypass that entirely and surface as an
        # unhandled 500 on every hosted-embedding query-time failure.
        raise ProviderConfigurationError(
            "HF_API_TOKEN is not configured for EMBEDDING_PROVIDER=hosted"
        )

    url = HF_FEATURE_EXTRACTION_URL.format(model=settings.EMBEDDING_MODEL)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.HF_API_TOKEN}"},
                json={"inputs": texts, "options": {"wait_for_model": True}},
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            raise ProviderConfigurationError(
                f"Hugging Face Inference API auth failed ({status})"
            ) from exc
        raise ModelUnavailableError(
            f"Hugging Face Inference API request failed ({status})"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelUnavailableError(f"Hugging Face Inference API unreachable: {exc}") from exc

    vectors = response.json()
    # A single-text request can come back as one flat vector instead of a
    # one-element batch — normalize to "list of vectors" either way.
    if vectors and isinstance(vectors[0], int | float):
        return [vectors]
    return vectors


async def _encode_batch(texts: list[str], *, provider: str) -> list[list[float]]:
    if provider == "hosted":
        return await _encode_batch_hosted(texts)
    return await asyncio.to_thread(_encode_batch_local, texts)


def _version_key_for(provider: str) -> str:
    return EMBEDDING_VERSION_KEY_HOSTED if provider == "hosted" else EMBEDDING_VERSION_KEY


async def get_current_embedding_configuration(
    session: AsyncSession, *, provider: str | None = None
) -> EmbeddingConfiguration | None:
    """Read-only lookup of the embedding configuration matching the active
    provider (`settings.EMBEDDING_PROVIDER` unless overridden) — the single
    source of truth for "which embedding space is currently authoritative."
    Every consumer of stored embeddings (clustering, retrieval) must go
    through this rather than deriving the version key independently, so they
    can never silently disagree with what `embed_unembedded_records` actually
    wrote (this is what let theme discovery report success while reading zero
    embeddings under the default EMBEDDING_PROVIDER=hosted config)."""
    settings = get_settings()
    active_provider = provider or settings.EMBEDDING_PROVIDER
    version_key = _version_key_for(active_provider)
    return await embedding_repo.get_embedding_configuration_by_version_key(
        session, version_key=version_key
    )


@dataclass(frozen=True, slots=True)
class EmbeddingSummary:
    selected: int
    embedded: int


async def embed_query_text(text: str, *, provider: str | None = None) -> list[float]:
    """Embeds a single ad-hoc string (e.g. a research question) with the
    same model/normalization used for feedback records, so it is directly
    comparable via cosine distance. `provider` defaults to
    `settings.EMBEDDING_PROVIDER`; pass it explicitly to pin a provider
    (e.g. in tests that must stay offline)."""
    active_provider = provider or get_settings().EMBEDDING_PROVIDER
    vectors = await _encode_batch([text], provider=active_provider)
    return vectors[0]


async def embed_unembedded_records(
    session: AsyncSession,
    *,
    source_connector_id: UUID | None = None,
    limit: int = 500,
    batch_size: int = DEFAULT_BATCH_SIZE,
    provider: str | None = None,
) -> EmbeddingSummary:
    settings = get_settings()
    active_provider = provider or settings.EMBEDDING_PROVIDER
    version_key = _version_key_for(active_provider)

    config = await embedding_repo.get_or_create_embedding_configuration(
        session,
        version_key=version_key,
        provider=active_provider,
        model_name=settings.EMBEDDING_MODEL,
        dimension=EMBEDDING_DIMENSION,
        normalization_strategy="l2_normalize",
    )
    await session.commit()

    records = await embedding_repo.get_unembedded_feedback_records(
        session,
        embedding_configuration_id=config.id,
        source_connector_id=source_connector_id,
        limit=limit,
    )
    if not records:
        return EmbeddingSummary(selected=0, embedded=0)

    embedded = 0
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        texts = [record.normalized_text for record in batch]

        try:
            vectors = await _encode_batch(texts, provider=active_provider)
        except Exception as exc:  # noqa: BLE001 — one bad batch must not abort the whole run
            logger.warning("embedding_batch_failed", error=str(exc), batch_size=len(batch))
            continue

        for record, vector in zip(batch, vectors, strict=True):
            checksum = hashlib.sha256(record.normalized_text.encode("utf-8")).hexdigest()
            await embedding_repo.upsert_embedding(
                session,
                embedding_configuration_id=config.id,
                object_type="feedback_record",
                object_id=record.id,
                text_variant="normalized",
                text_checksum=checksum,
                vector=vector,
            )
            embedded += 1
        await session.commit()

    return EmbeddingSummary(selected=len(records), embedded=embedded)
