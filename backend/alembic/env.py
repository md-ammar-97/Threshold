import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Import every domain module's models here so Base.metadata sees all tables
# before autogenerate runs. Add a line per module as each phase adds models.
from instamart_engine.ai.models import (  # noqa: E402,F401
    ModelCall,
    ModelConfiguration,
    PromptTemplate,
    PromptVersion,
)
from instamart_engine.analysis.embedding_models import (  # noqa: E402,F401
    Embedding,
    EmbeddingConfiguration,
)
from instamart_engine.analysis.models import (  # noqa: E402,F401
    AnalysisEvidenceSpan,
    AnalysisLabel,
    AnalysisRun,
    FeedbackAnalysis,
)
from instamart_engine.core.config import get_settings  # noqa: E402
from instamart_engine.core.database import Base  # noqa: E402
from instamart_engine.core.models import AuditEvent, CostLedgerEntry  # noqa: E402,F401
from instamart_engine.feedback.models import (  # noqa: E402,F401
    FeedbackDuplicateLink,
    FeedbackQualityEvent,
    FeedbackRecord,
    FeedbackRedaction,
    FeedbackThreadRelation,
)
from instamart_engine.ingestion.models import (  # noqa: E402,F401
    ConnectorCheckpointModel,
    IngestionRun,
    RawArtifact,
    RawSourceItem,
    SourceCollectionConfig,
)
from instamart_engine.insights.models import (  # noqa: E402,F401
    Insight,
    InsightEvidence,
    InsightSet,
    InsightTheme,
)
from instamart_engine.reports.models import (  # noqa: E402,F401
    Report,
    ReportEvidenceLink,
    ReportExport,
    ReportSection,
)
from instamart_engine.research.models import (  # noqa: E402,F401
    AnswerCitation,
    AnswerFinding,
    AnswerWarning,
    GeneratedAnswer,
    QueryPlan,
    ResearchQuestion,
    ResearchSession,
    RetrievalResult,
)
from instamart_engine.runs.models import JobRun  # noqa: E402,F401
from instamart_engine.sources.models import SourceConnectorModel  # noqa: E402,F401
from instamart_engine.taxonomy.models import (  # noqa: E402,F401
    TaxonomyDimension,
    TaxonomyLabel,
    TaxonomyVersion,
)
from instamart_engine.themes.models import (  # noqa: E402,F401
    ScoringProfile,
    Theme,
    ThemeMembership,
    ThemeMetric,
    ThemeSet,
)
from instamart_engine.validation.models import (  # noqa: E402,F401
    Annotation,
    EvaluationDataset,
    EvaluationDatasetItem,
    EvaluationMetric,
    EvaluationRun,
    ReviewDecision,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
# `set_main_option` stores the value via `configparser`, which treats `%` as
# its own interpolation syntax (`%(name)s`) — a literal `%` in the URL (e.g.
# a URL-encoded special character in the DB password, like `%40` for `@`)
# must be escaped to `%%` here or `configparser` raises `ValueError: invalid
# interpolation syntax` when the value is set, before any DB connection is
# even attempted.
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL.replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
