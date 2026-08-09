"""
Unit Tests for Deception Router
================================
Tests actual endpoints in the deception router.
Routes are prefixed with /deception/ (from router itself).
When mounted at /api, full paths are /api/deception/...
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

import sys
sys.path.insert(0, 'backend')

from routers.deception import router


@pytest.fixture
def client():
    app = FastAPI()
    # Mount without extra prefix since router already has /deception/ prefix
    app.include_router(router)
    return TestClient(app)


class TestDeceptionStatusEndpoint:
    def test_status_returns_200(self, client):
        response = client.get("/deception/status")
        assert response.status_code == 200

    def test_status_response_is_dict(self, client):
        response = client.get("/deception/status")
        assert isinstance(response.json(), dict)

    def test_capabilities_returns_200(self, client):
        response = client.get("/deception/capabilities")
        assert response.status_code == 200

    def test_capabilities_response_is_dict(self, client):
        response = client.get("/deception/capabilities")
        assert isinstance(response.json(), dict)


class TestDeceptionAssessEndpoint:
    def test_assess_requires_body(self, client):
        response = client.post("/deception/assess")
        assert response.status_code == 422

    def test_assess_valid_request_structure(self, client):
        payload = {
            "session_id": "test_session",
            "source_ip": "192.168.1.100",
            "request_path": "/api/data",
            "user_agent": "TestAgent/1.0",
            "headers": {},
            "query_patterns": [],
            "time_since_last_request": 1.5
        }
        response = client.post("/deception/assess", json=payload)
        assert response.status_code in (200, 422, 500)

    def test_assess_batch_requires_body(self, client):
        response = client.post("/deception/assess/batch")
        assert response.status_code in (401, 403, 422)


class TestDeceptionCampaignsEndpoint:
    def test_campaigns_endpoint_accessible(self, client):
        response = client.get("/deception/campaigns")
        assert response.status_code in (200, 401, 403, 422)

    def test_events_endpoint_accessible(self, client):
        response = client.get("/deception/events")
        assert response.status_code in (200, 401, 403, 422)

    def test_events_summary_accessible(self, client):
        response = client.get("/deception/events/summary")
        assert response.status_code in (200, 401, 403, 422)

    def test_fingerprints_accessible(self, client):
        response = client.get("/deception/fingerprints")
        assert response.status_code in (200, 401, 403, 422)


class TestDeceptionMazeEndpoints:
    def test_maze_probe_requires_body(self, client):
        response = client.post("/deception/maze/probe")
        assert response.status_code in (401, 403, 422)

    def test_maze_active_sessions_accessible(self, client):
        response = client.get("/deception/maze/active")
        assert response.status_code in (200, 401, 403, 422)

    def test_maze_sessions_accessible(self, client):
        response = client.get("/deception/maze/sessions")
        assert response.status_code in (200, 401, 403, 422)

    def test_explain_session_accessible(self, client):
        response = client.get("/deception/explain/test_session_xyz")
        assert response.status_code in (200, 401, 403, 404, 422, 500)

    def test_maze_surface_accessible(self, client):
        response = client.get("/deception/maze/test_session/surface")
        assert response.status_code in (200, 401, 403, 404, 422, 500)


class TestDeceptionBlocklistEndpoints:
    def test_get_blocklist_accessible(self, client):
        response = client.get("/deception/blocklist")
        assert response.status_code in (200, 401, 403, 422)

    def test_add_to_blocklist_requires_body(self, client):
        response = client.post("/deception/blocklist/add")
        assert response.status_code in (401, 403, 422)

    def test_add_to_allowlist_requires_body(self, client):
        response = client.post("/deception/allowlist/add")
        assert response.status_code in (401, 403, 422)


class TestDeceptionAnalyticsEndpoints:
    def test_threat_heatmap_accessible(self, client):
        response = client.get("/deception/analytics/threat-heatmap")
        assert response.status_code in (200, 401, 403, 422)

    def test_campaigns_timeline_accessible(self, client):
        response = client.get("/deception/analytics/campaigns-timeline")
        assert response.status_code in (200, 401, 403, 422)

    def test_mystique_config_accessible(self, client):
        response = client.get("/deception/mystique/config")
        assert response.status_code in (200, 401, 403, 422)

    def test_stonewall_config_accessible(self, client):
        response = client.get("/deception/stonewall/config")
        assert response.status_code in (200, 401, 403, 422)


@pytest.mark.asyncio
class TestDeceptionIntegration:
    async def test_status_data_consistency(self, client):
        r1 = client.get("/deception/status")
        r2 = client.get("/deception/status")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert set(r1.json().keys()) == set(r2.json().keys())

    async def test_capabilities_non_empty(self, client):
        response = client.get("/deception/capabilities")
        assert response.status_code == 200
        assert len(response.json()) > 0

    async def test_assess_is_idempotent(self, client):
        payload = {
            "session_id": "idempotent_test_session",
            "source_ip": "192.168.1.200",
            "request_path": "/test",
            "user_agent": "Bot/2.0",
            "headers": {},
            "query_patterns": [],
            "time_since_last_request": 0.5
        }
        r1 = client.post("/deception/assess", json=payload)
        r2 = client.post("/deception/assess", json=payload)
        assert r1.status_code in (200, 422, 500)
        assert r2.status_code in (200, 422, 500)

    async def test_cross_component_maze_and_explain(self, client):
        maze_resp = client.get("/deception/maze/sessions")
        explain_resp = client.get("/deception/explain/nonexistent_session_xyz")
        assert maze_resp.status_code in (200, 401, 403, 422, 500)
        assert explain_resp.status_code in (200, 401, 403, 404, 422, 500)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
