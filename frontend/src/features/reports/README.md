# reports

Report Builder feature module (design.md §33). Built in Phase 8:

- `reports-list.tsx` — report list/create view (`/reports`)
- `report-editor.tsx` — section editor: add/remove/reorder sections, attach evidence
- `export-panel.tsx` — Markdown/JSON export and Resend email delivery

Talks to the API via `../../lib/api/reports.ts`. Backend counterpart: `backend/src/instamart_engine/reports/`.
