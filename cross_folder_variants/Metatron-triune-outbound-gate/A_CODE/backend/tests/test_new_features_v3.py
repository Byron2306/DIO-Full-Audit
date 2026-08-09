"""
Test Suite for New v3 Features: Correlation, EDR, Threat Intel, Ransomware, Containers, VPN
Tests all 6 new pages and their API endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestAuthentication:
    """Authentication tests - run first to get token"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
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


class TestCorrelationAPI:
    """Correlation Engine API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_correlation_stats(self):
        """GET /api/correlation/stats - Get correlation statistics"""
        response = requests.get(f"{BASE_URL}/api/correlation/stats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        # Verify expected fields
        assert "cached_correlations" in data
        assert "known_threat_actors" in data
        assert "campaign_patterns" in data
        assert "auto_correlate_enabled" in data
    
    def test_correlation_history(self):
        """GET /api/correlation/history - Get correlation history"""
        response = requests.get(f"{BASE_URL}/api/correlation/history?limit=10", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "correlations" in data
        assert "count" in data
    
    def test_correlation_auto_actions(self):
        """GET /api/correlation/auto-actions - Get auto-action history"""
        response = requests.get(f"{BASE_URL}/api/correlation/auto-actions?limit=10", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert "count" in data
    
    def test_correlation_settings(self):
        """POST /api/correlation/settings - Update correlation settings"""
        response = requests.post(
            f"{BASE_URL}/api/correlation/settings?auto_correlate=true", 
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "auto_correlate_enabled" in data
    
    def test_correlation_requires_auth(self):
        """Verify correlation endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/correlation/stats")
        assert response.status_code in [401, 403]


class TestEDRAPI:
    """EDR (Endpoint Detection & Response) API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_edr_status(self):
        """GET /api/edr/status - Get EDR system status"""
        response = requests.get(f"{BASE_URL}/api/edr/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        # Verify expected fields
        assert "fim" in data
        assert "memory_forensics" in data
    
    def test_edr_telemetry(self):
        """GET /api/edr/telemetry - Collect EDR telemetry"""
        response = requests.get(f"{BASE_URL}/api/edr/telemetry", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        # Verify telemetry fields
        assert "cpu_usage" in data
        assert "memory_usage" in data
        assert "process_count" in data
    
    def test_edr_process_tree(self):
        """GET /api/edr/process-tree - Get process tree"""
        response = requests.get(f"{BASE_URL}/api/edr/process-tree", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "process_tree" in data
        assert "count" in data
    
    def test_edr_fim_status(self):
        """GET /api/edr/fim/status - Get FIM status"""
        response = requests.get(f"{BASE_URL}/api/edr/fim/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
    
    def test_edr_usb_devices(self):
        """GET /api/edr/usb/devices - Get USB devices"""
        response = requests.get(f"{BASE_URL}/api/edr/usb/devices", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "count" in data
    
    def test_edr_memory_status(self):
        """GET /api/edr/memory/status - Get memory forensics status"""
        response = requests.get(f"{BASE_URL}/api/edr/memory/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "volatility_installed" in data
    
    def test_edr_requires_auth(self):
        """Verify EDR endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/edr/status")
        assert response.status_code in [401, 403]


class TestThreatIntelAPI:
    """Threat Intelligence API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_threat_intel_stats(self):
        """GET /api/threat-intel/stats - Get threat intel statistics"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/stats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_indicators" in data
        assert "enabled_feeds" in data
        assert "by_type" in data
    
    def test_threat_intel_check_ip(self):
        """POST /api/threat-intel/check - Check single IP indicator"""
        response = requests.post(
            f"{BASE_URL}/api/threat-intel/check",
            json={"value": "8.8.8.8"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "matched" in data
        assert "query_value" in data
        assert "query_type" in data
    
    def test_threat_intel_check_domain(self):
        """POST /api/threat-intel/check - Check domain indicator"""
        response = requests.post(
            f"{BASE_URL}/api/threat-intel/check",
            json={"value": "example.com"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "matched" in data
    
    def test_threat_intel_bulk_check(self):
        """POST /api/threat-intel/check-bulk - Bulk IOC check"""
        response = requests.post(
            f"{BASE_URL}/api/threat-intel/check-bulk",
            json={"values": ["8.8.8.8", "1.1.1.1", "example.com"]},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_checked" in data
        assert "matches_found" in data
        assert "results" in data
    
    def test_threat_intel_feeds(self):
        """GET /api/threat-intel/feeds - Get feeds status"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/feeds", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "enabled_feeds" in data
        assert "total_indicators" in data
    
    def test_threat_intel_recent_matches(self):
        """GET /api/threat-intel/matches/recent - Get recent matches"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/matches/recent?limit=10", headers=self.headers)
        assert response.status_code == 200
    
    def test_threat_intel_requires_auth(self):
        """Verify threat intel endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/stats")
        assert response.status_code in [401, 403]


class TestRansomwareAPI:
    """Ransomware Protection API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_ransomware_status(self):
        """GET /api/ransomware/status - Get ransomware protection status"""
        response = requests.get(f"{BASE_URL}/api/ransomware/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "protection_active" in data
    
    def test_ransomware_canaries(self):
        """GET /api/ransomware/canaries - Get deployed canaries"""
        response = requests.get(f"{BASE_URL}/api/ransomware/canaries", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "active_canaries" in data or "canary_locations" in data
    
    def test_ransomware_protected_folders(self):
        """GET /api/ransomware/protected-folders - Get protected folders"""
        response = requests.get(f"{BASE_URL}/api/ransomware/protected-folders", headers=self.headers)
        assert response.status_code == 200
    
    def test_ransomware_behavioral_stats(self):
        """GET /api/ransomware/behavioral/stats - Get behavioral detection stats"""
        response = requests.get(f"{BASE_URL}/api/ransomware/behavioral/stats", headers=self.headers)
        assert response.status_code == 200
    
    def test_ransomware_requires_auth(self):
        """Verify ransomware endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/ransomware/status")
        assert response.status_code in [401, 403]


class TestContainerSecurityAPI:
    """Container Security API Tests (Trivy - MOCKED)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_container_stats(self):
        """GET /api/containers/stats - Get container security stats"""
        response = requests.get(f"{BASE_URL}/api/containers/stats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "trivy_enabled" in data
    
    def test_container_list(self):
        """GET /api/containers - Get running containers"""
        response = requests.get(f"{BASE_URL}/api/containers", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "containers" in data
        assert "count" in data
    
    def test_container_scan_history(self):
        """GET /api/containers/scans/history - Get scan history"""
        response = requests.get(f"{BASE_URL}/api/containers/scans/history", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "scans" in data
    
    def test_container_runtime_events(self):
        """GET /api/containers/runtime-events - Get runtime events"""
        response = requests.get(f"{BASE_URL}/api/containers/runtime-events", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
    
    def test_container_requires_auth(self):
        """Verify container endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/containers/stats")
        assert response.status_code in [401, 403]


class TestVPNAPI:
    """VPN Integration API Tests (WireGuard - MOCKED)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_vpn_status(self):
        """GET /api/vpn/status - Get VPN server status"""
        response = requests.get(f"{BASE_URL}/api/vpn/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "server" in data
    
    def test_vpn_peers(self):
        """GET /api/vpn/peers - Get VPN peers"""
        response = requests.get(f"{BASE_URL}/api/vpn/peers", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "peers" in data
        assert "count" in data
    
    def test_vpn_kill_switch(self):
        """GET /api/vpn/kill-switch - Get kill switch status"""
        response = requests.get(f"{BASE_URL}/api/vpn/kill-switch", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
    
    def test_vpn_requires_auth(self):
        """Verify VPN endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/vpn/status")
        assert response.status_code in [401, 403]


class TestNavigationIntegration:
    """Test that all new pages are accessible via navigation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_all_new_endpoints_accessible(self):
        """Verify all 6 new feature endpoints are accessible"""
        endpoints = [
            "/api/correlation/stats",
            "/api/edr/status",
            "/api/threat-intel/stats",
            "/api/ransomware/status",
            "/api/containers/stats",
            "/api/vpn/status"
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=self.headers)
            assert response.status_code == 200, f"Endpoint {endpoint} failed with status {response.status_code}"
            print(f"✓ {endpoint} - OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
