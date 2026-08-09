"""
Test Command Center, Network Topology, and Critical Alerts Features
Tests for iteration 19 - Command Center UI, Network Topology with Live Threats, Critical Alerts
"""
import pytest
import requests
import os
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestAuthentication:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        return data["access_token"]


class TestCriticalAlertsEndpoints:
    """Test critical alerts endpoints for auto-kill notifications"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_post_critical_alert(self):
        """Test POST /api/swarm/alerts/critical - receive auto-kill notification"""
        alert_data = {
            "alert_type": "AUTO_KILL_EXECUTED",
            "severity": "critical",
            "agent_id": "test-agent-001",
            "host_id": "test-host-001",
            "threat_id": f"threat-test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "threat_title": "Credential Theft Attempt",
            "threat_type": "credential_theft",
            "message": "Process mimikatz.exe was automatically terminated",
            "evidence": {
                "process_name": "mimikatz.exe",
                "pid": 12345,
                "user": "SYSTEM"
            },
            "remediation_action": "process_killed",
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(f"{BASE_URL}/api/swarm/alerts/critical", json=alert_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "received"
        assert data.get("alert_type") == "AUTO_KILL_EXECUTED"
    
    def test_get_critical_alerts(self, auth_token):
        """Test GET /api/swarm/alerts/critical - retrieve critical alerts"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/alerts/critical?limit=20", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "count" in data
        assert isinstance(data["alerts"], list)
    
    def test_get_critical_alerts_with_acknowledged_filter(self, auth_token):
        """Test GET /api/swarm/alerts/critical with acknowledged filter"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/alerts/critical?acknowledged=false", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        # All returned alerts should be unacknowledged
        for alert in data["alerts"]:
            assert alert.get("acknowledged") == False


class TestDeploymentEndpoints:
    """Test deployment endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_deploy_single_device(self, auth_token):
        """Test POST /api/swarm/deploy/single - deploy to single device"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        params = {
            "device_ip": "192.168.1.100",
            "os_type": "windows",
            "username": "admin",
            "password": "testpass"
        }
        response = requests.post(f"{BASE_URL}/api/swarm/deploy/single", params=params, headers=headers)
        # Should return 200 or 503 if deployment service not running
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "task_id" in data
    
    def test_deploy_winrm(self, auth_token):
        """Test POST /api/swarm/deploy/winrm - deploy via WinRM"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        params = {
            "device_ip": "192.168.1.101",
            "username": "administrator",
            "password": "testpass123"
        }
        response = requests.post(f"{BASE_URL}/api/swarm/deploy/winrm", params=params, headers=headers)
        # Should return 200 or 503 if deployment service not running
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "method" in data
            assert data["method"] == "winrm"


class TestNetworkTopologyEndpoints:
    """Test network topology endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_network_topology(self, auth_token):
        """Test GET /api/network/topology - get network map data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/network/topology", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "links" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["links"], list)


class TestSwarmOverviewEndpoints:
    """Test swarm overview endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_swarm_overview(self, auth_token):
        """Test GET /api/swarm/overview - get swarm statistics"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/overview", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "agents" in data
        assert "telemetry" in data
        assert "deployments" in data


class TestTelemetryEndpoints:
    """Test telemetry endpoints for live threats"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_telemetry_critical(self, auth_token):
        """Test GET /api/swarm/telemetry with severity=critical"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/telemetry?severity=critical&limit=50", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "count" in data
        assert isinstance(data["events"], list)
    
    def test_ingest_telemetry(self):
        """Test POST /api/swarm/telemetry/ingest - ingest telemetry events"""
        events = [
            {
                "host_id": "test-host-001",
                "agent_id": "test-agent-001",
                "event_type": "process.suspicious",
                "severity": "critical",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "name": "mimikatz.exe",
                    "pid": 12345,
                    "message": "Suspicious process detected"
                }
            }
        ]
        response = requests.post(f"{BASE_URL}/api/swarm/telemetry/ingest", json={"events": events})
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("ingested") >= 1


class TestAgentCommandsEndpoints:
    """Test agent commands endpoints for Command Center"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_pending_commands(self, auth_token):
        """Test GET /api/agent-commands/pending - get pending approval commands"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/agent-commands/pending", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        assert isinstance(data["commands"], list)
    
    def test_get_command_history(self, auth_token):
        """Test GET /api/agent-commands/history - get command history"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/agent-commands/history?limit=20", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        assert isinstance(data["commands"], list)
    
    def test_get_agents_status(self, auth_token):
        """Test GET /api/agent-commands/agents/status - get connected agents"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/agent-commands/agents/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)


class TestAgentDownloadEndpoints:
    """Test agent download endpoints"""
    
    def test_download_v7_agent(self):
        """Test GET /api/swarm/agent/download/v7 - download v7 agent with auto-kill"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/v7")
        assert response.status_code == 200
        assert "text/x-python" in response.headers.get("content-type", "")
        # Verify it contains auto-kill functionality
        content = response.text
        assert "auto_kill" in content.lower() or "AUTO_KILL" in content
    
    def test_download_mobile_v7_agent(self):
        """Test GET /api/swarm/agent/download/mobile-v7 - download mobile v7 agent"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/mobile-v7")
        assert response.status_code == 200
        assert "text/x-python" in response.headers.get("content-type", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
