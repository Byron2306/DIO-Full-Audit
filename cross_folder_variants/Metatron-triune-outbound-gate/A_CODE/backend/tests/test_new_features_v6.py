"""
Test New Features V6 - Iteration 25
===================================
Tests for:
- Cuckoo sandbox status
- VNS alerts service
- Enhanced quantum security with liboqs support
- PDF reporting
- Tactical heatmap data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://seraph-security.preview.emergentagent.com')


@pytest.fixture(scope="module")
def auth_token():
    """Authenticate and get token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "test@defender.io", "password": "test123"},
        headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        pytest.skip("Authentication failed")
    return response.json().get("access_token")


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestCuckooSandbox:
    """Cuckoo Sandbox API tests"""
    
    def test_sandbox_status(self, auth_headers):
        """Test /api/advanced/sandbox/status returns sandbox status"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/sandbox/status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "enabled" in data
        assert "mode" in data
        assert "stats" in data
        assert "api_version" in data
        assert "pending_tasks" in data
        assert "completed_tasks" in data
        
        # Verify mode is static_analysis when Cuckoo not configured
        assert data["mode"] in ["static_analysis", "remote"]
        print(f"Sandbox status: mode={data['mode']}, enabled={data['enabled']}")


class TestVNSAlerts:
    """VNS Alerts Service tests"""
    
    def test_alerts_status(self, auth_headers):
        """Test /api/advanced/alerts/status returns alert service status"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/alerts/status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "enabled" in data
        assert "slack_configured" in data
        assert "email_configured" in data
        assert "min_severity" in data
        assert "cooldown_minutes" in data
        assert "stats" in data
        
        print(f"Alerts status: enabled={data['enabled']}, slack={data['slack_configured']}, email={data['email_configured']}")
    
    def test_configure_slack_webhook(self, auth_headers):
        """Test /api/advanced/alerts/configure can configure Slack webhook"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/alerts/configure",
            headers=auth_headers,
            json={"slack_webhook_url": "https://hooks.slack.com/services/TEST/WEBHOOK/CONFIG"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify configuration was applied
        assert "status" in data
        assert data["status"] == "configured"
        assert data.get("slack_configured") == True
        
        print(f"Alerts configured: {data}")
    
    def test_configure_email(self, auth_headers):
        """Test /api/advanced/alerts/configure can configure email"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/alerts/configure",
            headers=auth_headers,
            json={
                "email_config": {
                    "smtp_host": "smtp.test.com",
                    "smtp_port": 587,
                    "smtp_user": "test@test.com",
                    "smtp_password": "testpass",
                    "from_address": "alerts@test.com",
                    "to_addresses": ["admin@test.com"]
                }
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "configured"
        print(f"Email config: {data}")


class TestQuantumSecurity:
    """Quantum Security tests"""
    
    def test_quantum_status_mode(self, auth_headers):
        """Test /api/advanced/quantum/status shows mode (simulation or liboqs)"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/quantum/status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "mode" in data
        assert data["mode"] in ["simulation", "liboqs", "pqcrypto"]
        assert "algorithms" in data
        assert "kem" in data["algorithms"]
        assert "signatures" in data["algorithms"]
        assert "hash" in data["algorithms"]
        assert "note" in data
        
        # Verify algorithms list
        assert "KYBER-768" in data["algorithms"]["kem"]
        assert "DILITHIUM-3" in data["algorithms"]["signatures"]
        assert data["algorithms"]["hash"] == "SHA3-256"
        
        print(f"Quantum mode: {data['mode']}, note: {data['note']}")


class TestPDFReporting:
    """PDF Report generation tests"""
    
    def test_generate_threat_intelligence_pdf(self, auth_headers):
        """Test /api/reports/threat-intelligence generates PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/threat-intelligence",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify PDF content type
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type
        
        # Verify content disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert "threat_report_" in content_disp
        assert ".pdf" in content_disp
        
        # Verify PDF content (should start with %PDF)
        assert len(response.content) > 0
        # PDF magic bytes
        assert response.content[:4] == b'%PDF' or len(response.content) > 1000
        
        print(f"PDF generated: {len(response.content)} bytes, content-disposition: {content_disp}")


class TestTacticalHeatmapData:
    """Tactical Heatmap data tests (API side)"""
    
    def test_threats_endpoint_for_heatmap(self, auth_headers):
        """Test /api/threats returns data suitable for heatmap"""
        response = requests.get(
            f"{BASE_URL}/api/threats?limit=200",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure - could be list directly or dict with threats key
        if isinstance(data, dict):
            threats = data.get("threats", [])
        else:
            threats = data
        assert isinstance(threats, list)
        
        # If there are threats, verify they have required fields for heatmap
        if threats:
            threat = threats[0]
            # Heatmap needs type and severity for grouping
            assert "type" in threat or "severity" in threat
            print(f"Found {len(threats)} threats for heatmap")
        else:
            print("No threats found - heatmap will show empty state")


class TestAdvancedDashboard:
    """Advanced Dashboard tests"""
    
    def test_advanced_dashboard_includes_new_services(self, auth_headers):
        """Test /api/advanced/dashboard includes all 5 service statuses"""
        response = requests.get(
            f"{BASE_URL}/api/advanced/dashboard",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all 5 services are present
        assert "mcp" in data
        assert "memory" in data
        assert "vns" in data
        assert "quantum" in data
        assert "ai" in data
        
        # Verify quantum includes mode
        assert "mode" in data["quantum"]
        
        print(f"Dashboard services: {list(data.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
