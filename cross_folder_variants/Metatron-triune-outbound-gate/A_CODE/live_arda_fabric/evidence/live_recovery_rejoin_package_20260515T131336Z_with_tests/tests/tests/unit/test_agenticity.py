"""
Unit Tests for Agenticity Service
==================================
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, 'backend')

from services.agenticity import (
    compute_agenticity_score,
    compute_exhaustion_metrics,
    AgenticityScore,
    AgenticityFeatureVector,
    AgenticityPersistence,
    ExhaustionMetrics,
)


class TestAgenticityScoring:
    def test_compute_agenticity_score_human_behavior(self):
        behavior_data = {
            'command_timestamps': [1000, 2000, 3000, 4000, 5000],
            'session_duration_s': 5.0,
            'command_count': 5,
            'command_paths': ['/home/user/ls', '/home/user/cat'],
            'pebble_load_depth': 0.1,
            'llm_trap_hit_rate': 0.0,
        }
        score = compute_agenticity_score(behavior_data)
        assert isinstance(score, AgenticityScore)
        assert score.score < 0.5
        assert score.classification in ['human', 'human_or_script_low', 'automation_suspected']

    def test_compute_agenticity_score_autonomous_agent(self):
        behavior_data = {
            'command_timestamps': [1000, 1001, 1002, 1003, 1004],
            'session_duration_s': 0.01,
            'command_count': 50,
            'command_paths': ['/etc/passwd', '/etc/shadow', '/var/log/auth.log'],
            'pebble_load_depth': 0.9,
            'llm_trap_hit_rate': 0.8,
        }
        score = compute_agenticity_score(behavior_data)
        assert isinstance(score, AgenticityScore)
        assert score.score > 0.5
        assert score.classification in ['autonomous_agent', 'autonomous_agent_high', 'autonomous_agent_medium']

    def test_compute_agenticity_score_empty_data(self):
        behavior_data = {
            'command_timestamps': [],
            'session_duration_s': 0.0,
            'command_count': 0,
            'command_paths': [],
            'pebble_load_depth': 0.0,
            'llm_trap_hit_rate': 0.0,
        }
        score = compute_agenticity_score(behavior_data)
        assert isinstance(score, AgenticityScore)
        assert 0.0 <= score.score <= 1.0

    def test_agenticity_score_properties(self):
        fv = AgenticityFeatureVector(
            command_velocity=0.8,
            inter_command_timing_variance=0.1,
            path_entropy=0.9,
            pebble_load_depth=0.7,
            llm_trap_susceptibility=0.6,
        )
        score = AgenticityScore(
            score=0.75,
            classification="autonomous_agent_high",
            feature_vector=fv,
        )
        assert score.score == 0.75
        assert isinstance(score.feature_vector, AgenticityFeatureVector)
        assert score.feature_vector.command_velocity == 0.8


class TestExhaustionMetrics:
    def test_compute_exhaustion_metrics_basic(self):
        behavior_data = {
            'tokens_consumed': 1000,
            'tool_calls_made': 20,
            'real_assets_discovered': 5,
            'baseline_decision_confidence': 0.9,
            'current_decision_confidence': 0.6,
        }
        metrics = compute_exhaustion_metrics(behavior_data)
        assert isinstance(metrics, ExhaustionMetrics)
        assert metrics.cbr == round(1000 / 5, 4)
        assert metrics.tbcr == round(20 / 5, 4)
        assert metrics.cdi > 0.0

    def test_compute_exhaustion_metrics_no_real_assets(self):
        behavior_data = {
            'tokens_consumed': 500,
            'tool_calls_made': 10,
            'real_assets_discovered': 0,
            'baseline_decision_confidence': 1.0,
            'current_decision_confidence': 1.0,
        }
        metrics = compute_exhaustion_metrics(behavior_data)
        assert isinstance(metrics, ExhaustionMetrics)
        assert metrics.cdi == 0.0

    def test_exhaustion_metrics_to_dict(self):
        m = ExhaustionMetrics(
            cbr=200.0, tbcr=4.0, cdi=0.33,
            tokens_consumed=1000, tool_calls_made=20,
            real_assets_discovered=5,
            baseline_confidence=0.9, current_confidence=0.6,
        )
        d = m.to_dict()
        assert isinstance(d, dict)
        assert d['cbr'] == 200.0


@pytest.mark.asyncio
class TestAgenticityPersistence:

    @pytest_asyncio.fixture
    async def mock_db(self):
        db = AsyncMock()

        db.agenticity_scores = AsyncMock()
        db.agenticity_scores.replace_one = AsyncMock(return_value=Mock())
        scores_cursor = MagicMock()
        scores_cursor.sort = MagicMock(return_value=scores_cursor)
        scores_cursor.limit = MagicMock(return_value=scores_cursor)
        scores_cursor.to_list = AsyncMock(return_value=[
            {"session_id": "session_123", "score": 0.75}
        ])
        db.agenticity_scores.find = MagicMock(return_value=scores_cursor)
        db.agenticity_scores.find_one = AsyncMock(return_value={"session_id": "session_123", "score": 0.75})
        db.agenticity_scores.count_documents = AsyncMock(return_value=1)

        db.exhaustion_metrics = AsyncMock()
        db.exhaustion_metrics.replace_one = AsyncMock(return_value=Mock())
        ex_cursor = MagicMock()
        ex_cursor.sort = MagicMock(return_value=ex_cursor)
        ex_cursor.limit = MagicMock(return_value=ex_cursor)
        ex_cursor.to_list = AsyncMock(return_value=[])
        db.exhaustion_metrics.find = MagicMock(return_value=ex_cursor)
        db.exhaustion_metrics.find_one = AsyncMock(return_value=None)
        db.exhaustion_metrics.count_documents = AsyncMock(return_value=0)

        db.agenticity_sessions = AsyncMock()
        db.agenticity_sessions.replace_one = AsyncMock(return_value=Mock())
        db.agenticity_sessions.find_one = AsyncMock(return_value=None)

        return db

    async def test_save_score(self, mock_db):
        persistence = AgenticityPersistence(mock_db)
        fv = AgenticityFeatureVector(
            command_velocity=0.5, inter_command_timing_variance=0.3,
            path_entropy=0.7, pebble_load_depth=0.2, llm_trap_susceptibility=0.8,
        )
        score = AgenticityScore(score=0.75, classification="autonomous_agent_high", feature_vector=fv)
        result = await persistence.save_score(score, "session_123")
        assert result is True
        mock_db.agenticity_scores.replace_one.assert_called_once()

    async def test_save_exhaustion_metrics(self, mock_db):
        persistence = AgenticityPersistence(mock_db)
        metrics = ExhaustionMetrics(
            cbr=200.0, tbcr=4.0, cdi=0.33,
            tokens_consumed=1000, tool_calls_made=20,
            real_assets_discovered=5, baseline_confidence=0.9, current_confidence=0.6,
        )
        result = await persistence.save_exhaustion_metrics(metrics, "session_123")
        assert result is True
        mock_db.exhaustion_metrics.replace_one.assert_called_once()

    async def test_get_score_history(self, mock_db):
        persistence = AgenticityPersistence(mock_db)
        history = await persistence.get_score_history("session_123", limit=10)
        assert isinstance(history, list)
        assert len(history) == 1
        assert history[0]["session_id"] == "session_123"

    async def test_get_session_summary(self, mock_db):
        persistence = AgenticityPersistence(mock_db)
        summary = await persistence.get_session_summary("session_123")
        assert isinstance(summary, dict)
        assert summary["session_id"] == "session_123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
