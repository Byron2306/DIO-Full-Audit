"""
Unit Tests for Honey Tokens Service
=====================================
Tests aligned with actual HoneyTokenManager API.
"""
import pytest
from unittest.mock import Mock
from datetime import datetime, timezone

import sys
sys.path.insert(0, 'backend')

from honey_tokens import HoneyToken, HoneyTokenType, HoneyTokenManager, honey_token_manager


class TestHoneyToken:
    """Test HoneyToken dataclass."""

    def test_honey_token_creation(self):
        token = HoneyToken(
            id="token_123",
            name="Test Token",
            token_type=HoneyTokenType.API_KEY,
            token_value="sk-abc123xyz789",
            token_hash="deadbeef" * 8,
            description="Test API key",
            location=".env",
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test_user"
        )
        assert token.id == "token_123"
        assert token.name == "Test Token"
        assert token.token_type == HoneyTokenType.API_KEY
        assert token.access_count == 0
        assert token.is_active is True
        assert token.last_accessed is None

    def test_honey_token_defaults(self):
        token = HoneyToken(
            id="t1", name="T1", token_type=HoneyTokenType.PASSWORD,
            token_value="secret", token_hash="hash",
            description="desc", location="loc",
            created_at="2024-01-01T00:00:00+00:00", created_by="sys"
        )
        assert token.access_count == 0
        assert token.alerts_enabled is True
        assert isinstance(token.metadata, dict)


class TestHoneyTokenManager:
    """Test HoneyTokenManager functionality."""

    @pytest.fixture
    def manager(self):
        return HoneyTokenManager()

    def test_manager_init_has_sample_tokens(self, manager):
        """Manager starts with pre-loaded sample tokens."""
        tokens = manager.get_tokens()
        assert len(tokens) >= 4  # 4 sample tokens

    def test_create_token_api_key(self, manager):
        result = manager.create_token(
            name="Test API Key",
            token_type=HoneyTokenType.API_KEY.value,
            description="Test",
            location=".env",
            created_by="test"
        )
        assert isinstance(result, dict)
        assert result["token_type"] == HoneyTokenType.API_KEY.value
        assert result["name"] == "Test API Key"

    def test_create_token_database_cred(self, manager):
        result = manager.create_token(
            name="DB Creds",
            token_type=HoneyTokenType.DATABASE_CRED.value,
            description="Fake DB",
            location="/etc/db.conf",
            created_by="test"
        )
        assert result["token_type"] == HoneyTokenType.DATABASE_CRED.value

    def test_create_token_aws_key(self, manager):
        result = manager.create_token(
            name="AWS Key",
            token_type=HoneyTokenType.AWS_KEY.value,
            description="Fake AWS",
            location="~/.aws/credentials",
            created_by="test"
        )
        assert result["token_value"].startswith("AKIA")

    def test_create_token_invalid_type(self, manager):
        with pytest.raises((ValueError, KeyError)):
            manager.create_token(
                name="Bad",
                token_type="invalid_type_xyz",
                description="Bad",
                location=".",
                created_by="test"
            )

    def test_get_tokens_returns_list(self, manager):
        tokens = manager.get_tokens()
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert "id" in tokens[0]
        assert "name" in tokens[0]
        assert "token_type" in tokens[0]

    def test_get_tokens_masks_values_by_default(self, manager):
        tokens = manager.get_tokens(include_values=False)
        for t in tokens:
            assert "..." in t["token_value"]

    def test_get_tokens_includes_values_when_requested(self, manager):
        tokens = manager.get_tokens(include_values=True)
        for t in tokens:
            assert "..." not in t["token_value"]

    def test_get_token_found(self, manager):
        tokens = manager.get_tokens(include_values=True)
        first_id = tokens[0]["id"]
        result = manager.get_token(first_id)
        assert result is not None
        assert result["id"] == first_id

    def test_get_token_not_found(self, manager):
        result = manager.get_token("nonexistent_id_xyz")
        assert result is None

    def test_record_access(self, manager):
        tokens = manager.get_tokens()
        token_id = tokens[0]["id"]

        access = manager.record_access(token_id, "192.168.1.100", user_agent="TestAgent")

        assert access.token_id == token_id
        assert access.source_ip == "192.168.1.100"
        assert access.user_agent == "TestAgent"
        assert access.severity == "critical"

        updated = manager.get_token(token_id)
        assert updated["access_count"] == 1
        assert updated["last_accessed"] is not None

    def test_record_access_invalid_token(self, manager):
        with pytest.raises(ValueError):
            manager.record_access("no_such_token", "127.0.0.1")

    def test_get_accesses_all(self, manager):
        tokens = manager.get_tokens()
        token_id = tokens[0]["id"]
        manager.record_access(token_id, "10.0.0.1")
        manager.record_access(token_id, "10.0.0.2")

        accesses = manager.get_accesses()
        assert len(accesses) >= 2

    def test_get_accesses_filtered_by_token(self, manager):
        tokens = manager.get_tokens()
        token_id = tokens[0]["id"]
        manager.record_access(token_id, "10.0.0.1")

        accesses = manager.get_accesses(token_id=token_id)
        assert all(a["token_id"] == token_id for a in accesses)

    def test_check_token_matches(self, manager):
        """check_token finds the token when the real value is used."""
        tokens = manager.get_tokens(include_values=True)
        first_value = tokens[0]["token_value"]
        result = manager.check_token(first_value)
        assert result is not None

    def test_check_token_no_match(self, manager):
        result = manager.check_token("totally_fake_value_xyz_123")
        assert result is None

    def test_delete_token(self, manager):
        result = manager.create_token(
            name="Delete Me", token_type=HoneyTokenType.API_KEY.value,
            description="temp", location="temp", created_by="test"
        )
        token_id = result["id"]
        assert manager.delete_token(token_id) is True
        assert manager.get_token(token_id) is None

    def test_delete_nonexistent_token(self, manager):
        assert manager.delete_token("no_such_id") is False

    def test_toggle_token(self, manager):
        tokens = manager.get_tokens()
        token_id = tokens[0]["id"]
        initial_active = tokens[0]["is_active"]

        toggled = manager.toggle_token(token_id)
        assert toggled["is_active"] != initial_active

        # Toggle back
        restored = manager.toggle_token(token_id)
        assert restored["is_active"] == initial_active

    def test_get_stats(self, manager):
        stats = manager.get_stats()
        assert isinstance(stats, dict)
        assert "total_tokens" in stats
        assert "active_tokens" in stats

    def test_singleton(self):
        """honey_token_manager global instance exists."""
        assert honey_token_manager is not None
        assert isinstance(honey_token_manager, HoneyTokenManager)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
