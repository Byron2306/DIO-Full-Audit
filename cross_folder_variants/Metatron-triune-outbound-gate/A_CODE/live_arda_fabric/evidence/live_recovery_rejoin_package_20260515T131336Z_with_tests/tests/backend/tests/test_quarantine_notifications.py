"""
Test suite for Quarantine and Notification features
Tests: Quarantine API endpoints, Notification settings, Elasticsearch status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestAuthentication:
    """Authentication tests for admin user"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@defender.io"
        return data["access_token"]
    
    def test_login_success(self, auth_token):
        """Verify admin login works"""
        assert auth_token is not None
        assert len(auth_token) > 0


class TestQuarantineEndpoints:
    """Tests for Quarantine API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_quarantine_list_endpoint(self, auth_headers):
        """Test GET /api/quarantine - list quarantined files"""
        response = requests.get(f"{BASE_URL}/api/quarantine", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should return a list (may be empty if no files quarantined)
        assert "entries" in data or isinstance(data, list), f"Unexpected response format: {data}"
    
    def test_quarantine_list_with_status_filter(self, auth_headers):
        """Test GET /api/quarantine with status filter"""
        response = requests.get(f"{BASE_URL}/api/quarantine?status=quarantined", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_quarantine_list_with_threat_type_filter(self, auth_headers):
        """Test GET /api/quarantine with threat_type filter"""
        response = requests.get(f"{BASE_URL}/api/quarantine?threat_type=malware", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_quarantine_summary_endpoint(self, auth_headers):
        """Test GET /api/quarantine/summary - get quarantine statistics"""
        response = requests.get(f"{BASE_URL}/api/quarantine/summary", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Verify expected fields in summary
        assert "total_entries" in data, f"Missing total_entries: {data}"
        assert "storage" in data, f"Missing storage: {data}"
        assert "by_status" in data, f"Missing by_status: {data}"
        # Verify storage stats structure
        storage = data["storage"]
        assert "total_size_bytes" in storage or "total_size_mb" in storage
    
    def test_quarantine_entry_not_found(self, auth_headers):
        """Test GET /api/quarantine/{entry_id} with non-existent ID"""
        response = requests.get(f"{BASE_URL}/api/quarantine/nonexistent-id-12345", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_quarantine_restore_not_found(self, auth_headers):
        """Test POST /api/quarantine/{entry_id}/restore with non-existent ID"""
        response = requests.post(f"{BASE_URL}/api/quarantine/nonexistent-id-12345/restore", headers=auth_headers)
        assert response.status_code in [404, 400], f"Expected 404 or 400, got {response.status_code}"
    
    def test_quarantine_delete_not_found(self, auth_headers):
        """Test DELETE /api/quarantine/{entry_id} with non-existent ID"""
        response = requests.delete(f"{BASE_URL}/api/quarantine/nonexistent-id-12345", headers=auth_headers)
        assert response.status_code in [404, 400], f"Expected 404 or 400, got {response.status_code}"
    
    def test_quarantine_requires_auth(self):
        """Test that quarantine endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/quarantine")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        
        response = requests.get(f"{BASE_URL}/api/quarantine/summary")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"


class TestNotificationSettings:
    """Tests for Notification Settings API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_notification_settings(self, auth_headers):
        """Test GET /api/settings/notifications - get current settings"""
        response = requests.get(f"{BASE_URL}/api/settings/notifications", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify expected structure
        assert "slack" in data, f"Missing slack config: {data}"
        assert "email" in data, f"Missing email config: {data}"
        assert "elasticsearch" in data, f"Missing elasticsearch config: {data}"
        
        # Verify slack structure
        slack = data["slack"]
        assert "enabled" in slack
        assert "webhook_configured" in slack
        
        # Verify email structure
        email = data["email"]
        assert "enabled" in email
        assert "sendgrid_configured" in email
        
        # Verify elasticsearch structure
        es = data["elasticsearch"]
        assert "enabled" in es
        assert "url_configured" in es
    
    def test_update_notification_settings(self, auth_headers):
        """Test POST /api/settings/notifications - update settings"""
        # Update with a test sender email
        payload = {
            "sender_email": "test-alerts@anti-ai-defense.io"
        }
        response = requests.post(
            f"{BASE_URL}/api/settings/notifications",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ok" or "message" in data
    
    def test_notification_settings_requires_auth(self):
        """Test that notification settings require authentication"""
        response = requests.get(f"{BASE_URL}/api/settings/notifications")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
    
    def test_test_notification_endpoint(self, auth_headers):
        """Test POST /api/settings/notifications/test - test notification"""
        # Test with 'all' channel (will likely fail since no real services configured)
        payload = {"channel": "all"}
        response = requests.post(
            f"{BASE_URL}/api/settings/notifications/test",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=payload
        )
        # Should return 200 even if notifications fail (returns results dict)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "results" in data, f"Missing results in response: {data}"


class TestElasticsearchStatus:
    """Tests for Elasticsearch status endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_elasticsearch_status_endpoint(self, auth_headers):
        """Test GET /api/elasticsearch/status"""
        response = requests.get(f"{BASE_URL}/api/elasticsearch/status", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should have status field
        assert "status" in data, f"Missing status field: {data}"
        # Status should be one of: connected, not_configured, error
        assert data["status"] in ["connected", "not_configured", "error"], f"Unexpected status: {data['status']}"
    
    def test_elasticsearch_status_requires_auth(self):
        """Test that elasticsearch status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/elasticsearch/status")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"


class TestYARAMalwareDetection:
    """Tests for YARA malware detection and auto-quarantine integration"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_yara_detection_event_endpoint(self, auth_headers):
        """Test agent event endpoint for YARA detection"""
        # Simulate a YARA detection event from an agent
        payload = {
            "agent_id": "test-agent-001",
            "agent_name": "Test Security Agent",
            "event_type": "yara_detection",
            "timestamp": "2026-01-15T10:00:00Z",
            "data": {
                "filepath": "/tmp/test_malware.exe",
                "rule_name": "TestMalwareRule",
                "rule_tags": ["malware", "test"],
                "severity": "high"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/agent/event",
            json=payload
        )
        # Agent events don't require auth
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "status" in data or "threat_id" in data


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work after new features added"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_dashboard_stats(self, auth_headers):
        """Test dashboard stats endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_threats" in data
        assert "active_threats" in data
    
    def test_threats_list(self, auth_headers):
        """Test threats list endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/threats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_alerts_list(self, auth_headers):
        """Test alerts list endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/alerts", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_agents_list(self, auth_headers):
        """Test agents list endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/agents", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
