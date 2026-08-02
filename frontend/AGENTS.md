<!-- BEGIN:vite-agent-rules -->
# Vite, not Next.js

This project migrated from Next.js to Vite + React Router (2026-07-24) — see `docs/implementationplan.md` Phase 7's migration status note for what changed and why. There is no App Router, no RSC, no API routes, no `next/*` imports, and no `"use client"` directives here. Routing is plain `react-router-dom` (`src/App.tsx`); the entry point is `src/main.tsx` + `index.html`. Installed tool versions (Vite, plugins) may be newer than your training data — check `package.json` and the installed package's own docs before assuming an API shape.
<!-- END:vite-agent-rules -->
