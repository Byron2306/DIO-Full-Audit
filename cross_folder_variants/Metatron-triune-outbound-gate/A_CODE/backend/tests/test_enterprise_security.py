"""
Enterprise Security Features Test Suite
========================================
Tests for:
- Identity & Attestation (mTLS, SPIFFE-style identity, trust scoring)
- Policy & Permissions (action gates, blast-radius caps, human-in-the-loop)
- Token Broker (scoped capability tokens)
- CLI Tool Gateway (governed tool execution)
- Tamper-Evident Telemetry (signed events, hash chains)
"""

import pytest
import requests
import os
from datetime import datetime, timezone

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')

# Test credentials
TEST_EMAIL = "test@defender.io"
TEST_PASSWORD = "test123"


class TestEnterpriseStatus:
    """Test enterprise security status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_enterprise_status_endpoint(self):
        """GET /api/enterprise/status - should return enterprise security status"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "identity" in data, "Response should contain 'identity' section"
        assert "policy" in data, "Response should contain 'policy' section"
        assert "tokens" in data, "Response should contain 'tokens' section"
        assert "tools" in data, "Response should contain 'tools' section"
        assert "telemetry" in data, "Response should contain 'telemetry' section"
        
        # Verify identity section
        assert "registered_agents" in data["identity"]
        
        # Verify policy section
        assert "pending_approvals" in data["policy"]
        assert "action_categories" in data["policy"]
        assert "approval_tiers" in data["policy"]
        
        # Verify tokens section
        assert "active_tokens" in data["tokens"]
        assert "stored_secrets" in data["tokens"]
        
        # Verify tools section
        assert "registered_tools" in data["tools"]
        assert "tools" in data["tools"]
        
        # Verify telemetry section
        assert "event_chain_length" in data["telemetry"]
        assert "integrity_verified" in data["telemetry"]
        
        print(f"Enterprise status: {data}")


class TestCLIToolGateway:
    """Test CLI Tool Gateway endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_list_tools_endpoint(self):
        """GET /api/enterprise/tools - should return list of registered CLI tools"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/tools")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tools" in data, "Response should contain 'tools' list"
        
        tools = data["tools"]
        assert isinstance(tools, list), "Tools should be a list"
        
        # Verify 7 registered tools as per requirements
        assert len(tools) >= 7, f"Expected at least 7 tools, got {len(tools)}"
        
        # Verify expected tools are present
        tool_ids = [t["tool_id"] for t in tools]
        expected_tools = [
            "process_list", "process_kill", "network_connections",
            "firewall_block", "file_hash", "memory_dump", "suricata_reload_rules"
        ]
        
        for expected in expected_tools:
            assert expected in tool_ids, f"Expected tool '{expected}' not found in {tool_ids}"
        
        # Verify tool structure
        for tool in tools:
            assert "tool_id" in tool
            assert "name" in tool
            assert "description" in tool
            assert "requires_approval" in tool
            assert "min_trust_state" in tool
        
        print(f"Registered tools ({len(tools)}): {tool_ids}")
    
    def test_get_specific_tool(self):
        """GET /api/enterprise/tools/{tool_id} - should return tool definition"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/tools/process_list")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["tool_id"] == "process_list"
        assert "name" in data
        assert "description" in data
        assert "args_schema" in data
        assert "allowed_flags" in data
        assert "requires_approval" in data
        assert "min_trust_state" in data
        assert "timeout_seconds" in data
        
        print(f"Tool definition: {data}")
    
    def test_gateway_status(self):
        """GET /api/enterprise/tools/status - should return gateway status"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/tools/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "registered_tools" in data
        assert "total_executions" in data
        assert "tools" in data
        
        assert data["registered_tools"] >= 7, f"Expected at least 7 tools, got {data['registered_tools']}"
        
        print(f"Gateway status: {data}")


class TestPolicyEngine:
    """Test Policy & Permissions Engine endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_policy_evaluate_observe_action(self):
        """POST /api/enterprise/policy/evaluate - should evaluate observe action (auto-approve)"""
        response = self.session.post(f"{BASE_URL}/api/enterprise/policy/evaluate", json={
            "principal": "agent:test-agent-001",
            "action": "list_processes",
            "targets": ["host-001"],
            "trust_state": "trusted",
            "role": "agent",
            "evidence_confidence": 0.8,
            "incident_mode": "normal"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "decision_id" in data
        assert "permitted" in data
        assert "approval_tier" in data
        assert "allowed_scopes" in data
        assert "rate_limit" in data
        assert "decision_hash" in data
        
        # Observe actions should be auto-approved
        assert data["permitted"] == True, "Observe action should be permitted"
        assert data["approval_tier"] == "auto", f"Expected 'auto' approval tier, got {data['approval_tier']}"
        
        print(f"Policy decision (observe): {data}")
    
    def test_policy_evaluate_remediate_action(self):
        """POST /api/enterprise/policy/evaluate - should evaluate remediate action (require approval)"""
        response = self.session.post(f"{BASE_URL}/api/enterprise/policy/evaluate", json={
            "principal": "agent:test-agent-001",
            "action": "kill_process",
            "targets": ["pid:1234"],
            "trust_state": "trusted",
            "role": "agent",
            "evidence_confidence": 0.9,
            "incident_mode": "normal"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["permitted"] == True
        # Remediate actions should require approval
        assert data["approval_tier"] == "require_approval", f"Expected 'require_approval', got {data['approval_tier']}"
        
        # Verify blast radius cap is set
        assert data["blast_radius_cap"] is not None
        
        print(f"Policy decision (remediate): {data}")
    
    def test_policy_evaluate_denied_by_trust_state(self):
        """POST /api/enterprise/policy/evaluate - should deny action for quarantined agent"""
        response = self.session.post(f"{BASE_URL}/api/enterprise/policy/evaluate", json={
            "principal": "agent:quarantined-agent",
            "action": "list_processes",
            "targets": ["host-001"],
            "trust_state": "quarantined",
            "role": "agent"
        })
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["permitted"] == False, "Quarantined agent should be denied"
        assert data["denial_reason"] is not None
        
        print(f"Policy decision (denied): {data}")
    
    def test_policy_pending_approvals(self):
        """GET /api/enterprise/policy/pending - should return pending approvals"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/policy/pending")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "pending" in data
        assert isinstance(data["pending"], list)
        
        print(f"Pending approvals: {len(data['pending'])}")
    
    def test_policy_status(self):
        """GET /api/enterprise/policy/status - should return policy engine status"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/policy/status")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "pending_approvals" in data
        assert "rate_limit_entries" in data
        assert "action_categories" in data
        assert "approval_tiers" in data
        
        # Verify action categories
        expected_categories = ["observe", "collect", "contain", "remediate", "credential", "deception"]
        for cat in expected_categories:
            assert cat in data["action_categories"], f"Missing action category: {cat}"
        
        # Verify approval tiers
        expected_tiers = ["auto", "suggest", "require_approval", "two_person"]
        for tier in expected_tiers:
            assert tier in data["approval_tiers"], f"Missing approval tier: {tier}"
        
        print(f"Policy status: {data}")


class TestTelemetryChain:
    """Test Tamper-Evident Telemetry endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_verify_chain_integrity(self):
        """GET /api/enterprise/telemetry/verify - should verify chain integrity"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/telemetry/verify")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "integrity_verified" in data
        assert "message" in data
        assert "event_chain_length" in data
        assert "audit_chain_length" in data
        assert "current_event_hash" in data
        assert "current_audit_hash" in data
        
        # Chain should be valid
        assert data["integrity_verified"] == True, f"Chain integrity failed: {data['message']}"
        
        print(f"Chain integrity: {data}")
    
    def test_ingest_telemetry_event(self):
        """POST /api/enterprise/telemetry/event - should ingest event into chain"""
        response = self.session.post(f"{BASE_URL}/api/enterprise/telemetry/event", json={
            "event_type": "test_event",
            "severity": "info",
            "data": {
                "test_key": "test_value",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "agent_id": "test-agent-001",
            "hostname": "test-host"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "event_id" in data
        assert "event_hash" in data
        assert "prev_hash" in data
        assert "trace_id" in data
        
        # Verify hash chain linkage
        assert data["event_hash"] != data["prev_hash"], "Event hash should differ from prev_hash"
        
        print(f"Ingested event: {data}")
    
    def test_query_telemetry_events(self):
        """GET /api/enterprise/telemetry/events - should query events"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/telemetry/events?limit=10")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        
        print(f"Events count: {len(data['events'])}")
    
    def test_query_audit_trail(self):
        """GET /api/enterprise/telemetry/audit - should query audit trail"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/telemetry/audit?limit=10")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "records" in data
        assert isinstance(data["records"], list)
        
        print(f"Audit records count: {len(data['records'])}")


class TestIdentityService:
    """Test Identity & Attestation endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_list_identities(self):
        """GET /api/enterprise/identity - should return registered identities"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/identity")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "identities" in data
        assert isinstance(data["identities"], list)
        
        print(f"Registered identities: {len(data['identities'])}")
    
    def test_get_attestation_nonce(self):
        """GET /api/enterprise/identity/nonce - should return one-time nonce"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/identity/nonce")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "nonce" in data
        assert "valid_seconds" in data
        assert len(data["nonce"]) == 32, "Nonce should be 32 hex characters"
        assert data["valid_seconds"] == 60
        
        print(f"Attestation nonce: {data}")
    
    def test_submit_attestation(self):
        """POST /api/enterprise/identity/attest - should register identity with trust scoring"""
        # First get a nonce
        nonce_response = self.session.get(f"{BASE_URL}/api/enterprise/identity/nonce")
        nonce = nonce_response.json()["nonce"]
        
        # Submit attestation
        response = self.session.post(f"{BASE_URL}/api/enterprise/identity/attest", json={
            "agent_id": "test-enterprise-agent-001",
            "hostname": "test-host-001",
            "os_type": "linux",
            "cert_fingerprint": "sha256:abc123def456",
            "agent_version_hash": "sha256:version123",
            "os_build_hash": "sha256:osbuild456",
            "secure_boot": True,
            "tpm_available": True,
            "key_isolated": True,
            "posture_score": 85,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": nonce,
            "signature": "test-signature-placeholder"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "spiffe_id" in data
        assert "trust_state" in data
        assert "trust_score" in data
        assert "expires_at" in data
        
        # Verify SPIFFE-style ID format
        assert data["spiffe_id"].startswith("spiffe://seraph.local/agent/")
        
        # Verify trust scoring (with secure_boot, tpm, key_isolated = high score)
        assert data["trust_score"] >= 50, f"Expected trust score >= 50, got {data['trust_score']}"
        
        # Trust state should be at least degraded with these settings
        assert data["trust_state"] in ["trusted", "degraded"], f"Unexpected trust state: {data['trust_state']}"
        
        print(f"Attestation result: {data}")
    
    def test_get_specific_identity(self):
        """GET /api/enterprise/identity/{agent_id} - should return identity details"""
        # First register an identity
        nonce_response = self.session.get(f"{BASE_URL}/api/enterprise/identity/nonce")
        nonce = nonce_response.json()["nonce"]
        
        self.session.post(f"{BASE_URL}/api/enterprise/identity/attest", json={
            "agent_id": "test-identity-lookup-agent",
            "hostname": "test-host",
            "os_type": "linux",
            "cert_fingerprint": "sha256:lookup123",
            "agent_version_hash": "sha256:v1",
            "os_build_hash": "sha256:os1",
            "secure_boot": False,
            "tpm_available": False,
            "key_isolated": False,
            "posture_score": 50,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": nonce,
            "signature": "sig"
        })
        
        # Now lookup the identity
        response = self.session.get(f"{BASE_URL}/api/enterprise/identity/test-identity-lookup-agent")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["agent_id"] == "test-identity-lookup-agent"
        assert "spiffe_id" in data
        assert "trust_state" in data
        assert "trust_score" in data
        
        print(f"Identity lookup: {data}")


class TestTokenBroker:
    """Test Token Broker endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_get_active_tokens(self):
        """GET /api/enterprise/token/active - should return active tokens"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/token/active")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tokens" in data
        assert isinstance(data["tokens"], list)
        
        print(f"Active tokens: {len(data['tokens'])}")
    
    def test_issue_capability_token(self):
        """POST /api/enterprise/token/issue - should issue scoped capability token"""
        response = self.session.post(f"{BASE_URL}/api/enterprise/token/issue", json={
            "principal": "agent:test-token-agent",
            "principal_identity": "spiffe://seraph.local/agent/test-token-agent",
            "action": "process_list",
            "targets": ["host-001", "host-002"],
            "tool_id": "process_list",
            "ttl_seconds": 300,
            "max_uses": 5,
            "constraints": {"max_results": 100}
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token_id" in data
        assert "expires_at" in data
        assert "max_uses" in data
        assert data["max_uses"] == 5
        
        # Token ID should have expected format
        assert data["token_id"].startswith("tok-")
        
        print(f"Issued token: {data}")
        
        return data["token_id"]
    
    def test_token_broker_status(self):
        """GET /api/enterprise/token/status - should return broker status"""
        response = self.session.get(f"{BASE_URL}/api/enterprise/token/status")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "active_tokens" in data
        assert "revoked_tokens" in data
        assert "stored_secrets" in data
        assert "access_log_size" in data
        
        print(f"Token broker status: {data}")
    
    def test_revoke_token(self):
        """POST /api/enterprise/token/revoke/{token_id} - should revoke token"""
        # First issue a token
        issue_response = self.session.post(f"{BASE_URL}/api/enterprise/token/issue", json={
            "principal": "agent:revoke-test-agent",
            "principal_identity": "spiffe://seraph.local/agent/revoke-test-agent",
            "action": "test_action",
            "targets": ["target-001"],
            "ttl_seconds": 60,
            "max_uses": 1
        })
        
        token_id = issue_response.json()["token_id"]
        
        # Revoke the token
        response = self.session.post(f"{BASE_URL}/api/enterprise/token/revoke/{token_id}")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        
        print(f"Token revoked: {token_id}")


class TestServiceImplementations:
    """Verify service implementations have required features"""
    
    def test_identity_service_has_trust_scoring(self):
        """Verify identity.py has IdentityService with trust scoring"""
        from backend.services.identity import IdentityService, TrustState
        
        service = IdentityService()
        
        # Verify trust scoring method exists
        assert hasattr(service, 'calculate_trust_score'), "IdentityService should have calculate_trust_score method"
        assert hasattr(service, 'determine_trust_state'), "IdentityService should have determine_trust_state method"
        
        # Verify trust states
        assert TrustState.TRUSTED.value == "trusted"
        assert TrustState.DEGRADED.value == "degraded"
        assert TrustState.QUARANTINED.value == "quarantined"
        assert TrustState.UNKNOWN.value == "unknown"
        
        print("IdentityService has trust scoring: VERIFIED")
    
    def test_policy_engine_has_action_categories(self):
        """Verify policy_engine.py has PolicyEngine with action categories"""
        from backend.services.policy_engine import PolicyEngine, ActionCategory, ApprovalTier
        
        engine = PolicyEngine()
        
        # Verify action categories
        expected_categories = ["observe", "collect", "contain", "remediate", "credential", "deception"]
        for cat in expected_categories:
            assert hasattr(ActionCategory, cat.upper()), f"Missing ActionCategory: {cat}"
        
        # Verify approval tiers
        expected_tiers = ["auto", "suggest", "require_approval", "two_person"]
        for tier in expected_tiers:
            tier_enum = tier.upper()
            assert hasattr(ApprovalTier, tier_enum), f"Missing ApprovalTier: {tier}"
        
        # Verify evaluate method
        assert hasattr(engine, 'evaluate'), "PolicyEngine should have evaluate method"
        
        print("PolicyEngine has action categories: VERIFIED")
    
    def test_token_broker_has_capability_tokens(self):
        """Verify token_broker.py has TokenBroker with capability tokens"""
        from backend.services.token_broker import TokenBroker, CapabilityToken
        
        broker = TokenBroker()
        
        # Verify token methods
        assert hasattr(broker, 'issue_token'), "TokenBroker should have issue_token method"
        assert hasattr(broker, 'validate_token'), "TokenBroker should have validate_token method"
        assert hasattr(broker, 'revoke_token'), "TokenBroker should have revoke_token method"
        
        # Verify CapabilityToken has required fields
        from dataclasses import fields
        token_fields = [f.name for f in fields(CapabilityToken)]
        required_fields = ['token_id', 'principal', 'principal_identity', 'action', 'targets', 'expires_at', 'max_uses']
        for field in required_fields:
            assert field in token_fields, f"CapabilityToken missing field: {field}"
        
        print("TokenBroker has capability tokens: VERIFIED")
    
    def test_tool_gateway_has_7_registered_tools(self):
        """Verify tool_gateway.py has ToolGateway with 7 registered tools"""
        from backend.services.tool_gateway import ToolGateway
        
        gateway = ToolGateway()
        
        # Verify 7 tools are registered
        tools = gateway.list_tools()
        assert len(tools) >= 7, f"Expected at least 7 tools, got {len(tools)}"
        
        # Verify expected tools
        tool_ids = [t["tool_id"] for t in tools]
        expected_tools = [
            "process_list", "process_kill", "network_connections",
            "firewall_block", "file_hash", "memory_dump", "suricata_reload_rules"
        ]
        
        for expected in expected_tools:
            assert expected in tool_ids, f"Missing tool: {expected}"
        
        print(f"ToolGateway has {len(tools)} registered tools: VERIFIED")
        print(f"Tools: {tool_ids}")
    
    def test_telemetry_chain_has_hash_chains(self):
        """Verify telemetry_chain.py has TamperEvidentTelemetry with hash chains"""
        from backend.services.telemetry_chain import TamperEvidentTelemetry
        
        telemetry = TamperEvidentTelemetry()
        
        # Verify hash chain methods
        assert hasattr(telemetry, 'verify_chain_integrity'), "Should have verify_chain_integrity method"
        assert hasattr(telemetry, 'ingest_event'), "Should have ingest_event method"
        assert hasattr(telemetry, 'record_action'), "Should have record_action method"
        
        # Verify chain attributes
        assert hasattr(telemetry, 'event_chain'), "Should have event_chain"
        assert hasattr(telemetry, 'audit_chain'), "Should have audit_chain"
        assert hasattr(telemetry, 'genesis_event_hash'), "Should have genesis_event_hash"
        
        # Verify chain integrity
        valid, msg = telemetry.verify_chain_integrity()
        assert valid, f"Chain integrity check failed: {msg}"
        
        print("TamperEvidentTelemetry has hash chains: VERIFIED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
