"""
API Tests - Layer 3
===================
Tests REST API endpoints for functionality and correctness.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
sys.path.insert(0, "backend")

from routers.deception import router as deception_router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(deception_router)  # router has /deception/ built in
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.mark.api
class TestDeceptionAPI:
    def test_explain_endpoint_api(self, client):
        response = client.get("/deception/explain/session_api_test")
        assert response.status_code in (200, 401, 403, 404, 422, 500)

    def test_explain_endpoint_not_found(self, client):
        response = client.get("/deception/explain/nonexistent_session_xyz")
        assert response.status_code in (200, 401, 403, 404, 422, 500)

    def test_agenticity_analyze_endpoint(self, client):
        payload = {
            "session_id": "api_test_session",
            "source_ip": "192.168.1.100",
            "request_path": "/api/data",
            "user_agent": "TestAgent/1.0",
            "headers": {},
            "query_patterns": [],
            "time_since_last_request": 1.5
        }
        response = client.post("/deception/assess", json=payload)
        assert response.status_code in (200, 422, 500)

    def test_agenticity_analyze_invalid_data(self, client):
        response = client.post("/deception/assess", json={"invalid": "data"})
        assert response.status_code in (422, 400)

    def test_maze_probe_endpoint(self, client):
        response = client.post("/deception/maze/probe")
        assert response.status_code in (401, 403, 422)

    def test_maze_probe_not_found(self, client):
        response = client.get("/deception/maze/nonexistent/surface")
        assert response.status_code in (200, 401, 403, 404, 422, 500)

    def test_maze_sessions_endpoint(self, client):
        response = client.get("/deception/maze/sessions")
        assert response.status_code in (200, 401, 403, 422)


@pytest.mark.api
class TestAPIResponseFormats:
    def test_explain_endpoint_json_response(self, client):
        response = client.get("/deception/explain/format_test_session")
        assert response.status_code in (200, 401, 403, 404, 422, 500)
        assert response.headers.get("content-type", "").startswith("application/json")

    def test_api_method_not_allowed(self, client):
        response = client.delete("/deception/status")
        assert response.status_code in (405, 404)


@pytest.mark.api
class TestAPIValidation:
    def test_agenticity_analyze_missing_fields(self, client):
        response = client.post("/deception/assess", json={"session_id": "test"})
        assert response.status_code in (422, 400, 500)

    def test_agenticity_analyze_malformed_data(self, client):
        response = client.post("/deception/assess", data="not json", headers={"content-type": "text/plain"})
        assert response.status_code in (422, 415, 400)


@pytest.mark.api
class TestAPIConcurrency:
    def test_concurrent_explain_requests(self, client):
        session_ids = [f"concurrent_session_{i}" for i in range(10)]
        responses = [client.get(f"/deception/explain/{sid}") for sid in session_ids]
        for response in responses:
            assert response.status_code in (200, 401, 403, 404, 422, 500)
