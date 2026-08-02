"""Integration tests for embedding generation. The `local` provider tests use
the REAL local sentence-transformers model (no API key needed, no mocking)
against the live Postgres; `hosted` provider tests mock the Hugging Face
Inference API HTTP call (no network access, no API key needed) since that
path is exercised for real separately.

Tests pin `provider="local"`/`"hosted"` explicitly rather than relying on
`settings.EMBEDDING_PROVIDER` (EMBEDDING_PROVIDER=hosted in .env by default)
so this suite's behavior doesn't depend on which provider happens to be
configured.
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from instamart_engine.ai.exceptions import ModelUnavailableError, ProviderConfigurationError
from instamart_engine.analysis.embed import (
    EMBEDDING_VERSION_KEY,
    EMBEDDING_VERSION_KEY_HOSTED,
    embed_query_text,
    embed_unembedded_records,
)
from instamart_engine.analysis.embedding_models import Embedding, EmbeddingConfiguration
from instamart_engine.core.config import get_settings
from instamart_engine.feedback.models import FeedbackRecord, QualityStatus, RelevanceStatus
from instamart_engine.ingestion.models import RawArtifact, RawSourceItem
from instamart_engine.sources.models import ConnectorType, SourceConnectorModel

pytestmark = pytest.mark.asyncio


async def _seed_feedback_record(db_session, *, body: str) -> FeedbackRecord:
    connector = SourceConnectorModel(
        key=f"test-embed-{uuid.uuid4()}",
        display_name="Test",
        connector_type=ConnectorType.LIBRARY,
        implementation_version="test",
    )
    db_session.add(connector)
    await db_session.flush()

    artifact = RawArtifact(
        ingestion_run_id=uuid.uuid4(),
        storage_backend="filesystem",
        storage_key=f"raw/test/{uuid.uuid4()}.json",
        media_type="application/json",
        byte_size=len(body),
        sha256="0" * 64,
        captured_at=datetime.now(UTC),
    )
    db_session.add(artifact)
    await db_session.flush()

    raw_item = RawSourceItem(
        raw_artifact_id=artifact.id,
        ingestion_run_id=artifact.ingestion_run_id,
        source_connector_id=connector.id,
        external_id=str(uuid.uuid4()),
        record_type="app_review",
        body=body,
        payload_checksum="1" * 64,
    )
    db_session.add(raw_item)
    await db_session.flush()

    record = FeedbackRecord(
        raw_source_item_id=raw_item.id,
        source_connector_id=connector.id,
        record_type="app_review",
        ingested_at=datetime.now(UTC),
        original_text=body,
        normalized_text=body,
        redacted_text=body,
        content_hash=str(uuid.uuid4()),
        normalized_length=len(body),
        relevance_status=RelevanceStatus.UNREVIEWED,
        quality_status=QualityStatus.USABLE,
    )
    db_session.add(record)
    await db_session.flush()
    return record, connector.id


async def test_embed_unembedded_records_creates_real_vectors(db_session) -> None:
    record, connector_id = await _seed_feedback_record(
        db_session, body="The app crashed while I was trying to check out my groceries."
    )

    summary = await embed_unembedded_records(
        db_session, source_connector_id=connector_id, provider="local"
    )

    assert summary.selected == 1
    assert summary.embedded == 1

    config = await db_session.scalar(
        select(EmbeddingConfiguration).where(
            EmbeddingConfiguration.version_key == EMBEDDING_VERSION_KEY
        )
    )
    assert config is not None
    assert config.dimension == 384

    embedding_row = await db_session.scalar(
        select(Embedding).where(
            Embedding.object_id == record.id, Embedding.object_type == "feedback_record"
        )
    )
    assert embedding_row is not None
    assert len(embedding_row.embedding_vector) == 384


async def test_embed_is_idempotent(db_session) -> None:
    _record, connector_id = await _seed_feedback_record(
        db_session, body="Delivery was very fast and the packaging was great this time."
    )

    first = await embed_unembedded_records(
        db_session, source_connector_id=connector_id, provider="local"
    )
    second = await embed_unembedded_records(
        db_session, source_connector_id=connector_id, provider="local"
    )

    assert first.embedded == 1
    assert second.selected == 0  # nothing left to embed


async def test_similar_texts_have_higher_cosine_similarity_than_unrelated(db_session) -> None:
    """A loose sanity check that the real model actually produces
    semantically meaningful vectors, not just correctly-shaped ones."""
    import numpy as np

    record_a, connector_id = await _seed_feedback_record(
        db_session, body="The delivery rider was late and the order arrived cold."
    )
    record_b, _ = await _seed_feedback_record(
        db_session, body="My order was delivered late and the food had gone cold."
    )
    record_c, _ = await _seed_feedback_record(
        db_session, body="I love browsing new snack brands on this app every weekend."
    )
    # Force all three onto the same connector so one call embeds them together.
    record_b.source_connector_id = connector_id
    record_c.source_connector_id = connector_id
    await db_session.flush()

    await embed_unembedded_records(db_session, source_connector_id=connector_id, provider="local")

    config = await db_session.scalar(
        select(EmbeddingConfiguration).where(
            EmbeddingConfiguration.version_key == EMBEDDING_VERSION_KEY
        )
    )
    vectors = {}
    for record in (record_a, record_b, record_c):
        row = await db_session.scalar(
            select(Embedding).where(
                Embedding.object_id == record.id,
                Embedding.embedding_configuration_id == config.id,
            )
        )
        vectors[record.id] = np.array(row.embedding_vector)

    sim_ab = float(np.dot(vectors[record_a.id], vectors[record_b.id]))
    sim_ac = float(np.dot(vectors[record_a.id], vectors[record_c.id]))
    assert sim_ab > sim_ac


class _FakeHFResponse:
    def __init__(self, payload: list[float]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> list[float]:
        return self._payload


class _FakeHFClient:
    """Stands in for `httpx.AsyncClient` — records the request it was given
    and returns a canned feature-extraction response, no network involved."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeHFClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url, *, headers, json):
        _FakeHFClient.captured_calls.append({"url": url, "headers": headers, "json": json})
        return _FakeHFResponse([0.1] * 384)

    captured_calls: list[dict] = []


async def test_embed_unembedded_records_hosted_calls_hf_api(db_session, monkeypatch) -> None:
    record, connector_id = await _seed_feedback_record(
        db_session, body="Hosted embedding path test."
    )

    _FakeHFClient.captured_calls = []
    monkeypatch.setattr("instamart_engine.analysis.embed.httpx.AsyncClient", _FakeHFClient)
    monkeypatch.setenv("HF_API_TOKEN", "hf_test_token")
    get_settings.cache_clear()
    try:
        summary = await embed_unembedded_records(
            db_session, source_connector_id=connector_id, provider="hosted"
        )
    finally:
        get_settings.cache_clear()

    assert summary.selected == 1
    assert summary.embedded == 1
    assert len(_FakeHFClient.captured_calls) == 1
    call = _FakeHFClient.captured_calls[0]
    assert call["headers"]["Authorization"] == "Bearer hf_test_token"
    assert call["json"]["inputs"] == [record.normalized_text]

    config = await db_session.scalar(
        select(EmbeddingConfiguration).where(
            EmbeddingConfiguration.version_key == EMBEDDING_VERSION_KEY_HOSTED
        )
    )
    assert config is not None
    assert config.provider == "hosted"

    embedding_row = await db_session.scalar(
        select(Embedding).where(
            Embedding.object_id == record.id, Embedding.object_type == "feedback_record"
        )
    )
    assert embedding_row is not None
    assert len(embedding_row.embedding_vector) == 384


async def test_embed_unembedded_records_hosted_without_token_skips_batch(
    db_session, monkeypatch
) -> None:
    _record, connector_id = await _seed_feedback_record(db_session, body="No token configured.")

    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    get_settings.cache_clear()
    try:
        summary = await embed_unembedded_records(
            db_session, source_connector_id=connector_id, provider="hosted"
        )
    finally:
        get_settings.cache_clear()

    # The missing-token error is caught per-batch (a bad batch must not abort
    # the whole run) rather than raised — selected but not embedded.
    assert summary.selected == 1
    assert summary.embedded == 0


class _FakeHFErrorResponse:
    """A non-2xx response — `raise_for_status()` raises like the real thing."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        request = httpx.Request("POST", "https://router.huggingface.co/fake")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)


class _FakeHFErrorClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeHFErrorClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url, *, headers, json):
        return _FakeHFErrorResponse(503)


async def test_embed_query_text_hosted_without_token_raises_provider_configuration_error(
    monkeypatch,
) -> None:
    """Regression test: a bare RuntimeError here used to bypass
    research/service.py's `except AIGatewayError` handling entirely and
    surface as an unhandled 500 on every Ask question when the hosted
    embedding provider has no token configured — this is the "chatbot not
    working" root cause fixed in this change."""
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ProviderConfigurationError):
            await embed_query_text("why do users repeat categories?", provider="hosted")
    finally:
        get_settings.cache_clear()


async def test_embed_query_text_hosted_http_error_raises_model_unavailable_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr("instamart_engine.analysis.embed.httpx.AsyncClient", _FakeHFErrorClient)
    monkeypatch.setenv("HF_API_TOKEN", "hf_test_token")
    get_settings.cache_clear()
    try:
        with pytest.raises(ModelUnavailableError):
            await embed_query_text("why do users repeat categories?", provider="hosted")
    finally:
        get_settings.cache_clear()
