"""
Test suite for Data Visibility Features - Testing endpoints that were reported as lacking frontend data visibility
Tests: Timeline, Correlation, ML Prediction, Network Hosts, Zero Trust, Auto Response, VPN, Browser Isolation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestAuthentication:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "testuser@test.com"


class TestTimelineEndpoints:
    """Timeline page data visibility tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_get_recent_timelines(self, auth_token):
        """Test GET /api/timelines/recent returns timeline data"""
        response = requests.get(
            f"{BASE_URL}/api/timelines/recent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "timelines" in data
        assert "count" in data
        assert isinstance(data["timelines"], list)
        
        # Verify data is present (seeded data should exist)
        assert data["count"] > 0, "No timeline data returned - data visibility issue"
        
        # Verify timeline item structure
        if data["timelines"]:
            timeline = data["timelines"][0]
            assert "threat_id" in timeline
            assert "threat_name" in timeline
            assert "severity" in timeline


class TestCorrelationEndpoints:
    """Correlation page data visibility tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_get_correlation_history(self, auth_token):
        """Test GET /api/correlation/history returns correlation data with attribution"""
        response = requests.get(
            f"{BASE_URL}/api/correlation/history?limit=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "correlations" in data
        assert "count" in data
        
        # Verify data is present
        assert data["count"] > 0, "No correlation data returned - data visibility issue"
        
        # Verify correlation item has attribution data
        if data["correlations"]:
            correlation = data["correlations"][0]
            assert "threat_id" in correlation
            assert "attribution" in correlation
            assert "confidence" in correlation
            
            # Verify attribution has threat actor info
            attribution = correlation["attribution"]
            assert "threat_actor" in attribution, "Missing threat actor in attribution"


class TestMLPredictionEndpoints:
    """ML Prediction page data visibility tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_get_predictions(self, auth_token):
        """Test GET /api/ml/predictions returns prediction data"""
        response = requests.get(
            f"{BASE_URL}/api/ml/predictions?limit=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "predictions" in data
        assert "count" in data
        
        # Verify data is present
        assert data["count"] > 0, "No ML prediction data returned - data visibility issue"
        
        # Verify prediction item structure
        if data["predictions"]:
            prediction = data["predictions"][0]
            assert "prediction_id" in prediction
            assert "category" in prediction
            assert "risk_level" in prediction
            assert "threat_score" in prediction
            
            # Verify prediction categories include expected types
            categories = [p["category"] for p in data["predictions"]]
            expected_categories = ["ransomware", "apt", "insider_threat", "malware", "data_exfiltration"]
            found_categories = [c for c in expected_categories if c in categories]
            assert len(found_categories) > 0, f"Expected categories not found. Got: {categories}"


class TestNetworkHostsEndpoints:
    """Network hosts data visibility tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_get_network_hosts(self, auth_token):
        """Test GET /api/network/hosts returns discovered hosts"""
        response = requests.get(
            f"{BASE_URL}/api/network/hosts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "hosts" in data
        assert "count" in data
        
        # Verify data is present
        assert data["count"] > 0, "No network hosts data returned - data visibility issue"
        
        # Verify host item structure
        if data["hosts"]:
            host = data["hosts"][0]
            assert "ip" in host
            assert "hostname" in host
            assert "status" in host
            assert "risk_level" in host


class TestZeroTrustEndpoints:
    """Zero Trust page data visibility tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_list_devices(self, auth_token):
        """Test GET /api/zero-trust/devices returns registered devices"""
        response = requests.get(
            f"{BASE_URL}/api/zero-trust/devices",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "devices" in data
        assert "count" in data
        
        # Verify data is present
        assert data["count"] > 0, "No Zero Trust devices returned - data visibility issue"
        
        # Verify device item structure
        if data["devices"]:
            device = data["devices"][0]
            assert "device_id" in device
            assert "device_name" in device
            assert "device_type" in device
            assert "trust_score" in device or "trust_level" in device
    
    def test_register_device(self, auth_token):
        """Test POST /api/zero-trust/devices creates device in database"""
        import uuid
        device_id = f"test-device-{uuid.uuid4().hex[:8]}"
        
        response = requests.post(
            f"{BASE_URL}/api/zero-trust/devices",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "device_id": device_id,
                "device_name": "Test Device",
                "device_type": "laptop",
                "os_info": {"name": "Windows 11", "version": "22H2"},
                "security_posture": {"antivirus": True, "firewall": True}
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify device was created
        assert data["device_id"] == device_id
        assert data["device_name"] == "Test Device"
        
        # Verify device appears in list (persisted to database)
        list_response = requests.get(
            f"{BASE_URL}/api/zero-trust/devices",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        devices = list_response.json()["devices"]
        device_ids = [d["device_id"] for d in devices]
        assert device_id in device_ids, "Device not persisted to database"


class TestAutoResponseEndpoints:
    """Auto Response page functionality tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_get_response_settings(self, auth_token):
        """Test GET /api/threat-response/settings returns proper auto_response structure"""
        response = requests.get(
            f"{BASE_URL}/api/threat-response/settings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify auto_response structure exists
        assert "auto_response" in data, "Missing auto_response in settings"
        auto_response = data["auto_response"]
        assert "auto_block_enabled" in auto_response
        assert "block_duration_hours" in auto_response
    
    def test_toggle_auto_block(self, auth_token):
        """Test POST /api/threat-response/settings/auto-block toggles state"""
        # Get current state
        settings_response = requests.get(
            f"{BASE_URL}/api/threat-response/settings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        current_state = settings_response.json()["auto_response"]["auto_block_enabled"]
        
        # Toggle to opposite state
        new_state = not current_state
        response = requests.post(
            f"{BASE_URL}/api/threat-response/settings/auto-block?enabled={str(new_state).lower()}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_block_enabled"] == new_state
        
        # Verify state was persisted
        verify_response = requests.get(
            f"{BASE_URL}/api/threat-response/settings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert verify_response.json()["auto_response"]["auto_block_enabled"] == new_state
        
        # Toggle back to original state
        requests.post(
            f"{BASE_URL}/api/threat-response/settings/auto-block?enabled={str(current_state).lower()}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )


class TestVPNEndpoints:
    """VPN page data visibility tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_get_vpn_status(self, auth_token):
        """Test GET /api/vpn/status returns server public key and instructions"""
        response = requests.get(
            f"{BASE_URL}/api/vpn/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "server" in data
        assert "config" in data
        
        # Verify server info
        server = data["server"]
        assert "status" in server
        assert "public_key" in server, "Missing server public key - VPN not configured"
        assert len(server["public_key"]) > 0, "Empty server public key"
        
        # Verify config
        config = data["config"]
        assert "port" in config
        assert config["port"] == 51820  # WireGuard default port


class TestBrowserIsolationEndpoints:
    """Browser Isolation page functionality tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test123!"
        })
        return response.json()["access_token"]
    
    def test_get_isolation_stats(self, auth_token):
        """Test GET /api/browser-isolation/stats returns stats"""
        response = requests.get(
            f"{BASE_URL}/api/browser-isolation/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify stats structure
        assert "total_sessions" in data or "blocked_domains" in data
    
    def test_get_isolation_modes(self, auth_token):
        """Test GET /api/browser-isolation/modes returns isolation modes"""
        response = requests.get(
            f"{BASE_URL}/api/browser-isolation/modes",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify modes structure
        assert "modes" in data
        modes = data["modes"]
        assert len(modes) > 0, "No isolation modes returned"
        
        # Verify expected modes exist
        mode_ids = [m["id"] for m in modes]
        expected_modes = ["full", "cdr", "read_only", "pixel_push"]
        for expected in expected_modes:
            assert expected in mode_ids, f"Missing isolation mode: {expected}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
