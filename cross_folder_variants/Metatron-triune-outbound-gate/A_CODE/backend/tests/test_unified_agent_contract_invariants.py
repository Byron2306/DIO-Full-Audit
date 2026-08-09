"""Contract assurance tests for unified EDM control-plane routes.

These tests enforce route, model, and response invariants so contract drift
is caught quickly in CI for fast-moving control-plane APIs.
"""

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


def _load_unified_agent_module():
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

    module_path = ROUTERS_DIR / "unified_agent.py"
    spec = importlib.util.spec_from_file_location("backend.routers.unified_agent", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.routers.unified_agent")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.routers.unified_agent"] = module
    spec.loader.exec_module(module)
    return module, dependencies_stub


ua, deps = _load_unified_agent_module()


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs or []

    @staticmethod
    def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$lt" in expected:
                    if actual is None or not (actual < expected["$lt"]):
                        return False
                elif "$in" in expected:
                    if actual not in expected["$in"]:
                        return False
                else:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None, sort: Optional[List] = None):
        matches = [d for d in self.docs if self._matches(d, query)]
        if not matches:
            return None

        if sort:
            field, direction = sort[0]
            reverse = int(direction) < 0
            matches = sorted(matches, key=lambda d: d.get(field, 0), reverse=reverse)

        doc = deepcopy(matches[0])
        if projection:
            include_keys = {k for k, v in projection.items() if v}
            if include_keys:
                doc = {k: v for k, v in doc.items() if k in include_keys}
        return doc

    async def insert_one(self, doc: Dict[str, Any]):
        self.docs.append(deepcopy(doc))
        return SimpleNamespace(inserted_id=len(self.docs))

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        matched = 0
        modified = 0
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                matched += 1
                if "$set" in update:
                    self.docs[idx] = {**doc, **update["$set"]}
                    modified += 1
                break
        return SimpleNamespace(matched_count=matched, modified_count=modified)

    async def create_index(self, *args, **kwargs):
        return None


class FakeDB:
    def __init__(self, dataset_docs: Optional[List[Dict[str, Any]]] = None):
        self._collections = {
            ua.EDM_DATASET_COLLECTION: FakeCollection(dataset_docs),
            ua.EDM_ROLLOUT_COLLECTION: FakeCollection([]),
            ua.EDM_HITS_COLLECTION: FakeCollection([]),
        }

    def __getitem__(self, key: str):
        return self._collections[key]


async def _noop_dispatch(*args, **kwargs):
    return {
        "matched_agents": 0,
        "dispatched": 0,
        "sent": 0,
        "queued": 0,
        "results": [],
    }


async def _noop_indexes():
    return None


def _make_resolve_targets(resolved_agents: Optional[List[Dict[str, Any]]]):
    async def _resolver(_targets):
        return deepcopy(resolved_agents or [])

    return _resolver


def _default_valid_dataset() -> Dict[str, Any]:
    return {
        "datasets": [
            {
                "dataset_id": "employee-pii",
                "precision": {
                    "min_confidence": 0.95,
                    "allowed_candidate_types": ["line", "delimited_bundle", "delimited_window_4"],
                },
                "records": [
                    {"record_id": "r1", "email": "alice@example.com", "name": "Alice"},
                    {"record_id": "r2", "email": "bob@example.com", "name": "Bob"},
                ],
            }
        ]
    }


def _build_client(dataset_docs: Optional[List[Dict[str, Any]]] = None, resolved_agents: Optional[List[Dict[str, Any]]] = None) -> TestClient:
    fake_db = FakeDB(dataset_docs=dataset_docs)

    ua.db = fake_db
    deps.db = fake_db
    ua._dispatch_edm_dataset_to_targets = _noop_dispatch
    ua._ensure_edm_indexes = _noop_indexes
    ua._resolve_edm_targets = _make_resolve_targets(resolved_agents)

    app = FastAPI()
    app.include_router(ua.router, prefix="/api")
    app.dependency_overrides[ua.get_current_user] = lambda: {
        "email": "tester@example.com",
        "role": "admin",
    }
    return TestClient(app)


def test_contract_version_constant_is_pinned():
    assert ua.EDM_CONTROL_PLANE_CONTRACT_VERSION == EXPECTED_CONTRACT_VERSION


def test_control_plane_route_set_invariants():
    app = FastAPI()
    app.include_router(ua.router, prefix="/api")

    route_methods = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
    }

    expected = {
        ("/api/unified/edm/datasets/{dataset_id}/versions", "POST"),
        ("/api/unified/edm/datasets/{dataset_id}/versions/{version}/publish", "POST"),
        ("/api/unified/edm/datasets/{dataset_id}/rollback", "POST"),
        ("/api/unified/edm/rollouts/start", "POST"),
    }

    for pair in expected:
        assert pair in route_methods


def test_request_model_schema_invariants():
    create_schema = ua.EDMDatasetVersionCreateModel.model_json_schema()
    rollback_schema = ua.EDMDatasetRollbackModel.model_json_schema()
    rollout_schema = ua.EDMRolloutStartModel.model_json_schema()

    assert "dataset" in (create_schema.get("required") or [])
    assert "target_version" in (rollback_schema.get("required") or [])
    assert "dataset_id" in (rollout_schema.get("required") or [])
    assert "target_version" in (rollout_schema.get("required") or [])


def test_invalid_create_includes_contract_validation_shape():
    client = _build_client()

    response = client.post(
        "/api/unified/edm/datasets/demo/versions",
        json={"dataset": {"foo": "bar"}, "note": "invalid"},
    )

    assert response.status_code == 422
    detail = response.json().get("detail", {})
    validation = detail.get("validation", {})
    assert detail.get("context") == "dataset version creation"
    assert isinstance(validation.get("schema_errors"), list)
    assert validation.get("quality_gate_passed") is False


def test_success_paths_emit_contract_version():
    valid = _default_valid_dataset()

    create_client = _build_client()
    create_resp = create_client.post(
        "/api/unified/edm/datasets/demo/versions",
        json={"dataset": valid, "note": "valid"},
    )
    assert create_resp.status_code == 200
    assert create_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    docs = [
        {
            "dataset_id": "demo",
            "version": 1,
            "dataset": valid,
            "checksum": "abc",
            "signature": "sig",
            "published_at": "2026-03-07T00:00:00Z",
        }
    ]
    publish_client = _build_client(dataset_docs=docs)
    publish_resp = publish_client.post(
        "/api/unified/edm/datasets/demo/versions/1/publish",
        json={},
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    rollback_client = _build_client(dataset_docs=docs)
    rollback_resp = rollback_client.post(
        "/api/unified/edm/datasets/demo/rollback",
        json={"target_version": 1, "publish": True},
    )
    assert rollback_resp.status_code == 200
    assert rollback_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION

    rollout_client = _build_client(dataset_docs=docs, resolved_agents=[{"agent_id": "agent-1", "platform": "linux", "status": "online"}])
    rollout_resp = rollout_client.post(
        "/api/unified/edm/rollouts/start",
        json={"dataset_id": "demo", "target_version": 1},
    )
    assert rollout_resp.status_code == 200
    assert rollout_resp.json().get("contract_version") == EXPECTED_CONTRACT_VERSION
