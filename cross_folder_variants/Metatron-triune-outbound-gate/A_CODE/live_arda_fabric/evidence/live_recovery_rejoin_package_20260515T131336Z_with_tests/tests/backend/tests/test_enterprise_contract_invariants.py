"""Contract assurance tests for enterprise control-plane routes."""

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "backend" / "routers"

EXPECTED_CONTRACT_VERSION = "2026-03-07.1"


def _load_enterprise_module():
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(ROOT / "backend")]
    sys.modules.setdefault("backend", backend_pkg)

    routers_pkg = types.ModuleType("backend.routers")
    routers_pkg.__path__ = [str(ROUTERS_DIR)]
    sys.modules.setdefault("backend.routers", routers_pkg)

    dependencies_stub = types.ModuleType("backend.routers.dependencies")

    async def _fake_get_current_user():
        return {"email": "tester@example.com", "role": "admin"}

    def _fake_check_permission(_permission):
        async def _dep():
            return {"email": "tester@example.com", "role": "admin"}

        return _dep

    dependencies_stub.get_current_user = _fake_get_current_user
    dependencies_stub.check_permission = _fake_check_permission
    dependencies_stub.db = None
    sys.modules.setdefault("backend.routers.dependencies", dependencies_stub)

    module_path = ROUTERS_DIR / "enterprise.py"
    spec = importlib.util.spec_from_file_location("backend.routers.enterprise", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.routers.enterprise")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.routers.enterprise"] = module
    spec.loader.exec_module(module)
    return module


enterprise = _load_enterprise_module()


def _install_service_stubs():
    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []
    sys.modules.setdefault("services", services_pkg)

    identity_mod = types.ModuleType("services.identity")

    class AttestationData:
        def __init__(self, **kwargs):
            self.payload = kwargs

    class _IdentityService:
        def register_identity(self, **_kwargs):
            return SimpleNamespace(
                spiffe_id="spiffe://metatron/agent/agent-1",
                trust_state=SimpleNamespace(value="trusted"),
                trust_score=95,
                expires_at="2026-03-08T00:00:00Z",
            )

        def generate_nonce(self):
            return "nonce-1"

    identity_mod.AttestationData = AttestationData
    identity_mod.identity_service = _IdentityService()
    sys.modules["services.identity"] = identity_mod

    policy_mod = types.ModuleType("services.policy_engine")

    class _PolicyEngine:
        def evaluate(self, **_kwargs):
            return SimpleNamespace(
                decision_id="decision-1",
                permitted=True,
                approval_tier=SimpleNamespace(value="tier0"),
                denial_reason=None,
                allowed_scopes=["host:all"],
                rate_limit=100,
                blast_radius_cap=10,
                ttl_seconds=300,
                decision_hash="hash-1",
            )

    policy_mod.policy_engine = _PolicyEngine()
    sys.modules["services.policy_engine"] = policy_mod

    token_mod = types.ModuleType("services.token_broker")

    class _TokenBroker:
        def issue_token(self, **_kwargs):
            return SimpleNamespace(
                token_id="token-1",
                expires_at="2026-03-08T00:00:00Z",
                max_uses=1,
            )

    token_mod.token_broker = _TokenBroker()
    sys.modules["services.token_broker"] = token_mod

    tool_mod = types.ModuleType("services.tool_gateway")

    class _ToolGateway:
        def execute(self, **_kwargs):
            return SimpleNamespace(
                execution_id="exec-1",
                status="completed",
                exit_code=0,
                stdout="ok",
                stderr="",
                duration_ms=10,
            )

    tool_mod.tool_gateway = _ToolGateway()
    sys.modules["services.tool_gateway"] = tool_mod

    telemetry_mod = types.ModuleType("services.telemetry_chain")

    class _TelemetryChain:
        def ingest_event(self, **_kwargs):
            return SimpleNamespace(
                event_id="event-1",
                event_hash="hash-event",
                prev_hash="hash-prev",
                trace_id="trace-1",
            )

        def record_action(self, **_kwargs):
            return SimpleNamespace(record_id="record-1", record_hash="hash-record")

    telemetry_mod.tamper_evident_telemetry = _TelemetryChain()
    sys.modules["services.telemetry_chain"] = telemetry_mod


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(enterprise.router, prefix="/api")
    return TestClient(app)


def test_contract_version_constant_is_pinned():
    assert enterprise.ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION == EXPECTED_CONTRACT_VERSION


def test_control_plane_route_set_invariants():
    app = FastAPI()
    app.include_router(enterprise.router, prefix="/api")

    route_methods = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
    }

    expected = {
        ("/api/enterprise/identity/attest", "POST"),
        ("/api/enterprise/policy/evaluate", "POST"),
        ("/api/enterprise/token/issue", "POST"),
        ("/api/enterprise/tools/execute", "POST"),
        ("/api/enterprise/telemetry/event", "POST"),
        ("/api/enterprise/telemetry/audit", "POST"),
    }

    for pair in expected:
        assert pair in route_methods


def test_request_model_schema_invariants():
    attest_schema = enterprise.AttestationRequest.model_json_schema()
    policy_schema = enterprise.PolicyEvaluationRequest.model_json_schema()
    token_schema = enterprise.TokenRequest.model_json_schema()
    tool_schema = enterprise.ToolExecutionRequest.model_json_schema()
    telemetry_schema = enterprise.TelemetryEventRequest.model_json_schema()
    audit_schema = enterprise.AuditActionRequest.model_json_schema()

    assert "agent_id" in (attest_schema.get("required") or [])
    assert "cert_fingerprint" in (attest_schema.get("required") or [])
    assert "nonce" in (attest_schema.get("required") or [])

    assert "principal" in (policy_schema.get("required") or [])
    assert "action" in (policy_schema.get("required") or [])
    assert "targets" in (policy_schema.get("required") or [])

    assert "principal_identity" in (token_schema.get("required") or [])
    assert "ttl_seconds" in token_schema.get("properties", {})

    assert "tool_id" in (tool_schema.get("required") or [])
    assert "token_id" in (tool_schema.get("required") or [])

    assert "event_type" in (telemetry_schema.get("required") or [])
    assert "severity" in (telemetry_schema.get("required") or [])
    assert "data" in (telemetry_schema.get("required") or [])

    assert "principal_trust_state" in (audit_schema.get("required") or [])
    assert "targets" in (audit_schema.get("required") or [])


def test_success_paths_emit_contract_version():
    _install_service_stubs()
    client = _build_client()

    attest_resp = client.post(
        "/api/enterprise/identity/attest",
        json={
            "agent_id": "agent-1",
            "hostname": "node-1",
            "os_type": "linux",
            "cert_fingerprint": "fp",
            "agent_version_hash": "vhash",
            "os_build_hash": "ohash",
            "secure_boot": True,
            "tpm_available": True,
            "key_isolated": True,
            "posture_score": 95,
            "timestamp": "2026-03-07T00:00:00Z",
            "nonce": "nonce-1",
            "signature": "sig",
        },
    )
    assert attest_resp.status_code == 200
    assert attest_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    policy_resp = client.post(
        "/api/enterprise/policy/evaluate",
        json={
            "principal": "operator:tester@example.com",
            "action": "investigate",
            "targets": ["host:all"],
            "trust_state": "trusted",
            "role": "operator",
        },
    )
    assert policy_resp.status_code == 200
    assert policy_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    token_resp = client.post(
        "/api/enterprise/token/issue",
        json={
            "principal": "operator:tester@example.com",
            "principal_identity": "spiffe://metatron/operator/tester",
            "action": "investigate",
            "targets": ["host:all"],
            "ttl_seconds": 300,
            "max_uses": 1,
        },
    )
    assert token_resp.status_code == 200
    assert token_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    execute_resp = client.post(
        "/api/enterprise/tools/execute",
        json={
            "tool_id": "process.list",
            "parameters": {"host": "node-1"},
            "token_id": "token-1",
            "trust_state": "trusted",
        },
    )
    assert execute_resp.status_code == 200
    assert execute_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    event_resp = client.post(
        "/api/enterprise/telemetry/event",
        json={"event_type": "alert", "severity": "high", "data": {"k": "v"}},
    )
    assert event_resp.status_code == 200
    assert event_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    audit_resp = client.post(
        "/api/enterprise/telemetry/audit",
        json={
            "principal": "operator:tester@example.com",
            "principal_trust_state": "trusted",
            "action": "contain",
            "targets": ["host:all"],
        },
    )
    assert audit_resp.status_code == 200
    assert audit_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION
