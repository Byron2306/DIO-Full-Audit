"""Smoke tests for foundation service router endpoints."""

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routers.foundation import router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_foundation_routes_registered():
    client = _build_client()
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json().get("paths", {})

    assert "/api/foundation/alqualonde/flow" in paths
    assert "/api/foundation/secure-boot/truth" in paths
    assert "/api/foundation/zpd/estimate" in paths


def test_foundation_requires_params_or_auth_returns_non_404():
    client = _build_client()

    response = client.get("/api/foundation/alqualonde/flow")
    assert response.status_code in (401, 403, 422)

    response = client.post("/api/foundation/heartbeat/start")
    assert response.status_code in (401, 403, 422, 500)


def test_foundation_presence_health_endpoint_exists():
    client = _build_client()
    response = client.get("/api/foundation/presence/health")
    assert response.status_code in (200, 401, 403, 422, 500, 501)
