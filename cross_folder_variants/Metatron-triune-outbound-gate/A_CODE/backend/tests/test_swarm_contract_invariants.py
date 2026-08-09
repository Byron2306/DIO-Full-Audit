"""Contract assurance tests for swarm control-plane routes."""

import importlib.util
import sys
import types
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "backend" / "routers"

EXPECTED_CONTRACT_VERSION = "2026-03-07.1"


def _load_swarm_module():
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
    dependencies_stub.get_db = lambda: None
    dependencies_stub.logger = SimpleNamespace(debug=lambda *_a, **_k: None, info=lambda *_a, **_k: None, warning=lambda *_a, **_k: None, error=lambda *_a, **_k: None)
    sys.modules.setdefault("backend.routers.dependencies", dependencies_stub)

    module_path = ROUTERS_DIR / "swarm.py"
    spec = importlib.util.spec_from_file_location("backend.routers.swarm", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.routers.swarm")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.routers.swarm"] = module
    spec.loader.exec_module(module)
    return module, dependencies_stub


swarm, deps = _load_swarm_module()


class FakeCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs

    def sort(self, field: str, direction: int):
        reverse = int(direction) < 0
        self.docs = sorted(self.docs, key=lambda d: d.get(field, ""), reverse=reverse)
        return self

    def limit(self, count: int):
        self.docs = self.docs[:count]
        return self

    async def to_list(self, count: int):
        return deepcopy(self.docs[:count])


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs or []

    @staticmethod
    def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if isinstance(expected, dict):
                if "$in" in expected:
                    if doc.get(key) not in expected["$in"]:
                        return False
                else:
                    return False
            elif doc.get(key) != expected:
                return False
        return True

    async def find_one(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        for doc in self.docs:
            if self._matches(doc, query):
                found = deepcopy(doc)
                if projection:
                    include_keys = {k for k, v in projection.items() if v}
                    if include_keys:
                        found = {k: v for k, v in found.items() if k in include_keys}
                return found
        return None

    def find(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        matched = [d for d in self.docs if self._matches(d, query)]
        if projection:
            include_keys = {k for k, v in projection.items() if v}
            if include_keys:
                matched = [{k: v for k, v in d.items() if k in include_keys} for d in matched]
        return FakeCursor(deepcopy(matched))

    async def insert_one(self, doc: Dict[str, Any]):
        self.docs.append(deepcopy(doc))
        return SimpleNamespace(inserted_id=len(self.docs))

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                next_doc = deepcopy(doc)
                if "$set" in update:
                    next_doc.update(update["$set"])
                if "$inc" in update:
                    for key, delta in update["$inc"].items():
                        next_doc[key] = next_doc.get(key, 0) + delta
                self.docs[idx] = next_doc
                return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

        if upsert:
            next_doc = deepcopy(query)
            if "$setOnInsert" in update:
                next_doc.update(update["$setOnInsert"])
            if "$set" in update:
                next_doc.update(update["$set"])
            if "$inc" in update:
                for key, delta in update["$inc"].items():
                    next_doc[key] = next_doc.get(key, 0) + delta
            self.docs.append(next_doc)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=len(self.docs))

        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

    async def count_documents(self, query: Dict[str, Any]):
        return len([d for d in self.docs if self._matches(d, query)])


class FakeDB:
    def __init__(self):
        self.agents = FakeCollection([])
        self.agent_commands = FakeCollection([])
        self.network_scanners = FakeCollection([])
        self.discovered_devices = FakeCollection([
            {
                "ip_address": "10.0.0.10",
                "hostname": "workstation-1",
                "os_type": "linux",
                "deployable": True,
                "deployment_status": "discovered",
            }
        ])
        self.unified_agents = FakeCollection([])
        self.deployment_tasks = FakeCollection([])
        self.agent_telemetry = FakeCollection([])
        self.alerts = FakeCollection([])


def _install_aatl_stub():
    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []
    sys.modules.setdefault("services", services_pkg)

    aatl_mod = types.ModuleType("services.aatl")

    def _get_aatl_engine():
        return None

    aatl_mod.get_aatl_engine = _get_aatl_engine
    sys.modules["services.aatl"] = aatl_mod


def _install_agent_deployment_stub():
    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []
    sys.modules.setdefault("services", services_pkg)

    agent_deploy_mod = types.ModuleType("services.agent_deployment")

    class _FakeService:
        async def queue_deployment(self, **_kwargs):
            return SimpleNamespace(status="queued")

    def _get_deployment_service():
        return _FakeService()

    agent_deploy_mod.get_deployment_service = _get_deployment_service
    sys.modules["services.agent_deployment"] = agent_deploy_mod


def _build_client() -> TestClient:
    fake_db = FakeDB()
    swarm.db = fake_db
    deps.db = fake_db

    app = FastAPI()
    app.include_router(swarm.router, prefix="/api")
    return TestClient(app)


def test_contract_version_constant_is_pinned():
    assert swarm.SWARM_CONTROL_PLANE_CONTRACT_VERSION == EXPECTED_CONTRACT_VERSION


def test_control_plane_route_set_invariants():
    app = FastAPI()
    app.include_router(swarm.router, prefix="/api")

    route_methods = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
    }

    expected = {
        ("/api/swarm/agents/register", "POST"),
        ("/api/swarm/agents/{agent_id}/command", "POST"),
        ("/api/swarm/scanner/report", "POST"),
        ("/api/swarm/deploy", "POST"),
        ("/api/swarm/deploy/batch", "POST"),
        ("/api/swarm/telemetry/ingest", "POST"),
    }

    for pair in expected:
        assert pair in route_methods


def test_request_model_schema_invariants():
    registration_schema = swarm.AgentRegistrationRequest.model_json_schema()
    scanner_schema = swarm.ScannerReportRequest.model_json_schema()
    deploy_schema = swarm.DeployAgentRequest.model_json_schema()
    telemetry_schema = swarm.TelemetryIngestRequest.model_json_schema()

    assert "agent_id" in (registration_schema.get("required") or [])
    assert "hostname" in (registration_schema.get("required") or [])
    assert "os_type" in (registration_schema.get("required") or [])
    assert "version" in (registration_schema.get("required") or [])

    assert "scanner_id" in (scanner_schema.get("required") or [])
    assert "network" in (scanner_schema.get("required") or [])
    assert "scan_time" in (scanner_schema.get("required") or [])
    assert "devices" in (scanner_schema.get("required") or [])

    assert "device_ip" in (deploy_schema.get("required") or [])
    assert "events" in (telemetry_schema.get("required") or [])


def test_success_paths_emit_contract_version():
    _install_aatl_stub()
    _install_agent_deployment_stub()

    client = _build_client()

    register_resp = client.post(
        "/api/swarm/agents/register",
        json={
            "agent_id": "agent-1",
            "hostname": "node-1",
            "os_type": "linux",
            "version": "1.0.0",
        },
    )
    assert register_resp.status_code == 200
    assert register_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    command_resp = client.post(
        "/api/swarm/agents/agent-1/command",
        json={"type": "scan", "params": {"depth": "quick"}, "priority": "normal"},
    )
    assert command_resp.status_code == 200
    assert command_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    scanner_resp = client.post(
        "/api/swarm/scanner/report",
        json={
            "scanner_id": "scanner-1",
            "network": "10.0.0.0/24",
            "scan_time": "2026-03-07T00:00:00Z",
            "devices": [
                {
                    "ip_address": "10.0.0.20",
                    "hostname": "node-20",
                    "os": "linux",
                    "device_type": "server",
                    "deployable": True,
                }
            ],
            "auto_deploy_request": True,
        },
    )
    assert scanner_resp.status_code == 200
    assert scanner_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    deploy_resp = client.post(
        "/api/swarm/deploy",
        json={"device_ip": "10.0.0.10", "credentials": None},
    )
    assert deploy_resp.status_code == 200
    assert deploy_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    telemetry_empty_resp = client.post("/api/swarm/telemetry/ingest", json={"events": []})
    assert telemetry_empty_resp.status_code == 200
    assert telemetry_empty_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    telemetry_resp = client.post(
        "/api/swarm/telemetry/ingest",
        json={
            "events": [
                {
                    "event_type": "agent.heartbeat",
                    "severity": "info",
                    "agent_id": "agent-1",
                    "data": {"hostname": "node-1", "os": "linux", "version": "1.0.0"},
                }
            ]
        },
    )
    assert telemetry_resp.status_code == 200
    payload = telemetry_resp.json()
    assert payload.get("contract_version") == EXPECTED_CONTRACT_VERSION
    assert payload.get("ingested") == 1
