"""
Comprehensive System Audit Tests - V30
======================================
Full system-wide audit for Seraph AI Defense System
Testing: Swarm, SOAR (14 templates), VNS Alerts, Threat Hunting, 
Network Topology, Command Center, Multi-Tenancy, PDF Reports, 
Browser Extension, and all other major features.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://seraph-security.preview.emergentagent.com').rstrip('/')

class TestAuthAndBasics:
    """Authentication and basic API health tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials"""
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        # Fallback: register and login
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_health_endpoint(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert data.get("database") == "connected"
        print(f"Health check passed: {data}")


class TestSwarmFeatures:
    """Swarm Dashboard API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_swarm_overview(self):
        """Test Swarm overview endpoint"""
        response = requests.get(f"{BASE_URL}/api/swarm/overview", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "agents" in data
        assert "telemetry" in data
        assert "deployments" in data
        print(f"Swarm overview: devices={data['devices']}, agents={data['agents']}")
    
    def test_swarm_devices(self):
        """Test Swarm devices list"""
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "stats" in data
        print(f"Swarm devices count: {len(data.get('devices', []))}")
    
    def test_swarm_telemetry(self):
        """Test Swarm telemetry endpoint"""
        response = requests.get(f"{BASE_URL}/api/swarm/telemetry?limit=50", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        print(f"Telemetry events: {len(data.get('events', []))}")
    
    def test_swarm_telemetry_stats(self):
        """Test Swarm telemetry stats"""
        response = requests.get(f"{BASE_URL}/api/swarm/telemetry/stats", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data
        print(f"Telemetry stats: total={data.get('total_events', 0)}")
    
    def test_swarm_deployment_status(self):
        """Test Swarm deployment status"""
        response = requests.get(f"{BASE_URL}/api/swarm/deployment/status", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        print(f"Deployment tasks: {len(data.get('tasks', []))}")
    
    def test_swarm_groups(self):
        """Test Swarm groups endpoint"""
        response = requests.get(f"{BASE_URL}/api/swarm/groups", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        print(f"Device groups: {len(data.get('groups', []))}")
    
    def test_swarm_tags(self):
        """Test Swarm tags endpoint"""
        response = requests.get(f"{BASE_URL}/api/swarm/tags", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        print(f"Device tags: {len(data.get('tags', []))}")
    
    def test_swarm_batch_deploy(self):
        """Test Swarm batch deployment endpoint (simulated)"""
        response = requests.post(f"{BASE_URL}/api/swarm/deploy/batch", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"Batch deploy result: {data.get('message', '')}")


class TestSOARFeatures:
    """SOAR Page API Tests - Including 14 Templates"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_soar_stats(self):
        """Test SOAR stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/soar/stats", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"SOAR stats: {data}")
    
    def test_soar_playbooks(self):
        """Test SOAR playbooks list"""
        response = requests.get(f"{BASE_URL}/api/soar/playbooks", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "playbooks" in data
        print(f"SOAR playbooks count: {len(data.get('playbooks', []))}")
    
    def test_soar_templates_count_14(self):
        """Test SOAR has exactly 14 templates"""
        response = requests.get(f"{BASE_URL}/api/soar/templates", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        templates = data.get("templates", [])
        assert len(templates) == 14, f"Expected 14 templates, got {len(templates)}"
        print(f"SOAR templates (14 verified): {[t.get('name', 'unknown') for t in templates]}")
    
    def test_soar_executions(self):
        """Test SOAR executions history"""
        response = requests.get(f"{BASE_URL}/api/soar/executions?limit=20", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "executions" in data
        print(f"SOAR executions: {len(data.get('executions', []))}")


class TestVNSAlertsFeatures:
    """VNS Alerts API Tests - Slack/Email configuration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_vns_alerts_status(self):
        """Test VNS alerts status endpoint"""
        response = requests.get(f"{BASE_URL}/api/advanced/alerts/status", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"VNS Alerts status: enabled={data.get('enabled')}, slack={data.get('slack_configured')}, email={data.get('email_configured')}")


class TestThreatHuntingFeatures:
    """Threat Hunting API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_hunting_status(self):
        """Test Threat Hunting status"""
        response = requests.get(f"{BASE_URL}/api/hunting/status", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"Hunting status: {data}")
    
    def test_hunting_rules(self):
        """Test Threat Hunting rules list"""
        response = requests.get(f"{BASE_URL}/api/hunting/rules", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        print(f"Hunting rules count: {len(data.get('rules', []))}")


class TestCommandCenterFeatures:
    """Command Center API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_command_center_agents(self):
        """Test Command Center agents list"""
        response = requests.get(f"{BASE_URL}/api/agents", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        print(f"Command Center agents: {len(data.get('agents', []))}")


class TestMultiTenancyFeatures:
    """Multi-Tenancy API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_tenants_list(self):
        """Test Tenants list endpoint"""
        response = requests.get(f"{BASE_URL}/api/tenants/", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"Tenants: {data}")
    
    def test_tenants_tiers(self):
        """Test Tenants tiers endpoint"""
        response = requests.get(f"{BASE_URL}/api/tenants/tiers", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        tiers = data.get("tiers", {})
        # Should have 4 tiers: free, starter, professional, enterprise
        assert len(tiers) >= 4, f"Expected at least 4 tiers, got {len(tiers)}"
        print(f"Tenant tiers: {list(tiers.keys())}")


class TestReportsFeatures:
    """PDF Reports API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_reports_health(self):
        """Test Reports health endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/health", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"Reports health: {data}")
    
    def test_reports_list(self):
        """Test Reports list endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"Reports: {data}")


class TestBrowserExtensionFeatures:
    """Browser Extension Download API Tests"""
    
    def test_browser_extension_download(self):
        """Test Browser Extension download returns ZIP"""
        response = requests.get(f"{BASE_URL}/api/extension/download")
        assert response.status_code == 200
        assert len(response.content) > 100  # ZIP should have content
        # Check ZIP magic bytes
        assert response.content[:2] == b'PK', "Response should be a ZIP file"
        print(f"Browser extension download: {len(response.content)} bytes")
    
    def test_browser_extension_check_safe_domain(self):
        """Test Browser Extension domain check for safe domain"""
        response = requests.post(f"{BASE_URL}/api/extension/check-domain", json={
            "domain": "google.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_malicious") == False
        print(f"Safe domain check: {data}")
    
    def test_browser_extension_check_malicious_domain(self):
        """Test Browser Extension domain check for malicious domain"""
        response = requests.post(f"{BASE_URL}/api/extension/check-domain", json={
            "domain": "malware-site.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_malicious") == True
        print(f"Malicious domain check: {data}")


class TestDashboardFeatures:
    """Dashboard API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_dashboard_stats(self):
        """Test Dashboard stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"Dashboard stats: active_threats={data.get('active_threats')}, total_threats={data.get('total_threats')}")


class TestAlertsFeatures:
    """Alerts API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_alerts_list(self):
        """Test Alerts list endpoint"""
        response = requests.get(f"{BASE_URL}/api/alerts", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        print(f"Alerts count: {len(data.get('alerts', []))}")


class TestNetworkTopologyFeatures:
    """Network Topology API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_network_topology_data(self):
        """Test Network topology data"""
        response = requests.get(f"{BASE_URL}/api/network/topology", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "links" in data
        print(f"Network topology: {len(data.get('nodes', []))} nodes, {len(data.get('links', []))} links")


class TestThreatIntelFeatures:
    """Threat Intel API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_threat_intel_feeds(self):
        """Test Threat Intel feeds"""
        response = requests.get(f"{BASE_URL}/api/intel/feeds", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"Threat Intel feeds: {data}")


class TestUnifiedAgentFeatures:
    """Unified Agent API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.email = "swarmtest@test.com"
        self.password = "TestPass123!"
        self.token = self._get_token()
    
    def _get_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Swarm Test User"
        })
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        return response.json().get("access_token")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def test_unified_agent_stats(self):
        """Test Unified Agent stats"""
        response = requests.get(f"{BASE_URL}/api/unified/stats", headers=self._headers())
        assert response.status_code == 200
        data = response.json()
        print(f"Unified agent stats: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
