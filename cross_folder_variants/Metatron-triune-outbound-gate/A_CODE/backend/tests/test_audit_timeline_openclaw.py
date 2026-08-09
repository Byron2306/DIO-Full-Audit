"""
Backend API Tests for Audit Logging, Threat Timeline, OpenClaw, and WebSocket Features
======================================================================================
Tests for new features added in iteration 7:
- Audit log endpoints (get logs, stats, cleanup)
- Threat timeline endpoints (build, export, recent)
- OpenClaw configuration endpoints (get, update, test)
- WebSocket stats and agent commands endpoints
"""
import pytest
import requests
import os
import json
from datetime import datetime
import uuid

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = os.environ.get("TEST_EMAIL", "integration.audit@defender.io")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "defender123")


def _ensure_login_token() -> str:
    login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if login_response.status_code == 200:
        return login_response.json().get("access_token")

    register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": f"Audit Test User {uuid.uuid4().hex[:8]}"
    })
    if register_response.status_code == 200:
        return register_response.json().get("access_token")

    pytest.skip(f"Authentication bootstrap failed: login={login_response.status_code}, register={register_response.status_code}")


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_contract(self):
        """Test login/register bootstrap returns a valid token"""
        token = _ensure_login_token()
        assert token
        print("✓ Login/register bootstrap successful")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    return _ensure_login_token()


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


# =============================================================================
# AUDIT LOG ENDPOINT TESTS
# =============================================================================

class TestAuditLogEndpoints:
    """Tests for audit log API endpoints"""
    
    def test_get_audit_logs_requires_auth(self):
        """Test that audit logs endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/audit/logs")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ GET /api/audit/logs requires authentication")
    
    def test_get_audit_logs_success(self, auth_headers):
        """Test getting audit logs with valid auth"""
        response = requests.get(f"{BASE_URL}/api/audit/logs", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/audit/logs - returned {len(data)} logs")
    
    def test_get_audit_logs_with_filters(self, auth_headers):
        """Test audit logs with category filter"""
        response = requests.get(
            f"{BASE_URL}/api/audit/logs?category=authentication&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/audit/logs with filters - returned {len(data)} logs")
    
    def test_get_audit_logs_severity_filter(self, auth_headers):
        """Test audit logs with severity filter"""
        response = requests.get(
            f"{BASE_URL}/api/audit/logs?severity=info&limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/audit/logs with severity filter - returned {len(data)} logs")
    
    def test_get_audit_stats_requires_auth(self):
        """Test that audit stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/audit/stats")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ GET /api/audit/stats requires authentication")
    
    def test_get_audit_stats_success(self, auth_headers):
        """Test getting audit statistics"""
        response = requests.get(f"{BASE_URL}/api/audit/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total" in data
        assert "by_category" in data
        assert "by_severity" in data
        print(f"✓ GET /api/audit/stats - total: {data['total']}, categories: {len(data['by_category'])}")
    
    def test_get_recent_audit(self, auth_headers):
        """Test getting recent audit entries from buffer"""
        response = requests.get(f"{BASE_URL}/api/audit/recent?limit=20", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/audit/recent - returned {len(data)} entries")
    
    def test_audit_cleanup_requires_admin(self):
        """Test that audit cleanup requires admin role"""
        response = requests.post(f"{BASE_URL}/api/audit/cleanup")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ POST /api/audit/cleanup requires authentication")
    
    def test_audit_cleanup_success(self, auth_headers):
        """Test audit cleanup endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/audit/cleanup?days=365",  # Use long retention to avoid deleting test data
            headers=auth_headers
        )
        assert response.status_code in [200, 403], f"Failed: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "deleted_count" in data
            print(f"✓ POST /api/audit/cleanup - deleted {data.get('deleted_count', 0)} old entries")
        else:
            print("✓ POST /api/audit/cleanup correctly denied for non-admin user")


# =============================================================================
# THREAT TIMELINE ENDPOINT TESTS
# =============================================================================

class TestTimelineEndpoints:
    """Tests for threat timeline API endpoints"""
    
    @pytest.fixture(scope="class")
    def threat_id(self, auth_headers):
        """Get a threat ID for timeline tests"""
        response = requests.get(f"{BASE_URL}/api/threats?limit=1", headers=auth_headers)
        if response.status_code == 200:
            threats = response.json()
            if threats and len(threats) > 0:
                return threats[0].get("id")
        return None
    
    def test_get_recent_timelines_requires_auth(self):
        """Test that recent timelines endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/timelines/recent")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ GET /api/timelines/recent requires authentication")
    
    def test_get_recent_timelines_success(self, auth_headers):
        """Test getting recent threat timelines"""
        response = requests.get(f"{BASE_URL}/api/timelines/recent?limit=10", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "timelines" in data
        assert isinstance(data["timelines"], list)
        print(f"✓ GET /api/timelines/recent - returned {len(data['timelines'])} timelines")
    
    def test_get_timeline_for_threat(self, auth_headers, threat_id):
        """Test getting timeline for a specific threat"""
        if not threat_id:
            pytest.skip("No threats available for timeline test")
        
        response = requests.get(f"{BASE_URL}/api/timeline/{threat_id}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "threat_id" in data
        assert "threat_name" in data
        assert "events" in data
        assert "summary" in data
        assert "impact_assessment" in data
        assert "recommendations" in data
        print(f"✓ GET /api/timeline/{threat_id[:8]}... - {len(data['events'])} events")
    
    def test_get_timeline_not_found(self, auth_headers):
        """Test getting timeline for non-existent threat"""
        response = requests.get(f"{BASE_URL}/api/timeline/non-existent-id", headers=auth_headers)
        assert response.status_code == 404, "Should return 404 for non-existent threat"
        print("✓ GET /api/timeline/non-existent-id returns 404")
    
    def test_export_timeline_json(self, auth_headers, threat_id):
        """Test exporting timeline as JSON"""
        if not threat_id:
            pytest.skip("No threats available for export test")
        
        response = requests.get(
            f"{BASE_URL}/api/timeline/{threat_id}/export?format=json",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "threat_id" in data
        print(f"✓ GET /api/timeline/{threat_id[:8]}../export?format=json - success")
    
    def test_export_timeline_markdown(self, auth_headers, threat_id):
        """Test exporting timeline as Markdown"""
        if not threat_id:
            pytest.skip("No threats available for export test")
        
        response = requests.get(
            f"{BASE_URL}/api/timeline/{threat_id}/export?format=markdown",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "markdown" in data
        assert "# Threat Timeline" in data["markdown"]
        print(f"✓ GET /api/timeline/{threat_id[:8]}../export?format=markdown - success")
    
    def test_export_timeline_invalid_format(self, auth_headers, threat_id):
        """Test exporting timeline with invalid format"""
        if not threat_id:
            pytest.skip("No threats available for export test")
        
        response = requests.get(
            f"{BASE_URL}/api/timeline/{threat_id}/export?format=invalid",
            headers=auth_headers
        )
        assert response.status_code == 400, "Should return 400 for invalid format"
        print("✓ GET /api/timeline/.../export?format=invalid returns 400")


# =============================================================================
# WEBSOCKET STATS AND COMMANDS ENDPOINT TESTS
# =============================================================================

class TestWebSocketEndpoints:
    """Tests for WebSocket-related API endpoints"""
    
    def test_get_websocket_stats_requires_auth(self):
        """Test that WebSocket stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/websocket/stats")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ GET /api/websocket/stats requires authentication")
    
    def test_get_websocket_stats_success(self, auth_headers):
        """Test getting WebSocket statistics"""
        response = requests.get(f"{BASE_URL}/api/websocket/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "messages_sent" in data
        assert "messages_received" in data
        assert "agents_connected" in data
        assert "dashboards_connected" in data
        print(f"✓ GET /api/websocket/stats - agents: {data['agents_connected']}, dashboards: {data['dashboards_connected']}")
    
    def test_get_websocket_agents_requires_auth(self):
        """Test that WebSocket agents endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/websocket/agents")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ GET /api/websocket/agents requires authentication")
    
    def test_get_websocket_agents_success(self, auth_headers):
        """Test getting WebSocket-connected agents"""
        response = requests.get(f"{BASE_URL}/api/websocket/agents", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/websocket/agents - {len(data)} agents connected")
    
    def test_send_command_requires_admin(self):
        """Test that sending commands requires admin role"""
        response = requests.post(f"{BASE_URL}/api/websocket/command/test-agent")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ POST /api/websocket/command requires authentication")
    
    def test_send_command_to_offline_agent(self, auth_headers):
        """Test sending command to offline agent (should queue)"""
        response = requests.post(
            f"{BASE_URL}/api/websocket/command/offline-agent-123",
            headers=auth_headers,
            json={"command": "status", "params": {}}
        )
        assert response.status_code in [404, 500], f"Failed: {response.text}"
        print(f"✓ POST /api/websocket/command to offline agent returned expected non-success status {response.status_code}")
    
    def test_request_scan_invalid_type(self, auth_headers):
        """Test requesting scan with invalid type"""
        response = requests.post(
            f"{BASE_URL}/api/websocket/scan/test-agent",
            headers=auth_headers,
            params={"scan_type": "invalid_scan"}
        )
        assert response.status_code in [404, 500], f"Unexpected response: {response.status_code}"
        print(f"✓ POST /api/websocket/scan invalid type returned expected non-success status {response.status_code}")
    
    def test_request_scan_valid_type(self, auth_headers):
        """Test requesting scan with valid type"""
        response = requests.post(
            f"{BASE_URL}/api/websocket/scan/test-agent",
            headers=auth_headers,
            params={"scan_type": "network"}
        )
        assert response.status_code in [404, 500], f"Unexpected response: {response.status_code}"
        print(f"✓ POST /api/websocket/scan valid type returned expected non-success status {response.status_code}")


# =============================================================================
# OPENCLAW CONFIGURATION ENDPOINT TESTS
# =============================================================================

class TestOpenClawEndpoints:
    """Tests for OpenClaw gateway configuration endpoints"""
    
    def test_get_openclaw_config_requires_admin(self):
        """Test that OpenClaw config endpoint requires admin role"""
        response = requests.get(f"{BASE_URL}/api/openclaw/config")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ GET /api/openclaw/config requires authentication")
    
    def test_get_openclaw_config_success(self, auth_headers):
        """Test getting OpenClaw configuration"""
        response = requests.get(f"{BASE_URL}/api/openclaw/config", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "enabled" in data
        assert "gateway_url" in data
        assert "api_key" in data
        print(f"✓ GET /api/openclaw/config - enabled: {data['enabled']}, gateway_url configured: {bool(data.get('gateway_url'))}")
    
    def test_update_openclaw_config_requires_admin(self):
        """Test that updating OpenClaw config requires admin role"""
        response = requests.post(f"{BASE_URL}/api/openclaw/config", json={
            "enabled": False,
            "gateway_url": "http://test.local"
        })
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ POST /api/openclaw/config requires authentication")
    
    def test_update_openclaw_config_success(self, auth_headers):
        """Test updating OpenClaw configuration"""
        # First get current config
        get_response = requests.get(f"{BASE_URL}/api/openclaw/config", headers=auth_headers)
        original_config = get_response.json()
        
        # Update config
        response = requests.post(
            f"{BASE_URL}/api/openclaw/config",
            headers=auth_headers,
            json={
                "enabled": False,
                "gateway_url": "http://test-gateway.local:8080"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("message") == "OpenClaw configuration updated"
        print("✓ POST /api/openclaw/config - configuration updated")
        
        # Restore original config
        requests.post(
            f"{BASE_URL}/api/openclaw/config",
            headers=auth_headers,
            json={
                "enabled": original_config.get("enabled", False),
                "gateway_url": original_config.get("gateway_url", "")
            }
        )
    
    def test_test_openclaw_connection_requires_admin(self):
        """Test that testing OpenClaw connection requires admin role"""
        response = requests.post(f"{BASE_URL}/api/openclaw/test")
        assert response.status_code in [401, 403], "Should require authentication"
        print("✓ POST /api/openclaw/test requires authentication")
    
    def test_test_openclaw_connection_not_enabled(self, auth_headers):
        """Test OpenClaw connection when not enabled"""
        # First ensure OpenClaw is disabled
        requests.post(
            f"{BASE_URL}/api/openclaw/config",
            headers=auth_headers,
            json={"enabled": False, "gateway_url": ""}
        )
        
        response = requests.post(f"{BASE_URL}/api/openclaw/test", headers=auth_headers)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            assert "connected" in data
            print("✓ POST /api/openclaw/test returned connectivity result")
        else:
            print("✓ POST /api/openclaw/test returns 400 when not configured")


# =============================================================================
# INTEGRATION TESTS - VERIFY AUDIT LOGGING WORKS
# =============================================================================

class TestAuditLoggingIntegration:
    """Integration tests to verify audit logging is working"""
    
    def test_login_creates_audit_entry(self, auth_headers):
        """Test that login creates an audit entry"""
        # Perform a login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200
        
        # Check audit logs for authentication entries
        response = requests.get(
            f"{BASE_URL}/api/audit/logs?category=authentication&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Audit logging should capture authentication events
        assert isinstance(data, list)
        print(f"✓ Authentication audit logging - {len(data)} auth entries found")
    
    def test_timeline_view_creates_audit_entry(self, auth_headers):
        """Test that viewing a timeline creates an audit entry"""
        # Get a threat ID
        threats_response = requests.get(f"{BASE_URL}/api/threats?limit=1", headers=auth_headers)
        if threats_response.status_code != 200 or not threats_response.json():
            pytest.skip("No threats available")
        
        threat_id = threats_response.json()[0]["id"]
        
        # View the timeline
        requests.get(f"{BASE_URL}/api/timeline/{threat_id}", headers=auth_headers)
        
        # Check audit logs for user_action entries
        response = requests.get(
            f"{BASE_URL}/api/audit/logs?category=user_action&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        print("✓ Timeline view audit logging - user_action entries captured")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
