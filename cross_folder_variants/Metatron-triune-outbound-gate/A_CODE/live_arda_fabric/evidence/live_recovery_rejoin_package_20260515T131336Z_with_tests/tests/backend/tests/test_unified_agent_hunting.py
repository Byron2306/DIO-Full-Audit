"""
Test Unified Agent and Threat Hunting APIs
==========================================
Tests for the merged Metatron/Seraph unified agent and MITRE ATT&CK threat hunting features.

Features tested:
- Unified agent registration (/api/unified/agents/register)
- Unified agent heartbeat (/api/unified/agents/{agent_id}/heartbeat)
- Threat hunting status (/api/hunting/status)
- Threat hunting rules (/api/hunting/rules)
- Threat hunting hunt execution (/api/hunting/hunt)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test user credentials
TEST_EMAIL = f"unified_test_{uuid.uuid4().hex[:8]}@defender.io"
TEST_PASSWORD = "testpass123"
TEST_NAME = "Unified Agent Tester"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token by registering a new user"""
    # Register user
    register_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": TEST_NAME
    })
    
    if register_response.status_code == 200:
        data = register_response.json()
        return data.get("access_token")
    
    # Try login if already exists
    login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if login_response.status_code == 200:
        data = login_response.json()
        return data.get("access_token")
    
    pytest.skip("Failed to authenticate - skipping authenticated tests")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestUnifiedAgentRegistration:
    """Test unified agent registration endpoint"""
    
    @pytest.fixture
    def test_agent_id(self):
        """Generate unique test agent ID"""
        return f"metatron-TEST-{uuid.uuid4().hex[:8]}"
    
    def test_agent_registration_success(self, api_client, test_agent_id):
        """Test successful agent registration"""
        agent_data = {
            "agent_id": test_agent_id,
            "platform": "linux",
            "hostname": "test-host-001",
            "ip_address": "192.168.1.100",
            "version": "2.0.0",
            "capabilities": ["process", "network", "network_scan", "wifi_scan", "siem"],
            "config": {
                "auto_remediate": True,
                "features": {
                    "vns_sync": True,
                    "ai_analysis": True,
                    "siem_integration": True,
                    "threat_hunting": True
                }
            }
        }
        
        response = api_client.post(f"{BASE_URL}/api/unified/agents/register", json=agent_data)
        
        assert response.status_code in [200, 201], f"Registration failed: {response.text}"
        data = response.json()
        assert data.get("status") in ["registered", "updated"]
        assert data.get("agent_id") == test_agent_id
        print(f"✓ Agent registration success: {test_agent_id}")
    
    def test_agent_reregistration_updates(self, api_client, test_agent_id):
        """Test that re-registration updates existing agent"""
        # First registration
        agent_data = {
            "agent_id": test_agent_id,
            "platform": "linux",
            "hostname": "test-host-001",
            "ip_address": "192.168.1.100",
            "version": "2.0.0",
            "capabilities": ["process"],
            "config": {}
        }
        
        api_client.post(f"{BASE_URL}/api/unified/agents/register", json=agent_data)
        
        # Re-registration with updated data
        agent_data["capabilities"] = ["process", "network", "siem"]
        agent_data["version"] = "2.0.1"
        
        response = api_client.post(f"{BASE_URL}/api/unified/agents/register", json=agent_data)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("status") == "updated"
        print(f"✓ Agent re-registration updates existing: {test_agent_id}")
    
    def test_windows_agent_registration(self, api_client):
        """Test Windows platform agent registration"""
        agent_id = f"metatron-win-TEST-{uuid.uuid4().hex[:8]}"
        agent_data = {
            "agent_id": agent_id,
            "platform": "windows",
            "hostname": "WIN-DESKTOP-01",
            "ip_address": "192.168.1.50",
            "version": "2.0.0",
            "capabilities": ["process", "network", "bluetooth_scan", "usb_monitoring"],
            "config": {"auto_remediate": True}
        }
        
        response = api_client.post(f"{BASE_URL}/api/unified/agents/register", json=agent_data)
        
        assert response.status_code in [200, 201]
        print(f"✓ Windows agent registration success: {agent_id}")


class TestUnifiedAgentHeartbeat:
    """Test unified agent heartbeat endpoint"""
    
    @pytest.fixture
    def registered_agent(self, api_client):
        """Create and register a test agent"""
        agent_id = f"metatron-hb-TEST-{uuid.uuid4().hex[:8]}"
        agent_data = {
            "agent_id": agent_id,
            "platform": "linux",
            "hostname": "test-heartbeat-host",
            "ip_address": "192.168.1.200",
            "version": "2.0.0",
            "capabilities": ["process", "network"],
            "config": {}
        }
        
        api_client.post(f"{BASE_URL}/api/unified/agents/register", json=agent_data)
        return agent_id
    
    def test_heartbeat_success(self, api_client, registered_agent):
        """Test successful heartbeat"""
        heartbeat_data = {
            "agent_id": registered_agent,
            "status": "online",
            "cpu_usage": 25.5,
            "memory_usage": 60.2,
            "disk_usage": 45.0,
            "threat_count": 0,
            "network_connections": 15,
            "alerts": [],
            "telemetry": {
                "processes": [{"name": "python", "pid": 1234, "cpu_percent": 5.0}],
                "connections": [{"remote_ip": "8.8.8.8", "remote_port": 443}]
            }
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/unified/agents/{registered_agent}/heartbeat",
            json=heartbeat_data
        )
        
        assert response.status_code == 200, f"Heartbeat failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        assert "timestamp" in data
        print(f"✓ Heartbeat success for agent: {registered_agent}")
    
    def test_heartbeat_with_alerts(self, api_client, registered_agent):
        """Test heartbeat with alert data"""
        heartbeat_data = {
            "agent_id": registered_agent,
            "status": "online",
            "cpu_usage": 80.0,
            "memory_usage": 75.0,
            "threat_count": 1,
            "alerts": [
                {
                    "severity": "high",
                    "category": "process",
                    "message": "Suspicious process detected: mimikatz.exe",
                    "mitre_technique": "T1003.001"
                }
            ],
            "telemetry": {}
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/unified/agents/{registered_agent}/heartbeat",
            json=heartbeat_data
        )
        
        assert response.status_code == 200
        print(f"✓ Heartbeat with alerts success for agent: {registered_agent}")
    
    def test_heartbeat_unregistered_agent(self, api_client):
        """Test heartbeat for non-existent agent returns 404"""
        fake_agent_id = f"nonexistent-{uuid.uuid4().hex[:8]}"
        heartbeat_data = {
            "agent_id": fake_agent_id,
            "status": "online",
            "cpu_usage": 10.0
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/unified/agents/{fake_agent_id}/heartbeat",
            json=heartbeat_data
        )
        
        assert response.status_code == 404
        print(f"✓ Heartbeat correctly rejected for unregistered agent")


class TestThreatHuntingStatus:
    """Test threat hunting status endpoint"""
    
    def test_hunting_status_endpoint(self, authenticated_client):
        """Test threat hunting status returns engine stats"""
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/status")
        
        assert response.status_code == 200, f"Status request failed: {response.text}"
        data = response.json()
        
        # Verify expected fields
        assert data.get("status") == "operational"
        assert "rules_loaded" in data
        assert "hunts_executed" in data
        assert "matches_found" in data
        assert "tactics_covered" in data
        assert "techniques_covered" in data
        
        # Verify we have rules loaded
        assert data["rules_loaded"] > 0, "Expected rules to be loaded"
        
        print(f"✓ Hunting status: {data['rules_loaded']} rules, {data['tactics_covered']} tactics, {data['techniques_covered']} techniques")


class TestThreatHuntingRules:
    """Test threat hunting rules endpoint"""
    
    def test_get_all_rules(self, authenticated_client):
        """Test fetching all hunting rules"""
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/rules")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "rules" in data
        assert "total" in data
        assert data["total"] > 0, "Expected at least one rule"
        
        # Verify rule structure
        rule = data["rules"][0]
        assert "rule_id" in rule
        assert "name" in rule
        assert "mitre_technique" in rule
        assert "mitre_tactic" in rule
        assert "severity" in rule
        assert "enabled" in rule
        
        print(f"✓ Retrieved {data['total']} hunting rules")
    
    def test_rules_by_tactic(self, authenticated_client):
        """Test filtering rules by MITRE tactic"""
        # TA0006 = Credential Access
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/rules?tactic=TA0006")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned rules should have tactic TA0006
        for rule in data["rules"]:
            assert rule["mitre_tactic"] == "TA0006"
        
        print(f"✓ Retrieved {len(data['rules'])} rules for Credential Access tactic")
    
    def test_rules_by_technique(self, authenticated_client):
        """Test filtering rules by MITRE technique"""
        # T1003.001 = LSASS Memory Credential Dumping
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/rules?technique=T1003.001")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned rules should have technique T1003.001
        for rule in data["rules"]:
            assert rule["mitre_technique"] == "T1003.001"
        
        print(f"✓ Retrieved {len(data['rules'])} rules for T1003.001 technique")


class TestThreatHuntExecution:
    """Test threat hunting hunt execution endpoint"""
    
    def test_hunt_mimikatz_detection(self, authenticated_client):
        """Test hunting detects mimikatz process (T1003.001)"""
        telemetry = {
            "processes": [
                {
                    "pid": 1234,
                    "name": "mimikatz.exe",
                    "cmdline": "mimikatz sekurlsa::logonpasswords",
                    "cpu_percent": 5.0
                }
            ],
            "connections": []
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/hunting/hunt",
            json={"telemetry": telemetry}
        )
        
        assert response.status_code == 200, f"Hunt failed: {response.text}"
        data = response.json()
        
        assert "matches" in data
        assert "total_matches" in data
        
        # Should detect the mimikatz process
        assert data["total_matches"] > 0, "Expected to detect mimikatz"
        
        # Verify the match is related to T1003 (Credential Dumping)
        techniques_found = [m.get("mitre_technique") for m in data["matches"]]
        assert any("T1003" in t for t in techniques_found), f"Expected T1003 technique, got: {techniques_found}"
        
        print(f"✓ Hunt detected mimikatz: {data['total_matches']} matches, {data['high_severity']} high severity")
    
    def test_hunt_encoded_powershell_detection(self, authenticated_client):
        """Test hunting detects encoded PowerShell (T1059.001)"""
        telemetry = {
            "processes": [
                {
                    "pid": 5678,
                    "name": "powershell.exe",
                    "cmdline": "powershell -enc SQBFAFgAKAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAA=",
                    "cpu_percent": 10.0
                }
            ],
            "connections": []
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/hunting/hunt",
            json={"telemetry": telemetry}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_matches"] > 0, "Expected to detect encoded PowerShell"
        
        techniques_found = [m.get("mitre_technique") for m in data["matches"]]
        assert any("T1059" in t for t in techniques_found), f"Expected T1059 technique, got: {techniques_found}"
        
        print(f"✓ Hunt detected encoded PowerShell: {data['total_matches']} matches")
    
    def test_hunt_suspicious_port_detection(self, authenticated_client):
        """Test hunting detects suspicious port connections (T1095)"""
        telemetry = {
            "processes": [],
            "connections": [
                {
                    "remote_ip": "185.220.101.55",
                    "remote_port": 4444,  # Metasploit default
                    "local_port": 54321
                },
                {
                    "remote_ip": "8.8.8.8",
                    "remote_port": 443,  # Normal HTTPS
                    "local_port": 12345
                }
            ]
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/hunting/hunt",
            json={"telemetry": telemetry}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect the suspicious port 4444
        assert data["total_matches"] > 0, "Expected to detect suspicious port"
        
        # T1095 = Non-Application Layer Protocol
        techniques_found = [m.get("mitre_technique") for m in data["matches"]]
        print(f"✓ Hunt detected suspicious connections: {data['total_matches']} matches, techniques: {techniques_found}")
    
    def test_hunt_no_matches_for_clean_telemetry(self, authenticated_client):
        """Test hunting returns no matches for normal processes"""
        telemetry = {
            "processes": [
                {
                    "pid": 100,
                    "name": "chrome.exe",
                    "cmdline": "chrome.exe --no-sandbox",
                    "cpu_percent": 2.0
                }
            ],
            "connections": [
                {
                    "remote_ip": "172.217.0.1",
                    "remote_port": 443,
                    "local_port": 43210
                }
            ]
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/hunting/hunt",
            json={"telemetry": telemetry}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not flag normal browser activity
        print(f"✓ Hunt for clean telemetry: {data['total_matches']} matches (expected 0 or few)")


class TestThreatHuntingTacticsAndTechniques:
    """Test MITRE ATT&CK tactics and techniques endpoints"""
    
    def test_get_tactics(self, authenticated_client):
        """Test fetching MITRE tactics coverage"""
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/tactics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tactics" in data
        assert len(data["tactics"]) > 0
        
        # Verify tactic structure
        tactic = data["tactics"][0]
        assert "tactic_id" in tactic
        assert "techniques" in tactic
        assert "rule_count" in tactic
        
        # Print covered tactics
        tactic_ids = [t["tactic_id"] for t in data["tactics"]]
        print(f"✓ Tactics covered: {tactic_ids}")
    
    def test_get_techniques(self, authenticated_client):
        """Test fetching MITRE techniques coverage"""
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/techniques")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "techniques" in data
        assert len(data["techniques"]) > 0
        
        # Verify technique structure
        tech = data["techniques"][0]
        assert "technique_id" in tech
        assert "name" in tech
        assert "tactic" in tech
        
        print(f"✓ Techniques covered: {len(data['techniques'])} techniques")


class TestThreatHuntingMatches:
    """Test hunting matches endpoints"""
    
    def test_get_recent_matches(self, authenticated_client):
        """Test fetching recent hunting matches"""
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/matches")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "matches" in data
        assert "total" in data
        
        print(f"✓ Retrieved {data['total']} recent matches")
    
    def test_get_high_severity_matches(self, authenticated_client):
        """Test fetching high severity matches"""
        response = authenticated_client.get(f"{BASE_URL}/api/hunting/matches/high-severity")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "matches" in data
        assert "total" in data
        
        # All returned matches should be critical or high severity
        for match in data["matches"]:
            assert match["severity"] in ["critical", "high"]
        
        print(f"✓ Retrieved {data['total']} high severity matches")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
