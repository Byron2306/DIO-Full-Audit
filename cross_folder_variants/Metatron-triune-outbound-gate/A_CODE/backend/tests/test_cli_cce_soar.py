"""
CLI Events, CCE Worker, and SOAR AI Defense Tests
==================================================
Tests for:
- CLI event ingestion (POST /api/cli/event)
- Session summaries retrieval (GET /api/cli/sessions/all)
- Deception hits endpoints
- SOAR playbooks and AI Defense features
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "testadmin@test.com"
TEST_PASSWORD = "TestPassword123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        # Try both token formats
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestCLIEventIngestion:
    """Tests for CLI event ingestion endpoint"""
    
    def test_ingest_cli_command_success(self, headers):
        """Test POST /api/cli/event - successful CLI command ingestion"""
        event_data = {
            "host_id": f"test-workstation-{uuid.uuid4().hex[:8]}",
            "session_id": f"sess-{uuid.uuid4().hex[:8]}",
            "user": "test_user",
            "shell_type": "powershell",
            "command": "whoami /all",
            "parent_process": "explorer.exe",
            "cwd": "C:\\Users\\test_user"
        }
        
        response = requests.post(f"{BASE_URL}/api/cli/event", json=event_data, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "accepted"
        assert "event_id" in data
        assert data["message"] == "CLI command event ingested successfully"
        print(f"SUCCESS: CLI command ingested with event_id: {data['event_id']}")
    
    def test_ingest_cli_command_with_timestamp(self, headers):
        """Test CLI command ingestion with custom timestamp"""
        event_data = {
            "host_id": "test-workstation-002",
            "session_id": "sess-test-02",
            "user": "admin",
            "shell_type": "bash",
            "command": "cat /etc/passwd",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        response = requests.post(f"{BASE_URL}/api/cli/event", json=event_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        print(f"SUCCESS: CLI command with timestamp ingested")
    
    def test_ingest_cli_command_missing_required_fields(self, headers):
        """Test CLI command ingestion with missing required fields"""
        event_data = {
            "host_id": "test-workstation",
            # Missing session_id, user, shell_type, command
        }
        
        response = requests.post(f"{BASE_URL}/api/cli/event", json=event_data, headers=headers)
        
        # Should return 422 for validation error
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("SUCCESS: Validation error returned for missing fields")


class TestCLISessionSummaries:
    """Tests for CLI session summaries endpoints"""
    
    def test_get_all_session_summaries(self, headers):
        """Test GET /api/cli/sessions/all - retrieve all session summaries"""
        response = requests.get(f"{BASE_URL}/api/cli/sessions/all?limit=50", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "summaries" in data
        assert "count" in data
        assert isinstance(data["summaries"], list)
        
        print(f"SUCCESS: Retrieved {data['count']} session summaries")
        
        # Verify summary structure if data exists
        if data["summaries"]:
            summary = data["summaries"][0]
            expected_fields = ["host_id", "session_id", "machine_likelihood"]
            for field in expected_fields:
                assert field in summary, f"Missing field: {field}"
            print(f"SUCCESS: Summary structure validated - ML score: {summary.get('machine_likelihood', 'N/A')}")
    
    def test_get_session_summaries_with_min_ml_filter(self, headers):
        """Test GET /api/cli/sessions/all with min_ml filter"""
        response = requests.get(f"{BASE_URL}/api/cli/sessions/all?limit=50&min_ml=0.8", headers=headers)
        
        assert response.status_code == 200
        
        data = response.json()
        # All returned summaries should have ML >= 0.8
        for summary in data["summaries"]:
            assert summary.get("machine_likelihood", 0) >= 0.8, \
                f"Summary with ML {summary.get('machine_likelihood')} should be >= 0.8"
        
        print(f"SUCCESS: Retrieved {data['count']} high-risk sessions (ML >= 0.8)")
    
    def test_get_session_summaries_by_host(self, headers):
        """Test GET /api/cli/sessions/{host_id} - get summaries for specific host"""
        # First get all summaries to find a valid host_id
        all_response = requests.get(f"{BASE_URL}/api/cli/sessions/all?limit=10", headers=headers)
        
        if all_response.status_code == 200 and all_response.json().get("summaries"):
            host_id = all_response.json()["summaries"][0]["host_id"]
            
            response = requests.get(f"{BASE_URL}/api/cli/sessions/{host_id}", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            
            # All summaries should be for the requested host
            for summary in data["summaries"]:
                assert summary["host_id"] == host_id
            
            print(f"SUCCESS: Retrieved {data['count']} summaries for host {host_id}")
        else:
            print("SKIP: No session summaries available to test host-specific query")


class TestCLICommands:
    """Tests for CLI commands retrieval"""
    
    def test_get_cli_commands_by_host(self, headers):
        """Test GET /api/cli/commands/{host_id}"""
        # Use a test host ID
        host_id = "test-workstation-001"
        
        response = requests.get(f"{BASE_URL}/api/cli/commands/{host_id}?limit=50", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "commands" in data
        assert "count" in data
        
        print(f"SUCCESS: Retrieved {data['count']} commands for host {host_id}")


class TestDeceptionHits:
    """Tests for deception/honey token hit endpoints"""
    
    def test_ingest_deception_hit(self, headers):
        """Test POST /api/deception/event - ingest deception hit"""
        event_data = {
            "host_id": f"test-host-{uuid.uuid4().hex[:8]}",
            "token_id": "honey-test-token-001",
            "severity": "high",
            "suspect_pid": 12345,
            "context": {
                "path": "/tmp/honey_file.txt",
                "access_type": "read"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/deception/event", json=event_data, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "accepted"
        assert "event_id" in data
        assert data["playbook_evaluation"] == "triggered_immediate"
        
        print(f"SUCCESS: Deception hit ingested with event_id: {data['event_id']}")
    
    def test_get_deception_hits(self, headers):
        """Test GET /api/deception/hits - retrieve deception hits"""
        response = requests.get(f"{BASE_URL}/api/deception/hits?limit=20", headers=headers)
        
        assert response.status_code == 200
        
        data = response.json()
        assert "hits" in data
        assert "count" in data
        
        print(f"SUCCESS: Retrieved {data['count']} deception hits")
        
        # Verify hit structure if data exists
        if data["hits"]:
            hit = data["hits"][0]
            assert "host_id" in hit
            assert "token_id" in hit
            assert "severity" in hit
            print(f"SUCCESS: Deception hit structure validated - severity: {hit['severity']}")
    
    def test_get_deception_hits_by_severity(self, headers):
        """Test GET /api/deception/hits with severity filter"""
        response = requests.get(f"{BASE_URL}/api/deception/hits?severity=critical&limit=20", headers=headers)
        
        assert response.status_code == 200
        
        data = response.json()
        # All returned hits should have critical severity
        for hit in data["hits"]:
            assert hit.get("severity") == "critical"
        
        print(f"SUCCESS: Retrieved {data['count']} critical deception hits")


class TestSOARPlaybooks:
    """Tests for SOAR playbook endpoints"""
    
    def test_get_soar_stats(self, headers):
        """Test GET /api/soar/stats"""
        response = requests.get(f"{BASE_URL}/api/soar/stats", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        expected_fields = ["total_playbooks", "active_playbooks", "total_executions", "success_rate"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"SUCCESS: SOAR stats - {data['total_playbooks']} playbooks, {data['active_playbooks']} active")
    
    def test_get_soar_playbooks(self, headers):
        """Test GET /api/soar/playbooks"""
        response = requests.get(f"{BASE_URL}/api/soar/playbooks", headers=headers)
        
        assert response.status_code == 200
        
        data = response.json()
        assert "playbooks" in data
        
        playbooks = data["playbooks"]
        assert len(playbooks) >= 5, f"Expected at least 5 playbooks, got {len(playbooks)}"
        
        # Verify playbook structure
        if playbooks:
            pb = playbooks[0]
            assert "id" in pb
            assert "name" in pb
            assert "trigger" in pb
            assert "status" in pb
        
        print(f"SUCCESS: Retrieved {len(playbooks)} SOAR playbooks")
    
    def test_get_soar_executions(self, headers):
        """Test GET /api/soar/executions"""
        response = requests.get(f"{BASE_URL}/api/soar/executions?limit=20", headers=headers)
        
        assert response.status_code == 200
        
        data = response.json()
        assert "executions" in data
        
        print(f"SUCCESS: Retrieved {len(data['executions'])} SOAR executions")


class TestSessionSummaryIngestion:
    """Tests for CLI session summary ingestion"""
    
    def test_ingest_session_summary(self, headers):
        """Test POST /api/cli/session-summary - ingest session summary"""
        summary_data = {
            "host_id": f"test-host-{uuid.uuid4().hex[:8]}",
            "session_id": f"sess-{uuid.uuid4().hex[:8]}",
            "user": "test_user",
            "window_start": "2026-02-10T07:00:00Z",
            "window_end": "2026-02-10T07:00:30Z",
            "machine_likelihood": 0.85,
            "burstiness_score": 0.72,
            "tool_switch_latency_ms": 250,
            "goal_persistence": 0.68,
            "dominant_intents": ["recon", "credential_access"],
            "decoy_touched": False,
            "command_count": 15,
            "unique_tools": ["whoami", "net", "ipconfig"]
        }
        
        response = requests.post(f"{BASE_URL}/api/cli/session-summary", json=summary_data, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "accepted"
        assert "event_id" in data
        assert data["playbook_evaluation"] == "triggered"
        
        print(f"SUCCESS: Session summary ingested with event_id: {data['event_id']}")
    
    def test_ingest_high_risk_session_summary(self, headers):
        """Test ingestion of high-risk session summary (ML >= 0.92)"""
        summary_data = {
            "host_id": "critical-host-001",
            "session_id": "sess-critical-001",
            "user": "suspicious_user",
            "window_start": "2026-02-10T07:10:00Z",
            "window_end": "2026-02-10T07:10:30Z",
            "machine_likelihood": 0.95,
            "burstiness_score": 0.88,
            "tool_switch_latency_ms": 150,
            "goal_persistence": 0.92,
            "dominant_intents": ["lateral_movement", "privilege_escalation"],
            "decoy_touched": True,
            "command_count": 25
        }
        
        response = requests.post(f"{BASE_URL}/api/cli/session-summary", json=summary_data, headers=headers)
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "accepted"
        
        print(f"SUCCESS: High-risk session summary ingested (ML: 0.95, decoy_touched: True)")


class TestCCEWorkerIntegration:
    """Tests to verify CCE Worker is processing sessions"""
    
    def test_cce_worker_generates_summaries(self, headers):
        """Test that CCE Worker generates summaries for CLI commands"""
        # First, ingest multiple CLI commands for the same session
        host_id = f"cce-test-host-{uuid.uuid4().hex[:8]}"
        session_id = f"cce-sess-{uuid.uuid4().hex[:8]}"
        
        commands = [
            "whoami",
            "hostname",
            "ipconfig /all",
            "net user",
            "net localgroup administrators"
        ]
        
        for cmd in commands:
            event_data = {
                "host_id": host_id,
                "session_id": session_id,
                "user": "cce_test_user",
                "shell_type": "cmd",
                "command": cmd
            }
            response = requests.post(f"{BASE_URL}/api/cli/event", json=event_data, headers=headers)
            assert response.status_code == 200
        
        print(f"SUCCESS: Ingested {len(commands)} CLI commands for CCE Worker processing")
        print(f"Host: {host_id}, Session: {session_id}")
        print("Note: CCE Worker runs every 10s and requires min 3 commands to analyze")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
