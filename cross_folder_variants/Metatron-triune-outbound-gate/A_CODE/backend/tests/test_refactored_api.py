"""
Backend API Tests - Post-Refactoring Verification
==================================================
Tests to verify all API endpoints work correctly after server.py was refactored
from a monolithic 2700+ line file into 17 modular router files.

Endpoints tested:
- Auth: /api/auth/register, /api/auth/login, /api/auth/me
- Threats: /api/threats (GET, POST)
- Alerts: /api/alerts (GET, POST)
- Dashboard: /api/dashboard/stats
- Network: /api/network/topology
- Agent: /api/agent/download
- Health: /api/health
- Settings: /api/settings/notifications
- Quarantine: /api/quarantine, /api/quarantine/summary
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "test@defender.io"
TEST_USER_PASSWORD = "test123"
ADMIN_EMAIL = "admin@defender.io"
ADMIN_PASSWORD = "defender123"


class TestHealthAndRoot:
    """Test basic health and root endpoints"""
    
    def test_health_endpoint(self):
        """Test /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        print(f"✓ Health check passed: {data}")
    
    def test_root_endpoint(self):
        """Test /api/ returns API info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"Root endpoint failed: {response.text}"
        data = response.json()
        assert data["name"] == "Anti-AI Defense System API"
        assert data["version"] == "2.0.0"
        assert "features" in data
        print(f"✓ Root endpoint passed: {data['name']} v{data['version']}")


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_register_new_user(self):
        """Test /api/auth/register creates new user"""
        unique_email = f"test_user_{uuid.uuid4().hex[:8]}@defender.io"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Test User"
        })
        assert response.status_code == 200, f"Register failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == unique_email
        assert data["user"]["role"] == "analyst"
        print(f"✓ Register passed: Created user {unique_email}")
    
    def test_register_duplicate_email(self):
        """Test /api/auth/register rejects duplicate email"""
        # First register
        unique_email = f"dup_test_{uuid.uuid4().hex[:8]}@defender.io"
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Test User"
        })
        # Try duplicate
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Test User 2"
        })
        assert response.status_code == 400, f"Expected 400 for duplicate: {response.text}"
        print(f"✓ Duplicate email rejection passed")
    
    def test_login_valid_credentials(self):
        """Test /api/auth/login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✓ Login passed: {data['user']['email']} ({data['user']['role']})")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test /api/auth/login rejects invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@defender.io",
            "password": "wrongpass"
        })
        assert response.status_code == 401, f"Expected 401: {response.text}"
        print(f"✓ Invalid credentials rejection passed")
    
    def test_get_me_authenticated(self):
        """Test /api/auth/me returns current user"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["access_token"]
        
        # Get me
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Get me failed: {response.text}"
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        print(f"✓ Get me passed: {data['email']}")
    
    def test_get_me_unauthenticated(self):
        """Test /api/auth/me requires authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code in [401, 403], f"Expected 401/403: {response.text}"
        print(f"✓ Unauthenticated rejection passed")


@pytest.fixture(scope="class")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Authentication failed")


class TestThreats:
    """Test threats endpoints"""
    
    def test_get_threats(self, auth_token):
        """Test GET /api/threats returns list"""
        response = requests.get(
            f"{BASE_URL}/api/threats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get threats failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get threats passed: {len(data)} threats found")
    
    def test_create_threat(self, auth_token):
        """Test POST /api/threats creates new threat"""
        threat_data = {
            "name": f"TEST_Threat_{uuid.uuid4().hex[:8]}",
            "type": "ai_agent",
            "severity": "high",
            "source_ip": "192.168.1.100",
            "target_system": "Test Server",
            "description": "Test threat for API verification",
            "indicators": ["Test indicator 1", "Test indicator 2"]
        }
        response = requests.post(
            f"{BASE_URL}/api/threats",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=threat_data
        )
        assert response.status_code == 200, f"Create threat failed: {response.text}"
        data = response.json()
        assert data["name"] == threat_data["name"]
        assert data["status"] == "active"
        assert "id" in data
        print(f"✓ Create threat passed: {data['id']}")
        return data["id"]
    
    def test_get_threat_by_id(self, auth_token):
        """Test GET /api/threats/{id} returns specific threat"""
        # Create a threat first
        threat_data = {
            "name": f"TEST_GetById_{uuid.uuid4().hex[:8]}",
            "type": "malware",
            "severity": "critical"
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/threats",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=threat_data
        )
        threat_id = create_resp.json()["id"]
        
        # Get by ID
        response = requests.get(
            f"{BASE_URL}/api/threats/{threat_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get threat by ID failed: {response.text}"
        data = response.json()
        assert data["id"] == threat_id
        print(f"✓ Get threat by ID passed: {threat_id}")
    
    def test_get_threats_with_filter(self, auth_token):
        """Test GET /api/threats with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/threats?status=active",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Filter threats failed: {response.text}"
        data = response.json()
        # All returned threats should be active
        for threat in data:
            assert threat["status"] == "active"
        print(f"✓ Filter threats passed: {len(data)} active threats")
    
    def test_threats_requires_auth(self):
        """Test /api/threats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/threats")
        assert response.status_code in [401, 403], f"Expected 401/403: {response.text}"
        print(f"✓ Threats auth requirement passed")


class TestAlerts:
    """Test alerts endpoints"""
    
    def test_get_alerts(self, auth_token):
        """Test GET /api/alerts returns list"""
        response = requests.get(
            f"{BASE_URL}/api/alerts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get alerts failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get alerts passed: {len(data)} alerts found")
    
    def test_create_alert(self, auth_token):
        """Test POST /api/alerts creates new alert"""
        alert_data = {
            "title": f"TEST_Alert_{uuid.uuid4().hex[:8]}",
            "type": "ai_detected",
            "severity": "high",
            "message": "Test alert for API verification"
        }
        response = requests.post(
            f"{BASE_URL}/api/alerts",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=alert_data
        )
        assert response.status_code == 200, f"Create alert failed: {response.text}"
        data = response.json()
        assert data["title"] == alert_data["title"]
        assert data["status"] == "new"
        assert "id" in data
        print(f"✓ Create alert passed: {data['id']}")
    
    def test_alerts_requires_auth(self):
        """Test /api/alerts requires authentication"""
        response = requests.get(f"{BASE_URL}/api/alerts")
        assert response.status_code in [401, 403], f"Expected 401/403: {response.text}"
        print(f"✓ Alerts auth requirement passed")


class TestDashboard:
    """Test dashboard endpoints"""
    
    def test_get_dashboard_stats(self, auth_token):
        """Test GET /api/dashboard/stats returns statistics"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get dashboard stats failed: {response.text}"
        data = response.json()
        
        # Verify all expected fields
        assert "total_threats" in data
        assert "active_threats" in data
        assert "contained_threats" in data
        assert "resolved_threats" in data
        assert "critical_alerts" in data
        assert "threats_by_type" in data
        assert "threats_by_severity" in data
        assert "recent_threats" in data
        assert "recent_alerts" in data
        assert "ai_scans_today" in data
        assert "system_health" in data
        
        print(f"✓ Dashboard stats passed: {data['total_threats']} total threats, {data['active_threats']} active")
    
    def test_dashboard_requires_auth(self):
        """Test /api/dashboard/stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code in [401, 403], f"Expected 401/403: {response.text}"
        print(f"✓ Dashboard auth requirement passed")


class TestNetwork:
    """Test network topology endpoints"""
    
    def test_get_network_topology(self, auth_token):
        """Test GET /api/network/topology returns network map"""
        response = requests.get(
            f"{BASE_URL}/api/network/topology",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get network topology failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "nodes" in data
        assert "links" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["links"], list)
        
        # Should have at least core infrastructure nodes
        assert len(data["nodes"]) > 0
        print(f"✓ Network topology passed: {len(data['nodes'])} nodes, {len(data['links'])} links")
    
    def test_network_requires_auth(self):
        """Test /api/network/topology requires authentication"""
        response = requests.get(f"{BASE_URL}/api/network/topology")
        assert response.status_code in [401, 403], f"Expected 401/403: {response.text}"
        print(f"✓ Network auth requirement passed")


class TestAgentDownload:
    """Test agent download endpoint"""
    
    def test_download_agent(self):
        """Test GET /api/agent/download returns installer"""
        response = requests.get(f"{BASE_URL}/api/agent/download")
        assert response.status_code == 200, f"Agent download failed: {response.text}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "python" in content_type or "octet-stream" in content_type or "text" in content_type
        
        # Check content disposition
        content_disp = response.headers.get("content-disposition", "")
        assert "defender_installer.py" in content_disp
        
        # Verify content is Python code
        content = response.text
        assert "#!/usr/bin/env python3" in content or "import" in content
        print(f"✓ Agent download passed: {len(content)} bytes")


class TestSettings:
    """Test settings endpoints"""
    
    def test_get_notification_settings(self, auth_token):
        """Test GET /api/settings/notifications returns settings"""
        response = requests.get(
            f"{BASE_URL}/api/settings/notifications",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get notification settings failed: {response.text}"
        data = response.json()
        
        # Verify expected fields
        assert "slack_enabled" in data
        assert "email_enabled" in data
        assert "elasticsearch_enabled" in data
        print(f"✓ Notification settings passed: slack={data['slack_enabled']}, email={data['email_enabled']}")
    
    def test_settings_requires_auth(self):
        """Test /api/settings/notifications requires authentication"""
        response = requests.get(f"{BASE_URL}/api/settings/notifications")
        assert response.status_code in [401, 403], f"Expected 401/403: {response.text}"
        print(f"✓ Settings auth requirement passed")


class TestQuarantine:
    """Test quarantine endpoints"""
    
    def test_get_quarantine_list(self, auth_token):
        """Test GET /api/quarantine returns list"""
        response = requests.get(
            f"{BASE_URL}/api/quarantine",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get quarantine list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Quarantine list passed: {len(data)} entries")
    
    def test_get_quarantine_summary(self, auth_token):
        """Test GET /api/quarantine/summary returns stats"""
        response = requests.get(
            f"{BASE_URL}/api/quarantine/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Get quarantine summary failed: {response.text}"
        data = response.json()
        
        # Verify expected fields
        assert "total_files" in data
        assert "total_size" in data
        print(f"✓ Quarantine summary passed: {data['total_files']} files, {data['total_size']} bytes")
    
    def test_quarantine_requires_auth(self):
        """Test /api/quarantine requires authentication"""
        response = requests.get(f"{BASE_URL}/api/quarantine")
        assert response.status_code in [401, 403], f"Expected 401/403: {response.text}"
        print(f"✓ Quarantine auth requirement passed")


class TestAdditionalRouters:
    """Test additional router endpoints to verify refactoring"""
    
    def test_ai_analysis_endpoint(self, auth_token):
        """Test /api/ai/analyze endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/ai/analyze",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"content": "test content", "analysis_type": "threat"}
        )
        # Should return 200 or 400/422 (validation), not 404
        assert response.status_code != 404, f"AI analyze endpoint not found: {response.text}"
        print(f"✓ AI analysis endpoint exists: status {response.status_code}")
    
    def test_hunting_endpoint(self, auth_token):
        """Test /api/hunting/hypotheses endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/hunting/hypotheses",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Hunting hypotheses failed: {response.text}"
        print(f"✓ Hunting endpoint passed")
    
    def test_honeypots_endpoint(self, auth_token):
        """Test /api/honeypots endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/honeypots",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Honeypots endpoint failed: {response.text}"
        print(f"✓ Honeypots endpoint passed")
    
    def test_reports_endpoint(self, auth_token):
        """Test /api/reports/threat-intelligence endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/reports/threat-intelligence",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Should return 200 (PDF) or 403 (permission denied), not 404
        assert response.status_code != 404, f"Reports endpoint not found: {response.text}"
        print(f"✓ Reports endpoint exists: status {response.status_code}")
    
    def test_agents_list_endpoint(self, auth_token):
        """Test /api/agents endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/agents",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Agents list failed: {response.text}"
        print(f"✓ Agents list endpoint passed")
    
    def test_response_rules_endpoint(self, auth_token):
        """Test /api/threat-response/stats endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/threat-response/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Response stats failed: {response.text}"
        print(f"✓ Response stats endpoint passed")
    
    def test_audit_logs_endpoint(self, auth_token):
        """Test /api/audit/logs endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/audit/logs",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Audit logs failed: {response.text}"
        print(f"✓ Audit logs endpoint passed")
    
    def test_timelines_endpoint(self, auth_token):
        """Test /api/timelines/recent endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/timelines/recent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Timelines failed: {response.text}"
        print(f"✓ Timelines endpoint passed")
    
    def test_websocket_stats_endpoint(self, auth_token):
        """Test /api/websocket/stats endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/websocket/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"WebSocket stats failed: {response.text}"
        print(f"✓ WebSocket stats endpoint passed")
    
    def test_openclaw_config_endpoint(self, auth_token):
        """Test /api/openclaw/config endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/openclaw/config",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"OpenClaw config failed: {response.text}"
        print(f"✓ OpenClaw config endpoint passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
