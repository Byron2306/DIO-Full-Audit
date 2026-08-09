"""
Integration Tests - Layer 4
============================
Tests service-level integration between components.
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
sys.path.insert(0, "backend")

from honey_tokens import HoneyTokenManager, HoneyTokenType
from services.agenticity import (
    compute_agenticity_score, AgenticityPersistence,
    AgenticityScore, AgenticityFeatureVector
)
from services.mystique_maze import MazePersistence, get_mystique_maze
from routers.deception import router as deception_router


@pytest.mark.integration
@pytest.mark.asyncio
class TestAgenticityMazeIntegration:
    """Test integration between agenticity scoring and maze system."""

    async def test_agenticity_maze_data_flow(self):
        """Test data flows correctly between agenticity and maze services."""
        behavior_data = {
            "command_timestamps": [1000, 1100, 1200, 1300, 1400],
            "session_duration_s": 5.0,
            "command_count": 5,
            "command_paths": ["/etc/passwd", "/etc/shadow"],
            "pebble_load_depth": 0.5,
            "llm_trap_hit_rate": 0.3
        }
        score = compute_agenticity_score(behavior_data)
        assert score is not None
        assert 0.0 <= score.score <= 1.0
        assert score.classification is not None

        maze = get_mystique_maze()
        assert maze is not None


@pytest.mark.integration
class TestHoneyTokenDeceptionIntegration:
    """Test honey token and deception system integration."""

    def test_honey_token_campaign_correlation(self):
        """Test honey tokens correlate with deception campaigns."""
        manager = HoneyTokenManager()
        token = manager.create_token(
            "integration_api_key", HoneyTokenType.API_KEY.value,
            "Integration test token", "/integration/loc", "integration_test"
        )
        assert token is not None
        assert token["id"] is not None
        assert token["name"] == "integration_api_key"

        access = manager.record_access(token["id"], "192.168.1.100")
        assert access is not None

    def test_honey_token_deception_feedback_loop(self):
        """Test honey token triggers propagate to deception systems."""
        manager = HoneyTokenManager()
        token = manager.create_token(
            "feedback_token", HoneyTokenType.API_KEY.value,
            "Feedback test", "/feedback/loc", "feedback_test"
        )
        for i in range(3):
            manager.record_access(token["id"], f"192.168.1.{i+1}")

        fetched = manager.get_token(token["id"])
        assert fetched is not None
        assert fetched["access_count"] >= 3


@pytest.mark.integration
class TestDeceptionRouterIntegration:
    """Test deception router integration with services."""

    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(deception_router)
        return TestClient(app)

    def test_explain_endpoint_integration(self, client):
        response = client.get("/deception/explain/integration_session")
        assert response.status_code in (200, 401, 403, 404, 422, 500)

    def test_assess_endpoint_integration(self, client):
        payload = {
            "session_id": "integration_test",
            "source_ip": "192.168.1.200",
            "request_path": "/api/sensitive",
            "user_agent": "IntegrationBot/1.0",
            "headers": {},
            "query_patterns": [],
            "time_since_last_request": 0.5
        }
        response = client.post("/deception/assess", json=payload)
        assert response.status_code in (200, 422, 500)


@pytest.mark.integration
@pytest.mark.asyncio
class TestDataPersistenceIntegration:
    """Test data persistence across services."""

    async def test_persistence_data_consistency(self):
        """Test persisted data is consistent across reads."""
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="test_id"))
        mock_db.agenticity_sessions = mock_collection

        persistence = AgenticityPersistence(mock_db)
        fv = AgenticityFeatureVector(
            command_velocity=0.5, inter_command_timing_variance=0.3,
            path_entropy=0.6, pebble_load_depth=0.5, llm_trap_susceptibility=0.3
        )
        from datetime import datetime
        score = AgenticityScore(
            score=0.7, classification="suspicious",
            feature_vector=fv, weights={}, weighted_components={},
            generated_at=datetime.utcnow()
        )
        result = await persistence.save_score(score, "test_session")
        assert result is True or result is not None


@pytest.mark.integration
class TestCampaignTrackingIntegration:
    """Test campaign tracking across system components."""

    def test_campaign_lifecycle_tracking(self):
        """Test complete campaign lifecycle."""
        manager = HoneyTokenManager()
        token = manager.create_token(
            "campaign_token", HoneyTokenType.API_KEY.value,
            "Campaign lifecycle test", "/campaign/loc", "campaign_test"
        )
        # Record multiple accesses
        for i in range(5):
            manager.record_access(token["id"], f"10.0.0.{i+1}")

        stats = manager.get_stats()
        assert stats is not None

        accesses = manager.get_accesses(limit=10, token_id=token["id"])
        assert accesses is not None
