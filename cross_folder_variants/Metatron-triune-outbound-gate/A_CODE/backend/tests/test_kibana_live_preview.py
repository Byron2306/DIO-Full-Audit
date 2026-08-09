"""
Test Kibana Live Preview and Credential Theft Detection Features
Tests P1 tasks: Kibana dashboards with live visualizations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser@test.com"
TEST_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestKibanaLivePreview:
    """Test Kibana Live Preview API endpoints"""
    
    DASHBOARD_IDS = [
        "security-overview",
        "threat-intelligence",
        "geo-threat-map",
        "mitre-attack",
        "endpoint-security",
        "playbook-analytics"
    ]
    
    def test_get_available_dashboards(self, auth_headers):
        """Test GET /api/kibana/dashboards returns all 6 dashboards"""
        response = requests.get(f"{BASE_URL}/api/kibana/dashboards", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "dashboards" in data, "Response should contain 'dashboards' key"
        assert "count" in data, "Response should contain 'count' key"
        
        dashboards = data["dashboards"]
        assert len(dashboards) == 6, f"Expected 6 dashboards, got {len(dashboards)}"
        
        # Verify all expected dashboards are present
        dashboard_ids = [d["id"] for d in dashboards]
        for expected_id in self.DASHBOARD_IDS:
            assert expected_id in dashboard_ids, f"Dashboard '{expected_id}' not found"
        
        # Verify dashboard structure
        for dashboard in dashboards:
            assert "id" in dashboard, "Dashboard should have 'id'"
            assert "title" in dashboard, "Dashboard should have 'title'"
            assert "description" in dashboard, "Dashboard should have 'description'"
            assert "panel_count" in dashboard, "Dashboard should have 'panel_count'"
    
    def test_get_kibana_status(self, auth_headers):
        """Test GET /api/kibana/status returns status info"""
        response = requests.get(f"{BASE_URL}/api/kibana/status", headers=auth_headers)
        
        assert response.status_code == 200
        
        data = response.json()
        assert "configured" in data
        assert "elasticsearch_url" in data
        assert "kibana_url" in data
        assert "dashboards_available" in data
        assert data["dashboards_available"] == 6
    
    @pytest.mark.parametrize("dashboard_id", DASHBOARD_IDS)
    def test_get_dashboard_config(self, auth_headers, dashboard_id):
        """Test GET /api/kibana/dashboards/{dashboard_id} returns config"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/dashboards/{dashboard_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Dashboard {dashboard_id} not found"
        
        data = response.json()
        assert "title" in data, "Config should have 'title'"
        assert "description" in data, "Config should have 'description'"
        assert "panels" in data, "Config should have 'panels'"
        assert len(data["panels"]) > 0, f"Dashboard {dashboard_id} should have panels"
    
    @pytest.mark.parametrize("dashboard_id", DASHBOARD_IDS)
    def test_get_live_dashboard_data(self, auth_headers, dashboard_id):
        """Test GET /api/kibana/live-data/{dashboard_id} returns panel data"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/live-data/{dashboard_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Live data for {dashboard_id} failed"
        
        data = response.json()
        assert "dashboard_id" in data, "Response should have 'dashboard_id'"
        assert "title" in data, "Response should have 'title'"
        assert "generated_at" in data, "Response should have 'generated_at'"
        assert "panels" in data, "Response should have 'panels'"
        
        assert data["dashboard_id"] == dashboard_id
        assert len(data["panels"]) > 0, f"Dashboard {dashboard_id} should have panel data"
        
        # Verify panel structure
        for panel in data["panels"]:
            assert "title" in panel, "Panel should have 'title'"
            assert "type" in panel, "Panel should have 'type'"
            # data can be None for some panels
    
    def test_security_overview_live_data_has_metrics(self, auth_headers):
        """Test security-overview dashboard has metric panels with data"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/live-data/security-overview",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find metric panels
        metric_panels = [p for p in data["panels"] if p["type"] == "metric"]
        assert len(metric_panels) > 0, "Security overview should have metric panels"
        
        # At least one metric should have data
        panels_with_data = [p for p in metric_panels if p.get("data")]
        assert len(panels_with_data) > 0, "At least one metric panel should have data"
    
    def test_mitre_attack_dashboard_has_heatmap(self, auth_headers):
        """Test MITRE ATT&CK dashboard has heatmap visualization"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/live-data/mitre-attack",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find heatmap panel
        heatmap_panels = [p for p in data["panels"] if p["type"] == "heatmap"]
        assert len(heatmap_panels) > 0, "MITRE dashboard should have heatmap panel"
        
        # Verify heatmap data structure
        heatmap = heatmap_panels[0]
        assert heatmap.get("data") is not None, "Heatmap should have data"
        
        heatmap_data = heatmap["data"]
        assert "tactics" in heatmap_data, "Heatmap should have tactics"
        assert "techniques" in heatmap_data, "Heatmap should have techniques"
        assert "values" in heatmap_data, "Heatmap should have values matrix"
    
    def test_geo_threat_map_has_map_data(self, auth_headers):
        """Test geo-threat-map dashboard has map visualization data"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/live-data/geo-threat-map",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find map panel
        map_panels = [p for p in data["panels"] if p["type"] == "map"]
        assert len(map_panels) > 0, "Geo threat map should have map panel"
        
        # Verify map data structure
        map_panel = map_panels[0]
        assert map_panel.get("data") is not None, "Map should have data"
        
        map_data = map_panel["data"]
        assert len(map_data) > 0, "Map should have geo points"
        
        # Verify geo point structure
        for point in map_data:
            assert "country" in point, "Geo point should have country"
            assert "lat" in point, "Geo point should have latitude"
            assert "lon" in point, "Geo point should have longitude"
            assert "count" in point, "Geo point should have count"
    
    def test_threat_intelligence_has_bar_charts(self, auth_headers):
        """Test threat-intelligence dashboard has bar chart visualizations"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/live-data/threat-intelligence",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find bar panels
        bar_panels = [p for p in data["panels"] if p["type"] == "bar"]
        assert len(bar_panels) > 0, "Threat intelligence should have bar charts"
    
    def test_export_dashboard(self, auth_headers):
        """Test dashboard export returns NDJSON"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/dashboards/security-overview/export",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "application/x-ndjson" in response.headers.get("content-type", "")
    
    def test_export_all_dashboards(self, auth_headers):
        """Test export all dashboards"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/export-all",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "application/x-ndjson" in response.headers.get("content-type", "")
    
    def test_get_dashboard_queries(self, auth_headers):
        """Test GET /api/kibana/dashboards/{id}/queries returns ES queries"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/dashboards/security-overview/queries",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "dashboard_id" in data
        assert "queries" in data
    
    def test_invalid_dashboard_returns_404(self, auth_headers):
        """Test invalid dashboard ID returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/dashboards/invalid-dashboard-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_invalid_live_data_returns_404(self, auth_headers):
        """Test invalid dashboard ID for live data returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/kibana/live-data/invalid-dashboard-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestCredentialTheftDetector:
    """Test Credential Theft Detector in advanced_agent.py"""
    
    def test_credential_theft_detector_class_exists(self):
        """Verify CredentialTheftDetector class exists in advanced_agent.py"""
        import sys
        sys.path.insert(0, '/app/scripts')
        
        # Import the module
        import importlib.util
        spec = importlib.util.spec_from_file_location("advanced_agent", "/app/scripts/advanced_agent.py")
        module = importlib.util.module_from_spec(spec)
        
        # Check class exists
        spec.loader.exec_module(module)
        assert hasattr(module, 'CredentialTheftDetector'), "CredentialTheftDetector class should exist"
    
    def test_credential_theft_detector_has_required_attributes(self):
        """Verify CredentialTheftDetector has required attributes"""
        import sys
        sys.path.insert(0, '/app/scripts')
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("advanced_agent", "/app/scripts/advanced_agent.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        detector_class = module.CredentialTheftDetector
        
        # Check class attributes
        assert hasattr(detector_class, 'CREDENTIAL_THEFT_TOOLS'), "Should have CREDENTIAL_THEFT_TOOLS"
        assert hasattr(detector_class, 'WINDOWS_CREDENTIAL_PATHS'), "Should have WINDOWS_CREDENTIAL_PATHS"
        assert hasattr(detector_class, 'LINUX_CREDENTIAL_PATHS'), "Should have LINUX_CREDENTIAL_PATHS"
        assert hasattr(detector_class, 'MACOS_CREDENTIAL_PATHS'), "Should have MACOS_CREDENTIAL_PATHS"
        assert hasattr(detector_class, 'LSASS_ACCESS_PATTERNS'), "Should have LSASS_ACCESS_PATTERNS"
    
    def test_credential_theft_tools_count(self):
        """Verify detector knows 37+ credential theft tools"""
        import sys
        sys.path.insert(0, '/app/scripts')
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("advanced_agent", "/app/scripts/advanced_agent.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        tools = module.CredentialTheftDetector.CREDENTIAL_THEFT_TOOLS
        assert len(tools) >= 37, f"Expected 37+ tools, got {len(tools)}"
    
    def test_credential_scan_cli_option_exists(self):
        """Verify --credential-scan CLI option exists"""
        with open('/app/scripts/advanced_agent.py', 'r') as f:
            content = f.read()
        
        assert '--credential-scan' in content, "--credential-scan CLI option should exist"
        assert 'credential_scan' in content, "credential_scan argument should be handled"
    
    def test_detector_scans_for_lsass_access(self):
        """Verify detector has LSASS access patterns"""
        import sys
        sys.path.insert(0, '/app/scripts')
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("advanced_agent", "/app/scripts/advanced_agent.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        patterns = module.CredentialTheftDetector.LSASS_ACCESS_PATTERNS
        assert len(patterns) > 0, "Should have LSASS access patterns"
        
        # Check for key patterns
        pattern_str = str(patterns)
        assert 'lsass' in pattern_str.lower(), "Should detect LSASS access"
        assert 'dump' in pattern_str.lower(), "Should detect dump operations"
    
    def test_detector_scans_browser_credentials(self):
        """Verify detector monitors browser credential files"""
        import sys
        sys.path.insert(0, '/app/scripts')
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("advanced_agent", "/app/scripts/advanced_agent.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check Windows paths
        win_paths = module.CredentialTheftDetector.WINDOWS_CREDENTIAL_PATHS
        win_paths_str = str(win_paths)
        assert 'Chrome' in win_paths_str, "Should monitor Chrome credentials"
        assert 'Firefox' in win_paths_str, "Should monitor Firefox credentials"
        assert 'Edge' in win_paths_str, "Should monitor Edge credentials"
        
        # Check Linux paths
        linux_paths = module.CredentialTheftDetector.LINUX_CREDENTIAL_PATHS
        linux_paths_str = str(linux_paths)
        assert 'chrome' in linux_paths_str.lower(), "Should monitor Chrome on Linux"
        assert 'firefox' in linux_paths_str.lower(), "Should monitor Firefox on Linux"
    
    def test_detector_scans_ssh_keys(self):
        """Verify detector monitors SSH key files"""
        import sys
        sys.path.insert(0, '/app/scripts')
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("advanced_agent", "/app/scripts/advanced_agent.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        linux_paths = module.CredentialTheftDetector.LINUX_CREDENTIAL_PATHS
        linux_paths_str = str(linux_paths)
        
        assert '.ssh' in linux_paths_str, "Should monitor SSH directory"
        assert 'id_rsa' in linux_paths_str, "Should monitor RSA keys"
        assert 'authorized_keys' in linux_paths_str, "Should monitor authorized_keys"
    
    def test_detector_knows_mimikatz(self):
        """Verify detector knows mimikatz and variants"""
        import sys
        sys.path.insert(0, '/app/scripts')
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("advanced_agent", "/app/scripts/advanced_agent.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        tools = module.CredentialTheftDetector.CREDENTIAL_THEFT_TOOLS
        tools_lower = {t.lower() for t in tools}
        
        assert 'mimikatz' in tools_lower, "Should detect mimikatz"
        assert 'mimikatz.exe' in tools_lower, "Should detect mimikatz.exe"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
