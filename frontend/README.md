# Frontend — Instamart Discovery Engine

Vite + React Router + TypeScript + Tailwind CSS. See `../docs/design.md` for the full design system and `../docs/implementationplan.md §12` for what Phase 7 builds out here, and `AGENTS.md` for the Next.js→Vite migration note.

## Structure

- `src/main.tsx` + `index.html` — entry point; `src/App.tsx` — route definitions (`react-router-dom`)
- `src/pages/` + `src/features/` — routes: `/`, `/themes`, `/themes/:themeId`, `/ask`, `/evidence`, `/validation`, `/reports`, `/runs`, `/methodology` (design.md §5.2)
- `src/components/` — `ui/`, `charts/`, `motion/`, `layout/`, `research/`, `feedback/` (design.md §55)
- `src/lib/` — `api/`, `query-client/`, `schemas/`, `events/`, `utils/`
- `src/styles/` — `tokens.css`, `typography.css`, `globals.css`, `print.css` (design.md §54)

Every currently-empty directory has a `README.md` explaining what it holds and which phase populates it — check that before adding files elsewhere.

## Local setup

```bash
npm install
cp ../.env.example ../.env.local   # VITE_API_URL etc.
npm run dev       # http://localhost:3000
npm run lint
npm run build
```

Requires the backend API running (see `../backend/README.md`) for any page beyond these Phase 0 placeholders to do anything useful.

## Production deployment

Deploys as a static build to Vercel (`vercel.json` in this directory pins the Vite build config and adds the SPA rewrite `react-router-dom` needs). See [`../docs/deployment.md`](../docs/deployment.md) for the full guide.
