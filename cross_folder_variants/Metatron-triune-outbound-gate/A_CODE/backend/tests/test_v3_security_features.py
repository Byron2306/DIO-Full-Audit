"""
Test Suite for v3.0 Security Features
======================================
Tests for:
1. Threat Intelligence Feeds (Abuse.ch, Emerging Threats)
2. Ransomware Protection (canary files, behavioral detection)
3. Container Security (Trivy scanner)
4. VPN Integration (WireGuard)

API Version: 3.0.0
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "test@defender.io"
TEST_PASSWORD = "test123"


class TestAPIVersion:
    """Verify API version is 3.0.0"""
    
    def test_api_version_is_3_0_0(self):
        """API version should be 3.0.0"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "3.0.0", f"Expected version 3.0.0, got {data.get('version')}"
        print(f"✓ API version is {data['version']}")
    
    def test_api_features_include_v3_features(self):
        """API should list all v3 features"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        features = data.get("features", [])
        
        expected_features = [
            "threat_intelligence_feeds",
            "ransomware_protection",
            "container_security",
            "vpn_integration"
        ]
        
        for feature in expected_features:
            assert feature in features, f"Missing feature: {feature}"
            print(f"✓ Feature present: {feature}")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        token = response.json().get("access_token")  # Fixed: field is access_token not token
        print(f"✓ Authenticated as {TEST_EMAIL}")
        return token
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestThreatIntelligence:
    """Test Threat Intelligence Feed endpoints"""
    
    def test_get_threat_intel_stats(self, auth_headers):
        """GET /api/threat-intel/stats - Should return ~20k indicators"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_indicators" in data, "Missing total_indicators field"
        assert "by_feed" in data, "Missing by_feed field"
        assert "by_type" in data, "Missing by_type field"
        assert "enabled_feeds" in data, "Missing enabled_feeds field"
        
        total = data["total_indicators"]
        print(f"✓ Threat Intel Stats: {total} total indicators")
        print(f"  - Enabled feeds: {data['enabled_feeds']}")
        print(f"  - By type: {data['by_type']}")
        
        # Should have significant number of indicators (feeds already updated)
        assert total > 0, f"Expected indicators > 0, got {total}"
    
    def test_check_single_indicator_ip(self, auth_headers):
        """POST /api/threat-intel/check - Check IP address"""
        # Test with a known malicious IP from Feodo Tracker (if available)
        test_ip = "1.2.3.4"  # Test IP
        
        response = requests.post(
            f"{BASE_URL}/api/threat-intel/check",
            headers=auth_headers,
            json={"value": test_ip, "ioc_type": "ip"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "matched" in data, "Missing matched field"
        assert "query_value" in data, "Missing query_value field"
        assert "query_type" in data, "Missing query_type field"
        assert "matched_at" in data, "Missing matched_at field"
        
        print(f"✓ IOC Check for {test_ip}: matched={data['matched']}, type={data['query_type']}")
    
    def test_check_single_indicator_domain(self, auth_headers):
        """POST /api/threat-intel/check - Check domain"""
        test_domain = "malware-test.example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/threat-intel/check",
            headers=auth_headers,
            json={"value": test_domain}  # Auto-detect type
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["query_type"] == "domain", f"Expected type 'domain', got {data['query_type']}"
        print(f"✓ IOC Check for domain: matched={data['matched']}")
    
    def test_check_bulk_indicators(self, auth_headers):
        """POST /api/threat-intel/check-bulk - Check multiple values"""
        test_values = [
            "192.168.1.1",
            "10.0.0.1",
            "malware.example.com",
            "http://evil.example.com/malware.exe",
            "d41d8cd98f00b204e9800998ecf8427e"  # MD5 hash
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/threat-intel/check-bulk",
            headers=auth_headers,
            json={"values": test_values}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_checked" in data, "Missing total_checked field"
        assert "matches_found" in data, "Missing matches_found field"
        assert "results" in data, "Missing results field"
        
        assert data["total_checked"] == len(test_values), f"Expected {len(test_values)} checked"
        assert len(data["results"]) == len(test_values), "Results count mismatch"
        
        print(f"✓ Bulk IOC Check: {data['total_checked']} checked, {data['matches_found']} matches")
    
    def test_get_feeds_status(self, auth_headers):
        """GET /api/threat-intel/feeds - Get feed status"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/feeds", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled_feeds" in data, "Missing enabled_feeds field"
        assert "by_feed" in data, "Missing by_feed field"
        assert "total_indicators" in data, "Missing total_indicators field"
        
        print(f"✓ Feeds Status: {data['enabled_feeds']}")
        for feed, info in data.get("by_feed", {}).items():
            print(f"  - {feed}: {info.get('total', 0)} indicators")
    
    def test_get_recent_matches(self, auth_headers):
        """GET /api/threat-intel/matches/recent - Get recent matches"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/matches/recent", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ Recent Matches: {len(data)} matches returned")


class TestRansomwareProtection:
    """Test Ransomware Protection endpoints"""
    
    def test_get_ransomware_status(self, auth_headers):
        """GET /api/ransomware/status - Get protection status"""
        response = requests.get(f"{BASE_URL}/api/ransomware/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "protection_active" in data, "Missing protection_active field"
        assert "canary_status" in data, "Missing canary_status field"
        assert "behavioral_status" in data, "Missing behavioral_status field"
        assert "protected_folders" in data, "Missing protected_folders field"
        assert "config" in data, "Missing config field"
        
        print(f"✓ Ransomware Status:")
        print(f"  - Protection active: {data['protection_active']}")
        print(f"  - Canary status: {data['canary_status']}")
        print(f"  - Protected folders: {data['protected_folders']}")
    
    def test_deploy_canaries(self, auth_headers):
        """POST /api/ransomware/canaries/deploy - Deploy canary files"""
        response = requests.post(
            f"{BASE_URL}/api/ransomware/canaries/deploy",
            headers=auth_headers,
            json={"directories": ["/tmp"]}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Missing message field"
        assert "canaries" in data, "Missing canaries field"
        
        print(f"✓ Deploy Canaries: {data['message']}")
        print(f"  - Deployed: {len(data['canaries'])} canaries")
    
    def test_get_canaries(self, auth_headers):
        """GET /api/ransomware/canaries - Get deployed canaries"""
        response = requests.get(f"{BASE_URL}/api/ransomware/canaries", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_canaries" in data, "Missing total_canaries field"
        assert "active_canaries" in data, "Missing active_canaries field"
        assert "triggered_canaries" in data, "Missing triggered_canaries field"
        
        print(f"✓ Canaries Status:")
        print(f"  - Total: {data['total_canaries']}")
        print(f"  - Active: {data['active_canaries']}")
        print(f"  - Triggered: {data['triggered_canaries']}")
    
    def test_get_protected_folders(self, auth_headers):
        """GET /api/ransomware/protected-folders - Get protected folders"""
        response = requests.get(f"{BASE_URL}/api/ransomware/protected-folders", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ Protected Folders: {len(data)} folders")
    
    def test_get_behavioral_stats(self, auth_headers):
        """GET /api/ransomware/behavioral/stats - Get behavioral detection stats"""
        response = requests.get(f"{BASE_URL}/api/ransomware/behavioral/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "monitoring" in data, "Missing monitoring field"
        assert "recent_file_events" in data, "Missing recent_file_events field"
        assert "recent_rename_events" in data, "Missing recent_rename_events field"
        
        print(f"✓ Behavioral Stats:")
        print(f"  - Monitoring: {data['monitoring']}")
        print(f"  - Recent file events: {data['recent_file_events']}")


class TestContainerSecurity:
    """Test Container Security (Trivy) endpoints"""
    
    def test_get_container_stats(self, auth_headers):
        """GET /api/containers/stats - Get container security stats"""
        response = requests.get(f"{BASE_URL}/api/containers/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "trivy_enabled" in data, "Missing trivy_enabled field"
        assert "falco_enabled" in data, "Missing falco_enabled field"
        assert "auto_scan" in data, "Missing auto_scan field"
        assert "cached_scans" in data, "Missing cached_scans field"
        
        print(f"✓ Container Stats:")
        print(f"  - Trivy enabled: {data['trivy_enabled']}")
        print(f"  - Falco enabled: {data['falco_enabled']}")
        print(f"  - Cached scans: {data['cached_scans']}")
    
    def test_get_containers(self, auth_headers):
        """GET /api/containers - Get running containers"""
        response = requests.get(f"{BASE_URL}/api/containers", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "containers" in data, "Missing containers field"
        assert "count" in data, "Missing count field"
        
        print(f"✓ Containers: {data['count']} running")
    
    def test_get_scan_history(self, auth_headers):
        """GET /api/containers/scans/history - Get scan history"""
        response = requests.get(f"{BASE_URL}/api/containers/scans/history", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "scans" in data, "Missing scans field"
        assert "total" in data, "Missing total field"
        
        print(f"✓ Scan History: {data['total']} scans")
    
    def test_get_runtime_events(self, auth_headers):
        """GET /api/containers/runtime-events - Get runtime events"""
        response = requests.get(f"{BASE_URL}/api/containers/runtime-events", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events" in data, "Missing events field"
        assert "count" in data, "Missing count field"
        
        print(f"✓ Runtime Events: {data['count']} events")


class TestVPNIntegration:
    """Test VPN (WireGuard) Integration endpoints"""
    
    def test_get_vpn_status(self, auth_headers):
        """GET /api/vpn/status - Get VPN status"""
        response = requests.get(f"{BASE_URL}/api/vpn/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "server" in data, "Missing server field"
        assert "kill_switch" in data, "Missing kill_switch field"
        assert "config" in data, "Missing config field"
        assert "peers" in data, "Missing peers field"
        
        server_status = data["server"].get("status", "unknown")
        print(f"✓ VPN Status:")
        print(f"  - Server status: {server_status}")
        print(f"  - Kill switch: {data['kill_switch']}")
        print(f"  - Peers: {len(data['peers'])}")
        
        # WireGuard may not be installed - that's expected
        if server_status == "not_installed":
            print("  - Note: WireGuard not installed (expected in this environment)")
    
    def test_get_vpn_peers(self, auth_headers):
        """GET /api/vpn/peers - Get VPN peers"""
        response = requests.get(f"{BASE_URL}/api/vpn/peers", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "peers" in data, "Missing peers field"
        assert "count" in data, "Missing count field"
        
        print(f"✓ VPN Peers: {data['count']} peers")
    
    def test_get_kill_switch_status(self, auth_headers):
        """GET /api/vpn/kill-switch - Get kill switch status"""
        response = requests.get(f"{BASE_URL}/api/vpn/kill-switch", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Missing enabled field"
        assert "interface" in data, "Missing interface field"
        
        print(f"✓ Kill Switch: enabled={data['enabled']}, interface={data['interface']}")


class TestAuthenticationRequired:
    """Test that all v3 endpoints require authentication"""
    
    def test_threat_intel_requires_auth(self):
        """Threat intel endpoints should require auth"""
        response = requests.get(f"{BASE_URL}/api/threat-intel/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Threat intel requires authentication")
    
    def test_ransomware_requires_auth(self):
        """Ransomware endpoints should require auth"""
        response = requests.get(f"{BASE_URL}/api/ransomware/status")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Ransomware requires authentication")
    
    def test_containers_requires_auth(self):
        """Container endpoints should require auth"""
        response = requests.get(f"{BASE_URL}/api/containers/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Containers requires authentication")
    
    def test_vpn_requires_auth(self):
        """VPN endpoints should require auth"""
        response = requests.get(f"{BASE_URL}/api/vpn/status")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ VPN requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
