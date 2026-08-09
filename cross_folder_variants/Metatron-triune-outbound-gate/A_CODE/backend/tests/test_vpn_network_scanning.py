"""
Test VPN and Network Scanning Features - Iteration 22 (updated for Unified Agent)
Tests:
- GET /api/swarm/vpn/server-config - VPN server config with split_tunnel=true
- POST /api/swarm/vpn/register-agent - Register agent for VPN access
- GET /api/swarm/vpn/agents - List registered VPN agents
- GET /api/swarm/agent/download/v7 - Unified agent tarball (seraph_defender_v7 removed)
- Verify unified agent core/agent.py exists on disk
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestVPNEndpoints:
    """Test VPN configuration and registration endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_vpn_server_config_returns_split_tunnel(self):
        """GET /api/swarm/vpn/server-config should return split_tunnel=true"""
        response = self.session.get(f"{BASE_URL}/api/swarm/vpn/server-config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify split tunnel mode is enabled
        assert data.get("split_tunnel") == True, f"Expected split_tunnel=True, got {data.get('split_tunnel')}"
        # Verify allowed_ips is only Seraph network (not 0.0.0.0/0)
        assert data.get("allowed_ips") == "10.200.200.0/24", f"Expected 10.200.200.0/24, got {data.get('allowed_ips')}"
        # Verify note mentions split tunnel
        assert "split tunnel" in data.get("note", "").lower() or "not affected" in data.get("note", "").lower(), \
            f"Note should mention split tunnel: {data.get('note')}"
        print(f"✓ VPN server config: split_tunnel={data.get('split_tunnel')}, allowed_ips={data.get('allowed_ips')}")
    
    def test_vpn_register_agent(self):
        """POST /api/swarm/vpn/register-agent should register agent and assign IP"""
        test_agent_id = "test-vpn-agent-001"
        test_public_key = "test-public-key-base64=="
        
        response = self.session.post(f"{BASE_URL}/api/swarm/vpn/register-agent", json={
            "agent_id": test_agent_id,
            "agent_public_key": test_public_key
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "registered", f"Expected status=registered, got {data.get('status')}"
        assert data.get("agent_id") == test_agent_id, f"Expected agent_id={test_agent_id}, got {data.get('agent_id')}"
        # Verify assigned IP is in the 10.200.200.x range
        assigned_ip = data.get("assigned_ip", "")
        assert assigned_ip.startswith("10.200.200."), f"Expected IP in 10.200.200.x range, got {assigned_ip}"
        print(f"✓ VPN agent registered: agent_id={test_agent_id}, assigned_ip={assigned_ip}")
    
    def test_vpn_list_agents(self):
        """GET /api/swarm/vpn/agents should list registered VPN agents"""
        response = self.session.get(f"{BASE_URL}/api/swarm/vpn/agents")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "agents" in data, "Response should contain 'agents' key"
        assert "count" in data, "Response should contain 'count' key"
        assert isinstance(data["agents"], list), "agents should be a list"
        print(f"✓ VPN agents list: count={data.get('count')}")


class TestAgentDownloadV7:
    """Test that /api/swarm/agent/download/v7 now serves the unified agent tarball."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
    
    def test_agent_download_v7_returns_tarball(self):
        """GET /api/swarm/agent/download/v7 should return unified agent tarball"""
        response = self.session.get(f"{BASE_URL}/api/swarm/agent/download/v7")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        content_type = response.headers.get("Content-Type", "")
        assert (
            "gzip" in content_type
            or "octet-stream" in content_type
            or "zip" in content_type
            or "tar" in content_type
        ), f"Expected archive content type, got {content_type}"
        
        assert len(response.content) > 100, "Response should be non-empty archive"
        print(f"✓ Agent v7 download alias returns unified agent archive: {len(response.content)} bytes")
    
    def test_agent_v7_download_url_documented_in_installer(self):
        """The new Windows installer should reference the unified agent download endpoint"""
        bat_path = "/app/scripts/install_seraph_windows.bat"
        if not os.path.exists(bat_path):
            pytest.skip("Batch installer not mounted at /app/scripts")
        with open(bat_path, "r") as f:
            content = f.read()
        assert "unified/agent/download" in content, (
            "Windows installer should download from /api/unified/agent/download/windows"
        )
        print("✓ Windows installer references unified agent download endpoint")


class TestUnifiedAgentFileOnDisk:
    """Verify the unified agent file is present on disk (replaces TestSeraphDefenderV7File)."""

    UNIFIED_AGENT_PATH = "/app/unified_agent/core/agent.py"

    def test_unified_agent_exists(self):
        """unified_agent/core/agent.py should exist and be the canonical agent"""
        assert os.path.exists(self.UNIFIED_AGENT_PATH), (
            f"Unified agent not found at {self.UNIFIED_AGENT_PATH}"
        )
        print(f"✓ Unified agent exists at {self.UNIFIED_AGENT_PATH}")

    def test_unified_agent_is_substantial(self):
        """Unified agent should be a large, comprehensive file (>14000 lines)"""
        with open(self.UNIFIED_AGENT_PATH, "r", errors="replace") as f:
            lines = f.readlines()
        assert len(lines) > 14000, (
            f"Expected >14000 lines, got {len(lines)}"
        )
        print(f"✓ Unified agent has {len(lines)} lines")

    def test_mini_agents_removed(self):
        """Legacy mini-agent files should no longer exist in /app/scripts"""
        deleted = [
            "/app/scripts/seraph_defender_v7.py",
            "/app/scripts/seraph_defender.py",
            "/app/scripts/seraph_defender_local.py",
            "/app/scripts/seraph_mobile_v7.py",
            "/app/scripts/seraph_mobile_agent.py",
            "/app/scripts/advanced_agent.py",
            "/app/scripts/agent.py",
            "/app/scripts/local_agent.py",
            "/app/scripts/anti_ai_defense.py",
            "/app/scripts/seraph_network_scanner.py",
        ]
        for path in deleted:
            assert not os.path.exists(path), (
                f"Mini-agent {path} should have been removed; only the unified agent should exist"
            )
        print(f"✓ All {len(deleted)} legacy mini-agent files have been removed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
