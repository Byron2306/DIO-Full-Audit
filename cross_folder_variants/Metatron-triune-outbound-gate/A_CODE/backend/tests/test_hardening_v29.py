"""
Seraph AI System-Wide Hardening Test v29
=========================================
Comprehensive test suite for all new features:
- SOAR Page with Templates (14 templates)
- Tenants Page
- Unified Agent Page
- VNS Alerts Page
- Browser Extension Page
- Setup Guide Page
- All relevant API endpoints
"""

import pytest
import requests
import os
from datetime import datetime

# Get API URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "test@defender.io"
TEST_PASSWORD = "test123"

class TestAuthAndSetup:
    """Authentication and basic setup tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        # Try login first
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            return response.json().get("access_token")
        
        # If login fails, register new user
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test User"
        })
        
        if response.status_code in [200, 201]:
            return response.json().get("access_token")
        
        # Try login again after registration
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            return response.json().get("access_token")
        
        pytest.skip(f"Authentication failed: {response.status_code}")
        return None
    
    @pytest.fixture
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")


class TestSOARTemplates:
    """SOAR Playbook Templates tests - Verify 14 templates"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth required")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_soar_templates_count(self, headers):
        """Test SOAR templates endpoint returns 14 templates"""
        response = requests.get(f"{BASE_URL}/api/soar/templates", headers=headers)
        assert response.status_code == 200
        data = response.json()
        templates = data.get("templates", [])
        count = data.get("count", len(templates))
        
        print(f"✓ SOAR templates count: {count}")
        assert count == 14, f"Expected 14 templates, got {count}"
        
        # Verify templates have required fields
        for tpl in templates:
            assert "id" in tpl
            assert "name" in tpl
            assert "description" in tpl
        
        print("✓ All 14 SOAR templates verified")
    
    def test_soar_stats(self, headers):
        """Test SOAR stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/soar/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_playbooks" in data or "success_rate" in data
        print("✓ SOAR stats endpoint working")
    
    def test_soar_playbooks(self, headers):
        """Test SOAR playbooks list"""
        response = requests.get(f"{BASE_URL}/api/soar/playbooks", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "playbooks" in data
        print(f"✓ SOAR playbooks: {len(data.get('playbooks', []))} found")


class TestTenantsAPI:
    """Multi-Tenant Management API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth required")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_tenants_list(self, headers):
        """Test tenants list endpoint"""
        response = requests.get(f"{BASE_URL}/api/tenants/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "tenants" in data
        print(f"✓ Tenants list: {len(data.get('tenants', []))} tenants")
    
    def test_tenants_tiers(self, headers):
        """Test tenants tiers endpoint - should return 4 tiers"""
        response = requests.get(f"{BASE_URL}/api/tenants/tiers", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        expected_tiers = ["free", "starter", "professional", "enterprise"]
        for tier in expected_tiers:
            assert tier in data, f"Missing tier: {tier}"
            assert "quota" in data[tier], f"Missing quota for {tier}"
        
        print("✓ All 4 tenant tiers verified (free, starter, professional, enterprise)")
    
    def test_tenants_stats(self, headers):
        """Test tenants stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/tenants/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_tenants" in data or "active_tenants" in data
        print("✓ Tenants stats endpoint working")


class TestUnifiedAgentAPI:
    """Unified Agent Dashboard API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth required")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_unified_stats(self, headers):
        """Test unified agent stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/unified/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check expected fields
        expected_fields = ["total_agents", "online_agents", "supported_platforms"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Unified agent stats: {data.get('total_agents', 0)} total agents")
    
    def test_unified_agents_list(self, headers):
        """Test unified agents list"""
        response = requests.get(f"{BASE_URL}/api/unified/agents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        print(f"✓ Unified agents list: {len(data.get('agents', []))} agents")
    
    def test_unified_dashboard(self, headers):
        """Test unified dashboard endpoint"""
        response = requests.get(f"{BASE_URL}/api/unified/dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data or "alerts" in data
        print("✓ Unified dashboard endpoint working")


class TestVNSAlertsAPI:
    """VNS Alerts (Slack/Email) API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth required")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_alerts_status(self, headers):
        """Test VNS alerts status endpoint"""
        response = requests.get(f"{BASE_URL}/api/advanced/alerts/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Check for expected fields
        assert "enabled" in data or "slack_configured" in data or "stats" in data
        print("✓ VNS alerts status endpoint working")


class TestBrowserExtensionAPI:
    """Browser Extension API tests"""
    
    def test_extension_download(self):
        """Test extension download endpoint"""
        response = requests.get(f"{BASE_URL}/api/extension/download")
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/zip' or 'zip' in response.headers.get('content-type', '')
        # Check file size is reasonable (should be > 100KB)
        assert len(response.content) > 100000, "Extension ZIP too small"
        print(f"✓ Extension download: {len(response.content)} bytes")
    
    def test_extension_check_domain_safe(self):
        """Test domain check - safe domain"""
        response = requests.post(f"{BASE_URL}/api/extension/check-domain", json={
            "domain": "google.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_malicious") == False
        print("✓ Domain check (safe): google.com not flagged")
    
    def test_extension_check_domain_malicious(self):
        """Test domain check - known malicious domain"""
        response = requests.post(f"{BASE_URL}/api/extension/check-domain", json={
            "domain": "malware-site.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_malicious") == True
        assert "reason" in data
        print(f"✓ Domain check (malicious): malware-site.com flagged - {data.get('reason')}")


class TestQuantumAndAdvancedAPI:
    """Quantum Security and Advanced Services API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth required")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_quantum_status(self, headers):
        """Test quantum security status"""
        response = requests.get(f"{BASE_URL}/api/advanced/quantum/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data or "enabled" in data
        print(f"✓ Quantum security status: mode={data.get('mode', 'unknown')}")
    
    def test_sandbox_status(self, headers):
        """Test Cuckoo sandbox status"""
        response = requests.get(f"{BASE_URL}/api/advanced/sandbox/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data or "mode" in data
        print(f"✓ Sandbox status: enabled={data.get('enabled', False)}")


class TestReportsAPI:
    """Reports API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth required")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_reports_health(self, headers):
        """Test reports health endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/health", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Reports health: healthy")
    
    def test_reports_stress(self, headers):
        """Test PDF stress test endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/stress-test?iterations=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Check success rate - field is "success_rate" as string like "100.0%"
        success_rate_str = data.get("success_rate", "0%")
        success_rate = float(success_rate_str.replace("%", "")) if "%" in success_rate_str else float(success_rate_str)
        print(f"✓ Reports stress test: {success_rate}% success rate")
        assert success_rate >= 80, f"Low success rate: {success_rate}%"


class TestVPNAPI:
    """VPN API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Auth required")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_vpn_status(self, headers):
        """Test VPN status endpoint"""
        response = requests.get(f"{BASE_URL}/api/vpn/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # VPN may not be installed in preview, but API should work
        print(f"✓ VPN status: {data.get('status', 'unknown')}")


class TestBuilderScriptCheck:
    """Verify builder script contains all required functions"""
    
    def test_builder_script_exists(self):
        """Test that seraph_builder.sh exists and has required functions"""
        script_path = "/app/scripts/seraph_builder.sh"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check for required functions
        required_functions = [
            "install_wireguard",
            "install_cuckoo",
            "install_liboqs",
            "install_mongodb",
            "install_elasticsearch",
            "install_docker",
            "verify_installation",
            "setup_slack_notifications",
            "setup_email_notifications"
        ]
        
        for func in required_functions:
            assert func in content, f"Missing function: {func}"
            print(f"✓ Builder script has: {func}")
        
        print("✓ All required builder script functions present")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
