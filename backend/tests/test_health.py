"""Phase 0 smoke test: the API must start and respond even when its
dependencies (Postgres, Redis) are unavailable, per architecture.md §7.5
(unavailable-source / degraded states) rather than crashing outright.
"""

from fastapi.testclient import TestClient

from instamart_engine.api.main import app


def test_health_endpoint_responds_even_when_dependencies_are_down() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert set(body["checks"].keys()) == {"database", "redis"}
