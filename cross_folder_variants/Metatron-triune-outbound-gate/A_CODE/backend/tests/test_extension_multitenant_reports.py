"""
Test Extension, Multi-Tenant, and Reports APIs
===============================================
Tests for browser extension download, domain checking, PDF reports stress test,
and multi-tenant CRUD operations.
"""

import pytest
import requests
import os
import zipfile
import io

# Get API URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")


class TestBrowserExtension:
    """Test browser extension API endpoints"""
    
    def test_extension_download_returns_valid_zip(self):
        """Test that /api/extension/download returns a valid ZIP file"""
        response = requests.get(f"{BASE_URL}/api/extension/download", stream=True)
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check Content-Type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/zip' in content_type or 'application/octet-stream' in content_type, \
            f"Expected zip content type, got {content_type}"
        
        # Check Content-Disposition
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'seraph-extension.zip' in content_disp, f"Expected filename in Content-Disposition, got {content_disp}"
        
        # Verify it's a valid ZIP file by reading content
        content = response.content
        assert len(content) > 1000, f"ZIP file too small: {len(content)} bytes"
        
        # Verify ZIP magic bytes (PK..)
        assert content[:2] == b'PK', "File does not start with ZIP magic bytes"
        
        # Try to parse as ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                file_list = zf.namelist()
                print(f"ZIP contains {len(file_list)} files: {file_list[:10]}")
                
                # Check for essential extension files
                has_manifest = any('manifest.json' in f for f in file_list)
                has_background = any('background.js' in f for f in file_list)
                
                assert has_manifest, "ZIP should contain manifest.json"
                print("ZIP validation passed - contains manifest.json and valid structure")
        except zipfile.BadZipFile as e:
            pytest.fail(f"Downloaded file is not a valid ZIP: {e}")
    
    def test_extension_check_domain_safe(self):
        """Test domain check for a safe domain"""
        response = requests.post(
            f"{BASE_URL}/api/extension/check-domain",
            json={"domain": "google.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "domain" in data
        assert "is_malicious" in data
        assert "risk_score" in data
        
        assert data["is_malicious"] == False, "google.com should not be marked malicious"
        assert data["risk_score"] == 0, f"Safe domain should have 0 risk score, got {data['risk_score']}"
        print(f"Safe domain check passed: {data}")
    
    def test_extension_check_domain_malicious(self):
        """Test domain check for a known malicious domain"""
        response = requests.post(
            f"{BASE_URL}/api/extension/check-domain",
            json={"domain": "malware-site.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_malicious"] == True, "malware-site.com should be marked malicious"
        assert data["risk_score"] > 0, f"Malicious domain should have risk score > 0, got {data['risk_score']}"
        assert "reason" in data and data["reason"] is not None
        print(f"Malicious domain check passed: {data}")
    
    def test_extension_check_domain_suspicious_pattern(self):
        """Test domain check for suspicious pattern (.onion)"""
        response = requests.post(
            f"{BASE_URL}/api/extension/check-domain",
            json={"domain": "suspicious.onion"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_malicious"] == True, ".onion domain should be flagged"
        assert "onion" in data.get("reason", "").lower()
        print(f"Suspicious pattern check passed: {data}")


class TestPDFReports:
    """Test PDF reporting endpoints"""
    
    def test_reports_health_check(self):
        """Test /api/reports/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/reports/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "healthy", f"Expected healthy status, got {data['status']}"
        assert "pdf_generation" in data
        assert data["pdf_generation"] == "working"
        assert "pdf_size_bytes" in data
        assert data["pdf_size_bytes"] > 0, "PDF size should be > 0"
        print(f"Reports health check passed: {data}")
    
    def test_reports_stress_test(self):
        """Test /api/reports/stress-test with 10 iterations"""
        # First register/login to get auth token
        auth_token = self._get_auth_token()
        
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        
        response = requests.get(
            f"{BASE_URL}/api/reports/stress-test?iterations=10",
            headers=headers,
            timeout=60  # Stress test may take time
        )
        
        # May require auth
        if response.status_code == 401:
            pytest.skip("Stress test requires authentication")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "total_iterations" in data
        assert data["total_iterations"] == 10
        assert "successful" in data
        assert "failed" in data
        assert "success_rate" in data
        
        # Check success rate
        success_rate = data["success_rate"]
        assert "100" in success_rate, f"Expected 100% success rate, got {success_rate}"
        
        assert data["successful"] == 10, f"Expected 10 successful iterations, got {data['successful']}"
        assert data["failed"] == 0, f"Expected 0 failures, got {data['failed']}"
        
        print(f"Stress test results: {data['successful']}/{data['total_iterations']} successful")
        print(f"Avg time: {data.get('avg_time_ms', 'N/A')}ms, Success rate: {data['success_rate']}")
    
    def _get_auth_token(self):
        """Get auth token for authenticated endpoints"""
        # Try to login with test credentials
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test@defender.io", "password": "test123"}
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            return data.get("access_token") or data.get("token")
        
        # Try to register first
        register_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "test_ext@defender.io", 
                "password": "testpass123",
                "name": "Test User Extension"
            }
        )
        
        if register_response.status_code in [200, 201]:
            data = register_response.json()
            return data.get("access_token") or data.get("token")
        
        # Try login again after registration
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test_ext@defender.io", "password": "testpass123"}
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            return data.get("access_token") or data.get("token")
        
        return None


class TestMultiTenant:
    """Test multi-tenant API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Setup authentication for tenant tests"""
        self.auth_token = self._get_auth_token()
        self.headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
    
    def _get_auth_token(self):
        """Get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test@defender.io", "password": "test123"}
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            return data.get("access_token") or data.get("token")
        
        # Try register
        register_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": "test_mt@defender.io",
                "password": "testpass123",
                "name": "Test User Multi-Tenant"
            }
        )
        
        if register_response.status_code in [200, 201]:
            data = register_response.json()
            return data.get("access_token") or data.get("token")
        
        # Login after register
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test_mt@defender.io", "password": "testpass123"}
        )
        
        if login_response.status_code == 200:
            return login_response.json().get("access_token") or login_response.json().get("token")
        
        return None
    
    def test_tenant_tiers_returns_quota_info(self):
        """Test /api/tenants/tiers returns tier quotas"""
        response = requests.get(f"{BASE_URL}/api/tenants/tiers")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all tiers present
        expected_tiers = ["free", "starter", "professional", "enterprise"]
        for tier in expected_tiers:
            assert tier in data, f"Missing tier: {tier}"
            
            tier_data = data[tier]
            assert "name" in tier_data
            assert "quota" in tier_data
            
            quota = tier_data["quota"]
            assert "max_agents" in quota
            assert "max_users" in quota
            assert "max_playbooks" in quota
            assert "features" in quota
        
        print(f"Tiers found: {list(data.keys())}")
        print(f"Enterprise features: {data['enterprise']['quota'].get('features', [])}")
    
    def test_tenant_stats_returns_statistics(self):
        """Test /api/tenants/stats returns tenant statistics"""
        response = requests.get(
            f"{BASE_URL}/api/tenants/stats",
            headers=self.headers
        )
        
        if response.status_code == 401:
            pytest.skip("Tenant stats requires authentication")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate stats structure
        assert "total_tenants" in data
        assert "active_tenants" in data
        assert "trial_tenants" in data
        assert "by_tier" in data
        assert "total_users" in data
        
        assert data["total_tenants"] >= 1, "Should have at least 1 tenant (default)"
        
        print(f"Tenant stats: {data}")
    
    def test_list_tenants(self):
        """Test /api/tenants returns tenant list"""
        response = requests.get(
            f"{BASE_URL}/api/tenants/",
            headers=self.headers
        )
        
        if response.status_code == 401:
            pytest.skip("List tenants requires authentication")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "tenants" in data
        assert "total" in data
        assert isinstance(data["tenants"], list)
        
        # Should have at least the default tenant
        assert data["total"] >= 1, "Should have at least 1 tenant"
        
        if data["tenants"]:
            tenant = data["tenants"][0]
            assert "id" in tenant
            assert "name" in tenant
            assert "tier" in tenant
            assert "status" in tenant
        
        print(f"Found {data['total']} tenants")
    
    def test_create_tenant(self):
        """Test /api/tenants creates new tenant"""
        response = requests.post(
            f"{BASE_URL}/api/tenants/",
            headers=self.headers,
            json={
                "name": "TEST_Extension_Tenant",
                "contact_email": "test_ext_tenant@example.com",
                "tier": "starter",
                "trial_days": 14
            }
        )
        
        if response.status_code == 401:
            pytest.skip("Create tenant requires authentication")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert "name" in data
        assert data["name"] == "TEST_Extension_Tenant"
        assert data["tier"] == "starter"
        assert "message" in data
        
        print(f"Created tenant: {data}")


class TestVPNStatus:
    """Test VPN status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Setup authentication for VPN tests"""
        self.auth_token = self._get_auth_token()
        self.headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
    
    def _get_auth_token(self):
        """Get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test@defender.io", "password": "test123"}
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            return data.get("access_token") or data.get("token")
        return None
    
    def test_vpn_status(self):
        """Test /api/vpn/status returns server status"""
        response = requests.get(
            f"{BASE_URL}/api/vpn/status",
            headers=self.headers
        )
        
        if response.status_code == 401 or response.status_code == 403:
            pytest.skip("VPN status requires authentication")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate response has expected fields
        assert "server" in data, "Response should have 'server' field"
        assert "config" in data, "Response should have 'config' field"
        
        # Check server status (expected: not_installed in preview env)
        server_status = data.get("server", {}).get("status")
        assert server_status is not None, "Server should have status"
        
        print(f"VPN status: {server_status}")
        print(f"Kill switch enabled: {data.get('kill_switch', {}).get('enabled', False)}")


class TestBuilderScript:
    """Test builder script existence"""
    
    def test_builder_script_exists(self):
        """Verify seraph_builder.sh exists at /app/scripts/"""
        script_path = "/app/scripts/seraph_builder.sh"
        
        assert os.path.exists(script_path), f"Builder script not found at {script_path}"
        
        # Check it's executable or at least readable
        with open(script_path, 'r') as f:
            content = f.read()
            
        assert "#!/bin/bash" in content, "Script should start with bash shebang"
        assert "SERAPH" in content, "Script should contain SERAPH"
        assert "install_wireguard" in content, "Script should have WireGuard installation"
        assert "install_cuckoo" in content, "Script should have Cuckoo installation"
        assert "install_liboqs" in content, "Script should have liboqs installation"
        
        print(f"Builder script found: {len(content)} bytes")
        print("Contains: WireGuard, Cuckoo, liboqs installation functions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
