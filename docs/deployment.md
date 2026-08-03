# Deployment

This is the phased guide for taking Instamart Discovery Engine from local Docker Compose to a real, publicly reachable deployment: **Vercel** (frontend) + **Render** (backend API + daily extraction cron + Redis) + **Supabase** (Postgres/pgvector + raw-artifact storage), with **GitHub** as the source of truth both platforms deploy from.

## Status at a glance

| Phase | What it covers | Status |
|---|---|---|
| 0 | Repository readiness — config files, local verification, CI | ✅ **Done** |
| 1 | Push to GitHub | ✅ **Done** — `https://github.com/md-ammar-97/Threshold`, `main`, CI green |
| 2 | Supabase — database + storage | ✅ **Done** — schema migrated, taxonomy seeded, storage bucket live |
| 3 | Render — backend API + daily cron + Redis | ✅ **Done** — `instamart-api` live, `/health` green; `instamart-daily-extraction` deployed |
| 4 | Vercel — frontend | ✅ **Done** — `https://instamart-discovery-engine.vercel.app`, CORS verified working end to end |
| 5 | End-to-end verification | 🟡 **Partial** — health check and frontend↔backend connectivity confirmed; cron run and a real report export not yet done |

**Next up: Phase 5.** Trigger a manual cron run to confirm the daily pipeline actually completes against the live stack, then create and export a report through the deployed frontend.

## Why this split (not "everything on Vercel")

Vercel is excellent for the frontend — the app is a plain static Vite build with no server-side rendering, and Vercel auto-detects that.

The backend does **not** fit Vercel's serverless model, for two concrete reasons specific to this codebase:

1. **`sentence-transformers` (and therefore `torch`) is an unconditional import** in `analysis/embed.py`, even though the default `EMBEDDING_PROVIDER=hosted` never calls the local-model path. Serverless functions have hard size limits; a torch-containing bundle blows well past what Vercel's Python runtime allows.
2. **The API needs a persistent process**, not a request-scoped function — plain `uvicorn`, no adaptation layer exists (or is needed) for a serverless entrypoint.

So the backend goes to **Render** instead: it deploys the same Docker image as a real, always-on web service, and — just as importantly — its Cron Job feature can run the daily extraction job by reusing that exact same image and installed dependencies, with no separate "reinstall everything on a schedule" step the way a GitHub Actions cron would need.

**Database and file storage go to Supabase.** Supabase Postgres is pgvector-compatible (this app already depends on the `vector` extension for embeddings), and this codebase already has a working Supabase Storage backend for raw artifacts (`storage/supabase.py`, previously only documented as an option — this guide is what actually turns it on).

**Redis stays**, via Render's own Redis-compatible Key Value service — one platform, no extra account. Today Redis only backs a `/health` ping and an unused Celery broker (`core/celery_app.py` defines queues, but zero tasks are registered anywhere in the codebase — it's forward-looking scaffolding, not something currently load-bearing). Keeping it costs nothing extra on Render and means `/health` and Celery keep behaving exactly like local dev if that scaffolding is ever picked up.

## Accounts and keys you need

| Provider | What for | Get it from |
|---|---|---|
| GitHub | Source of truth; Vercel and Render both deploy from a connected repo | you already have `https://github.com/md-ammar-97/Threshold.git` |
| Vercel | Frontend hosting | vercel.com — sign in with GitHub |
| Render | Backend API + daily cron + Redis | render.com — sign in with GitHub |
| Supabase | Postgres (pgvector) + Storage | supabase.com |
| Groq | Primary LLM provider (classification/synthesis/answers/transcription) | console.groq.com |
| OpenRouter | Fallback LLM provider | openrouter.ai |
| Hugging Face | Hosted embeddings (`EMBEDDING_PROVIDER=hosted`, the default) | huggingface.co → Settings → Access Tokens |
| Apify | Reddit/Twitter/Instagram connectors | apify.com |
| Resend | Emailing report exports (optional — the feature degrades to a clean "not configured" response without it) | resend.com |

Reddit's own `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are declared in config but the Reddit connector currently goes through Apify, not PRAW/OAuth directly — leave them blank unless you've wired up the OAuth path yourself.

---

## Phase 0 — Repository readiness ✅ Done

Everything needed to deploy is already written, committed, and verified:

- `backend/Dockerfile.prod` — production image; installs the CPU-only PyTorch wheel explicitly (the default wheel pulls the full CUDA toolkit even though Render's services are CPU-only — verified locally: CUDA build is 3.3GB/~24min, CPU-only build is 779MB/~10min).
- `render.yaml` — Blueprint defining all three Render resources (`instamart-api`, `instamart-daily-extraction`, `instamart-redis`) from one file.
- `frontend/vercel.json` — pins the Vite build command/output dir and adds the SPA catch-all rewrite `react-router-dom` needs.
- `scripts/daily_extraction.sh` — orchestrates the 8-source ingest → media extraction → classify/embed/cluster/synthesize/insights pipeline; verified to run end-to-end and degrade gracefully (continues past a failed source instead of aborting).
- `.github/workflows/ci.yml` — lints (ruff/eslint), type-checks (mypy/tsc), runs migrations against a real Postgres, runs the P0 adversarial suite, runs the full test suite, and builds the frontend, on every push. **Currently green.**

Local verification performed before any of this was trusted: production Docker image built and smoke-tested against real Postgres/Redis (`/health` returns `ok`), `scripts/daily_extraction.sh` run live against the dev stack, full backend test suite (233 tests) passed against a freshly-migrated database matching CI's exact environment, frontend `npm ci`/lint/type-check/build all verified in a Linux Node 22 container matching the CI runner.

## Phase 1 — Push to GitHub ✅ Done

```bash
git add -A
git status               # sanity-check what's staged — .env must NOT appear
git commit -m "Initial commit"
git remote add origin https://github.com/md-ammar-97/Threshold.git
git branch -M main
git push -u origin main
```

Live at `https://github.com/md-ammar-97/Threshold`, branch `main`, CI passing on every push. `.gitignore` excludes `.env`, `data/raw|interim|processed/**`, `node_modules`, and the Python virtualenv — verified clean before every push so far.

---

## Phase 2 — Supabase: database + storage ✅ Done

Project created, `vector`/`pgcrypto`/`pg_trgm`/`citext` extensions enabled (the first migration does this automatically via `CREATE EXTENSION IF NOT EXISTS`, no manual dashboard step needed), storage bucket (`raw-artifacts`) live, all 9 migrations applied (55 tables), taxonomy v3 seeded (9 dimensions, 235 labels). `DATABASE_URL`/`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`/`SUPABASE_STORAGE_BUCKET` are in local `.env`, ready to copy into Render's dashboard in Phase 3.

**Bug found and fixed along the way**: `alembic/env.py` crashed with `ValueError: invalid interpolation syntax` the first time this ran against the real Supabase URL — `config.set_main_option()` stores the URL via Python's `configparser`, which treats a literal `%` as its own interpolation syntax. A URL-encoded special character in the DB password (e.g. `%40` for a literal `@`) triggered it. Fixed by escaping `%` to `%%` before that call (configparser's own documented workaround) — this would otherwise have broken Render's deploy identically in Phase 3, since Render's env var UI stores the same password.

The steps below are kept for reference / re-running if the project is ever rebuilt from scratch.

1. Create a new Supabase project.
2. **Database → Extensions**: enable `vector` (pgvector). This project's embeddings and every vector-backed table assume Postgres 16+ with pgvector, which Supabase provides.
3. **Database → Connection string → "Session pooler" tab.** Not "Direct connection" and not "Transaction pooler" — both are wrong for different reasons: the **direct** connection (`db.<project-ref>.supabase.co:5432`) is **IPv6-only by default** (Supabase doesn't include a free IPv4 address), and most cloud hosts including Render only support outbound IPv4 — confirmed live: it worked from a local machine with IPv6 but the deployed Render service couldn't reach it at all. The **transaction pooler** (port `6543`) breaks `asyncpg`'s prepared-statement caching. The **session pooler** (port `5432`, host `aws-<n>-<region>.pooler.supabase.com`) is IPv4-native and behaves like a normal persistent connection, so it works cleanly with `asyncpg`. Rewrite it to this app's driver prefix:
   ```
   postgresql+asyncpg://postgres.<project-ref>:<password>@aws-<n>-<region>.pooler.supabase.com:5432/postgres
   ```
   This is your `DATABASE_URL`. Note the username changes to `postgres.<project-ref>` (not just `postgres`) for pooler connections.
4. **Storage → New bucket**: create one (e.g. `instamart-raw`), any visibility (the app only ever accesses it server-side via the service_role key, never a public URL). This is your `SUPABASE_STORAGE_BUCKET`.
5. **Project Settings → API**: copy the **Project URL** (`SUPABASE_URL`) and the **`service_role` secret key** (`SUPABASE_SERVICE_ROLE_KEY`) — not the `anon`/public key. The service_role key is required because `storage/supabase.py` writes objects server-side.
6. Run migrations against this database from your local machine (needs the local `backend/.venv` set up per `backend/README.md`):
   ```bash
   cd backend
   DATABASE_URL="postgresql+asyncpg://postgres.<project-ref>:<password>@aws-<n>-<region>.pooler.supabase.com:5432/postgres" \
     ./.venv/Scripts/python.exe -m alembic upgrade head
   ```
   (`alembic.ini`'s `sqlalchemy.url` is a placeholder — `alembic/env.py` always overrides it from `DATABASE_URL` at runtime, so this is the only thing you need to set.)
7. Load the taxonomy the app depends on (run once, same env var):
   ```bash
   DATABASE_URL="postgresql+asyncpg://..." ./.venv/Scripts/python.exe -c "
   import asyncio
   from instamart_engine.core.database import get_session_factory
   from instamart_engine.taxonomy.seed_v3 import load_taxonomy_v3
   async def main():
       async with get_session_factory()() as session:
           await load_taxonomy_v3(session)
           await session.commit()
   asyncio.run(main())
   "
   ```
   Without this, classification has nothing to classify against.

**Exit criteria** (met): `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET` all in hand; `alembic upgrade head` and the taxonomy seed both ran successfully against the Supabase database.

## Phase 3 — Render: backend API + daily cron + Redis ⬜ Not started

Depends on Phase 2 for `DATABASE_URL`/`SUPABASE_*`. Also needs `GROQ_API_KEY` (console.groq.com), `OPENROUTER_API_KEY` (openrouter.ai), `HF_API_TOKEN` (huggingface.co), `APIFY_TOKEN` (apify.com), and optionally `RESEND_API_KEY`/`RESEND_FROM_EMAIL` (resend.com) in hand.

This repo ships a `render.yaml` Blueprint at the repo root defining all three Render resources (`instamart-api`, `instamart-daily-extraction`, `instamart-redis`) from one file — in practice, the Blueprint dashboard flow failed to create anything (see below), so both services were created directly via Render's REST API instead. `render.yaml` stays as accurate reference/documentation and would work for a from-scratch rebuild via the dashboard, with two corrections noted below.

**What actually happened, and what it revealed:**

1. **Billing is required before creating any paid-plan resource** — the Blueprint apply failed silently (no error surfaced clearly in the UI) because the account had no card on file and `instamart-api` needs the `starter` plan (Render's free web-service tier spins down after 15 minutes idle, which breaks a user-facing API with a slow cold-start on the next request). Adding a card at https://dashboard.render.com/billing resolved this.
2. **`render.yaml`'s `plan: free` for the cron job is invalid** — Render's cron jobs don't support a free plan at all (confirmed via the API: valid plans are `starter` and up). This means the Blueprint as originally written could never have deployed successfully even with billing set up. `instamart-daily-extraction` runs on `starter` too.
3. **Render's account-wide limit of one free-tier Key Value instance** — if you already have another free Redis/Key Value instance on the account (from an unrelated project), you'll either need a paid plan for a second one, or reuse the existing instance. This project reuses an existing free instance from another project via its internal connection string (`redis://<instance-id>:6379`) rather than provisioning a dedicated one.
4. **Supabase's direct database connection is IPv6-only by default**, and Render (like most cloud hosts) only supports outbound IPv4 — `DATABASE_URL` using the direct connection (`db.<ref>.supabase.co:5432`) worked fine locally but `/health` reported `"database": "unavailable"` once deployed. Fixed by switching to Supabase's **Session Pooler** connection string instead (see Phase 2's corrected step 3) — IPv4-native and, unlike the Transaction Pooler, doesn't break `asyncpg`'s prepared-statement caching.

Once `DATABASE_URL` was corrected, `https://<your-api>.onrender.com/health` returned `{"status": "ok", "checks": {"database": "ok", "redis": "ok"}}`.

**Reference — the dashboard Blueprint flow**, for a from-scratch rebuild (apply the two corrections above first: add billing before deploying, and use the Session Pooler connection string):

1. Render dashboard → **New → Blueprint**, connect the GitHub repo, select `render.yaml`.
2. Render will prompt for every env var marked `sync: false` in the blueprint — fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_API_TOKEN`, `APIFY_TOKEN`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL` (these live in one shared `envVarGroup`, so you only enter them once for both the API and the cron job).
3. Deploy. **The first build takes a few minutes** — see Phase 0's note on the CPU-only PyTorch build (in practice, Render's build infra finished it in ~2.5 minutes, faster than local). Subsequent deploys reuse Docker layer caching and are much faster unless `backend/pyproject.toml` changes.
4. The cron job's schedule is `30 0 * * *` — Render Cron Jobs use standard cron syntax in **UTC**. `00:30 UTC = 6:00 AM IST` (IST is UTC+5:30 — a 30-minute offset, not a clean hour shift, easy to get wrong). You can trigger a manual run from the Render dashboard (cron service → "Trigger Run") to test it without waiting for the schedule, and check past runs' logs the same way.
5. **Groq free-tier rate limits will govern how long the cron job actually takes.** Verified live during development: Groq's `on_demand` tier caps `openai/gpt-oss-120b` at 8,000 tokens/minute *and* 200,000 tokens/day. The classify/synthesize step in `scripts/pipeline.py` retries transient 429s automatically and fails over to `OPENROUTER_API_KEY` (`LLM_FALLBACK_PROVIDER`) once Groq's per-call retries are exhausted, so a rate-limited run degrades gracefully rather than crashing — but on a heavy ingestion day (100s of new records), the daily job can genuinely take well over an hour to finish classifying everything, and if the *daily* Groq quota is already exhausted (e.g. from manual testing earlier that day), most calls will fail over to the fallback model for the rest of the day. If this matters for your volume, upgrade the Groq org to a paid tier before relying on the daily cron.

**Exit criteria** (met): `https://<your-api>.onrender.com/health` returns `{"status": "ok", ...}`. Still pending: a manually-triggered cron run confirmed to complete (or clearly degrade gracefully under rate limits) — see Phase 5.

## Phase 4 — Vercel: frontend ✅ Done

Live at `https://instamart-discovery-engine.vercel.app` (Hobby/free tier, no card required), linked to the GitHub repo with production branch `main` — auto-deploys on every push.

1. Vercel dashboard → **Add New → Project**, import the GitHub repo.
2. Set **Root Directory** to `frontend`. Vercel auto-detects the Vite framework preset; `frontend/vercel.json` (committed in this repo) pins the build command (`npm run build`), output directory (`dist`), and adds a catch-all rewrite to `index.html` — required because this is a client-side-routed SPA (`react-router-dom`'s `BrowserRouter`); without the rewrite, refreshing on a deep link like `/themes/<id>` would 404. Verified live: `/themes` and `/validation` both return 200, not 404.
3. Add one environment variable: `VITE_API_URL` = your deployed Render API's public URL (e.g. `https://instamart-api-v40x.onrender.com`) — this is the *only* place the frontend reads a backend URL from (`frontend/src/lib/api/client.ts`), confirmed by grep across the whole `frontend/src` tree.
4. Deploy. Vercel will auto-redeploy on every push to `main` from here on.

**Bug found and fixed along the way**: `backend/src/instamart_engine/api/main.py`'s CORS middleware had `allow_origins` hardcoded to `http://localhost:3000` only. Harmless in local dev, but would have silently broken every API call from the deployed frontend — browsers block cross-origin responses whose origin isn't in `Access-Control-Allow-Origin`, and the failure is invisible from the backend's own logs, only visible as failed `fetch()` calls in the browser's devtools console. Caught by testing the actual deployed frontend against the actual deployed backend before declaring this phase done, rather than trusting that both being "live" meant they could talk to each other. Fixed with a new `CORS_ORIGINS` setting (comma-separated, defaults to `http://localhost:3000` so local dev is unaffected) — see the env var reference below. Verified via a real preflight (`OPTIONS`) and `GET` request with `Origin: https://instamart-discovery-engine.vercel.app`, both returning the correct `Access-Control-Allow-Origin` header.

**Exit criteria** (met): Vercel URL loads the app shell, deep-linked routes don't 404, and a real cross-origin request from the Vercel origin to the Render API succeeds with correct CORS headers.

## Phase 5 — End-to-end verification ⬜ Not started

Depends on Phases 2–4 all being live.

- `GET /health` on the Render URL → `{"status": "ok", "postgres": "ok", "redis": "ok"}`.
- Open the Vercel URL, confirm the Themes/Insights/Validation pages load (they'll be empty until the first extraction run has happened).
- Trigger the `instamart-daily-extraction` cron job manually from the Render dashboard, watch its logs — expect several `[OK] ingestion_run=...` lines per source, then `[CLASSIFIED]`/`[EMBEDDED]`/`[CLUSTERED]`/`[SYNTHESIZED]` lines from `scripts/pipeline.py`.
- Reload the frontend — Themes/Insights should now show real data.
- Create a report in the Report Builder, export it to Markdown, confirm the content traces back to real theme/insight data (not a placeholder).

**Exit criteria**: all five checks above pass. At that point the deployment is fully live and self-sustaining on its daily schedule.

---

## Reference

### Environment variable reference

Every field on `Settings` (`backend/src/instamart_engine/core/config.py`), grouped the same way the file itself groups them. "Required in prod" means the app is meaningfully degraded or non-functional without it; blank/default is otherwise fine.

| Variable | Default | Required in prod? | Notes |
|---|---|---|---|
| `APP_ENV` | `local` | Set to `production` | Gates a startup check that refuses to boot with default/local-looking config in production |
| `DATABASE_URL` | local Postgres | **Yes** | Supabase direct connection string, `+asyncpg` driver, port 5432 not 6543 |
| `REDIS_URL` | local Redis | **Yes** | Injected automatically from the `instamart-redis` Render service if using `render.yaml` |
| `CORS_ORIGINS` | `http://localhost:3000` | **Yes** | Comma-separated allowed frontend origins; must include your deployed Vercel URL(s) or every API call from the browser fails cross-origin |
| `RAW_STORAGE_BACKEND` | `filesystem` | **Yes — set to `supabase`** | `filesystem` has no meaning on Render's ephemeral containers |
| `RAW_STORAGE_PATH` | `./data/raw` | No | Only used by the filesystem backend |
| `SUPABASE_URL` | — | **Yes** (if using Supabase storage) | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | **Yes** | The `service_role` secret, not `anon` |
| `SUPABASE_STORAGE_BUCKET` | — | **Yes** | Bucket created in Phase 2 |
| `LLM_PROVIDER` | `groq` | No | |
| `LLM_FALLBACK_PROVIDER` | `openrouter` | No | |
| `LLM_MODEL_CLASSIFICATION`/`_SYNTHESIS`/`_ANSWER` | `openai/gpt-oss-120b` | No | Groq-hosted model name |
| `LLM_FALLBACK_MODEL` | `nvidia/nemotron-3-super-120b-a12b:free` | No | OpenRouter model name |
| `LLM_MODEL_TRANSCRIPTION` | `whisper-large-v3-turbo` | No | Groq-hosted Whisper, used by `extract_media.py` |
| `GROQ_API_KEY` | — | **Yes** | Nothing classifies/synthesizes/answers without it |
| `OPENROUTER_API_KEY` | — | Recommended | Fallback when Groq rate-limits or errors |
| `EMBEDDING_PROVIDER` | `hosted` | No | `hosted` = Hugging Face Inference API (no torch download at runtime); `local` needs `HF_API_TOKEN` unset but downloads model weights into the container instead |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | No | |
| `EMBEDDING_DIMENSION` | `384` | No | Must match the model above if changed |
| `HF_API_TOKEN` | — | **Yes** (with default `EMBEDDING_PROVIDER=hosted`) | Retrieval/clustering silently produce nothing without it — see the "chatbot not working" root cause this was built to guard against |
| `APIFY_TOKEN` | — | **Yes** (for reddit/twitter/instagram) | |
| `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` | — | No | Unused today — Reddit goes through Apify |
| `REDDIT_USER_AGENT` | `instamart-discovery-engine/0.1` | No | |
| `RESEND_API_KEY` | — | Optional | Email-a-report feature; a clean 503 without it, not a crash |
| `RESEND_FROM_EMAIL` | `reports@instamart-discovery-engine.dev` | Only if using Resend | Must be a domain verified in your Resend account |
| `DEFAULT_COLLECTION_LIMIT` | `500` | No | |
| `MAX_COLLECTION_COST_USD` | `25.0` | No | |
| `MODEL_MAX_RETRIES` | `3` | No | |
| `MODEL_CONCURRENCY` | `4` | No | |

### Redeploys and rollback

Both Vercel and Render auto-deploy on every push to `main` once connected — no GitHub Actions changes needed for that (the existing `.github/workflows/ci.yml` only lints/tests/builds; it doesn't deploy anything, and doesn't need to).

- **Vercel rollback**: dashboard → Deployments → pick a previous one → "Promote to Production." Instant, no rebuild.
- **Render rollback**: dashboard → the `instamart-api` service → Deploys → pick a previous successful deploy → "Rollback." Also instant (reuses the previously-built image).
- **Database migrations are not automatically rolled back** by either of the above — if a deploy included a migration, rolling back the app code without also considering the schema can leave things inconsistent. For this project's current size, treat migrations as forward-only and fix forward rather than reaching for `alembic downgrade`.

### Local dev is unaffected

Nothing here changes local development. `docker compose up --build` still uses `backend/Dockerfile` (the dev image, editable install + `--reload`) and `frontend/Dockerfile` (the dev image, `npm run dev`) exactly as before — `backend/Dockerfile.prod` and `render.yaml`/`vercel.json` are new, additive files, not replacements.
