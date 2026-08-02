# Instamart Discovery Engine

An AI-powered discovery engine that analyzes public user feedback (Google Play, Apple App Store, Reddit, Twitter/X, Instagram, community forums, MouthShut, quick-commerce industry commentary) to surface evidence-backed insights about category-exploration behaviour in quick commerce — classification, theme discovery, grounded Q&A, a validation/evaluation framework, and a Report Builder with email delivery, all backed by real data, not mockups.

Repo: [github.com/md-ammar-97/Threshold](https://github.com/md-ammar-97/Threshold)

Full product, architecture, data, design, failure-handling, evaluation, and build-sequence specifications live in [`docs/`](./docs/README.md) — start there.

## Quick facts

- **Frontend:** Vite + React Router + TypeScript + Tailwind CSS + shadcn/ui components + Motion
- **Backend:** FastAPI + PostgreSQL/pgvector + Redis
- **AI:** Groq (primary) / OpenRouter (fallback) behind a provider-neutral gateway, OpenAI-SDK-compatible; embeddings via Hugging Face Inference API by default
- **Local dev:** Docker Compose (`frontend`, `api`, `worker`, `redis`, `postgres`) — the `worker` (Celery) service is scaffolding for future async tasks; nothing dispatches to it yet, everything runs as direct CLI scripts or synchronous API calls today
- **Production:** Vercel (frontend) + Render (API + daily extraction cron + Redis) + Supabase (Postgres/pgvector + storage) — see [`docs/deployment.md`](./docs/deployment.md)

## Getting started (local development)

Prerequisites: Docker Desktop running, Node 20+, Python 3.12+.

```bash
cp .env.example .env   # fill in GROQ_API_KEY at minimum, plus any connector credentials you have
docker compose up --build
```

- API: http://localhost:8010 (health check at `/health`, docs at `/docs`)
- Frontend: http://localhost:3000
- Postgres: `localhost:5434`, Redis: `localhost:6381` (non-default host ports — see the comment in `docker-compose.yml`)

See [`backend/README.md`](./backend/README.md) and [`frontend/README.md`](./frontend/README.md) for running each service outside Docker, and [`docs/implementationplan.md`](./docs/implementationplan.md) for the phased build sequence this repository follows.

## Deployment

Production deploy target is **Vercel + Render + Supabase**, with a real, committed `render.yaml` blueprint, a production `backend/Dockerfile.prod`, and a scheduled daily extraction job (`scripts/daily_extraction.sh`, runs 6:00 AM IST via a Render Cron Job). Full step-by-step guide, architecture rationale, and the complete environment-variable reference: [`docs/deployment.md`](./docs/deployment.md).

## Repository structure

See `docs/architecture.md §29` for the authoritative structure; `docs/README.md` explains why each document is a single source of truth for its area so this repo's structure and docs don't drift apart.
