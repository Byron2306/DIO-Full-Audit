"""
Test Suite for VPN, Zero Trust, Browser Isolation, and Agent Commands
Tests the following features:
- VPN page: Initialize Server, Download Config, Add/List Peers
- Zero Trust: Block/Unblock devices, Remediation commands
- Browser Isolation: URL analysis, Create isolated sessions
- Agent Commands: Pending commands including Zero Trust triggered ones
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "testadmin@test.com"
TEST_PASSWORD = "TestPassword123!"


class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        # Try to register if login fails
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test Admin"
        })
        if register_response.status_code in [200, 201]:
            login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            if login_response.status_code == 200:
                return login_response.json().get("access_token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_login_success(self, auth_token):
        """Test that we can authenticate"""
        assert auth_token is not None
        print(f"Authentication successful, token obtained")


class TestVPNEndpoints:
    """VPN API endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_vpn_status(self, headers):
        """Test GET /api/vpn/status returns server status"""
        response = requests.get(f"{BASE_URL}/api/vpn/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "server" in data
        assert "config" in data
        print(f"VPN Status: {data.get('server', {}).get('status')}")
        print(f"Server configured: {data.get('server', {}).get('server_configured')}")
    
    def test_vpn_initialize(self, headers):
        """Test POST /api/vpn/initialize - Initialize VPN server"""
        response = requests.post(f"{BASE_URL}/api/vpn/initialize", headers=headers)
        # May return 200 if already initialized or success
        assert response.status_code in [200, 201]
        data = response.json()
        assert "status" in data
        print(f"VPN Initialize result: {data}")
    
    def test_vpn_get_peers(self, headers):
        """Test GET /api/vpn/peers - List all VPN peers"""
        response = requests.get(f"{BASE_URL}/api/vpn/peers", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "peers" in data
        assert "count" in data
        print(f"VPN Peers count: {data.get('count')}")
    
    def test_vpn_add_peer(self, headers):
        """Test POST /api/vpn/peers - Add a new VPN peer"""
        response = requests.post(f"{BASE_URL}/api/vpn/peers", headers=headers, json={
            "name": "TEST_peer_agent_001"
        })
        assert response.status_code in [200, 201]
        data = response.json()
        assert "peer" in data or "message" in data
        print(f"Add peer result: {data}")
    
    def test_vpn_peer_config_download(self, headers):
        """Test GET /api/vpn/peers/{peer_id}/config - Download peer config"""
        # First get list of peers
        peers_response = requests.get(f"{BASE_URL}/api/vpn/peers", headers=headers)
        assert peers_response.status_code == 200
        peers = peers_response.json().get("peers", [])
        
        if len(peers) == 0:
            # Add a peer first
            add_response = requests.post(f"{BASE_URL}/api/vpn/peers", headers=headers, json={
                "name": "TEST_config_download_peer"
            })
            assert add_response.status_code in [200, 201]
            peer_id = add_response.json().get("peer", {}).get("peer_id")
        else:
            peer_id = peers[0].get("peer_id")
        
        # Download config
        config_response = requests.get(f"{BASE_URL}/api/vpn/peers/{peer_id}/config", headers=headers)
        assert config_response.status_code == 200
        
        # Should return plain text WireGuard config
        config_content = config_response.text
        assert "[Interface]" in config_content
        assert "PrivateKey" in config_content
        assert "[Peer]" in config_content
        assert "PublicKey" in config_content
        print(f"Config download successful, contains WireGuard config format")
        print(f"Config preview: {config_content[:200]}...")
    
    def test_vpn_invalid_peer_config(self, headers):
        """Test GET /api/vpn/peers/{invalid_id}/config returns 404"""
        response = requests.get(f"{BASE_URL}/api/vpn/peers/invalid_peer_id_12345/config", headers=headers)
        assert response.status_code == 404


class TestZeroTrustEndpoints:
    """Zero Trust API endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_zero_trust_stats(self, headers):
        """Test GET /api/zero-trust/stats"""
        response = requests.get(f"{BASE_URL}/api/zero-trust/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"Zero Trust Stats: {data}")
    
    def test_zero_trust_devices(self, headers):
        """Test GET /api/zero-trust/devices - List all devices"""
        response = requests.get(f"{BASE_URL}/api/zero-trust/devices", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "count" in data
        print(f"Zero Trust Devices count: {data.get('count')}")
    
    def test_zero_trust_register_device(self, headers):
        """Test POST /api/zero-trust/devices - Register a new device"""
        response = requests.post(f"{BASE_URL}/api/zero-trust/devices", headers=headers, json={
            "device_id": "TEST_device_001",
            "device_name": "Test Workstation",
            "device_type": "workstation",
            "os_info": {"name": "Windows", "version": "11"},
            "security_posture": {"antivirus": True, "firewall": True}
        })
        assert response.status_code in [200, 201]
        data = response.json()
        assert "device_id" in data
        print(f"Registered device: {data.get('device_id')}")
    
    def test_zero_trust_block_device(self, headers):
        """Test POST /api/zero-trust/devices/{id}/block - Block device and create remediation command"""
        # First ensure we have a device to block
        device_id = "TEST_block_device_001"
        
        # Register device first
        requests.post(f"{BASE_URL}/api/zero-trust/devices", headers=headers, json={
            "device_id": device_id,
            "device_name": "Test Block Device",
            "device_type": "workstation",
            "os_info": {"name": "Windows", "version": "11"},
            "security_posture": {}
        })
        
        # Block the device
        response = requests.post(f"{BASE_URL}/api/zero-trust/devices/{device_id}/block", headers=headers, json={
            "device_id": device_id,
            "reason": "Test Zero Trust violation",
            "trigger_remediation": True
        })
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("success") == True
        assert data.get("status") == "blocked"
        assert "remediation_commands" in data
        print(f"Block device result: {data}")
        print(f"Remediation commands created: {data.get('remediation_commands')}")
    
    def test_zero_trust_unblock_device(self, headers):
        """Test POST /api/zero-trust/devices/{id}/unblock - Unblock device"""
        device_id = "TEST_block_device_001"
        
        # Unblock the device
        response = requests.post(f"{BASE_URL}/api/zero-trust/devices/{device_id}/unblock", headers=headers)
        
        # May return 200 or 404 if device not found
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True
            assert data.get("status") == "unblocked"
            print(f"Unblock device result: {data}")
        else:
            print(f"Unblock returned {response.status_code} - device may not exist in memory")
    
    def test_zero_trust_policies(self, headers):
        """Test GET /api/zero-trust/policies - List access policies"""
        response = requests.get(f"{BASE_URL}/api/zero-trust/policies", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "policies" in data
        print(f"Zero Trust Policies count: {data.get('count')}")
    
    def test_zero_trust_access_logs(self, headers):
        """Test GET /api/zero-trust/access-logs"""
        response = requests.get(f"{BASE_URL}/api/zero-trust/access-logs", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        print(f"Access logs count: {data.get('count')}")


class TestBrowserIsolationEndpoints:
    """Browser Isolation API endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_browser_isolation_stats(self, headers):
        """Test GET /api/browser-isolation/stats"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"Browser Isolation Stats: {data}")
    
    def test_browser_isolation_modes(self, headers):
        """Test GET /api/browser-isolation/modes - List isolation modes"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/modes", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "modes" in data
        print(f"Isolation modes: {[m.get('id') for m in data.get('modes', [])]}")
    
    def test_browser_isolation_analyze_url(self, headers):
        """Test POST /api/browser-isolation/analyze-url - Analyze URL"""
        response = requests.post(f"{BASE_URL}/api/browser-isolation/analyze-url", headers=headers, json={
            "url": "https://example.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "threat_level" in data
        assert "is_blocked" in data
        print(f"URL Analysis: {data}")
    
    def test_browser_isolation_analyze_suspicious_url(self, headers):
        """Test URL analysis with suspicious domain"""
        response = requests.post(f"{BASE_URL}/api/browser-isolation/analyze-url", headers=headers, json={
            "url": "https://malware-test.com/download.exe"
        })
        assert response.status_code == 200
        data = response.json()
        print(f"Suspicious URL Analysis: {data}")
    
    def test_browser_isolation_create_session(self, headers):
        """Test POST /api/browser-isolation/sessions - Create isolated session"""
        response = requests.post(f"{BASE_URL}/api/browser-isolation/sessions", headers=headers, json={
            "url": "https://example.com",
            "isolation_mode": "full"
        })
        assert response.status_code in [200, 201]
        data = response.json()
        assert "session_id" in data
        print(f"Created session: {data.get('session_id')}")
    
    def test_browser_isolation_list_sessions(self, headers):
        """Test GET /api/browser-isolation/sessions - List active sessions"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/sessions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        print(f"Active sessions count: {len(data.get('sessions', []))}")
    
    def test_browser_isolation_blocklist(self, headers):
        """Test GET /api/browser-isolation/blocked-domains"""
        response = requests.get(f"{BASE_URL}/api/browser-isolation/blocked-domains", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "domains" in data
        print(f"Blocked domains count: {len(data.get('domains', []))}")


class TestAgentCommandsEndpoints:
    """Agent Commands API endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_agent_commands_types(self, headers):
        """Test GET /api/agent-commands/types - List command types"""
        response = requests.get(f"{BASE_URL}/api/agent-commands/types", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "command_types" in data
        print(f"Command types: {list(data.get('command_types', {}).keys())}")
    
    def test_agent_commands_agents_status(self, headers):
        """Test GET /api/agent-commands/agents/status - List registered agents"""
        response = requests.get(f"{BASE_URL}/api/agent-commands/agents/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        print(f"Registered agents: {len(data.get('agents', []))}")
    
    def test_agent_commands_connected(self, headers):
        """Test GET /api/agent-commands/agents/connected - List connected agents"""
        response = requests.get(f"{BASE_URL}/api/agent-commands/agents/connected", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        print(f"Connected agents: {len(data.get('agents', []))}")
    
    def test_agent_commands_pending(self, headers):
        """Test GET /api/agent-commands/pending - List pending commands"""
        response = requests.get(f"{BASE_URL}/api/agent-commands/pending", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        print(f"Pending commands: {len(data.get('commands', []))}")
        
        # Check if Zero Trust triggered commands are present
        for cmd in data.get("commands", []):
            if cmd.get("source") == "zero_trust_violation":
                print(f"Found Zero Trust triggered command: {cmd.get('command_id')}")
    
    def test_agent_commands_history(self, headers):
        """Test GET /api/agent-commands/history - Command history"""
        response = requests.get(f"{BASE_URL}/api/agent-commands/history?limit=50", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        print(f"Command history count: {len(data.get('commands', []))}")
    
    def test_agent_commands_create(self, headers):
        """Test POST /api/agent-commands/create - Create a new command"""
        # First check if we have any agents
        agents_response = requests.get(f"{BASE_URL}/api/agent-commands/agents/status", headers=headers)
        agents = agents_response.json().get("agents", [])
        
        if len(agents) == 0:
            print("No agents registered, skipping command creation test")
            return
        
        agent_id = agents[0].get("agent_id")
        
        response = requests.post(f"{BASE_URL}/api/agent-commands/create", headers=headers, json={
            "agent_id": agent_id,
            "command_type": "system_scan",
            "parameters": {"scan_type": "quick"},
            "priority": "medium"
        })
        
        assert response.status_code in [200, 201]
        data = response.json()
        print(f"Created command: {data}")


class TestZeroTrustAgentIntegration:
    """Test Zero Trust to Agent Commands integration"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_block_device_creates_remediation_command(self, headers):
        """Test that blocking a device creates a remediation command in Agent Commands"""
        device_id = "TEST_integration_device_001"
        
        # Register device
        requests.post(f"{BASE_URL}/api/zero-trust/devices", headers=headers, json={
            "device_id": device_id,
            "device_name": "Integration Test Device",
            "device_type": "workstation",
            "os_info": {"name": "Windows", "version": "11"},
            "security_posture": {}
        })
        
        # Get pending commands count before
        pending_before = requests.get(f"{BASE_URL}/api/agent-commands/pending", headers=headers)
        count_before = len(pending_before.json().get("commands", []))
        
        # Block device with remediation
        block_response = requests.post(f"{BASE_URL}/api/zero-trust/devices/{device_id}/block", headers=headers, json={
            "device_id": device_id,
            "reason": "Integration test - Zero Trust violation",
            "trigger_remediation": True
        })
        
        assert block_response.status_code in [200, 201]
        block_data = block_response.json()
        
        # Check that remediation commands were created
        assert len(block_data.get("remediation_commands", [])) > 0
        
        # Verify command appears in pending commands
        pending_after = requests.get(f"{BASE_URL}/api/agent-commands/pending", headers=headers)
        commands_after = pending_after.json().get("commands", [])
        
        # Find the remediation command
        remediation_found = False
        for cmd in commands_after:
            if cmd.get("agent_id") == device_id and cmd.get("source") == "zero_trust_violation":
                remediation_found = True
                print(f"Found remediation command: {cmd.get('command_id')}")
                print(f"Command type: {cmd.get('command_type')}")
                print(f"Parameters: {cmd.get('parameters')}")
                break
        
        assert remediation_found, "Remediation command should appear in pending commands"
        print("Zero Trust to Agent Commands integration working correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
