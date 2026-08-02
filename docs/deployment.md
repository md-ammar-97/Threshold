# Deployment

This is the guide for taking Instamart Discovery Engine from local Docker Compose to a real, publicly reachable deployment: **Vercel** (frontend) + **Render** (backend API + daily extraction cron + Redis) + **Supabase** (Postgres/pgvector + raw-artifact storage), with **GitHub** as the source of truth both platforms deploy from.

## 1. Why this split (not "everything on Vercel")

Vercel is excellent for the frontend — the app is a plain static Vite build with no server-side rendering, and Vercel auto-detects that.

The backend does **not** fit Vercel's serverless model, for two concrete reasons specific to this codebase:

1. **`sentence-transformers` (and therefore `torch`) is an unconditional import** in `analysis/embed.py`, even though the default `EMBEDDING_PROVIDER=hosted` never calls the local-model path. Serverless functions have hard size limits; a torch-containing bundle blows well past what Vercel's Python runtime allows.
2. **The API needs a persistent process**, not a request-scoped function — plain `uvicorn`, no adaptation layer exists (or is needed) for a serverless entrypoint.

So the backend goes to **Render** instead: it deploys the same Docker image as a real, always-on web service, and — just as importantly — its Cron Job feature can run the daily extraction job by reusing that exact same image and installed dependencies, with no separate "reinstall everything on a schedule" step the way a GitHub Actions cron would need.

**Database and file storage go to Supabase.** Supabase Postgres is pgvector-compatible (this app already depends on the `vector` extension for embeddings), and this codebase already has a working Supabase Storage backend for raw artifacts (`storage/supabase.py`, previously only documented as an option — this guide is what actually turns it on).

**Redis stays**, via Render's own Redis-compatible Key Value service — one platform, no extra account. Today Redis only backs a `/health` ping and an unused Celery broker (`core/celery_app.py` defines queues, but zero tasks are registered anywhere in the codebase — it's forward-looking scaffolding, not something currently load-bearing). Keeping it costs nothing extra on Render and means `/health` and Celery keep behaving exactly like local dev if that scaffolding is ever picked up.

## 2. Accounts and keys you need

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

## 3. Push the code to GitHub

The repo has no commits yet as of this guide being written. From the repo root:

```bash
git add -A
git status               # sanity-check what's staged — .env must NOT appear
git commit -m "Initial commit"
git remote add origin https://github.com/md-ammar-97/Threshold.git
git branch -M main
git push -u origin main
```

`.gitignore` already excludes `.env`, `data/raw|interim|processed/**`, `node_modules`, and the Python virtualenv — verified before this guide was written. Double-check `git status` yourself before pushing regardless; it's cheap insurance against a leaked key.

## 4. Supabase — database and storage

1. Create a new Supabase project.
2. **Database → Extensions**: enable `vector` (pgvector). This project's `report_export.sha256`, embeddings, and every other table assume Postgres 16+ with pgvector, which Supabase provides.
3. **Database → Connection string**: copy the **direct** connection (port `5432`), not the pooled/PgBouncer one (port `6543`). `asyncpg` (this app's driver) doesn't speak PgBouncer's transaction-pooling mode cleanly without extra tuning that isn't configured here — use the direct connection to avoid that entirely. Rewrite it to this app's driver prefix:
   ```
   postgresql+asyncpg://postgres:<password>@<project-ref>.supabase.co:5432/postgres
   ```
   This is your `DATABASE_URL`.
4. **Storage → New bucket**: create one (e.g. `instamart-raw`), any visibility (the app only ever accesses it server-side via the service_role key, never a public URL). This is your `SUPABASE_STORAGE_BUCKET`.
5. **Project Settings → API**: copy the **Project URL** (`SUPABASE_URL`) and the **`service_role` secret key** (`SUPABASE_SERVICE_ROLE_KEY`) — not the `anon`/public key. The service_role key is required because `storage/supabase.py` writes objects server-side.
6. Run migrations against this database from your local machine (needs the local `backend/.venv` set up per `backend/README.md`):
   ```bash
   cd backend
   DATABASE_URL="postgresql+asyncpg://postgres:<password>@<project-ref>.supabase.co:5432/postgres" \
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

## 5. Render — backend API + daily cron + Redis

This repo ships a `render.yaml` Blueprint at the repo root defining all three Render resources (`instamart-api`, `instamart-daily-extraction`, `instamart-redis`) from one file.

1. Render dashboard → **New → Blueprint**, connect the GitHub repo, select `render.yaml`.
2. Render will prompt for every env var marked `sync: false` in the blueprint — fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_API_TOKEN`, `APIFY_TOKEN`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL` (these live in one shared `envVarGroup`, so you only enter them once for both the API and the cron job).
3. Deploy. **The first build is slow** — `sentence-transformers`/`torch` alone is a large dependency tree; expect 10–25 minutes, matching what full rebuilds took locally during development. Subsequent deploys reuse Docker layer caching and are much faster unless `backend/pyproject.toml` changes.
4. Once live, confirm `https://<your-api>.onrender.com/health` returns `{"status": "ok", ...}`.
5. **Plan note**: `instamart-api` is set to Render's `starter` plan in `render.yaml`, not `free` — Render's free web-service tier spins down after 15 minutes of inactivity, which would mean the first request after any quiet period gets a slow cold-start (or times out from the frontend's perspective). `instamart-daily-extraction` is fine on `free` since it's only invoked on its schedule, never expected to stay warm.
6. The cron job's schedule is `30 0 * * *` — Render Cron Jobs use standard cron syntax in **UTC**. `00:30 UTC = 6:00 AM IST` (IST is UTC+5:30 — a 30-minute offset, not a clean hour shift, easy to get wrong). You can trigger a manual run from the Render dashboard (cron service → "Trigger Run") to test it without waiting for the schedule, and check past runs' logs the same way.

## 6. Vercel — frontend

1. Vercel dashboard → **Add New → Project**, import the GitHub repo.
2. Set **Root Directory** to `frontend`. Vercel will auto-detect the Vite framework preset; `frontend/vercel.json` (committed in this repo) pins the build command (`npm run build`), output directory (`dist`), and adds a catch-all rewrite to `index.html` — required because this is a client-side-routed SPA (`react-router-dom`'s `BrowserRouter`); without the rewrite, refreshing on a deep link like `/themes/<id>` would 404.
3. Add one environment variable: `VITE_API_URL` = your deployed Render API's public URL (e.g. `https://instamart-api.onrender.com`) — this is the *only* place the frontend reads a backend URL from (`frontend/src/lib/api/client.ts`), confirmed by grep across the whole `frontend/src` tree.
4. Deploy. Vercel will auto-redeploy on every push to `main` from here on.

## 7. Verify the whole thing end to end

- `GET /health` on the Render URL → `{"status": "ok", "postgres": "ok", "redis": "ok"}`.
- Open the Vercel URL, confirm the Themes/Insights/Validation pages load (they'll be empty until the first extraction run has happened).
- Trigger the `instamart-daily-extraction` cron job manually from the Render dashboard, watch its logs — expect several `[OK] ingestion_run=...` lines per source, then `[CLASSIFIED]`/`[EMBEDDED]`/`[CLUSTERED]`/`[SYNTHESIZED]` lines from `scripts/pipeline.py`.
- Reload the frontend — Themes/Insights should now show real data.
- Create a report in the Report Builder, export it to Markdown, confirm the content traces back to real theme/insight data (not a placeholder).

## 8. Environment variable reference

Every field on `Settings` (`backend/src/instamart_engine/core/config.py`), grouped the same way the file itself groups them. "Required in prod" means the app is meaningfully degraded or non-functional without it; blank/default is otherwise fine.

| Variable | Default | Required in prod? | Notes |
|---|---|---|---|
| `APP_ENV` | `local` | Set to `production` | Gates a startup check that refuses to boot with default/local-looking config in production |
| `DATABASE_URL` | local Postgres | **Yes** | Supabase direct connection string, `+asyncpg` driver, port 5432 not 6543 |
| `REDIS_URL` | local Redis | **Yes** | Injected automatically from the `instamart-redis` Render service if using `render.yaml` |
| `RAW_STORAGE_BACKEND` | `filesystem` | **Yes — set to `supabase`** | `filesystem` has no meaning on Render's ephemeral containers |
| `RAW_STORAGE_PATH` | `./data/raw` | No | Only used by the filesystem backend |
| `SUPABASE_URL` | — | **Yes** (if using Supabase storage) | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | **Yes** | The `service_role` secret, not `anon` |
| `SUPABASE_STORAGE_BUCKET` | — | **Yes** | Bucket created in step 4 above |
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

## 9. Redeploys and rollback

Both Vercel and Render auto-deploy on every push to `main` once connected — no GitHub Actions changes needed for that (the existing `.github/workflows/ci.yml` only lints/tests/builds; it doesn't deploy anything, and doesn't need to).

- **Vercel rollback**: dashboard → Deployments → pick a previous one → "Promote to Production." Instant, no rebuild.
- **Render rollback**: dashboard → the `instamart-api` service → Deploys → pick a previous successful deploy → "Rollback." Also instant (reuses the previously-built image).
- **Database migrations are not automatically rolled back** by either of the above — if a deploy included a migration, rolling back the app code without also considering the schema can leave things inconsistent. For this project's current size, treat migrations as forward-only and fix forward rather than reaching for `alembic downgrade`.

## 10. Local dev is unaffected

Nothing here changes local development. `docker compose up --build` still uses `backend/Dockerfile` (the dev image, editable install + `--reload`) and `frontend/Dockerfile` (the dev image, `npm run dev`) exactly as before — `backend/Dockerfile.prod` and `render.yaml`/`vercel.json` are new, additive files, not replacements.
