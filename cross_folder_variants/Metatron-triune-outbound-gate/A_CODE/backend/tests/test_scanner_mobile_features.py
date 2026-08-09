"""
Test Suite for Network Scanner and Mobile Agent Features
=========================================================
Tests the new scanner report endpoint, agent downloads, and device discovery.
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://seraph-security.preview.emergentagent.com').rstrip('/')


class TestScannerReportEndpoint:
    """Tests for POST /api/swarm/scanner/report - Public endpoint for network scanners"""
    
    def test_scanner_report_accepts_devices(self):
        """Scanner report endpoint should accept device reports without auth"""
        payload = {
            "scanner_id": "pytest-scanner-001",
            "network": "10.0.0.0/24",
            "scan_time": datetime.now().isoformat(),
            "devices": [
                {
                    "ip_address": "10.0.0.100",
                    "mac_address": "aa:bb:cc:dd:ee:ff",
                    "hostname": "pytest-test-device",
                    "os": "Linux",
                    "device_type": "server",
                    "deployable": True,
                    "mobile_manageable": False
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/swarm/scanner/report", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data
        assert "new_devices" in data or "updated_devices" in data
    
    def test_scanner_report_multiple_device_types(self):
        """Scanner should accept various device types (Windows, macOS, Linux, iOS, Android, IoT)"""
        payload = {
            "scanner_id": "pytest-scanner-002",
            "network": "172.16.0.0/24",
            "scan_time": datetime.now().isoformat(),
            "devices": [
                {"ip_address": "172.16.0.10", "os": "Windows", "device_type": "workstation", "deployable": True, "mobile_manageable": False},
                {"ip_address": "172.16.0.11", "os": "macOS", "device_type": "workstation", "deployable": True, "mobile_manageable": False},
                {"ip_address": "172.16.0.12", "os": "Linux", "device_type": "server", "deployable": True, "mobile_manageable": False},
                {"ip_address": "172.16.0.20", "os": "iOS", "device_type": "mobile", "deployable": False, "mobile_manageable": True},
                {"ip_address": "172.16.0.21", "os": "Android", "device_type": "mobile", "deployable": False, "mobile_manageable": True},
                {"ip_address": "172.16.0.30", "os": "Embedded", "device_type": "iot", "deployable": False, "mobile_manageable": False}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/swarm/scanner/report", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
    
    def test_scanner_report_no_auth_required(self):
        """Scanner report endpoint should work without authentication"""
        payload = {
            "scanner_id": "pytest-no-auth-scanner",
            "network": "192.168.100.0/24",
            "scan_time": datetime.now().isoformat(),
            "devices": []
        }
        
        # No Authorization header
        response = requests.post(f"{BASE_URL}/api/swarm/scanner/report", json=payload)
        assert response.status_code == 200


class TestAgentDownloadEndpoints:
    """Tests for agent download endpoints"""
    
    def test_download_scanner_script(self):
        """GET /api/swarm/agent/download/scanner should return Python script"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/scanner")
        assert response.status_code == 200
        
        content = response.text
        assert "#!/usr/bin/env python3" in content
        assert "SeraphNetworkScanner" in content
        assert "scan_network" in content
        assert "report_devices" in content
    
    def test_download_mobile_agent(self):
        """GET /api/swarm/agent/download/mobile should return mobile agent script"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/mobile")
        assert response.status_code == 200
        
        content = response.text
        assert "#!/usr/bin/env python3" in content
        assert "SeraphMobileAgent" in content
        assert "Pythonista" in content or "Termux" in content
    
    def test_download_linux_agent(self):
        """GET /api/swarm/agent/download/linux should return defender agent"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/linux")
        assert response.status_code == 200
        
        content = response.text
        assert "#!/usr/bin/env python3" in content
        assert "Seraph Defender" in content or "seraph_defender" in content.lower()
    
    def test_download_windows_agent(self):
        """GET /api/swarm/agent/download/windows should return defender agent"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/windows")
        assert response.status_code == 200
        
        content = response.text
        assert "#!/usr/bin/env python3" in content
    
    def test_download_macos_agent(self):
        """GET /api/swarm/agent/download/macos should return defender agent"""
        response = requests.get(f"{BASE_URL}/api/swarm/agent/download/macos")
        assert response.status_code == 200
        
        content = response.text
        assert "#!/usr/bin/env python3" in content


class TestDevicesEndpoint:
    """Tests for GET /api/swarm/devices - Requires authentication"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@seraph.ai",
            "password": "seraph123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_devices_returns_all_discovered(self, auth_token):
        """Devices endpoint should return all discovered devices"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "devices" in data
        assert "stats" in data
        assert data["stats"]["total"] >= 10  # Should have at least 10 devices (8 from scanner + 2 from container)
    
    def test_devices_have_correct_fields(self, auth_token):
        """Each device should have required fields"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        assert response.status_code == 200
        devices = response.json()["devices"]
        
        for device in devices:
            assert "ip_address" in device
            assert "os_type" in device
            assert "device_type" in device
    
    def test_devices_stats_by_os(self, auth_token):
        """Stats should include breakdown by OS type"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        assert response.status_code == 200
        stats = response.json()["stats"]
        
        assert "by_os" in stats
        # Should have various OS types
        os_types = stats["by_os"]
        assert len(os_types) > 0
    
    def test_deployable_flag_correct(self, auth_token):
        """Windows/macOS/Linux workstations should be deployable"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        assert response.status_code == 200
        devices = response.json()["devices"]
        
        for device in devices:
            os_type = device.get("os_type", "").lower()
            device_type = device.get("device_type", "").lower()
            deployable = device.get("deployable")
            
            # Workstations with Windows/macOS/Linux should be deployable
            if os_type in ["windows", "macos", "linux"] and device_type in ["workstation", "server"]:
                assert deployable == True, f"Device {device['ip_address']} with OS {os_type} should be deployable"
    
    def test_mobile_manageable_flag_correct(self, auth_token):
        """iOS/Android devices should be mobile_manageable"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        assert response.status_code == 200
        devices = response.json()["devices"]
        
        for device in devices:
            os_type = device.get("os_type", "").lower()
            mobile_manageable = device.get("mobile_manageable")
            
            if os_type in ["ios", "android"]:
                assert mobile_manageable == True, f"Device {device['ip_address']} with OS {os_type} should be mobile_manageable"


class TestOverviewEndpoint:
    """Tests for GET /api/swarm/overview"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@seraph.ai",
            "password": "seraph123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_overview_returns_device_count(self, auth_token):
        """Overview should return correct device count"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/overview", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "devices" in data
        assert data["devices"]["total"] >= 10  # At least 10 devices
    
    def test_overview_structure(self, auth_token):
        """Overview should have all required sections"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/overview", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "devices" in data
        assert "agents" in data
        assert "telemetry" in data
        assert "deployments" in data
        
        # Check device stats
        assert "total" in data["devices"]
        assert "managed" in data["devices"]
        assert "unmanaged" in data["devices"]


class TestScannersEndpoint:
    """Tests for GET /api/swarm/scanners"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@seraph.ai",
            "password": "seraph123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_scanners_list(self, auth_token):
        """Should return list of registered scanners"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/scanners", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "scanners" in data
        assert len(data["scanners"]) >= 1  # At least one scanner registered
    
    def test_scanner_has_required_fields(self, auth_token):
        """Each scanner should have required fields"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/scanners", headers=headers)
        
        assert response.status_code == 200
        scanners = response.json()["scanners"]
        
        for scanner in scanners:
            assert "scanner_id" in scanner
            assert "network" in scanner
            assert "last_report" in scanner


class TestDeviceTypeIdentification:
    """Tests for correct device type identification"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@seraph.ai",
            "password": "seraph123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_windows_identified(self, auth_token):
        """Windows devices should be identified"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        devices = response.json()["devices"]
        windows_devices = [d for d in devices if d.get("os_type") == "Windows"]
        
        assert len(windows_devices) >= 1, "Should have at least one Windows device"
    
    def test_linux_identified(self, auth_token):
        """Linux devices should be identified"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        devices = response.json()["devices"]
        linux_devices = [d for d in devices if d.get("os_type") == "Linux"]
        
        assert len(linux_devices) >= 1, "Should have at least one Linux device"
    
    def test_ios_identified(self, auth_token):
        """iOS devices should be identified"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        devices = response.json()["devices"]
        ios_devices = [d for d in devices if d.get("os_type") == "iOS"]
        
        assert len(ios_devices) >= 1, "Should have at least one iOS device"
    
    def test_android_identified(self, auth_token):
        """Android devices should be identified"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        devices = response.json()["devices"]
        android_devices = [d for d in devices if d.get("os_type") == "Android"]
        
        assert len(android_devices) >= 1, "Should have at least one Android device"
    
    def test_iot_identified(self, auth_token):
        """IoT devices should be identified"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        devices = response.json()["devices"]
        iot_devices = [d for d in devices if d.get("device_type") == "iot"]
        
        assert len(iot_devices) >= 1, "Should have at least one IoT device"
