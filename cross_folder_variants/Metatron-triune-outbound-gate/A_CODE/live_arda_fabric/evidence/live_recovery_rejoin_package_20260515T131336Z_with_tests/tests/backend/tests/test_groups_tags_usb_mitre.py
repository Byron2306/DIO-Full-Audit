"""
Test Suite for New Swarm Features:
- Device Groups CRUD API
- Device Tagging API
- USB Scan API
- AI Threat Prioritization with MITRE ATT&CK
- Windows Batch Installer Download
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

class TestAuth:
    """Authentication for protected endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@defender.io",
            "password": "test123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}


class TestDeviceGroups(TestAuth):
    """Device Groups CRUD API Tests"""
    
    def test_create_device_group(self, headers):
        """POST /api/swarm/groups - Create device group"""
        group_name = f"TEST_Group_{uuid.uuid4().hex[:6]}"
        response = requests.post(
            f"{BASE_URL}/api/swarm/groups",
            json={
                "name": group_name,
                "description": "Test group for automated testing",
                "color": "#ff5733"
            },
            headers=headers
        )
        assert response.status_code == 200, f"Create group failed: {response.text}"
        data = response.json()
        assert data.get("status") == "created"
        assert "group" in data
        assert data["group"]["name"] == group_name
        assert data["group"]["color"] == "#ff5733"
        assert "group_id" in data["group"]
        # Store for cleanup
        TestDeviceGroups.created_group_id = data["group"]["group_id"]
        print(f"✓ Created group: {group_name} with ID: {data['group']['group_id']}")
    
    def test_list_device_groups(self, headers):
        """GET /api/swarm/groups - List device groups"""
        response = requests.get(f"{BASE_URL}/api/swarm/groups", headers=headers)
        assert response.status_code == 200, f"List groups failed: {response.text}"
        data = response.json()
        assert "groups" in data
        assert isinstance(data["groups"], list)
        print(f"✓ Listed {len(data['groups'])} groups")
    
    def test_update_device_group(self, headers):
        """PUT /api/swarm/groups/{group_id} - Update device group"""
        if not hasattr(TestDeviceGroups, 'created_group_id'):
            pytest.skip("No group created to update")
        
        response = requests.put(
            f"{BASE_URL}/api/swarm/groups/{TestDeviceGroups.created_group_id}",
            json={
                "name": "TEST_Updated_Group",
                "description": "Updated description",
                "color": "#00ff00"
            },
            headers=headers
        )
        assert response.status_code == 200, f"Update group failed: {response.text}"
        data = response.json()
        assert data.get("status") == "updated"
        print(f"✓ Updated group: {TestDeviceGroups.created_group_id}")
    
    def test_delete_device_group(self, headers):
        """DELETE /api/swarm/groups/{group_id} - Delete device group"""
        if not hasattr(TestDeviceGroups, 'created_group_id'):
            pytest.skip("No group created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/swarm/groups/{TestDeviceGroups.created_group_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Delete group failed: {response.text}"
        data = response.json()
        assert data.get("status") == "deleted"
        print(f"✓ Deleted group: {TestDeviceGroups.created_group_id}")


class TestDeviceTags(TestAuth):
    """Device Tagging API Tests"""
    
    def test_list_all_tags(self, headers):
        """GET /api/swarm/tags - List all unique tags"""
        response = requests.get(f"{BASE_URL}/api/swarm/tags", headers=headers)
        assert response.status_code == 200, f"List tags failed: {response.text}"
        data = response.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)
        print(f"✓ Listed {len(data['tags'])} unique tags")
    
    def test_update_device_tags_requires_device(self, headers):
        """PUT /api/swarm/devices/{ip}/tags - Update device tags (needs existing device)"""
        # First get a device to tag
        devices_response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        if devices_response.status_code != 200:
            pytest.skip("Cannot get devices list")
        
        devices = devices_response.json().get("devices", [])
        if not devices:
            # Test with non-existent device - should return 404
            response = requests.put(
                f"{BASE_URL}/api/swarm/devices/192.168.99.99/tags",
                json={"tags": ["test-tag", "automated"]},
                headers=headers
            )
            # Should return 404 for non-existent device
            assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
            print("✓ Tags endpoint responds correctly (no devices to tag)")
        else:
            device_ip = devices[0]["ip_address"]
            response = requests.put(
                f"{BASE_URL}/api/swarm/devices/{device_ip}/tags",
                json={"tags": ["test-tag", "automated", "critical"]},
                headers=headers
            )
            # Device might have been deleted between list and update
            assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                assert data.get("status") == "updated"
                print(f"✓ Updated tags for device: {device_ip}")
            else:
                print(f"✓ Tags endpoint responds correctly (device {device_ip} not found)")


class TestDeviceGroupAssignment(TestAuth):
    """Device to Group Assignment Tests"""
    
    def test_assign_device_to_group(self, headers):
        """PUT /api/swarm/devices/{ip}/group - Assign device to group"""
        # First create a group
        group_name = f"TEST_AssignGroup_{uuid.uuid4().hex[:6]}"
        create_response = requests.post(
            f"{BASE_URL}/api/swarm/groups",
            json={"name": group_name, "description": "For assignment test"},
            headers=headers
        )
        if create_response.status_code != 200:
            pytest.skip("Cannot create group for assignment test")
        
        group_id = create_response.json()["group"]["group_id"]
        
        # Get a device to assign
        devices_response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        devices = devices_response.json().get("devices", [])
        
        if not devices:
            # Test with non-existent device
            response = requests.put(
                f"{BASE_URL}/api/swarm/devices/192.168.99.99/group?group_id={group_id}",
                headers=headers
            )
            assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
            print("✓ Group assignment endpoint responds correctly (no devices)")
        else:
            device_ip = devices[0]["ip_address"]
            response = requests.put(
                f"{BASE_URL}/api/swarm/devices/{device_ip}/group?group_id={group_id}",
                headers=headers
            )
            assert response.status_code == 200, f"Assign to group failed: {response.text}"
            data = response.json()
            assert data.get("status") == "assigned"
            print(f"✓ Assigned device {device_ip} to group {group_id}")
        
        # Cleanup - delete the test group
        requests.delete(f"{BASE_URL}/api/swarm/groups/{group_id}", headers=headers)


class TestUSBScan(TestAuth):
    """USB Scan API Tests"""
    
    def test_initiate_usb_scan(self, headers):
        """POST /api/swarm/usb/scan - Initiate USB scan"""
        response = requests.post(
            f"{BASE_URL}/api/swarm/usb/scan",
            json={
                "host_id": "test-host-001",
                "device_path": "/dev/sdb1",
                "device_name": "TEST_USB_Drive"
            },
            headers=headers
        )
        assert response.status_code == 200, f"Initiate USB scan failed: {response.text}"
        data = response.json()
        assert data.get("status") == "queued"
        assert "scan_id" in data
        TestUSBScan.scan_id = data["scan_id"]
        print(f"✓ USB scan initiated with ID: {data['scan_id']}")
    
    def test_list_usb_scans(self, headers):
        """GET /api/swarm/usb/scans - List USB scan results"""
        response = requests.get(f"{BASE_URL}/api/swarm/usb/scans", headers=headers)
        assert response.status_code == 200, f"List USB scans failed: {response.text}"
        data = response.json()
        assert "scans" in data
        assert isinstance(data["scans"], list)
        print(f"✓ Listed {len(data['scans'])} USB scans")
    
    def test_list_usb_scans_by_host(self, headers):
        """GET /api/swarm/usb/scans?host_id=xxx - Filter USB scans by host"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/usb/scans?host_id=test-host-001",
            headers=headers
        )
        assert response.status_code == 200, f"Filter USB scans failed: {response.text}"
        data = response.json()
        assert "scans" in data
        print(f"✓ Filtered USB scans for host: {len(data['scans'])} results")
    
    def test_submit_usb_scan_results(self, headers):
        """POST /api/swarm/usb/scan/{scan_id}/results - Submit scan results"""
        if not hasattr(TestUSBScan, 'scan_id'):
            pytest.skip("No scan ID available")
        
        response = requests.post(
            f"{BASE_URL}/api/swarm/usb/scan/{TestUSBScan.scan_id}/results",
            json={
                "files_scanned": 150,
                "threats_found": [
                    {"type": "suspicious", "file": "autorun.inf", "reason": "Autorun file detected"},
                    {"type": "malware", "file": "virus.exe", "reason": "Known malware signature"}
                ],
                "host_id": "test-host-001"
            }
        )
        assert response.status_code == 200, f"Submit results failed: {response.text}"
        data = response.json()
        assert data.get("status") == "recorded"
        assert data.get("threat_level") == "critical"  # Because malware was detected
        print(f"✓ USB scan results submitted, threat level: {data['threat_level']}")


class TestAIThreatPrioritization(TestAuth):
    """AI Threat Prioritization with MITRE ATT&CK Tests"""
    
    def test_prioritize_threats(self, headers):
        """POST /api/swarm/threats/prioritize - AI threat prioritization"""
        response = requests.post(
            f"{BASE_URL}/api/swarm/threats/prioritize?limit=20",
            headers=headers
        )
        assert response.status_code == 200, f"Prioritize threats failed: {response.text}"
        data = response.json()
        assert "prioritized_threats" in data
        assert "summary" in data
        assert "analyzed_at" in data
        
        summary = data["summary"]
        assert "total_threats" in summary
        assert "critical_priority" in summary
        assert "high_priority" in summary
        assert "medium_priority" in summary
        
        print(f"✓ Threat prioritization complete:")
        print(f"  - Total threats: {summary['total_threats']}")
        print(f"  - Critical: {summary['critical_priority']}")
        print(f"  - High: {summary['high_priority']}")
        print(f"  - Medium: {summary['medium_priority']}")
        
        # Check MITRE mapping in threats
        for threat in data["prioritized_threats"][:3]:
            assert "mitre_tactic" in threat
            assert "mitre_tactic_name" in threat
            assert "priority_score" in threat
            assert "priority_level" in threat
            assert "recommended_action" in threat
            print(f"  - Threat: {threat.get('message', 'N/A')[:50]}... | MITRE: {threat['mitre_tactic']} | Score: {threat['priority_score']}")
    
    def test_get_mitre_mapping(self, headers):
        """GET /api/swarm/threats/mitre-mapping - Get MITRE ATT&CK mapping"""
        response = requests.get(f"{BASE_URL}/api/swarm/threats/mitre-mapping", headers=headers)
        assert response.status_code == 200, f"Get MITRE mapping failed: {response.text}"
        data = response.json()
        
        assert "all_tactics" in data
        assert "active_tactics" in data
        assert "keyword_mappings" in data
        
        # Verify MITRE tactics structure
        all_tactics = data["all_tactics"]
        assert "TA0001" in all_tactics  # Initial Access
        assert "TA0006" in all_tactics  # Credential Access
        assert "TA0010" in all_tactics  # Exfiltration
        assert "TA0040" in all_tactics  # Impact
        
        # Check tactic structure
        for tactic_id, tactic_info in all_tactics.items():
            assert "name" in tactic_info
            assert "severity_weight" in tactic_info
        
        print(f"✓ MITRE ATT&CK mapping retrieved:")
        print(f"  - Total tactics: {len(all_tactics)}")
        print(f"  - Active tactics: {len(data['active_tactics'])}")
        print(f"  - Keyword mappings: {data['keyword_mappings']}")


class TestWindowsBatchInstaller(TestAuth):
    """Windows Batch Installer Download Tests"""
    
    def test_download_windows_installer(self, headers):
        """GET /api/swarm/agent/download/windows-installer - Download Windows batch file"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/windows-installer",
            headers=headers
        )
        assert response.status_code == 200, f"Download installer failed: {response.text}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "application/x-bat" in content_type or "octet-stream" in content_type, f"Unexpected content type: {content_type}"
        
        # Check content
        content = response.text
        assert "@echo off" in content, "Batch file should start with @echo off"
        assert "SERAPH" in content.upper(), "Batch file should mention SERAPH"
        assert "python" in content.lower(), "Batch file should reference python"
        
        print(f"✓ Windows batch installer downloaded ({len(content)} bytes)")
    
    def test_download_batch_alias(self, headers):
        """GET /api/swarm/agent/download/batch - Download via 'batch' alias"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/agent/download/batch",
            headers=headers
        )
        assert response.status_code == 200, f"Download batch failed: {response.text}"
        print("✓ Batch installer accessible via 'batch' alias")


class TestIntegration(TestAuth):
    """Integration tests for combined features"""
    
    def test_full_group_workflow(self, headers):
        """Test complete group workflow: create -> assign -> list -> delete"""
        # 1. Create group
        group_name = f"TEST_Workflow_{uuid.uuid4().hex[:6]}"
        create_resp = requests.post(
            f"{BASE_URL}/api/swarm/groups",
            json={"name": group_name, "description": "Workflow test", "color": "#123456"},
            headers=headers
        )
        assert create_resp.status_code == 200
        group_id = create_resp.json()["group"]["group_id"]
        print(f"  1. Created group: {group_id}")
        
        # 2. List groups and verify
        list_resp = requests.get(f"{BASE_URL}/api/swarm/groups", headers=headers)
        assert list_resp.status_code == 200
        groups = list_resp.json()["groups"]
        group_ids = [g["group_id"] for g in groups]
        assert group_id in group_ids
        print(f"  2. Verified group in list")
        
        # 3. Delete group
        delete_resp = requests.delete(f"{BASE_URL}/api/swarm/groups/{group_id}", headers=headers)
        assert delete_resp.status_code == 200
        print(f"  3. Deleted group")
        
        # 4. Verify deletion
        list_resp2 = requests.get(f"{BASE_URL}/api/swarm/groups", headers=headers)
        groups2 = list_resp2.json()["groups"]
        group_ids2 = [g["group_id"] for g in groups2]
        assert group_id not in group_ids2
        print(f"  4. Verified group deleted")
        
        print("✓ Full group workflow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
