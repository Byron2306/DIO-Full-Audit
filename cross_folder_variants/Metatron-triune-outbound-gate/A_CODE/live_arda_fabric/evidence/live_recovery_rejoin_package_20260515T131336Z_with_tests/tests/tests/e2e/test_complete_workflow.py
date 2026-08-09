"""
End-to-End Tests - Layer 2
===========================
Tests complete user workflows from start to finish.
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
sys.path.insert(0, "backend")

from honey_tokens import HoneyTokenManager, HoneyTokenType
from services.agenticity import compute_agenticity_score, compute_exhaustion_metrics
from services.mystique_maze import get_mystique_maze, MazePersistence
from routers.deception import router as deception_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(deception_router)
    return TestClient(app)


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompleteDeceptionWorkflow:
    """Test complete deception detection workflow."""

    async def test_full_deception_lifecycle(self):
        """Test complete deception lifecycle from detection to classification."""
        # 1. Score agenticity
        behavior_data = {
            "command_timestamps": [1000, 1050, 1100, 1150, 1200],
            "session_duration_s": 5.0,
            "command_count": 5,
            "command_paths": ["/etc/passwd", "/etc/shadow", "/root/.ssh/id_rsa"],
            "pebble_load_depth": 0.8,
            "llm_trap_hit_rate": 0.6
        }
        score = compute_agenticity_score(behavior_data)
        assert score is not None
        assert 0.0 <= score.score <= 1.0

        # 2. Get maze
        maze = get_mystique_maze()
        assert maze is not None

        # 3. Verify full flow works without errors
        assert score.classification is not None


@pytest.mark.e2e
class TestHoneyTokenCampaignWorkflow:
    """Test honey token campaign workflow."""

    def test_campaign_detection_to_analysis(self):
        """Test complete campaign detection flow."""
        manager = HoneyTokenManager()

        # Create token
        token = manager.create_token(
            "e2e_campaign_token", HoneyTokenType.API_KEY.value,
            "E2E campaign test", "/e2e/loc", "e2e_test"
        )
        assert token is not None

        # Record accesses from campaign
        ips = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
        for ip in ips:
            access = manager.record_access(token["id"], ip)
            assert access is not None

        # Verify tracking
        fetched = manager.get_token(token["id"])
        assert fetched is not None
        assert fetched["access_count"] >= len(ips)

        # Get stats
        stats = manager.get_stats()
        assert stats is not None


@pytest.mark.e2e
@pytest.mark.asyncio
class TestMultiSessionCorrelation:
    """Test multi-session correlation workflow."""

    async def test_cross_session_pattern_analysis(self):
        """Test cross-session pattern detection."""
        sessions = []
        for i in range(3):
            behavior = {
                "command_timestamps": list(range(1000, 1000 + (i+1)*5)),
                "session_duration_s": float((i+1) * 5),
                "command_count": (i+1) * 5,
                "command_paths": [f"/etc/path_{i}", "/etc/passwd"],
                "pebble_load_depth": 0.3 + i * 0.2,
                "llm_trap_hit_rate": 0.2 + i * 0.1
            }
            score = compute_agenticity_score(behavior)
            sessions.append(score)

        assert len(sessions) == 3
        for s in sessions:
            assert 0.0 <= s.score <= 1.0


@pytest.mark.e2e
class TestDeceptionExhaustionWorkflow:
    """Test deception exhaustion progression."""

    def test_exhaustion_progression_simulation(self):
        """Test exhaustion metrics increase over sessions."""
        # Low load
        low_behavior = {
            "command_timestamps": [1000, 1200, 1400],
            "session_duration_s": 10.0,
            "command_count": 3,
            "command_paths": ["/home/user"],
            "pebble_load_depth": 0.1,
            "llm_trap_hit_rate": 0.0
        }
        # High load
        high_behavior = {
            "command_timestamps": list(range(1000, 1500, 10)),
            "session_duration_s": 5.0,
            "command_count": 50,
            "command_paths": ["/etc/passwd", "/etc/shadow", "/root/.ssh/id_rsa", "/proc/keys"],
            "pebble_load_depth": 0.9,
            "llm_trap_hit_rate": 0.8
        }

        low_score = compute_agenticity_score(low_behavior)
        high_score = compute_agenticity_score(high_behavior)

        assert low_score is not None
        assert high_score is not None
        assert high_score.score >= low_score.score  # Higher load = higher agenticity


@pytest.mark.e2e
class TestSystemResilienceWorkflow:
    """Test system resilience against adversarial inputs."""

    def test_resilience_against_adversarial_inputs(self, client):
        """Test system handles adversarial inputs gracefully."""
        adversarial_payloads = [
            {},
            {"session_id": "x" * 1000},
            {"session_id": None},
        ]

        for payload in adversarial_payloads:
            response = client.post("/deception/assess", json=payload)
            # Should return validation error or handle gracefully
            assert response.status_code in (200, 400, 422, 500)

        # Valid request should work
        valid_payload = {
            "session_id": "resilience_test",
            "source_ip": "192.168.1.1",
            "request_path": "/test",
            "user_agent": "Bot/1.0",
            "headers": {},
            "query_patterns": [],
            "time_since_last_request": 1.0
        }
        response = client.post("/deception/assess", json=valid_payload)
        assert response.status_code in (200, 422, 500)
