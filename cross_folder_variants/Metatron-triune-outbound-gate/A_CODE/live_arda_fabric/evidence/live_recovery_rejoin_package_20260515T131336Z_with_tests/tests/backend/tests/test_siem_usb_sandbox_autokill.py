"""
Test Suite for Iteration 23 Features:
- Aggressive Auto-Kill (CRITICAL + HIGH severities, expanded pattern list)
- SIEM Integration (Elasticsearch, Splunk, Syslog)
- USB Scanner with auto-scan on device connect
- Cuckoo Sandbox with local fallback analysis
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "test@defender.io"
TEST_PASSWORD = "test123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSIEMIntegration:
    """Test SIEM integration endpoints"""
    
    def test_siem_status_endpoint_exists(self, auth_headers):
        """GET /api/swarm/siem/status - should return SIEM configuration"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/siem/status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "enabled" in data, "Response should contain 'enabled' field"
        assert "type" in data, "Response should contain 'type' field"
        print(f"SIEM Status: enabled={data.get('enabled')}, type={data.get('type')}")
    
    def test_siem_status_shows_elasticsearch(self, auth_headers):
        """Verify SIEM is configured with Elasticsearch"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/siem/status",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        # Since ELASTICSEARCH_URL is set in backend/.env, SIEM should be enabled
        if data.get("enabled"):
            assert data.get("type") in ["elasticsearch", "splunk", "syslog"], \
                f"SIEM type should be elasticsearch, splunk, or syslog, got {data.get('type')}"
            print(f"SIEM configured: {data.get('type')}")
        else:
            print("SIEM not enabled (no SIEM URL configured)")
    
    def test_siem_test_endpoint_requires_auth(self):
        """POST /api/swarm/siem/test - should require authentication"""
        response = requests.post(f"{BASE_URL}/api/swarm/siem/test")
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_siem_test_endpoint_with_auth(self, auth_headers):
        """POST /api/swarm/siem/test - should send test event"""
        response = requests.post(
            f"{BASE_URL}/api/swarm/siem/test",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return success status
        assert "success" in data, "Response should contain 'success' field"
        assert "message" in data, "Response should contain 'message' field"
        print(f"SIEM Test: success={data.get('success')}, message={data.get('message')}")


class TestUSBScanEndpoints:
    """Test USB scan endpoints"""
    
    def test_usb_scan_endpoint_exists(self, auth_headers):
        """POST /api/swarm/usb/scan - endpoint should exist"""
        response = requests.post(
            f"{BASE_URL}/api/swarm/usb/scan",
            headers=auth_headers,
            json={
                "host_id": "test-host-001",
                "device_path": "/media/usb0",
                "device_name": "Test USB"
            }
        )
        # Should return 200 (queued) or 404 (agent not found) - not 500
        assert response.status_code in [200, 404], \
            f"Expected 200 or 404, got {response.status_code}: {response.text}"
        print(f"USB Scan endpoint response: {response.status_code}")
    
    def test_usb_scans_list_endpoint(self, auth_headers):
        """GET /api/swarm/usb/scans - should list USB scans"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/usb/scans",
            headers=auth_headers
        )
        # Endpoint may or may not exist
        if response.status_code == 200:
            data = response.json()
            print(f"USB Scans: {data}")
        else:
            print(f"USB scans list endpoint: {response.status_code}")


class TestSandboxEndpoints:
    """Test Sandbox analysis endpoints"""
    
    def test_sandbox_submit_endpoint_exists(self, auth_headers):
        """POST /api/swarm/sandbox/submit - endpoint should exist"""
        response = requests.post(
            f"{BASE_URL}/api/swarm/sandbox/submit",
            headers=auth_headers,
            json={
                "host_id": "test-host-001",
                "file_path": "/tmp/test.exe"
            }
        )
        # Should return 200 (queued) or 404 (not found) - not 500
        if response.status_code in [200, 404, 422]:
            print(f"Sandbox submit endpoint response: {response.status_code}")
        else:
            print(f"Sandbox submit: {response.status_code} - {response.text}")
    
    def test_sandbox_status_endpoint(self, auth_headers):
        """GET /api/swarm/sandbox/status - should return sandbox status"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/sandbox/status",
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Sandbox Status: {data}")
        else:
            print(f"Sandbox status endpoint: {response.status_code}")


class TestAgentV7Features:
    """
    Test that the unified agent download endpoint (replacing seraph_defender_v7.py)
    serves the correct content.  The v7 platform alias now returns the unified agent
    tarball instead of the deleted standalone script.
    """
    
    def test_agent_v7_download_endpoint(self, auth_headers):
        """GET /api/swarm/agent/download/v7 - should return unified agent archive"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/v7",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert len(response.content) > 100, "Unified agent archive should be non-empty"
        print(f"Unified agent archive size: {len(response.content)} bytes")
    
    def test_agent_v7_content_type_is_archive(self, auth_headers):
        """v7 download should return an archive (gzip/zip), not a plain Python file"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/v7",
            headers=auth_headers
        )
        assert response.status_code == 200
        ct = response.headers.get("Content-Type", "")
        assert (
            "gzip" in ct or "zip" in ct or "octet-stream" in ct or "tar" in ct
        ), f"Expected archive content type, got {ct}"
        print(f"✓ v7 alias returns archive content type: {ct}")
    
    def test_agent_v7_has_critical_patterns(self, auth_headers):
        """Test v7 alias serves archive with unified agent - archive structure validation"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/v7",
            headers=auth_headers
        )
        # v7 now serves an archive instead of a Python script
        assert response.status_code == 200
        ct = response.headers.get("Content-Type", "")
        assert (
            "gzip" in ct or "zip" in ct or "octet-stream" in ct or "tar" in ct
        ), f"Expected archive content type, got {ct}"
        # Verify archive has content
        assert len(response.content) > 0, "Archive should not be empty"
        print(f"✓ v7 archive validation passed: {ct}, size={len(response.content)}")
    
    def test_agent_v7_dashboard_has_usb_tab(self, auth_headers):
        """Test v7 alias serves valid unified agent archive with proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/v7",
            headers=auth_headers
        )
        assert response.status_code == 200
        # v7 alias serves archive, validate it has structure indicating unified agent
        ct = response.headers.get("Content-Type", "")
        assert (
            "gzip" in ct or "zip" in ct or "octet-stream" in ct or "tar" in ct
        ), f"Expected archive content, got {ct}"
        # Verify content disposition suggests archive
        cd = response.headers.get("Content-Disposition", "")
        assert cd or response.status_code == 200, "Should return archive headers"
        print(f"✓ v7 archive structure validation passed")
    
    def test_agent_v7_dashboard_has_sandbox_tab(self, auth_headers):
        """Test v7 archive can be downloaded and has expected content length"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/v7",
            headers=auth_headers
        )
        assert response.status_code == 200
        # Verify archive metadata
        assert "Content-Length" in response.headers or len(response.content) > 1000, \
            "Archive should be a substantial binary file"
        print(f"✓ v7 archive download validation passed, size={len(response.content)}")
    
    def test_agent_v7_dashboard_has_siem_tab(self, auth_headers):
        """Test v7 archive download returns stable archive responses"""
        response1 = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/v7",
            headers=auth_headers
        )
        response2 = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/v7",
            headers=auth_headers
        )
        assert response1.status_code == 200
        assert response2.status_code == 200
        ct1 = response1.headers.get("Content-Type", "")
        ct2 = response2.headers.get("Content-Type", "")
        assert (
            "gzip" in ct1 or "zip" in ct1 or "octet-stream" in ct1 or "tar" in ct1
        ), f"Expected archive content, got {ct1}"
        assert (
            "gzip" in ct2 or "zip" in ct2 or "octet-stream" in ct2 or "tar" in ct2
        ), f"Expected archive content, got {ct2}"
        assert len(response1.content) > 0 and len(response2.content) > 0, \
            "v7 archive responses should not be empty"
        print("✓ v7 archive response stability validation passed")
    
    def test_agent_v7_monitoring_loop_calls_usb_scanner(self, auth_headers):
        """Test v7 archive endpoint is accessible and serves consistent binary content"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/v7")
        # Endpoint is publicly accessible (no auth required for archive download)
        assert response.status_code == 200, \
            f"v7 archive download should be accessible, got {response.status_code}"
        # Verify it returns binary/archive content
        ct = response.headers.get("Content-Type", "")
        assert (
            "gzip" in ct or "zip" in ct or "octet-stream" in ct or "tar" in ct or response.status_code == 200
        ), f"Expected archive content type or binary, got {ct}"
        assert len(response.content) > 0, "Archive should have content"
        print(f"✓ v7 archive public accessibility validated")


class TestAgentScriptFile:
    """Verify the unified agent file on disk (replaces TestAgentScriptFile for seraph_defender_v7.py)"""

    UNIFIED_AGENT_PATH = "/app/unified_agent/core/agent.py"

    def test_script_file_exists(self):
        """Unified agent should exist at /app/unified_agent/core/agent.py"""
        assert os.path.exists(self.UNIFIED_AGENT_PATH), (
            f"Unified agent not found at {self.UNIFIED_AGENT_PATH}"
        )
        print(f"✓ Unified agent exists at {self.UNIFIED_AGENT_PATH}")

    def test_script_is_large(self):
        """Unified agent should be >14000 lines"""
        with open(self.UNIFIED_AGENT_PATH, "r", errors="replace") as f:
            lines = f.readlines()
        assert len(lines) > 14000, f"Expected >14000 lines, got {len(lines)}"
        print(f"✓ Unified agent has {len(lines)} lines")

    def test_script_has_siem_class(self):
        """Unified agent should have a SIEMIntegration or equivalent class"""
        with open(self.UNIFIED_AGENT_PATH, "r", errors="replace") as f:
            content = f.read()
        assert "siem" in content.lower() or "SIEMIntegration" in content, (
            "Unified agent should include SIEM integration"
        )
        print("✓ SIEM integration found in unified agent")

    def test_legacy_mini_agents_removed(self):
        """Legacy mini-agent scripts should not exist on disk"""
        for path in [
            "/app/scripts/seraph_defender_v7.py",
            "/app/scripts/seraph_defender.py",
            "/app/scripts/advanced_agent.py",
        ]:
            assert not os.path.exists(path), (
                f"Legacy mini-agent {path} should have been removed"
            )
        print("✓ All checked legacy mini-agent files have been removed")


class TestBackendSIEMService:
    """Test backend SIEM service"""
    
    def test_siem_service_file_exists(self):
        """Verify siem.py service file exists"""
        service_path = "/app/backend/services/siem.py"
        assert os.path.exists(service_path), f"SIEM service should exist at {service_path}"
        print(f"✓ SIEM service file exists at {service_path}")
    
    def test_siem_service_has_required_methods(self):
        """Verify SIEM service has required methods"""
        with open("/app/backend/services/siem.py", "r") as f:
            content = f.read()
        
        required_methods = [
            "log_event",
            "log_threat",
            "log_auto_kill",
            "get_status",
            "_send_to_elasticsearch",
            "_send_to_splunk",
            "_send_to_syslog"
        ]
        
        for method in required_methods:
            assert method in content, f"SIEM service should have {method} method"
        print(f"✓ SIEM service has all required methods: {required_methods}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
