# Implementation Plan: Instamart Discovery Engine

## 1. Purpose

This document turns `problemstatement.md`, `context.md`, `architecture.md`, `datamodel.md`, `design.md`, `edgecases.md`, and `ai_evals.md` into one ordered, executable build sequence.

It does not redefine anything those documents already specify. Each task below points back to the section that governs it. When implementation details and this plan disagree, the referenced source document wins — update this plan, not the other way around.

## 2. Source Document Roles

| Document | Answers |
|---|---|
| `problemstatement.md` | What was asked for |
| `context.md` | What we're actually building, MVP scope, phased plan (§18), assumptions (§20) |
| `architecture.md` | Services, data flow, APIs, deployment, implementation sequence (§31) |
| `datamodel.md` | Entities, constraints, lineage, migration order (§80) |
| `design.md` | Tokens, components, product surfaces, states |
| `edgecases.md` | Failure/partial/adversarial behaviour, by stable ID |
| `ai_evals.md` | Evaluation suites, gold datasets, release gates |

This plan reconciles `context.md §18` (6 phases) and `architecture.md §31` (7 stages) into 11 phases (0–10) that also fold in data-model migrations, design-system work, edge-case coverage, and evaluation gates per phase, so no phase is "done" without its evidence, UI states, and quality bar in place together.

---

## 3. Guiding Principles Carried Into Every Phase

- Raw evidence is immutable; nothing overwrites it (`datamodel.md §2.1`).
- No LLM output is authoritative for counts, demographics, or citations (`architecture.md §3.2`).
- Every derived artifact (label, theme, insight, answer) traces back to stored evidence (`architecture.md §3.1`).
- A phase is not complete just because the happy path works — its P0/P1 edge cases and evaluation gate must pass too (`edgecases.md §3`, `ai_evals.md §2.6`).
- Prompts, taxonomy, embeddings, and scoring are versioned; reruns create new versions, never overwrite history (`datamodel.md §2.3–2.4`).

---

## 4. Milestone Overview

| Phase | Goal | Primary Gate |
|---|---|---|
| 0 | Repo, infra, and CI run locally | `docker compose up` is healthy; clean-DB migration succeeds |
| 1 | Ingest and canonicalize evidence from ≥2 sources | `architecture.md §32` items 2–3 |
| 2 | Classify evidence against the research taxonomy | Classification gold-set gates (`ai_evals.md §13.3, §14.4`) |
| 3 | Discover and score themes | Theme coherence ≥ 4/5 median (`ai_evals.md §30.1`) |
| 4 | Synthesize evidence-linked insights | Zero insight hard failures (`ai_evals.md §33`) |
| 5 | Answer research questions via grounded RAG | Citation precision ≥ 0.97, numeric accuracy 100% (`ai_evals.md §42`) |
| 6 | Stand up the evaluation/validation product surface | `ai_evals.md §87` DoD |
| 7 | Build the Vite + React design system and product surfaces | `design.md §63` DoD |
| 8 | Report builder and export | `edgecases.md` RPT-*/EXP-* P0/P1 handled |
| 9 | Security, reliability, observability hardening | `edgecases.md §58` DoD |
| 10 | Demo-ready end-to-end product | All five documents' DoD sections pass simultaneously |

---

## 5. Phase 0 — Repository, Environment, and CI

**Sources:** `architecture.md §2, §6.1, §28, §29`; `datamodel.md §3.1, §80`

Tasks:
- [x] Initialize repository using the structure in `architecture.md §29` (authoritative — see `docs/README.md`).
- [x] Write `docker-compose.yml`: `frontend`, `api`, `worker`, `redis`, `postgres` (`architecture.md §6.1`). `worker-ai` deferred — not needed until AI job volume justifies a dedicated queue worker.
- [x] Enable PostgreSQL extensions: `pgcrypto`, `vector`, `pg_trgm`, `citext` (`datamodel.md §3.1`) — in migration `b454289024bc`.
- [x] Set up Alembic (async template); first migration = extensions + shared enums (`datamodel.md §80` step 1).
- [x] Create `.env.example` with placeholders only, matching `architecture.md §28.2`.
- [x] Stand up `job_run`, `audit_event`, `cost_ledger_entry` early (`datamodel.md §57–59`) — every later phase logs into these.
- [x] CI skeleton: lint, type-check, test, migration check, build (`architecture.md §2` table) — `.github/workflows/ci.yml`.
- [x] Health check for API (`/health`, checks Postgres + Redis, degrades rather than crashing). Worker/Postgres/Redis health covered via Docker healthchecks and the CI service containers.

**Exit criteria:** clean-database migration succeeds; all containers report healthy; CI pipeline runs (even with near-empty test suite).

**Status (2026-07-20):** Backend (FastAPI + SQLAlchemy async + Alembic + Celery) and frontend (Next.js 16 App Router + Tailwind v4) scaffolds are built and verified locally — `pytest`, `ruff`, `mypy`, `tsc --noEmit`, `eslint`, and `next build` all pass; `docker compose config` validates. **Not yet verified:** `docker compose up` end-to-end and `alembic upgrade head` against a live Postgres — Docker Desktop's engine was not running in the dev environment this was built in. The CI workflow runs the migration against a real Postgres service container on every push, so that gap closes on first push to a remote.

---

## 6. Phase 1 — Ingestion Foundation

**Sources:** `context.md §10, §18 Phase 1`; `architecture.md §10, §11, §31 Stage 2`; `datamodel.md Parts I–II`; `edgecases.md Parts I–II`

Tasks:
- [x] Implement `SourceConnector` protocol (`architecture.md §10.1`).
- [x] Build Google Play connector; build one of Reddit or public-web connector (`context.md §10`) — built public-web (Reddit deferred, needs Apify/PRAW credentials neither of which are available yet; connector protocol is ready for it).
- [x] Migrate: `source_connector`, `source_collection_config`, `ingestion_run`, `raw_artifact`, `raw_source_item`, `connector_checkpoint` (`datamodel.md Part I`).
- [x] Immutable raw storage with the `raw/{source}/{yyyy}/{mm}/{dd}/{run}/{item}.json` key pattern (`architecture.md §10.4`) — filesystem backend; S3 backend deferred per architecture.md §34.4.
- [x] Normalization pipeline: schema validation → normalization → language detection → PII redaction → relevance/spam filter → exact + near dedup (`architecture.md §11`) — relevance/spam and near-dup are deterministic-rule-only for Phase 1, as specified; the Phase 2 LLM classifier refines `unreviewed` records, and Phase 3's embeddings give semantic (not just lexical) near-dup.
- [x] Migrate: `feedback_record`, `feedback_thread_relation`, `feedback_duplicate_link`, `feedback_redaction`, `feedback_quality_event` (`datamodel.md Part II`).
- [x] Implement P0/P1 edge cases: `SRC-001/002/006/008/012/013` (config validation, SSRF), `ING-001…006/012/013` (connector failure taxonomy, challenge detection), `CHK-009` (terminal-checkpoint short-circuit), `REC-002/003/007/012` (upsert-latest, missing rating scale, URL-only content), `RAW-001/003/006/011` (checksum verify, size cap, path sanitization), `NRM-001/008/009/012`, `PII-001/002/003` (email/phone/UPI redaction). Remaining listed IDs (Apify-specific, Playwright-specific, distributed-lock CHK-008, full address/person-name redaction) are deferred with the connectors/infra they depend on.

**Exit criteria:** `context.md §19` items 1–3; `architecture.md §32` items 2–3; P0 rows in the tables above pass automated tests.

**Status (2026-07-20):** Fully verified against a live Postgres + real network calls, not just mocked tests — `alembic upgrade head`/`downgrade`/re-`upgrade` roundtrips cleanly; 61 backend tests pass (`ruff`, `mypy`, `pytest`) including DB-integration tests using a SAVEPOINT-rollback fixture (`tests/conftest.py`) so they're safe to run against the shared dev database. `scripts/ingest.py` ran for real: 60 distinct Swiggy Google Play reviews collected across two paginated runs (confirms checkpoint resume works, not just single-page fetches), and a real public page through the web connector (confirms trafilatura extraction and SSRF/error-handling work against live traffic, including a real 403 handled cleanly). One real bug caught and fixed only because a live DB was used: an `ON CONFLICT DO UPDATE` upsert against the mapped ORM class silently left stale data in the session's identity map — fixed by operating on the Core `Table` instead (see `ingestion/repository.py`). A second real bug caught: `quality_status` mislabelled short reviews (e.g. "good") as `unsupported_language` instead of `low_information` because language detection was skipped (not confirmed) for short text — fixed in `feedback/relevance.py`.

---

## 7. Phase 2 — Classification and Taxonomy

**Sources:** `context.md §12–13 Step 2, §18 Phase 2`; `architecture.md §12–13, §31 Stage 3`; `datamodel.md Parts III–IV`; `edgecases.md Part III`; `ai_evals.md Part III`

Tasks:
- [x] Migrate: `taxonomy_version`, `taxonomy_dimension`, `taxonomy_label`, `prompt_template`, `prompt_version`, `model_configuration`, `model_call` (`datamodel.md Part III`) — plus `analysis_run` (also Part III), which this plan's task list had grouped with Part IV but actually belongs here.
- [x] Define taxonomy v1 from `context.md §12` (journey stages, behavioural drivers, exploration barriers, frustration families, unmet-need families) — 5 dimensions, 68 labels, loaded via `taxonomy/seed_v1.py`, verified in the live DB.
- [x] Build the AI gateway (`architecture.md §12`): provider abstraction, structured-output validation with bounded repair, model-call audit logging — `ai/gateway.py`, using Anthropic's native `messages.parse(output_format=...)` structured-output API rather than manual tool-use JSON extraction (a newer SDK capability that made this simpler and more reliable than architecture.md anticipated).
- [x] Write and version the classification prompt; enforce "rely only on supplied text, no demographic inference" (`context.md §13 Step 2`) — `prompts/classification/v1_{system,user}.md`; demographic-inference backstop in `analysis/demographic_guard.py` (CLS-017).
- [x] Migrate: `feedback_analysis`, `analysis_label`, `analysis_evidence_span` (`datamodel.md Part IV`).
- [x] Implement edge cases: `TAX-001/007` (taxonomy-version-scoped labels enforced structurally via a dynamically-built Pydantic schema, not just at persistence time), `AISEC-001/004/005/008` (untrusted-content delimiting, tested adversarially), `MOD-001/002/003/004/007/012` (transient retry, invalid-output repair retry, provider-config guard), `CLS-004/006/013/017` (no forced labels, evidence-span rejection, pre-filtered classifiable records, demographic-inference backstop). Remaining IDs (e.g. MOD-006 refusal handling, CLS-002/003/005 nuanced label interactions) are lower-priority and deferred to real-traffic observation once a live API key is in use.
- [ ] Build Classification Gold Set v1 — 300 records per `ai_evals.md §77` distribution. **Not done — see status note below; this needs real human annotators per `ai_evals.md §7`, which is beyond what this session can produce authentically.**
- [ ] Run relevance, taxonomy, sentiment, severity, and evidence-span evaluation suites (`ai_evals.md §13–19`) against release gates. **Not done for the same reason — deferred to Phase 6, when the evaluation-framework tables/UI exist and real gold annotation can happen.**

**Exit criteria:** `architecture.md §32` item 5; classification release gates in `ai_evals.md §13.3, §14.4, §15, §16, §17` all pass on the blind test.

**Status (2026-07-20):** Data model, migrations, taxonomy content, AI gateway, and classification service are built and verified against the live Postgres with 68 passing tests (unit + DB-integration + a mocked-Anthropic-client gateway suite covering success, invalid-output repair, rate-limit backoff, non-retryable-error, and exhausted-retry paths). **Real Claude API calls were not exercised — no `ANTHROPIC_API_KEY` is configured in this environment.** `scripts/classify.py` was run for real against the CLI and fails cleanly with a clear `ProviderConfigurationError` rather than attempting a call or crashing, confirming the MOD-012 guard works. Once a key is added to `.env`, running `python scripts/classify.py --limit 20 --source-key google_play` against the 60 already-ingested real Swiggy reviews is the natural next verification step.
The 300-record Classification Gold Set and the ai_evals.md release-gate suites are explicitly **not** built: `ai_evals.md §7` requires independent human annotators, adjudication, and blind-test isolation — an AI agent hand-labeling its own gold set would not be a genuine quality bar, it would be circular. That work is deferred to Phase 6 (when the evaluation-framework tables/workspace exist) and requires human involvement regardless of which phase it happens in.

---

## 8. Phase 3 — Embeddings and Theme Discovery

**Sources:** `context.md §13 Step 3, §18 Phase 3`; `architecture.md §14–15, §31 Stage 4`; `datamodel.md Parts V–VI`; `edgecases.md Parts IV–V §21–24`; `ai_evals.md Part IV, Part VI`

Tasks:
- [x] Migrate: `embedding_configuration`, `embedding` (`datamodel.md Part V`).
- [x] Generate embeddings for normalized feedback text; version by configuration + text checksum (`architecture.md §14`) — `analysis/embed.py`, using `sentence-transformers/all-MiniLM-L6-v2` locally (`EMBEDDING_PROVIDER=local`). This runs with **no API key** — a genuinely useful decoupling from Phase 2/5's Claude dependency.
- [x] Migrate: `theme_set`, `theme`, `theme_membership`, `theme_metric`, `scoring_profile` (`datamodel.md Part VI`) — `theme.opportunity_score`/`score_components` populated and kept in sync with `theme_metric` by `themes/metrics.py`.
- [x] Implement clustering workflow (`architecture.md §15.2`): cluster (HDBSCAN via scikit-learn) → provisional membership → representative + contradictory evidence selection → LLM naming/summarization → publish versioned theme set. Coherence is computed deterministically (mean membership similarity) in `themes/metrics.py`; the human coherence *rubric* (ai_evals.md §29) is not run — see status note.
- [x] Implement edge cases: `EMB-002/005/006/012` (dimension mismatch guard via fixed column width, checksum-versioned re-embedding, upsert idempotency, immutable config per run), `THM-001/002` (no eligible records / too-few-records fallback — both tested), `THM-008` (a theme is never created without representative evidence), `MET-001` (zero-denominator guards throughout `metrics.py`). Remaining IDs (Apify/Playwright-adjacent, THM-006 semantic-duplicate merge detection, full MET-* set) are deferred — most assume a larger dataset or a validation UI (Phase 6/7) to act on.
- [ ] Build Theme Review Set v1 (`ai_evals.md §79`); run theme membership metrics and the human coherence rubric (`ai_evals.md §27–31`). **Not done — same reasoning as Phase 2's gold set: this requires a genuine human reviewer, not a self-assessment.**

**Exit criteria:** `architecture.md §32` items 6–7; median human coherence ≥ 4.0/5 and ≥ 75% of themes score ≥ 4 (`ai_evals.md §30.1`).

**Status (2026-07-20):** Fully verified against the live Postgres — 78 passing tests, including a *real* (non-mocked) embedding test asserting that semantically similar texts score higher cosine similarity than unrelated ones, and a real HDBSCAN clustering test on synthetic vectors that correctly separates two obvious clusters plus outliers. **`scripts/analyze.py` was run for real** against the 60 already-ingested Swiggy reviews: 36 were eligible (others filtered as low-information/unsupported-language by Phase 1's pipeline), producing 3 real clusters (23 clustered, 13 outliers) with deterministic opportunity scores. Inspecting the actual representative evidence honestly: one cluster is a coherent complaint pattern (poor food/service quality), one is dominated by near-duplicate one-word "good" reviews (lexically tight but not a substantive research theme), and one is a mixed bag of positive and negative short reviews — a real, unflattering demonstration of a general-purpose small embedding model's limited signal on very short texts at small dataset scale, not a claim that clustering is production-quality yet. Theme naming/summarization (the LLM step) is built and tested with a mocked client but not run for real — no `ANTHROPIC_API_KEY` configured, consistent with Phase 2's gap.
A second real bug was caught by testing against the live DB (not by mocks): SQLAlchemy's `JSONB` column type silently serializes Python `None` as the JSON literal `'null'` rather than SQL `NULL` unless `none_as_null=True` is set — this broke `theme_metric`'s "exactly one value" CHECK constraint. Fixed there and proactively across every other nullable JSONB column in the codebase (`ai.models`, `core.models`, `ingestion.models`) before it could cause a silent `IS NULL` query bug in a later phase.

---

## 9. Phase 4 — Insight Synthesis and Opportunity Scoring

**Sources:** `context.md §13 Step 5, §14, §18 Phase 3`; `architecture.md §16, §31 Stage 4`; `datamodel.md Part VI cont.`; `edgecases.md §25`; `ai_evals.md Part VII`

Tasks:
- [x] Migrate: `insight_set`, `insight`, `insight_theme`, `insight_evidence` (`datamodel.md Part VI`) — 5 new enum types (`insight_set_status`, `insight_type`, `confidence_level`, `insight_theme_relationship`, `evidence_role`), `review_status` reused via `postgresql.ENUM(..., create_type=False)`.
- [x] Implement insight generation flow: deterministic theme metrics + evidence candidates → LLM structured synthesis; counts always come from the database, never the model (`architecture.md §16.2`) — `insights/synthesize.py`, one insight per theme, evidence cited by excerpt number (not model-supplied IDs, sidestepping INS-016 by construction) and resolved back to real `feedback_record` offsets.
- [x] Implement the deterministic opportunity-scoring service (`architecture.md §16.4`, `context.md §14`): frequency, severity, recency, source breadth, confidence, discovery relevance, actionability — components always visible. Implemented as a **snapshot** of the theme's already-computed Phase 3 score (`theme.opportunity_score`/`score_components`) copied onto the insight, rather than a second, parallel scoring formula — this is what `datamodel.md §64` ("a deterministic score snapshot when an opportunity score is displayed") actually asks for, and avoids two formulas drifting apart.
- [x] Enforce publishability rule: an insight needs ≥1 evidence relationship, a validation recommendation if it's a hypothesis, and a score snapshot if scored (`datamodel.md §64`) — `insights/publishability.py`, checked at the service layer (not the DB layer, per `insights/models.py`'s docstring), so a draft insight can exist before it clears these rules.
- [x] Implement edge cases: `INS-001` (a theme with no representative evidence is skipped rather than generating a guaranteed-unpublishable insight; also re-checked at the publishability layer), `INS-002` (`insights/causal_guard.py` — a narrow deterministic phrase detector mirroring `demographic_guard`, matching `ai_evals.md §33`'s "causal phrase detector" grader; logs a warning rather than silently passing causal language through, since blocking would need actual rewriting the pipeline can't do), `INS-003` (reuses `analysis.demographic_guard` to redact unsafe text plus an explicit prompt instruction against inventing segments), `INS-004`/`INS-015` (opportunity score and components are always the Phase 3 snapshot — the model is never asked to produce a count or score), `INS-010` (`validation_recommendation` required for `product_hypothesis`, enforced by `publishability.py`, not silently defaulted), `INS-016` (a citation to an excerpt number that wasn't offered is logged and dropped, never stored), `INS-018` (a run with any per-theme failure or skipped theme is finalized as `draft`, not `ready_for_review`, so a partial batch is never mistaken for a complete one). Remaining IDs (`INS-005/006/007/008/009/011/012/013/014/017/019/020`) assume a review/report UI or Phase 5's research-answer generation that doesn't exist yet — deferred, same reasoning as Phase 2/3's deferred IDs.
- [ ] Build Insight Review Set v1 (`ai_evals.md §80`); run the insight rubric and hard-failure checks (`ai_evals.md §32–34`). **Not done — same reasoning as Phase 2/3's gold/review sets: requires genuine human reviewers.**

**Exit criteria:** `architecture.md §32` item 8; zero insight hard failures (`ai_evals.md §33`); evidence-support pass rate ≥ 0.95 (`ai_evals.md §34.1`).

**Status (2026-07-21):** Migration verified against the live Postgres with a full upgrade → downgrade -1 → re-upgrade roundtrip, then confirmed table/constraint/enum existence via `psql`. 91 passing tests total (13 new: 5 live-DB integration tests for `generate_insights_for_theme_set` against a mocked Anthropic client, 3 `causal_guard` unit tests, 5 `publishability` unit tests). **Real Claude API calls were not exercised — no `ANTHROPIC_API_KEY` is configured**, consistent with Phases 2/3: `scripts/analyze.py --source-key google_play --synthesize --generate-insights` was run for real against the 60 already-ingested Swiggy reviews (Phase 3's same 3 real clusters) and failed cleanly with `ProviderConfigurationError`, confirming the MOD-012 guard still holds for this new call site. To verify the real (non-mocked-away) code paths end-to-end, `generate_insights_for_theme_set` was then run directly against that same real, live `theme_set` with a mocked Anthropic client: all 3 real themes produced an insight (2 `synthesized_insight`, 1 `product_hypothesis`, 0 failed), all 3 published (0 blocked) — each with a correctly-resolved evidence citation into real `feedback_record` text (start/end offsets found, not guessed), `opportunity_score` matching Phase 3's metrics output exactly (51.64 / 57.54 / 59.18), and the `product_hypothesis` insight carrying a `validation_recommendation` while the two `synthesized_insight` rows correctly did not need one. Once a key is added to `.env`, this same command is the natural next real-verification step.
The 60-insight Insight Review Set and the `ai_evals.md §32–34` rubric/hard-failure checks are explicitly **not** built, for the same reason Phase 2's Classification Gold Set and Phase 3's Theme Review Set weren't: genuine human adjudication, deferred to Phase 6.

---

## 10. Phase 5 — Research Workspace (Grounded RAG)

**Sources:** `context.md §13 Step 6, §18 Phase 4`; `architecture.md §17, §20.6, §31 Stage 5`; `datamodel.md Part VII`; `edgecases.md Part VI`; `ai_evals.md Part V, Part VIII`

Tasks:
- [x] Migrate: `research_session`, `research_question`, `query_plan`, `retrieval_result`, `generated_answer`, `answer_finding`, `answer_citation`, `answer_warning` (`datamodel.md Part VII`) — 8 new enum types; `review_status`/`insight_type`/`confidence_level`/`evidence_role`/`quality_event_severity` reused across domains via `postgresql.ENUM(..., create_type=False)`.
- [x] Implement query planning: parse question into research dimension, filters, intent (`explain/count/compare/rank/find_examples/summarize/validate_hypothesis`) (`architecture.md §17.2`) — `research/planner.py` (LLM structured output) + `research/query_filters.py` (the deterministic backstop that actually decides `effective_filters`; the model's raw output is stored too, so a rejected filter stays auditable).
- [x] Implement hybrid retrieval: exact filters → themes/insights → hybrid record search → reranking → source-diversity balancing → contradiction retrieval → context-size control (`architecture.md §17.3`) — `research/retrieval.py`: structured filters (source/date/taxonomy) → top themes/insights by `opportunity_score` → pgvector cosine similarity + Postgres full-text search (reusing the real `idx_embedding_vector_hnsw`/`idx_feedback_record_fts` indexes from Phases 1/3) → weighted rerank → per-source-connector diversity cap → forced-include of a known counterexample if one exists → hard caps on themes/insights/records. Every candidate considered is persisted to `retrieval_result`, advancing through `retrieval_stage`.
- [x] Implement grounded answer generation with citation labels sourced only from the evidence package (`architecture.md §17.4–17.5`) — `research/generate.py` + `research/grounding.py`: the model cites server-assigned labels (`E1`, `T1`, `I1`, mirroring Phase 4's excerpt-number pattern) that are resolved against the exact evidence package built moments earlier in the same request; an unresolvable label is dropped, not stored (structurally prevents CIT-001). `citation_count`/`warning_count`/knowledge-type counts on `generated_answer` are always recomputed from the actual persisted rows, never trusted from the model's own output (ANS-024).
- [x] Implement SSE streaming (`answer.started/delta/citation.added/warning.added/completed/failed`) with the persisted answer as authoritative (`architecture.md §17.6`) — **partially real**: `GET /api/v1/research/questions/{id}/events` emits the correct event *shape* and treats the persisted answer as authoritative, but replays already-completed state rather than live token-by-token deltas, because the AI gateway's `messages.parse` call is not itself a token stream (a genuine gap, not hidden — noted in the route's docstring; revisit once the gateway supports real streaming or this needs to serve a live UI).
- [x] Build `/api/v1/research/*` endpoints (`architecture.md §20.6`) — `POST /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/questions`, `GET /questions/{id}`, `GET /questions/{id}/events`. These are the **first product routes** added under `/api/v1`, closing the gap Phase 0's `api/main.py` docstring explicitly left open.
- [x] Implement edge cases: `QRY-010/011/018` (invalid/demographic filter rejection, requested-vs-effective filter tracking), `ANS-001/004/006/019/024` (insufficient-evidence early exit with no LLM call, unsupported-finding marking, citation object existence via same-request resolution, demographic-inference hard rejection, recomputed counts), `CIT-001/002` (citations structurally can't point to a wrong object; labels are answer-scoped via the finding they belong to). **A real `ANS-017`-class cross-version-contamination bug was caught by testing against the live DB, not by mocks**: hybrid record retrieval wasn't originally scoped to the research session's own `analysis_run`, so a supposedly "empty-evidence" test session was actually retrieving unrelated real records left over from earlier phases' runs. Fixed by always joining `feedback_analysis` on `analysis_run_id` in the hybrid query, re-verified with both a genuinely empty session (0 records) and the full pipeline (correct records only). Remaining IDs (`QRY-001-009/012-017`, most of `ANS-002/003/007-018/020-023`, `SSE-001-012` except the shape already covered, `CIT-003-015`) assume a frontend/reconnecting client, a query-plan gold set, or human review workflow that doesn't exist yet — deferred, same reasoning as prior phases.
- [ ] Build Retrieval Gold Set v1 (60 questions, `ai_evals.md §78`) and Grounded Answer Set v1 (60 answers, `ai_evals.md §81`); run query-plan, retrieval, citation, numeric, and insufficient-evidence evaluations (`ai_evals.md §22–42`). **Not done — same reasoning as every prior phase's gold/review set: requires genuine human annotators.**

**Exit criteria:** `architecture.md §32` items 9–10; citation precision ≥ 0.97, citation coverage 1.00, exact numeric accuracy 1.00 (`ai_evals.md §42`); correct abstention ≥ 0.90 (`ai_evals.md §39`).

**Status (2026-07-21):** Migration verified against the live Postgres with a full upgrade → downgrade -1 → re-upgrade roundtrip. 105 passing tests total (14 new: 5 query-filter unit tests, 6 grounding-validation unit tests, 2 live-DB integration tests for the full `ask_question` pipeline with a mocked Anthropic client — one of which is what caught the cross-version-contamination bug above — plus 1 fix to an existing Phase 4 test whose unscoped query was incidentally exposed by new real data). **Real Claude API calls were not exercised — no `ANTHROPIC_API_KEY` is configured**: `scripts/ask.py --session-id <uuid> --question "..."` was run for real against a genuinely real research session and failed cleanly with `ProviderConfigurationError`, confirming the MOD-012 guard extends correctly to the two new LLM call sites (planning, answer generation).
To verify the real, non-mocked-away code paths end-to-end — including the analysis_run-scoping fix — a one-off script built one **correctly-linked** single-`analysis_run` pipeline from the 60 real, already-ingested Google Play reviews: real classification attempt (mocked model output, incidentally malformed against the schema, so all 10 records legitimately failed and were recorded `FAILED` — a bug in the throwaway mock, not in production code, and it didn't block anything downstream since embedding/clustering don't depend on classification succeeding), real embedding, real HDBSCAN clustering (10 themes from 36 eligible records), mocked theme synthesis, mocked insight generation (10/10 published), then a real research session asking a real question against that data with mocked planning/answer-generation calls: the retrieval genuinely ran pgvector cosine similarity + Postgres full-text search against real record text, correctly scoped to that one `analysis_run`, and produced a `passed`-grounding answer with 2 correctly-resolved citations. `/health` plus all 5 research routes were confirmed registered via the FastAPI app's own OpenAPI schema.
The 60-question Retrieval Gold Set and 60-answer Grounded Answer Set, and the `ai_evals.md §22–42` release-gate suites, are explicitly **not** built, for the same reason every prior phase's gold set wasn't: genuine human adjudication, deferred to Phase 6.

---

## 11. Phase 6 — Validation Framework and Workspace

**Sources:** `context.md §15, §18 Phase 5`; `architecture.md §18, §20.7, §31 Stage 6`; `datamodel.md Part VII (validation)`; `edgecases.md §30–31`; `ai_evals.md Parts I–II, XII`

Tasks:
- [x] Migrate: `evaluation_dataset`, `evaluation_dataset_item`, `annotation`, `evaluation_run`, `evaluation_metric`, `review_decision` (`datamodel.md Part VII`) — 5 new enum types; `review_status` reused via `postgresql.ENUM(..., create_type=False)`.
- [x] Implement the grader hierarchy in order: schema/integrity → gold comparison → rule-based semantic checks → human rubric → LLM judge (`ai_evals.md §11`) — `validation/graders/{base,schema,citations,privacy,grounding}.py` implement tiers 1 and 3 (the deterministic ones): `SchemaIntegrityGrader`, `CitationIntegrityGrader` (fabricated-citation + count-mismatch + coverage, reusing the excerpt-number-not-model-ID resolution pattern from Phase 4/5), `DemographicInferenceGrader`/`CausalOverclaimGrader` (reusing `demographic_guard`/`causal_guard` as regression checks, not duplicate controls), `InsufficientEvidencePolicyGrader`. Tier 2 (gold comparison) is implemented generically via `validation/annotations.py`'s adjudication lookup, ready for a grader once a gold dataset exists. Tiers 4–5 (human rubric, LLM judge) need a review-workspace UI and a calibrated judge prompt (`ai_evals.md §12.4`) that don't exist yet — deferred, same reasoning as every prior phase's human-dependent gap.
- [x] Implement release-gate configuration as versioned YAML with zero-tolerance categories (`ai_evals.md §85`) — `validation/release_gates.py` + `backend/config/release_gates/mvp-v1.yaml`, matching §85's exact schema (`release_profile`/`zero_tolerance`/`metrics`) with metric keys that are actually computed today rather than placeholders nothing populates; decision logic follows §51 exactly (any zero-tolerance failure → `fail`, otherwise a metric miss → `pass_with_conditions`, otherwise `pass`).
- [x] Separate development / validation / blind-test dataset partitions; prevent blind-test leakage into prompts (`ai_evals.md §6.1`) — stored in `evaluation_dataset.selection_method` (`{"partition": ...}`) rather than a new enum column, per `ai_evals.md §82`'s explicit instruction not to proliferate enums prematurely; `validation/datasets.is_blind_test()` is the check a future prompt-builder must call before pulling item text into a template.
- [x] Support two-annotator + adjudication workflow (`ai_evals.md §7`) — `validation/annotations.py`: independent round-1/round-2 annotations are preserved (never overwritten) for agreement calculation, and `adjudicate()` inserts a new, separately-flagged (`is_adjudicated`) annotation as the item's gold output rather than mutating an existing row.
- [x] Build `/api/v1/validation/*` endpoints (`architecture.md §20.7`) — `GET /summary`, `/classification`, `/retrieval`, `/themes`, `/grounding` (each returns the latest `evaluation_run` for that type plus its metrics and a live release-gate decision), `POST /reviews`.
- [x] Implement edge cases: `EVAL-001` (empty dataset blocks the run — `EmptyDatasetError`), `EVAL-003` (locked dataset rejects new items — `DatasetLockedError`), `EVAL-005` (a dataset item pointing at a deleted/nonexistent object is excluded and counted as a run failure, not silently skipped), `EVAL-006` (no adjudicated annotation → `get_gold_output()` returns `None`, never a guessed label), `EVAL-007` (a grader with zero results for a run isn't recorded, avoiding a metric with an undefined denominator), `EVAL-009` (one bad item is caught and counted, never aborts the whole run — `COMPLETED_WITH_WARNINGS`), `REV-004` (reject/needs-second-review decisions require `reason_code` — `ReviewReasonRequiredError`), `REV-005` (an `analysis_label` edit is checked against the live published taxonomy — `InvalidTaxonomyLabelError`), `REV-006` (`review_decision` is insert-only and requires a real `previous_snapshot` — `MissingPreviousSnapshotError` — so a review can never destructively overwrite the object it's reviewing). Remaining IDs (`EVAL-002/004/008/010-012`, most of `REV-*`) assume a review-workspace UI, concurrent-editor session semantics, or a gold dataset that doesn't exist yet — deferred, same reasoning as every prior phase.
- [x] Wire P0 adversarial suite into CI (`ai_evals.md §62`) — a `p0_adversarial` pytest marker (registered in `pyproject.toml`) tags the safety-critical deterministic tests (prompt-injection delimiting, demographic-inference detection, causal-overclaim detection, fabricated-citation detection — 13 tests total), and `.github/workflows/ci.yml` runs `pytest -q -m p0_adversarial` as its own fast, always-blocking step before the full suite.

**Exit criteria:** `ai_evals.md §87` items 1–21 (framework-level DoD, ahead of the full-product DoD in Phase 10).

**Status (2026-07-21):** Migration verified against the live Postgres with a full upgrade → downgrade -1 → re-upgrade roundtrip. 161 passing tests total (28 new: 12 grader unit tests, 7 release-gate unit tests, 7 dataset/annotation/review-rule integration tests, 2 live-DB evaluation-runner integration tests — one of which deliberately seeds a real `feedback_record`/`theme` plus one genuinely fabricated citation UUID to prove `CitationIntegrityGrader`'s existence check runs a real database lookup, not a mock — plus 3 API smoke tests against the live-running FastAPI app, and 1 fix to a pre-existing Phase 4 test whose module-wide-marker exposure was incidental, not a regression). `scripts/evaluate.py` was run for real: it builds a `grounding` dataset from every real `generated_answer` row already in the database (one, left over from Phase 5's real end-to-end verification run), grades it with the full deterministic chain, and reports a real `pass` release-gate decision under `mvp-v1.yaml` — every grader (schema, citation integrity, demographic inference, causal overclaim, insufficient-evidence policy) scored 1.0 against that real answer. No LLM-judge or human-rubric call was exercised — there is no calibrated judge prompt yet, and no `ANTHROPIC_API_KEY` regardless.
Discovered along the way (not a bug fix, a test-infrastructure note): Starlette's `TestClient` opens a fresh event loop per call outside a `with` block, which crashes against `core.database`'s cached asyncpg engine singleton on Windows — the same class of issue `conftest.py`'s `db_session` fixture already works around for integration tests. Fixed for the new validation API smoke test by using `with TestClient(app) as client:` and resetting the cached singleton first; pre-existing `test_health.py` was not touched since it only ever makes one request per test.
The two-annotator agreement metrics (Cohen's kappa etc., `ai_evals.md §7.5`), the classification/retrieval/theme graders and their candidate-output resolvers (only `generated_answer`/grounding-type items have one built this phase), and the LLM-judge tier are explicitly **not** built — they require either a gold dataset that needs genuine human annotators (deferred to whenever real annotation happens, same as every prior phase's gold-set gap) or a judge-prompt calibration pass this session cannot perform without human-adjudicated examples to calibrate against (`ai_evals.md §12.4`).

---

## 12. Phase 7 — Frontend Design System and Product Surfaces (Vite + React)

**Sources:** `context.md §16, §18 Phase 6`; `architecture.md §7, §31 Stage 7`; `design.md` (all parts); `edgecases.md Part VIII`

Tasks:
- [x] Build tokens before components: primitives → semantic color (light/dark) → spacing/shape/typography/elevation/motion/data-viz (`design.md Part I`) — `styles/tokens.css` (full neutral/orange/green/blue/violet/status primitive scales + light/dark semantic layer + an OS-preference media-query fallback, matching design.md §7 exactly), `styles/typography.css` (the complete 13-step type scale as utility classes), `components/motion/motion-tokens.ts` (durations/easings/springs, design.md §38/§53). `globals.css` maps the semantic tokens into Tailwind v4's `@theme inline` so both `var(--color-*)` and Tailwind utilities stay in sync from one source.
- [x] Build components bottom-up: Tier 0 foundations → Tier 1 controls → Tier 2 navigation/overlays → Tier 3 product data components → Tier 4 composites (`design.md §18`) — Tier 0/1 built in full (`components/ui/`: Icon, Spinner, Skeleton, Badge, StatusDot, Divider, Tooltip, Kbd, Button, IconButton, Input, Textarea, Tabs). Tier 2: Sidebar item (inline in the app shell), Drawer (Radix Dialog + Framer Motion `forceMount`/`AnimatePresence`, the documented pattern for animating a Radix primitive). Tier 3 (`components/research/`, a project-specific location alongside `ui`/`layout`/`motion` since these are shared across every feature, not owned by one): KnowledgeTypeBadge, ConfidenceIndicator, CitationChip, WarningBanner, SourceBadge, EvidenceExcerpt, EvidenceCard, MetricCard, ThemeCard, RunStatusCard, RunStageStepper, ValidationMetricCard. **Not built**: Combobox/multi-select/date-range/slider/pagination (Tier 1), DropdownMenu/ContextMenu/Popover/CommandMenu/Toast (Tier 2), most Tier 4 composites (Filter toolbar, Evidence/Theme/Insight inspector panels beyond the basic Drawer, Report outline editor, Pipeline run monitor) — deferred; none of the seven surfaces below required them to be real rather than a mockup.
- [x] Build the seven primary surfaces + Methodology: Overview, Themes, Ask, Evidence, Validation, Reports, Runs (`design.md Part IV`) — all seven built and wired to real data. Ask and Validation are fully real against Phase 5/6's existing APIs. Themes, Evidence, and Runs required **new minimal read-only backend endpoints** (`GET /api/v1/themes[/{id}]`, `GET /api/v1/evidence[/{id}]`, `GET /api/v1/runs`) since architecture.md §20.2-20.5's fuller CRUD surfaces were never built in Phases 1-4 — these are read-only, list+detail only, explicitly not the full management API. Reports is an honest empty state (the `report`/`report_section`/`report_export` tables are Phase 8 scope, per this file's own next section) rather than a mockup with invented data. Overview aggregates real counts from the evidence/themes/runs endpoints; the Signal Field visualization (§27.4) and session-history/processing-health panels are deferred (no session-list or per-run-detail endpoint exists yet).
- [x] Implement every required state per surface: loading, empty, partial, stale, error, rate-limited, unavailable-source, low-confidence, reduced-motion (`architecture.md §7.5`) — loading (skeletons matching final layout, never a bare spinner), empty (explicit "no data yet" messaging per surface, not a shared illustration), error (`WarningBanner` surfacing the real `ApiError` message, which itself parses FastAPI's `{"detail": ...}` / `{"error": {...}}` contracts), and reduced-motion (`usePrefersReducedMotion` + a global `@media (prefers-reduced-motion: reduce)` CSS override, belt-and-suspenders) are real everywhere. Partial/stale/rate-limited/unavailable-source states are only as real as the backend signals available today: Validation's zero-tolerance-failure banner and Ask's unsupported-finding warning are real; a dedicated stale-analysis or rate-limited-connector banner has no backend signal yet to drive it and was not fabricated.
- [x] Implement knowledge-type distinction (observed/synthesized/hypothesis) and confidence display everywhere required (`design.md §4.3–4.4`) — `KnowledgeTypeBadge` (icon + label, never color alone, per §47.6) and `ConfidenceIndicator` (level + optional numeric + tooltip) are used on every Ask finding and every theme card.
- [x] Implement edge cases: relevant `UI-*`/`STATE-*`/`A11Y-*` items achievable without a design tool or full test suite: visible focus rings (`:focus-visible` at 2px, `--color-border-focus`), skip link, semantic nav landmarks, icon-only controls always paired with an accessible label + tooltip (`IconButton`), color-independent status (icon+label+tone on every badge/warning), 200%-zoom-safe layouts (relative units, no fixed-height clipped cards), keyboard-operable Radix primitives (Tooltip/Tabs/Dialog inherit Radix's focus-trap/Escape/arrow-key behaviour for free). **Not implemented**: `RSP-*` (responsive) beyond what Tailwind's default breakpoints give for free — no dedicated tablet/mobile layout pass was done; `VIZ-*` — no chart library was integrated (Recharts was scoped but no surface in this pass needed a chart over the metric cards already built). A full `UI-001…012`/`STATE-001…012`/`A11Y-001…018` audit requires the design QA checklist (design.md §58-59) run by a human or a dedicated accessibility-testing pass, not a one-shot session.
- [ ] Verify WCAG 2.2 AA, keyboard, and reduced-motion behaviour (`design.md Part VIII`) — verified by code review (semantic HTML, focus-visible styling, aria-labels on icon buttons, `role="status"`/`role="alert"` on warnings, `aria-live="polite"` on the evidence result count) and by confirming every page returns 200 with no error overlay and correct server-rendered titles/nav. **Not verified**: an actual contrast-ratio measurement, a screen-reader pass, or interactive click-through/keyboard-tab testing — this session's environment has no browser-automation tool (no Playwright/Puppeteer/Chrome DevTools MCP configured), so verification stopped at HTTP-level checks and real API calls via curl, not a rendered, interactive browser. This is a real gap, not a claimed pass — a follow-up session with browser tooling (or a human) should do the interactive/visual QA pass before calling this DoD-complete.

**Exit criteria:** `design.md §63` DoD items 1–20. Items 1-6, 8 (partial — pointer only, not verified keyboard), 10, 14, 16 (partial — desktop verified, tablet/mobile not), and 17 (Reports now built — see Phase 8 below, though its own edge-case/evaluation tasks remain open) are met; items 7 (Ask streams synchronously, not token-by-token — see Phase 5's status note), 9 (no chart library wired), 12-13 (not independently verified, see above), 19 are not yet met.

**Status (2026-07-21):** Built for real against the live backend: `styles/tokens.css`/`typography.css`/`globals.css` implement design.md's complete token system (not the Phase 0 abbreviated skeleton); ~40 new components across `components/{ui,motion,research,layout}`; three new minimal FastAPI read routers (`themes`, `evidence`, `runs` — 5 endpoints, all tested for real with curl against the live database: themes returns 10 real themes with real opportunity scores from Phase 4/5/6's actual runs, evidence returns 61 real Google Play reviews, runs returns the real ingestion/analysis run history across every phase); a typed TanStack Query API client (`lib/api/`); and all seven surfaces plus Methodology wired to that client with real loading/empty/error states. `npm run lint`, `npx tsc --noEmit`, and `npm run build` all pass cleanly. A pre-existing, unrelated infrastructure gap was discovered and fixed along the way: the `api` Docker image was stale (missing `sentence-transformers` and other Phase 3+ dependencies, crash-looping on every file-watcher reload) — rebuilt via `docker compose up --build api`, then verified the rebuilt container serves real data and fails at exactly the expected point (`ProviderConfigurationError`, no `ANTHROPIC_API_KEY`) when asked a real question through the full plan→retrieve→generate pipeline, confirming the local embedding model and hybrid retrieval both run correctly inside the container. **Full interactive browser verification (click-through, keyboard-only navigation, dark-mode toggle, screen-reader pass, WCAG contrast measurement) was not possible in this environment — no browser-automation tool is configured — and is honestly reported as not done above, not claimed.**
Also not built: a component showcase/Storybook (design.md §62 "if the project timeline allows"), the global ⌘K command menu, Toast, dropdown/context menus, tablet/tablet-specific and mobile-specific layout passes beyond default responsive behavior, chart integration, and the human-review-queue UI for Validation (the `POST /reviews` endpoint exists and enforces every rule from Phase 6, but there is no list of reviewable items to drive it from yet).

**Status (2026-07-24) — migrated from Next.js to Vite + React Router:** the frontend was rebuilt from Next.js (App Router) onto Vite, at the user's request, for a lighter build toolchain and to move off Next 16's breaking-change surface. A full scan of the pre-migration codebase found only 7 files depending on Next-specific APIs (`next/link`, `next/navigation`, `next/font`, `Metadata`) — everything else (`features/*`, `components/ui/*`, `lib/api/*`, all TanStack Query data-fetching) was already plain React with no Next dependency, no API routes, no server actions, and no RSC data-fetching, so this was a routing/build-tool swap rather than an architectural rewrite. React Router replaces the App Router's file-based routing (same 9 URL paths, unchanged); Geist fonts moved from `next/font/google` to self-hosted `@fontsource` packages; static `<title>`/`<meta>` in `index.html` replace the `Metadata` export. `framer-motion` was also renamed to its current package, `motion` (same API, imported from `motion/react`). The shadcn/ui CLI (`components.json`) was formally adopted — `components/ui/*` already hand-implemented the same recipe design.md §51 describes, so existing components were preserved as-is; new Tier 1/2 components go through `npx shadcn add` going forward instead of being hand-rolled. This migration is documentation- and tooling-only: no product surface, API contract, or backend code changed.

---

---

## 13. Phase 8 — Report Builder and Export

**Sources:** `context.md §16.6`; `architecture.md §20.8`; `datamodel.md Part IX`; `design.md §33`; `edgecases.md §37–38`; `ai_evals.md §43`

Tasks:
- [x] Migrate: `report`, `report_section`, `report_evidence_link`, `report_export` (`datamodel.md Part IX`) — `alembic/versions/ce417019667f_reporting_domain.py`, matches the datamodel's §53-56 columns/constraints exactly (including `UNIQUE(report_id, position)` and `UNIQUE(report_section_id, object_type, object_id)`).
- [x] Build Report Builder UI: theme/insight selection → report canvas → section settings/evidence panel (`design.md §33`) — `frontend/src/features/reports/` (`reports-list.tsx`, `report-editor.tsx`'s three-pane layout, `export-panel.tsx`), backed by `reports/repository.py`, `reports/evidence.py`, `reports/export.py`, and `api/routes/reports.py`. One deliberate, documented scope reduction: reordering uses explicit up/down buttons, not drag-and-drop — `design.md §33.4` requires "preserve keyboard alternative to drag and drop" regardless, so the keyboard-accessible mechanism ships as primary rather than building both; the backend reorder endpoint (`POST /sections/reorder`) works identically either way.
- [x] Pin published-report references to immutable evidence/theme/insight snapshots (`datamodel.md §66`) — `report_evidence_link.snapshot` is captured by `reports/evidence.py::resolve_evidence_snapshot()` at link time (real theme/insight/feedback_record/theme_metric/generated_answer data, verified live end-to-end against real theme data), not re-read at export time.
- [x] Support Markdown and JSON export first; PDF may follow (`datamodel.md §83`) — `reports/export.py::render_markdown/render_json`, verified live (real theme data flows through into a real Markdown export). PDF is a documented, deferred `ReportExportFormat` member — `POST /exports` returns a clean `400` for it, not a crash or a silent no-op.
- [ ] Implement edge cases: `RPT-001…018`, `EXP-001…018` — **not done as a systematic pass.** A few are incidentally satisfied by the design above (`RPT-002`'s pinned-snapshot half via evidence-link snapshotting, `RPT-005` via `is_locked`, `RPT-010` via the keyboard-accessible reorder buttons), but autosave (`RPT-011`), concurrent-tab/version-conflict detection (`RPT-004`, `RPT-012`), PII/redaction checks on export (`EXP-009`), source-concentration warnings (`RPT-016`), and the rest of the catalog were not built. Treat this task as still open.
- [ ] Run report narrative evaluation and hard-failure checks (`ai_evals.md §43`) — not built. The three new deterministic grader suites added alongside this Report Builder work (`validation/graders/classification.py`, `retrieval.py`, `theme_quality.py`) cover classification/retrieval/theme quality, not report narratives specifically.

**Exit criteria:** `context.md §19` item 10 — met for the core create/populate/export loop; the `edgecases.md EXP-009, EXP-018` no-unredacted-PII/no-broken-citations guarantee is **not independently verified** for reports specifically (citations in the underlying evidence snapshots inherit whatever redaction already happened upstream in `feedback/privacy.py` at ingestion time, but no report-specific check re-verifies this at export time) — do not treat this exit criterion as met without that follow-up pass.

---

## 14. Phase 9 — Security, Reliability, and Observability Hardening

**Sources:** `architecture.md §21–26`; `datamodel.md Part XV`; `edgecases.md Parts X–XV`; `ai_evals.md Part X`

Tasks:
- [ ] Implement caching strategy with version-scoped keys (`architecture.md §21`); edge cases `CAC-001…010`.
- [ ] Implement authentication boundary (single-user mode acceptable for MVP) and role checks (`architecture.md §22`); edge cases `AUTH-001…010`.
- [ ] Implement security controls: input sanitization, SSRF allowlisting, secret isolation, prompt-injection delimiting (`architecture.md §23`); edge cases `SEC-001…020`.
- [ ] Implement retry/idempotency/partial-completion policy (`architecture.md §24`); edge cases `JOB-001…018`, `DB-001…018`.
- [ ] Implement structured logging, metrics, and cost telemetry (`architecture.md §25`); edge cases `OBS-001…015`.
- [ ] Implement the source-removal and hard-deletion workflows (`datamodel.md §75–76`); edge cases `DEL-001…012`, `VER-001…010`.
- [ ] Implement deployment/config edge cases: `DEP-001…016`.
- [ ] Resolve cross-surface consistency edge cases: `XFN-001…015`.
- [ ] Run the full adversarial suite (`ai_evals.md §44–45`) with zero hard failures.

**Exit criteria:** `edgecases.md §58` DoD items 1–20; `ai_evals.md §53` mandatory PII/adversarial/numeric items.

---

## 15. Phase 10 — Demo Readiness and Final Sign-off

**Sources:** `context.md §19`; `architecture.md §32`; `design.md §63`; `datamodel.md Part XVI, §85`; `edgecases.md §53–56`; `ai_evals.md §53, §87`

Tasks:
- [ ] Build the seed/demo dataset with the entity-count minimums in `datamodel.md §77` and the intentional edge-case fixtures in `edgecases.md §53` (duplicates, undated records, code-mixed content, PII, prompt injection, contradictions, low confidence, removed evidence, etc.).
- [ ] Use deterministic seed UUIDs (`datamodel.md §78`).
- [ ] Run the full end-to-end test suite (`architecture.md §27.6`): open demo → inspect theme → trace to evidence → ask preset question → inspect citations → open validation metrics → create/export report.
- [ ] Generate and review the final insight report.
- [ ] Document local setup, known limitations, and deferred scope (`context.md §6` deferred list, §21 open decisions).
- [ ] Run every Definition of Done checklist below and confirm all items pass together, not just individually.

**Exit criteria — all of the following simultaneously:**
- `context.md §19` — Definition of Done for the first demonstrable version (12 items)
- `architecture.md §32` — MVP Architecture Acceptance Criteria (18 items)
- `datamodel.md §85` — Data-model acceptance criteria (25 items)
- `design.md §63` — Design Definition of Done (20 items)
- `edgecases.md §58` — Edge-case Definition of Done (20 items)
- `ai_evals.md §87` — AI Evaluation Definition of Done (25 items)

---

## 16. Cross-Cutting Workstreams (Run Throughout, Not Phase-Bound)

| Workstream | Owner activity | Source |
|---|---|---|
| Versioning discipline | Every taxonomy, prompt, model, embedding, clustering, and scoring change creates a new version; nothing is overwritten | `datamodel.md §2.3–2.4`, `architecture.md §3.3` |
| ADRs | Log each architectural decision as it's made, starting from the 10 seeded in `architecture.md §30` | `architecture.md §30` |
| Cost tracking | Every model/connector call writes a `cost_ledger_entry`; enforce budget caps before large jobs | `datamodel.md §59`, `architecture.md §25.4` |
| Testing pyramid | Unit → connector (fixture-based) → integration → API contract → frontend → E2E → evaluation, added alongside each phase's code, not after | `architecture.md §27` |
| Edge-case traceability | New failure modes discovered during implementation get a stable ID added to `edgecases.md`, then a test | `edgecases.md §3.1`, `ai_evals.md §82` |
| Documentation sync | When a phase changes a service boundary, entity, token, or gate, update the owning document in the same change (see `docs/README.md` source-of-truth rules) | `docs/README.md` |

---

## 17. Open Decisions Requiring User Input Before Later Phases

Carried from `context.md §21` — implementation should proceed under the stated assumptions (`context.md §20`) until these are answered, but they should be confirmed before Phase 8–10:

1. Is the deliverable a working application, a prototype plus analysis, or both?
2. May paid services (Apify, hosted LLM API) be used, and what's the approximate budget?
3. Are Apple App Store and Twitter/X mandatory sources or optional extensions?
4. Must the final demo run fully locally, or may it depend on hosted services?
5. Must Hindi and other Indian languages be analyzed in the first version?
6. Should the output compare Instamart against Blinkit/Zepto, or stay brand-specific?
7. Does the evaluator expect a live dashboard, a recorded walkthrough, a slide deck, a written report, or a combination?

---

## 18. Risk Register

| Risk | Phase most exposed | Mitigation already specified |
|---|---|---|
| Reddit/Apple scraping breaks or gets rate-limited | 1 | Pluggable connectors, checkpointing, `ING-*` edge cases |
| LLM invents counts, segments, or causality | 2, 4, 5 | Deterministic counts only, `INS-002/003/004`, `ANS-004/005/019` |
| Theme clustering produces incoherent or unstable themes | 3 | Coherence rubric, stability reruns, `THM-*` |
| Prompt injection via scraped content | 2, 5, 9 | System-prompt delimiting, `AISEC-*`, adversarial suite |
| PII leaks into UI, logs, or exports | 1, 8, 9 | Redaction pipeline, `PII-*`, `EXP-009`, zero-tolerance gate |
| Documents/specs drift from implementation | All | Cross-cutting "Documentation sync" workstream (§16) |
| Scope creep beyond MVP (multilingual, Twitter/X, causal claims) | 10 | Explicit non-goals in `context.md §6`, `architecture.md §33` |

---

## 19. Guidance for Claude Code

- Work phase by phase; don't start a phase's evaluation gate work before its build tasks are functionally complete, but don't defer edge-case handling to "later" — implement it inline with the feature, per `edgecases.md §3.1`.
- Reference edge-case IDs directly in code comments, error codes, and test names (e.g. a test named for `ING-003`) so `edgecases.md` stays the traceable source of truth.
- When a phase's tasks reveal a gap in one of the seven source documents, fix that document in the same change, then continue — don't let this plan or the source docs silently diverge.
- Update this file's checkboxes as work completes; it is the single place to see overall progress across all seven source documents.
