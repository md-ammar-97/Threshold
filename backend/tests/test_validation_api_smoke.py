"""Smoke test: the validation workspace endpoints respond correctly against
the live Postgres (architecture.md §20.7). Structural checks only — the
content reflects whatever evaluation runs actually exist in the shared dev
database, so exact values aren't asserted here (see test_validation_runner.py
for content-level assertions against data seeded within a rolled-back
transaction).

All requests share one `with TestClient(app) as client:` block: outside a
`with` block, Starlette's `TestClient` opens and tears down its own event
loop/portal *per call*, but `core.database` caches its engine/session
factory in a module-level singleton — a second call's fresh loop trying to
use pooled connections bound to the first (now-closed) loop crashes on
teardown (the same asyncpg cross-event-loop issue the `db_session` fixture's
docstring describes). The `with` form keeps one loop alive for every
request made inside it, so the cached engine is only ever touched from the
loop it was created in. Resetting the cached singleton first ensures this
test doesn't inherit a stale engine bound to an already-closed loop from
some earlier TestClient use in the same test session.
"""

from fastapi.testclient import TestClient

import instamart_engine.core.database as database_module
from instamart_engine.api.main import app


def test_validation_endpoints_respond() -> None:
    database_module._engine = None
    database_module._session_factory = None

    with TestClient(app) as client:
        summary_response = client.get("/api/v1/validation/summary")
        assert summary_response.status_code == 200
        summary_body = summary_response.json()
        assert set(summary_body.keys()) == {"classification", "retrieval", "theme", "grounding"}
        for summary in summary_body.values():
            assert "evaluation_type" in summary
            assert "latest_run" in summary

        grounding_response = client.get("/api/v1/validation/grounding")
        assert grounding_response.status_code == 200
        assert grounding_response.json()["evaluation_type"] == "grounding"

        review_response = client.post(
            "/api/v1/validation/reviews",
            json={
                "object_type": "insight",
                "object_id": "00000000-0000-0000-0000-000000000000",
                "decision": "rejected",
                "previous_snapshot": {"title": "some insight"},
            },
        )
        assert review_response.status_code == 400
