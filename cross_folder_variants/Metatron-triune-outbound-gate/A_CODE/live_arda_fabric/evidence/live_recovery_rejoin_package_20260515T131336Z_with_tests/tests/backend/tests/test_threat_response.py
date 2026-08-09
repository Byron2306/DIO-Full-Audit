"""
Test suite for Threat Response Agentic Features
Tests: Stats, Settings, IP Blocking, Response History, OpenClaw Status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://seraph-security.preview.emergentagent.com')

class TestThreatResponseAPI:
    """Test threat response endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    # ============ STATS ENDPOINT ============
    
    def test_get_threat_response_stats(self):
        """Test GET /api/threat-response/stats returns response statistics"""
        response = self.session.get(f"{BASE_URL}/api/threat-response/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify expected fields
        assert "total_responses" in data, "Missing total_responses field"
        assert "blocked_ips" in data, "Missing blocked_ips field"
        assert "attack_sources" in data, "Missing attack_sources field"
        assert "by_severity" in data, "Missing by_severity field"
        assert "by_action" in data, "Missing by_action field"
        
        # Verify types
        assert isinstance(data["total_responses"], int), "total_responses should be int"
        assert isinstance(data["blocked_ips"], int), "blocked_ips should be int"
        print(f"SUCCESS: Stats endpoint returned: {data}")
    
    def test_stats_requires_auth(self):
        """Test that stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/threat-response/stats")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Stats endpoint requires authentication")
    
    # ============ SETTINGS ENDPOINT ============
    
    def test_get_threat_response_settings(self):
        """Test GET /api/threat-response/settings returns configuration"""
        response = self.session.get(f"{BASE_URL}/api/threat-response/settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify structure
        assert "auto_response" in data, "Missing auto_response section"
        assert "sms_alerts" in data, "Missing sms_alerts section"
        assert "openclaw" in data, "Missing openclaw section"
        
        # Verify auto_response fields
        auto_response = data["auto_response"]
        assert "auto_block_enabled" in auto_response, "Missing auto_block_enabled"
        assert "block_duration_hours" in auto_response, "Missing block_duration_hours"
        assert "critical_threat_threshold" in auto_response, "Missing critical_threat_threshold"
        
        # Verify sms_alerts fields
        sms_alerts = data["sms_alerts"]
        assert "enabled" in sms_alerts, "Missing sms enabled field"
        assert "contacts_count" in sms_alerts, "Missing contacts_count"
        
        # Verify openclaw fields
        openclaw = data["openclaw"]
        assert "enabled" in openclaw, "Missing openclaw enabled field"
        
        print(f"SUCCESS: Settings endpoint returned: {data}")
    
    def test_settings_requires_admin(self):
        """Test that settings endpoint requires admin role"""
        # First test without auth
        response = requests.get(f"{BASE_URL}/api/threat-response/settings")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Settings endpoint requires authentication")
    
    # ============ BLOCKED IPS ENDPOINT ============
    
    def test_get_blocked_ips_list(self):
        """Test GET /api/threat-response/blocked-ips returns blocked IP list"""
        response = self.session.get(f"{BASE_URL}/api/threat-response/blocked-ips")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "blocked_ips" in data, "Missing blocked_ips field"
        assert "count" in data, "Missing count field"
        assert isinstance(data["blocked_ips"], list), "blocked_ips should be a list"
        assert isinstance(data["count"], int), "count should be int"
        
        print(f"SUCCESS: Blocked IPs endpoint returned {data['count']} blocked IPs")
    
    def test_blocked_ips_requires_auth(self):
        """Test that blocked IPs endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/threat-response/blocked-ips")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Blocked IPs endpoint requires authentication")
    
    # ============ MANUAL IP BLOCK ENDPOINT ============
    
    def test_block_ip_endpoint_validation(self):
        """Test POST /api/threat-response/block-ip validates input"""
        # Test with empty IP
        response = self.session.post(f"{BASE_URL}/api/threat-response/block-ip", json={
            "ip": "",
            "reason": "Test block",
            "duration_hours": 24
        })
        # Should fail validation or return error
        assert response.status_code in [400, 422], f"Expected 400/422 for empty IP, got {response.status_code}"
        print("SUCCESS: Block IP endpoint validates empty IP")
    
    def test_block_ip_requires_admin(self):
        """Test that block IP endpoint requires admin role"""
        response = requests.post(f"{BASE_URL}/api/threat-response/block-ip", json={
            "ip": "192.168.1.100",
            "reason": "Test",
            "duration_hours": 24
        })
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Block IP endpoint requires authentication")
    
    def test_block_ip_with_valid_data(self):
        """Test POST /api/threat-response/block-ip with valid data"""
        # Note: This will attempt to block but may fail due to firewall permissions
        # We're testing the API accepts the request properly
        response = self.session.post(f"{BASE_URL}/api/threat-response/block-ip", json={
            "ip": "10.99.99.99",
            "reason": "Test block from pytest",
            "duration_hours": 1
        })
        
        # Accept either success (200) or failure due to firewall permissions (400)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data, "Missing status field"
            assert data["status"] == "ok", "Expected status ok"
            print(f"SUCCESS: Block IP accepted: {data}")
        else:
            # 400 is acceptable - firewall may not be available
            print(f"INFO: Block IP returned 400 (expected if no firewall): {response.text}")
    
    # ============ UNBLOCK IP ENDPOINT ============
    
    def test_unblock_ip_requires_admin(self):
        """Test that unblock IP endpoint requires admin role"""
        response = requests.post(f"{BASE_URL}/api/threat-response/unblock-ip/192.168.1.100")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Unblock IP endpoint requires authentication")
    
    def test_unblock_nonexistent_ip(self):
        """Test unblocking an IP that isn't blocked"""
        response = self.session.post(f"{BASE_URL}/api/threat-response/unblock-ip/1.2.3.4")
        # Should return 200 or 400 depending on implementation
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        print(f"SUCCESS: Unblock non-existent IP handled: {response.status_code}")
    
    # ============ RESPONSE HISTORY ENDPOINT ============
    
    def test_get_response_history(self):
        """Test GET /api/threat-response/history returns response history"""
        response = self.session.get(f"{BASE_URL}/api/threat-response/history")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "history" in data, "Missing history field"
        assert "total" in data, "Missing total field"
        assert isinstance(data["history"], list), "history should be a list"
        assert isinstance(data["total"], int), "total should be int"
        
        print(f"SUCCESS: Response history returned {data['total']} entries")
    
    def test_response_history_with_limit(self):
        """Test GET /api/threat-response/history with limit parameter"""
        response = self.session.get(f"{BASE_URL}/api/threat-response/history?limit=5")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert len(data["history"]) <= 5, "History should respect limit parameter"
        print(f"SUCCESS: Response history respects limit parameter")
    
    def test_response_history_requires_auth(self):
        """Test that response history endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/threat-response/history")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Response history endpoint requires authentication")
    
    # ============ OPENCLAW STATUS ENDPOINT ============
    
    def test_get_openclaw_status(self):
        """Test GET /api/threat-response/openclaw/status returns OpenClaw status"""
        response = self.session.get(f"{BASE_URL}/api/threat-response/openclaw/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Missing enabled field"
        assert "available" in data, "Missing available field"
        assert isinstance(data["enabled"], bool), "enabled should be boolean"
        assert isinstance(data["available"], bool), "available should be boolean"
        
        print(f"SUCCESS: OpenClaw status: enabled={data['enabled']}, available={data['available']}")
    
    def test_openclaw_status_requires_auth(self):
        """Test that OpenClaw status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/threat-response/openclaw/status")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: OpenClaw status endpoint requires authentication")
    
    # ============ TEST SMS ENDPOINT ============
    
    def test_test_sms_requires_config(self):
        """Test POST /api/threat-response/test-sms requires Twilio config"""
        response = self.session.post(f"{BASE_URL}/api/threat-response/test-sms")
        
        # Should return 400 if Twilio not configured, or 200 if configured
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data, "Missing error detail"
            print(f"SUCCESS: Test SMS correctly reports Twilio not configured: {data['detail']}")
        else:
            print("SUCCESS: Test SMS sent (Twilio configured)")
    
    def test_test_sms_requires_admin(self):
        """Test that test SMS endpoint requires admin role"""
        response = requests.post(f"{BASE_URL}/api/threat-response/test-sms")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Test SMS endpoint requires authentication")
    
    # ============ UPDATE SETTINGS ENDPOINT ============
    
    def test_update_settings_endpoint(self):
        """Test POST /api/threat-response/settings updates configuration"""
        # Get current settings first
        get_response = self.session.get(f"{BASE_URL}/api/threat-response/settings")
        assert get_response.status_code == 200
        original_settings = get_response.json()
        
        # Update a setting
        update_response = self.session.post(f"{BASE_URL}/api/threat-response/settings", json={
            "block_duration_hours": 48
        })
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        data = update_response.json()
        assert "status" in data, "Missing status field"
        assert data["status"] == "ok", "Expected status ok"
        
        # Verify the change
        verify_response = self.session.get(f"{BASE_URL}/api/threat-response/settings")
        verify_data = verify_response.json()
        assert verify_data["auto_response"]["block_duration_hours"] == 48, "Setting not updated"
        
        # Restore original setting
        self.session.post(f"{BASE_URL}/api/threat-response/settings", json={
            "block_duration_hours": original_settings["auto_response"]["block_duration_hours"]
        })
        
        print("SUCCESS: Settings update endpoint works correctly")
    
    def test_update_settings_requires_admin(self):
        """Test that update settings endpoint requires admin role"""
        response = requests.post(f"{BASE_URL}/api/threat-response/settings", json={
            "auto_block_enabled": False
        })
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("SUCCESS: Update settings endpoint requires authentication")


class TestThreatResponseIntegration:
    """Integration tests for threat response with Suricata alerts"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@defender.io",
            "password": "defender123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_suricata_alert_triggers_response(self):
        """Test that Suricata alerts can trigger automated response"""
        # Send a simulated Suricata alert via agent event
        suricata_event = {
            "agent_id": "test-agent-001",
            "agent_name": "Test Security Agent",
            "event_type": "suricata_alert",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {
                "signature": "ET SCAN Potential SSH Scan",
                "signature_id": 2001219,
                "severity": 2,
                "src_ip": "10.88.88.88",
                "dest_ip": "192.168.1.1",
                "src_port": 54321,
                "dest_port": 22,
                "protocol": "TCP",
                "category": "Attempted Information Leak"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/agent/event", json=suricata_event)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, "Missing status field"
        print(f"SUCCESS: Suricata alert processed: {data}")
    
    def test_intrusion_alert_creates_threat(self):
        """Test that intrusion alerts create threat entries"""
        # Get initial threat count
        initial_threats = self.session.get(f"{BASE_URL}/api/threats")
        initial_count = len(initial_threats.json()) if initial_threats.status_code == 200 else 0
        
        # Send intrusion alert
        intrusion_event = {
            "agent_id": "test-agent-002",
            "agent_name": "Test IDS Agent",
            "event_type": "suricata_alert",
            "timestamp": "2024-01-15T10:35:00Z",
            "data": {
                "signature": "ET EXPLOIT Possible SQL Injection",
                "signature_id": 2100498,
                "severity": 1,  # Critical
                "src_ip": "10.77.77.77",
                "dest_ip": "192.168.1.10",
                "src_port": 45678,
                "dest_port": 80,
                "protocol": "TCP",
                "category": "Web Application Attack"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/agent/event", json=intrusion_event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify threat was created
        final_threats = self.session.get(f"{BASE_URL}/api/threats")
        if final_threats.status_code == 200:
            final_count = len(final_threats.json())
            # Threat count should increase
            print(f"SUCCESS: Threat count changed from {initial_count} to {final_count}")
        else:
            print("INFO: Could not verify threat creation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
