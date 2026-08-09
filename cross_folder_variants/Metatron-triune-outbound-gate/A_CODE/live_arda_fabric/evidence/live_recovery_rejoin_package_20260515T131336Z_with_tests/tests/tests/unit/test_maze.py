"""
Unit Tests for Mystique Maze Service
====================================

Tests the mirror world maze generation and persistence functionality.
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# Add backend to path for imports
import sys
sys.path.insert(0, 'backend')

from services.mystique_maze import (
    MazeNode,
    MazeState,
    MazePersistence,
    get_maze_persistence,
    NodeType,
    MazeTier,
    ProbeIntent
)


@pytest_asyncio.fixture
async def mock_db():
    """Mock MongoDB database."""
    db = AsyncMock()
    db.maze_states = AsyncMock()
    db.maze_states.replace_one = AsyncMock(return_value=Mock(modified_count=1))
    db.maze_states.find_one = AsyncMock(return_value={
        "_id": "maze_123",
        "maze_id": "maze_123",
        "session_id": "session_123",
        "campaign_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_probe_at": None,
        "tier": "surface",
        "inferred_intent": "unknown",
        "nodes": {
            "node_1": {
                "node_id": "node_1",
                "node_type": "file",
                "label": "Test deceptive file",
                "payload": {"content": "fake file content"},
                "depth": 1,
                "children": [],
                "accessed": False,
                "accessed_at": None,
                "access_count": 0
            }
        },
        "root_node_ids": ["node_1"],
        "probes": [],
        "total_probes": 0,
        "total_bytes_consumed": 0
    })
    db.maze_sessions.update_one = AsyncMock(return_value=Mock(modified_count=1))
    return db


@pytest.mark.asyncio
class TestMazePersistence:
    """Test MazeNode dataclass functionality."""

    def test_maze_node_creation(self):
        """Test creating a maze node."""
        node = MazeNode(
            node_id="node_1",
            node_type=NodeType.FILE,
            label="Test deceptive file",
            payload={"content": "fake file content"},
            depth=1
        )

        assert node.node_id == "node_1"
        assert node.node_type == NodeType.FILE
        assert node.label == "Test deceptive file"
        assert node.payload == {"content": "fake file content"}
        assert node.depth == 1
        assert node.children == []
        assert node.accessed == False
        assert node.access_count == 0

    def test_maze_node_defaults(self):
        """Test maze node default values."""
        node = MazeNode(
            node_id="node_1",
            node_type=NodeType.CREDENTIAL,
            label="Test credential",
            payload={"username": "fakeuser", "password": "fakepass"},
            depth=1
        )

        assert node.accessed == False
        assert node.accessed_at is None
        assert node.access_count == 0
        assert node.children == []


class TestMazeState:
    """Test MazeState dataclass functionality."""

    def test_maze_state_creation(self):
        """Test creating a maze state."""
        nodes = {
            "node_1": MazeNode(
                node_id="node_1",
                node_type=NodeType.FILE,
                label="Content 1",
                payload={"content": "Content 1"},
                depth=1
            ),
            "node_2": MazeNode(
                node_id="node_2",
                node_type=NodeType.CREDENTIAL,
                label="Content 2",
                payload={"username": "user", "password": "pass"},
                depth=2
            )
        }

        state = MazeState(
            maze_id="maze_123",
            session_id="session_123",
            campaign_id="campaign_456",
            created_at=datetime.now(timezone.utc).isoformat(),
            last_probe_at=None,
            nodes=nodes,
            root_node_ids=["node_1"],
            tier=MazeTier.SHALLOW,
            inferred_intent=ProbeIntent.CREDENTIAL_HUNT
        )

        assert state.maze_id == "maze_123"
        assert state.session_id == "session_123"
        assert state.campaign_id == "campaign_456"
        assert len(state.nodes) == 2
        assert state.tier == MazeTier.SHALLOW
        assert state.inferred_intent == ProbeIntent.CREDENTIAL_HUNT

    def test_maze_state_defaults(self):
        """Test maze state default values."""
        state = MazeState(
            maze_id="maze_123",
            session_id="session_123",
            campaign_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_probe_at=None
        )

        assert state.tier == MazeTier.SURFACE
        assert state.inferred_intent == ProbeIntent.UNKNOWN
        assert state.nodes == {}
        assert state.root_node_ids == []
        assert state.probes == []
        assert state.total_probes == 0
        assert state.total_bytes_consumed == 0


@pytest.mark.asyncio
class TestMazePersistence:
    """Test MongoDB persistence for maze data."""

    async def test_save_maze_state(self, mock_db):
        """Test saving maze state to database."""
        persistence = MazePersistence(mock_db)

        nodes = {
            "node_1": MazeNode(
                node_id="node_1",
                node_type=NodeType.FILE,
                label="Test file",
                payload={"content": "Test content"},
                depth=1
            )
        }
        state = MazeState(
            maze_id="maze_123",
            session_id="session_123",
            campaign_id=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_probe_at=None,
            nodes=nodes,
            root_node_ids=["node_1"]
        )

        result = await persistence.save_maze_state(state)

        assert result is True
        mock_db.maze_states.replace_one.assert_called_once()

    async def test_get_maze_state(self, mock_db):
        """Test retrieving maze state from database."""
        persistence = MazePersistence(mock_db)

        state = await persistence.load_maze_state("maze_123")

        assert state is not None
        assert state.maze_id == "maze_123"
        assert state.session_id == "session_123"
        assert len(state.nodes) == 1
        assert "node_1" in state.nodes
        mock_db.maze_states.find_one.assert_called_once()


class TestMazePersistenceSingleton:
    """Test the singleton pattern for MazePersistence."""

    def test_get_maze_persistence_singleton(self):
        """Test that get_maze_persistence returns a singleton."""
        from services.mystique_maze import get_maze_persistence
        import services.mystique_maze
        
        # Reset the global singleton for testing
        services.mystique_maze._maze_persistence = None
        
        mock_db = AsyncMock()
        
        # First call with db
        persistence1 = get_maze_persistence(mock_db)
        # Second call without db (should return same instance)
        persistence2 = get_maze_persistence()

        # Should be the same instance
        assert persistence1 is persistence2
        assert isinstance(persistence1, MazePersistence)


@pytest.mark.asyncio
class TestMazeGeneration:
    """Test maze generation logic."""

    async def test_generate_tiered_nodes(self):
        """Test generating nodes by tier."""
        from services.mystique_maze import MystiqueMaze

        builder = MystiqueMaze()
        builder.set_persistence(AsyncMock())  # Mock persistence

        # Test building initial maze
        maze = await builder.get_or_create_maze("session_123", agenticity_score=0.5)

        assert maze.maze_id.startswith("mz-")
        assert maze.session_id == "session_123"
        assert len(maze.nodes) > 0
        assert len(maze.root_node_ids) > 0

        # Check that root nodes exist
        for root_id in maze.root_node_ids:
            assert root_id in maze.nodes

    async def test_generate_maze_structure(self):
        """Test generating complete maze structure."""
        from services.mystique_maze import MystiqueMaze

        builder = MystiqueMaze()
        builder.set_persistence(AsyncMock())  # Mock persistence

        maze_state = await builder.get_or_create_maze("session_456", agenticity_score=0.8)

        assert maze_state.session_id == "session_456"
        assert maze_state.maze_id is not None
        assert len(maze_state.nodes) > 0

        # Check that all nodes have proper structure
        for node in maze_state.nodes.values():
            assert node.node_id is not None
            assert node.node_type is not None
            assert node.label is not None
            assert node.payload is not None
            assert node.depth >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])