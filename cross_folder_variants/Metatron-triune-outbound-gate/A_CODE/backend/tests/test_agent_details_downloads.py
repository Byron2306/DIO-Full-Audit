"""
Test suite for Agent Details page, Agent Downloads, and WebSocket features
Tests iteration 14 features:
- Agent Details page at /agent-commands/{agentId}
- Agent download endpoints (advanced-agent and installer)
- Quick Actions command creation
- Agent Commands page Details button navigation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestAgentDownloads:
    """Test agent download endpoints"""
    
    def test_download_advanced_agent_redirects_to_unified(self):
        """GET /api/agent/download/advanced-agent now redirects to the unified agent download"""
        response = requests.get(f"{BASE_URL}/api/agent/download/advanced-agent", allow_redirects=False)
        # Expect a redirect (307/308/301/302) to the unified agent download
        assert response.status_code in (301, 302, 307, 308), (
            f"Expected redirect, got {response.status_code}"
        )
        location = response.headers.get("location", "")
        assert "unified" in location or "agent/download" in location, (
            f"Redirect location unexpected: {location}"
        )
        print("SUCCESS: advanced-agent endpoint redirects to unified agent download")
    
    def test_download_defender_installer(self):
        """GET /api/agent/download/installer returns defender installer script"""
        response = requests.get(f"{BASE_URL}/api/agent/download/installer")
        
        assert response.status_code == 200
        assert "text/x-python" in response.headers.get("content-type", "")
        
        # Verify it's the defender installer
        content = response.text
        assert "defender" in content.lower() or "install" in content.lower()
        assert "def " in content  # Contains Python functions
        print("SUCCESS: Defender installer download returns valid Python script")
    
    def test_download_content_disposition(self):
        """Installer endpoint sets correct Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/agent/download/installer")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "defender_installer.py" in response.headers.get("content-disposition", "")
        print("SUCCESS: Installer download endpoint sets correct Content-Disposition header")


class TestAgentCommandsAPI:
    """Test Agent Commands API endpoints"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testadmin@test.com",
            "password": "TestPassword123!"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_get_agents_status(self, auth_headers):
        """GET /api/agent-commands/agents/status returns registered agents"""
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)
        print(f"SUCCESS: Found {len(data['agents'])} registered agents")
    
    def test_get_connected_agents(self, auth_headers):
        """GET /api/agent-commands/agents/connected returns connected agents"""
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/connected",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        print(f"SUCCESS: Found {len(data['agents'])} connected agents")
    
    def test_get_command_types(self, auth_headers):
        """GET /api/agent-commands/types returns available command types"""
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/types",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "command_types" in data
        
        # Verify expected command types exist
        command_types = data["command_types"]
        expected_types = ["full_scan", "collect_forensics", "update_agent", "restart_service"]
        for cmd_type in expected_types:
            assert cmd_type in command_types, f"Missing command type: {cmd_type}"
        
        print(f"SUCCESS: Found {len(command_types)} command types")
    
    def test_get_pending_commands(self, auth_headers):
        """GET /api/agent-commands/pending returns pending commands"""
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/pending",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        print(f"SUCCESS: Found {len(data['commands'])} pending commands")
    
    def test_get_command_history(self, auth_headers):
        """GET /api/agent-commands/history returns command history"""
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/history?limit=50",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        print(f"SUCCESS: Found {len(data['commands'])} commands in history")
    
    def test_create_command(self, auth_headers):
        """POST /api/agent-commands/create creates a new command"""
        # First get an agent ID
        agents_response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/status",
            headers=auth_headers
        )
        agents = agents_response.json().get("agents", [])
        
        if not agents:
            pytest.skip("No agents available for testing")
        
        agent_id = agents[0]["agent_id"]
        
        # Create a command
        response = requests.post(
            f"{BASE_URL}/api/agent-commands/create",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "command_type": "full_scan",
                "parameters": {"scan_types": ["processes", "files"]},
                "priority": "medium"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "command_id" in data or "id" in data
        print(f"SUCCESS: Created command for agent {agent_id}")
    
    def test_get_agent_alerts(self, auth_headers):
        """GET /api/agent-commands/agents/{agentId}/alerts returns agent alerts"""
        # First get an agent ID
        agents_response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/status",
            headers=auth_headers
        )
        agents = agents_response.json().get("agents", [])
        
        if not agents:
            pytest.skip("No agents available for testing")
        
        agent_id = agents[0]["agent_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/{agent_id}/alerts",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        print(f"SUCCESS: Retrieved alerts for agent {agent_id}")
    
    def test_get_agent_scan_results(self, auth_headers):
        """GET /api/agent-commands/agents/{agentId}/scan-results returns scan results"""
        # First get an agent ID
        agents_response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/status",
            headers=auth_headers
        )
        agents = agents_response.json().get("agents", [])
        
        if not agents:
            pytest.skip("No agents available for testing")
        
        agent_id = agents[0]["agent_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/{agent_id}/scan-results",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        print(f"SUCCESS: Retrieved scan results for agent {agent_id}")


class TestAgentDetailsPageData:
    """Test data required for Agent Details page"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testadmin@test.com",
            "password": "TestPassword123!"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_agent_details_data_available(self, auth_headers):
        """Verify all data needed for Agent Details page is available"""
        # Get agents
        agents_response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/status",
            headers=auth_headers
        )
        assert agents_response.status_code == 200
        agents = agents_response.json().get("agents", [])
        
        if not agents:
            pytest.skip("No agents available for testing")
        
        agent = agents[0]
        agent_id = agent["agent_id"]
        
        # Verify agent has required fields for details page
        required_fields = ["agent_id", "hostname", "os", "ip_address"]
        for field in required_fields:
            assert field in agent, f"Agent missing required field: {field}"
        
        # Get alerts for agent
        alerts_response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/{agent_id}/alerts",
            headers=auth_headers
        )
        assert alerts_response.status_code == 200
        
        # Get scan results for agent
        scans_response = requests.get(
            f"{BASE_URL}/api/agent-commands/agents/{agent_id}/scan-results",
            headers=auth_headers
        )
        assert scans_response.status_code == 200
        
        # Get command history for agent
        history_response = requests.get(
            f"{BASE_URL}/api/agent-commands/history?agent_id={agent_id}",
            headers=auth_headers
        )
        assert history_response.status_code == 200
        
        print(f"SUCCESS: All Agent Details page data available for agent {agent_id}")
    
    def test_quick_actions_command_types_available(self, auth_headers):
        """Verify Quick Actions command types are available"""
        response = requests.get(
            f"{BASE_URL}/api/agent-commands/types",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        command_types = response.json().get("command_types", {})
        
        # Quick Actions buttons: Full Scan, Collect Forensics, Update Agent, Restart Service
        quick_action_types = ["full_scan", "collect_forensics", "update_agent", "restart_service"]
        
        for action_type in quick_action_types:
            assert action_type in command_types, f"Missing Quick Action type: {action_type}"
            
            # Verify command type has required info
            cmd_info = command_types[action_type]
            assert "name" in cmd_info
            assert "risk_level" in cmd_info
        
        print("SUCCESS: All Quick Action command types available")


class TestAgentsPageAPI:
    """Test Agents page API endpoints"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testadmin@test.com",
            "password": "TestPassword123!"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Authentication failed")
    
    def test_get_agents_list(self, auth_headers):
        """GET /api/agents returns list of agents"""
        response = requests.get(
            f"{BASE_URL}/api/agents",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: Found {len(data)} agents in agents list")
    
    def test_get_discovered_hosts(self, auth_headers):
        """GET /api/network/discovered-hosts returns discovered hosts"""
        response = requests.get(
            f"{BASE_URL}/api/network/discovered-hosts",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        # Response can be a list or an object with hosts key
        if isinstance(data, dict):
            assert "hosts" in data
            hosts = data["hosts"]
        else:
            hosts = data
        assert isinstance(hosts, list)
        print(f"SUCCESS: Found {len(hosts)} discovered hosts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
