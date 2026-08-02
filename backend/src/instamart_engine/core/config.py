"""Application configuration.

Env vars mirror architecture.md §28.2 exactly so `.env.example` and this class
never drift apart. Add a new setting here and to `.env.example` in the same change.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    APP_ENV: Literal["local", "test", "staging", "production"] = "local"
    # Defaults match docker-compose.yml's non-standard host ports (5434/6381)
    # chosen to avoid colliding with other projects' containers on this
    # machine using the conventional 5432/6379. See .env.example.
    DATABASE_URL: str = "postgresql+asyncpg://instamart:instamart@localhost:5434/instamart"
    REDIS_URL: str = "redis://localhost:6381/0"

    # Raw artifact storage
    RAW_STORAGE_BACKEND: Literal["filesystem", "supabase"] = "filesystem"
    RAW_STORAGE_PATH: str = "./data/raw"
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_STORAGE_BUCKET: str | None = None

    # LLM — both providers are OpenAI-compatible (Chat Completions), reached
    # via the `openai` SDK with a swapped base_url. Groq is primary; OpenRouter
    # is an automatic failover if Groq is unavailable or exhausts its retries.
    LLM_PROVIDER: Literal["groq", "openrouter"] = "groq"
    LLM_FALLBACK_PROVIDER: Literal["groq", "openrouter"] | None = "openrouter"
    LLM_MODEL_CLASSIFICATION: str = "openai/gpt-oss-120b"
    LLM_MODEL_SYNTHESIS: str = "openai/gpt-oss-120b"
    LLM_MODEL_ANSWER: str = "openai/gpt-oss-120b"
    LLM_FALLBACK_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    # Groq's hosted Whisper endpoint (audio/transcriptions) — multilingual,
    # "best price for performance" per Groq's docs; used for Phase 1 media
    # pipeline speech-to-text (feedback/media_extraction.py).
    LLM_MODEL_TRANSCRIPTION: str = "whisper-large-v3-turbo"
    GROQ_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None

    # Embeddings
    EMBEDDING_PROVIDER: Literal["local", "hosted"] = "hosted"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    HF_API_TOKEN: str | None = None

    # Connectors
    APIFY_TOKEN: str | None = None
    REDDIT_CLIENT_ID: str | None = None
    REDDIT_CLIENT_SECRET: str | None = None
    REDDIT_USER_AGENT: str = "instamart-discovery-engine/0.1"

    # Email (report export delivery)
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str = "reports@instamart-discovery-engine.dev"

    # Operational limits
    DEFAULT_COLLECTION_LIMIT: int = 500
    MAX_COLLECTION_COST_USD: float = 25.0
    MODEL_MAX_RETRIES: int = 3
    MODEL_CONCURRENCY: int = 4

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
