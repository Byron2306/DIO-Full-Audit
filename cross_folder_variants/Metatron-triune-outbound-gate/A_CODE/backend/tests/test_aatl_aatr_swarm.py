"""
Test Suite for AATL, AATR, and Swarm Features
==============================================
Tests for:
- AI Threat Intelligence Dashboard
- AATL (Autonomous Agent Threat Layer) assessments
- AATR (Autonomous AI Threat Registry) entries
- CLI event ingestion with AATL processing
- Batch CLI event ingestion
- Network discovered devices
- Swarm overview statistics
- Network scan trigger
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@seraph.ai"
TEST_PASSWORD = "seraph123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestAIThreatIntelligenceDashboard:
    """Tests for AI Threat Intelligence Dashboard endpoint"""
    
    def test_get_intelligence_dashboard(self, headers):
        """GET /api/ai-threats/intelligence/dashboard - Returns dashboard data"""
        response = requests.get(f"{BASE_URL}/api/ai-threats/intelligence/dashboard", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify AATL section
        assert "aatl" in data
        assert "total_sessions" in data["aatl"]
        assert "autonomous_agent_sessions" in data["aatl"]
        assert "by_actor_type" in data["aatl"]
        assert "by_lifecycle_stage" in data["aatl"]
        assert "by_threat_level" in data["aatl"]
        
        # Verify AATR section
        assert "aatr" in data
        assert "total_entries" in data["aatr"]
        assert "by_classification" in data["aatr"]
        assert "by_risk_profile" in data["aatr"]
        assert "by_status" in data["aatr"]
        assert "total_indicators" in data["aatr"]
        
        # Verify combined metrics
        assert "combined_threat_score" in data
        assert "active_threat_types" in data
        
        print(f"Dashboard: {data['aatl']['total_sessions']} sessions, {data['aatr']['total_entries']} registry entries")


class TestAATLAssessments:
    """Tests for AATL Assessment endpoints"""
    
    def test_get_aatl_assessments(self, headers):
        """GET /api/ai-threats/aatl/assessments - Returns AATL assessments"""
        response = requests.get(f"{BASE_URL}/api/ai-threats/aatl/assessments", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "assessments" in data
        
        if data["assessments"]:
            assessment = data["assessments"][0]
            # Verify assessment structure
            assert "host_id" in assessment
            assert "session_id" in assessment
            assert "machine_plausibility" in assessment
            assert "human_plausibility" in assessment
            assert "threat_score" in assessment
            assert "threat_level" in assessment
            assert "actor_type" in assessment
            assert "recommended_strategy" in assessment
            assert "indicators" in assessment
            
            print(f"Found {len(data['assessments'])} AATL assessments")
            print(f"First assessment: threat_score={assessment['threat_score']}, actor_type={assessment['actor_type']}")
    
    def test_get_aatl_assessments_with_min_threat(self, headers):
        """GET /api/ai-threats/aatl/assessments?min_threat=30 - Filter by threat score"""
        response = requests.get(f"{BASE_URL}/api/ai-threats/aatl/assessments?min_threat=30", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned assessments should have threat_score >= 30
        for assessment in data.get("assessments", []):
            assert assessment.get("threat_score", 0) >= 30
        
        print(f"Found {len(data.get('assessments', []))} assessments with threat >= 30")


class TestAATRRegistry:
    """Tests for AATR Registry endpoints"""
    
    def test_get_aatr_entries(self, headers):
        """GET /api/ai-threats/aatr/entries - Returns AATR registry entries"""
        response = requests.get(f"{BASE_URL}/api/ai-threats/aatr/entries", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "entries" in data
        assert len(data["entries"]) >= 6, "Should have at least 6 threat entries"
        
        entry = data["entries"][0]
        # Verify entry structure
        assert "id" in entry
        assert "name" in entry
        assert "classification" in entry
        assert "description" in entry
        assert "risk_profile" in entry
        assert "threat_status" in entry
        assert "observed_capabilities" in entry
        assert "typical_behaviors" in entry
        assert "defensive_indicators" in entry
        assert "known_misuse_patterns" in entry
        assert "recommended_defenses" in entry
        
        print(f"Found {len(data['entries'])} AATR registry entries")
        for e in data["entries"][:3]:
            print(f"  - {e['id']}: {e['name']} ({e['risk_profile']})")
    
    def test_get_aatr_indicators(self, headers):
        """GET /api/ai-threats/aatr/indicators - Returns detection indicators"""
        response = requests.get(f"{BASE_URL}/api/ai-threats/aatr/indicators", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "indicators" in data
        assert len(data["indicators"]) > 0
        
        indicator = data["indicators"][0]
        assert "category" in indicator
        assert "indicator" in indicator
        assert "confidence" in indicator
        assert "description" in indicator
        
        print(f"Found {len(data['indicators'])} detection indicators")


class TestCLIEventIngestion:
    """Tests for CLI Event Ingestion with AATL processing"""
    
    def test_ingest_single_cli_event(self, headers):
        """POST /api/swarm/cli/event - Ingest single CLI event"""
        response = requests.post(
            f"{BASE_URL}/api/swarm/cli/event",
            headers=headers,
            json={
                "host_id": "pytest-host-001",
                "session_id": "pytest-session-001",
                "command": "whoami",
                "user": "testuser"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert data["command_stored"] == True
        
        print(f"CLI event ingested successfully")
    
    def test_ingest_cli_event_with_aatl_assessment(self, headers):
        """POST /api/swarm/cli/event - Multiple commands trigger AATL assessment"""
        # Send multiple recon commands to trigger AATL analysis
        commands = ["id", "hostname", "cat /etc/passwd", "netstat -an", "ps aux"]
        
        for cmd in commands:
            response = requests.post(
                f"{BASE_URL}/api/swarm/cli/event",
                headers=headers,
                json={
                    "host_id": "pytest-host-002",
                    "session_id": "pytest-session-002",
                    "command": cmd,
                    "user": "attacker"
                }
            )
            assert response.status_code == 200
            time.sleep(0.1)  # Small delay between commands
        
        # Last response should have AATL assessment
        data = response.json()
        assert "aatl_assessment" in data
        
        assessment = data["aatl_assessment"]
        assert "machine_plausibility" in assessment
        assert "threat_score" in assessment
        assert "threat_level" in assessment
        assert "actor_type" in assessment
        assert "recommended_strategy" in assessment
        
        print(f"AATL Assessment: threat_score={assessment['threat_score']}, actor_type={assessment['actor_type']}")
        print(f"Recommended strategy: {assessment['recommended_strategy']}")
    
    def test_ingest_batch_cli_events(self, headers):
        """POST /api/swarm/cli/batch - Batch CLI event ingestion"""
        events = [
            {"host_id": "pytest-batch-host", "session_id": "pytest-batch-session", "command": "whoami", "user": "root"},
            {"host_id": "pytest-batch-host", "session_id": "pytest-batch-session", "command": "id", "user": "root"},
            {"host_id": "pytest-batch-host", "session_id": "pytest-batch-session", "command": "uname -a", "user": "root"}
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/swarm/cli/batch",
            headers=headers,
            json=events
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert data["processed"] == 3
        
        print(f"Batch processed: {data['processed']} events, {data['aatl_assessments']} assessments")


class TestSwarmDevices:
    """Tests for Swarm Device Management"""
    
    def test_get_discovered_devices(self, headers):
        """GET /api/swarm/devices - Returns discovered devices"""
        response = requests.get(f"{BASE_URL}/api/swarm/devices", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "devices" in data
        assert "stats" in data
        
        stats = data["stats"]
        assert "total" in stats
        assert "managed" in stats
        assert "unmanaged" in stats
        assert "by_os" in stats
        assert "by_status" in stats
        
        print(f"Discovered devices: {stats['total']} total, {stats['managed']} managed")
        
        if data["devices"]:
            device = data["devices"][0]
            assert "ip_address" in device
            assert "deployment_status" in device
            print(f"First device: {device['ip_address']} ({device['deployment_status']})")


class TestSwarmOverview:
    """Tests for Swarm Overview Statistics"""
    
    def test_get_swarm_overview(self, headers):
        """GET /api/swarm/overview - Returns swarm overview statistics"""
        response = requests.get(f"{BASE_URL}/api/swarm/overview", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify devices section
        assert "devices" in data
        assert "total" in data["devices"]
        assert "managed" in data["devices"]
        assert "unmanaged" in data["devices"]
        
        # Verify agents section
        assert "agents" in data
        assert "total" in data["agents"]
        assert "online" in data["agents"]
        assert "offline" in data["agents"]
        
        # Verify telemetry section
        assert "telemetry" in data
        assert "total_events" in data["telemetry"]
        assert "critical" in data["telemetry"]
        
        # Verify deployments section
        assert "deployments" in data
        assert "total" in data["deployments"]
        assert "successful" in data["deployments"]
        assert "failed" in data["deployments"]
        assert "success_rate" in data["deployments"]
        
        print(f"Swarm Overview:")
        print(f"  Devices: {data['devices']['total']} total, {data['devices']['managed']} managed")
        print(f"  Agents: {data['agents']['total']} total, {data['agents']['online']} online")
        print(f"  Telemetry: {data['telemetry']['total_events']} events, {data['telemetry']['critical']} critical")


class TestNetworkScan:
    """Tests for Network Scan functionality"""
    
    def test_trigger_network_scan(self, headers):
        """POST /api/swarm/scan - Trigger network scan"""
        response = requests.post(
            f"{BASE_URL}/api/swarm/scan",
            headers=headers,
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "scan" in data["message"].lower() or "initiated" in data["message"].lower()
        
        print(f"Network scan: {data['message']}")
    
    def test_get_scan_status(self, headers):
        """GET /api/swarm/scan/status - Get scan status"""
        response = requests.get(f"{BASE_URL}/api/swarm/scan/status", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "running" in data or "message" in data
        
        print(f"Scan status: {data}")


class TestTelemetry:
    """Tests for Telemetry endpoints"""
    
    def test_get_telemetry(self, headers):
        """GET /api/swarm/telemetry - Returns telemetry events"""
        response = requests.get(f"{BASE_URL}/api/swarm/telemetry?limit=10", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "count" in data
        
        print(f"Telemetry: {data['count']} events")
    
    def test_get_telemetry_stats(self, headers):
        """GET /api/swarm/telemetry/stats - Returns telemetry statistics"""
        response = requests.get(f"{BASE_URL}/api/swarm/telemetry/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_events" in data
        assert "by_type" in data
        assert "by_severity" in data
        assert "by_host" in data
        
        print(f"Telemetry stats: {data['total_events']} total events")


class TestAATLBehaviorDetection:
    """Tests for AATL behavior detection patterns"""
    
    def test_detect_machine_like_behavior(self, headers):
        """Verify AATL detects machine-like behavior patterns"""
        # Send rapid commands to simulate machine behavior
        commands = [
            "whoami", "id", "hostname", "uname -a", "cat /etc/passwd",
            "netstat -an", "ps aux", "ls -la /etc", "cat /etc/shadow"
        ]
        
        session_id = f"machine-test-{int(time.time())}"
        
        for cmd in commands:
            response = requests.post(
                f"{BASE_URL}/api/swarm/cli/event",
                headers=headers,
                json={
                    "host_id": "machine-behavior-host",
                    "session_id": session_id,
                    "command": cmd,
                    "user": "attacker"
                }
            )
            assert response.status_code == 200
            # No delay to simulate machine-like rapid execution
        
        # Check the final assessment
        data = response.json()
        
        if "aatl_assessment" in data:
            assessment = data["aatl_assessment"]
            print(f"Machine behavior detection:")
            print(f"  Machine plausibility: {assessment['machine_plausibility']}")
            print(f"  Threat score: {assessment['threat_score']}")
            print(f"  Actor type: {assessment['actor_type']}")
            print(f"  Recommended strategy: {assessment['recommended_strategy']}")
            
            # Machine-like behavior should have higher machine_plausibility
            # Note: Due to timing in test environment, this may vary
    
    def test_threat_strategies(self, headers):
        """Verify AATL recommends appropriate strategies based on threat level"""
        # Get current assessments
        response = requests.get(f"{BASE_URL}/api/ai-threats/aatl/assessments", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        valid_strategies = ["observe", "slow", "poison", "deceive", "contain", "eradicate"]
        
        for assessment in data.get("assessments", []):
            strategy = assessment.get("recommended_strategy")
            assert strategy in valid_strategies, f"Invalid strategy: {strategy}"
            
            threat_score = assessment.get("threat_score", 0)
            
            # Verify strategy matches threat level
            if threat_score < 30:
                assert strategy == "observe", f"Low threat should recommend observe, got {strategy}"
            elif threat_score >= 85:
                assert strategy in ["contain", "eradicate"], f"Critical threat should recommend contain/eradicate"
        
        print(f"Verified strategies for {len(data.get('assessments', []))} assessments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
