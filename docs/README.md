# Documentation Index: Instamart Discovery Engine

This folder defines a complete product, architecture, data, design, failure-handling, and evaluation specification for the Instamart Discovery Engine assignment. The documents build on each other in this order:

| # | File | What it defines |
|---|---|---|
| 0 | [`problemNL.txt`](./problemNL.txt) | The raw, original assignment brief in unstructured form. Kept for provenance only — superseded by `problemstatement.md`. |
| 1 | [`problemstatement.md`](./problemstatement.md) | A cleaned, structured restatement of the assignment: objective, data sources, key research questions, expected demonstration. |
| 2 | [`context.md`](./context.md) | The concrete product definition: what is actually being built, why, MVP scope, research taxonomy, technical approach, and phased implementation plan. |
| 3 | [`architecture.md`](./architecture.md) | The system architecture: services, background jobs, source connectors, AI gateway, retrieval, APIs, deployment topology, and reliability model. |
| 4 | [`datamodel.md`](./datamodel.md) | The canonical PostgreSQL/pgvector data model: entities, lineage, versioning, constraints, indexes, and retention rules. |
| 5 | [`design.md`](./design.md) | The frontend design system: tokens, components, product surfaces, motion, accessibility, and content voice. |
| 6 | [`edgecases.md`](./edgecases.md) | Expected behaviour for failure, partial, stale, and adversarial conditions, organized as stable IDs (e.g. `ING-003`, `AISEC-001`). |
| 7 | [`ai_evals.md`](./ai_evals.md) | How every AI-dependent capability is evaluated, gated for release, and monitored, referencing `edgecases.md` IDs as fixtures. |
| 8 | [`implementationplan.md`](./implementationplan.md) | The ordered, phased build sequence that synthesizes all seven documents above into actionable tasks, exit criteria, and a rolled-up Definition of Done. |
| 9 | [`deployment.md`](./deployment.md) | How to actually deploy this: Vercel (frontend) + Render (backend + daily extraction cron + Redis) + Supabase (Postgres/pgvector + storage), step by step, with the full environment-variable reference. |

Not part of the numbered build sequence, but kept for the historical record: [`audit-2026-07-31.md`](./audit-2026-07-31.md) — a full engineering audit with a "Resolved since this audit" addendum at the top tracking which findings have since been fixed.

## Reading order

- **New to the project?** Read `problemstatement.md` → `context.md` → `architecture.md` in that order for the "what and why," then dip into `datamodel.md`, `design.md`, `edgecases.md`, and `ai_evals.md` as needed.
- **Implementing a feature?** Start from `architecture.md` for the relevant service boundary, `datamodel.md` for the entities involved, `design.md` for the UI surface, and check `edgecases.md` for the failure states that surface must handle.
- **Changing a model, prompt, or taxonomy?** Read `ai_evals.md` section on evaluation cadence first — most changes require a specific evaluation suite before release.
- **Deploying or changing infrastructure?** `deployment.md` is authoritative and self-contained; `architecture.md §6.2` points to it rather than duplicating it.

## Source-of-truth rules

To prevent the documents drifting apart as the project evolves:

- **Repository structure** is authoritative in `architecture.md` (§29) and mirrored only at a high level elsewhere.
- **Frontend design decisions** (tokens, components, motion, copy) are authoritative in `design.md`.
- **Database entities and constraints** are authoritative in `datamodel.md`.
- **Failure-state behaviour** is authoritative in `edgecases.md`, referenced by ID from other documents and from tests.
- **Release gates and evaluation metrics** are authoritative in `ai_evals.md`.

When a change affects more than one document, update all affected documents in the same change rather than letting one fall behind.
