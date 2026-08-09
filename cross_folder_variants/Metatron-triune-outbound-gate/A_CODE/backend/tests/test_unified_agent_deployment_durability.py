"""Durability tests for unified deployment control-state transitions."""

import asyncio
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
                if "$in" in expected:
                    if actual not in expected["$in"]:
                        return False
                else:
                    return False
            elif actual != expected:
                return False
        return True

    async def insert_one(self, doc: Dict[str, Any]):
        self.docs.append(deepcopy(doc))
        return SimpleNamespace(inserted_id=len(self.docs))

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
        matched = [deepcopy(d) for d in self.docs if self._matches(d, query)]

        class _Cursor:
            def __init__(self, docs):
                self.docs = docs

            async def to_list(self, _length):
                out = self.docs
                if projection:
                    include_keys = {k for k, v in projection.items() if v}
                    if include_keys:
                        out = [{k: v for k, v in d.items() if k in include_keys} for d in out]
                return out

        return _Cursor(matched)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        matched = 0
        modified = 0
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                matched += 1
                next_doc = deepcopy(doc)
                if "$set" in update:
                    next_doc.update(update["$set"])
                if "$inc" in update:
                    for key, delta in update["$inc"].items():
                        next_doc[key] = next_doc.get(key, 0) + delta
                if "$push" in update:
                    for key, value in update["$push"].items():
                        arr = list(next_doc.get(key) or [])
                        arr.append(deepcopy(value))
                        next_doc[key] = arr
                self.docs[idx] = next_doc
                modified += 1
                break
        return SimpleNamespace(matched_count=matched, modified_count=modified)


class FakeDB:
    def __init__(
        self,
        deployments: Optional[List[Dict[str, Any]]] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
    ):
        self.unified_deployments = FakeCollection(deployments)
        self.deployment_tasks = FakeCollection(tasks)


def _set_db(db_obj: FakeDB):
    ua.db = db_obj
    deps.db = db_obj


def test_create_deployment_initializes_state_version(monkeypatch):
    fake_db = FakeDB(deployments=[], tasks=[])
    _set_db(fake_db)

    async def _noop_process(_deployment_id, _deployment):
        return None

    monkeypatch.setattr(ua, "_process_deployment", _noop_process)

    app = FastAPI()
    app.include_router(ua.router, prefix="/api")
    app.dependency_overrides[ua.get_current_user] = lambda: {
        "email": "tester@example.com",
        "role": "admin",
    }

    client = TestClient(app)
    resp = client.post(
        "/api/unified/deployments",
        json={"target_platform": "linux", "target_ip": "10.0.0.10"},
    )

    assert resp.status_code == 200
    deployment_id = resp.json().get("deployment_id")
    doc = asyncio.run(fake_db.unified_deployments.find_one({"deployment_id": deployment_id}))
    assert doc is not None
    assert doc.get("state_version") == 1
    assert doc.get("status") == "pending"
    assert len(doc.get("state_transition_log") or []) == 1
    assert doc["state_transition_log"][0].get("to_status") == "pending"


def test_sync_does_not_downgrade_terminal_status():
    fake_db = FakeDB(
        deployments=[
            {
                "deployment_id": "dep-1",
                "deployment_task_id": "task-1",
                "status": "completed",
                "state_version": 7,
            }
        ],
        tasks=[
            {
                "task_id": "task-1",
                "status": "deploying",
                "simulated": False,
            }
        ],
    )
    _set_db(fake_db)

    asyncio.run(ua._sync_unified_deployment_status(fake_db.unified_deployments.docs[0]))

    doc = asyncio.run(fake_db.unified_deployments.find_one({"deployment_id": "dep-1"}))
    assert doc is not None
    assert doc.get("status") == "completed"
    assert doc.get("state_version") == 7


def test_sync_promotes_running_to_completed_with_state_version_increment():
    fake_db = FakeDB(
        deployments=[
            {
                "deployment_id": "dep-2",
                "deployment_task_id": "task-2",
                "status": "running",
                "state_version": 2,
            }
        ],
        tasks=[
            {
                "task_id": "task-2",
                "status": "deployed",
                "simulated": True,
            }
        ],
    )
    _set_db(fake_db)

    asyncio.run(ua._sync_unified_deployment_status(fake_db.unified_deployments.docs[0]))

    doc = asyncio.run(fake_db.unified_deployments.find_one({"deployment_id": "dep-2"}))
    assert doc is not None
    assert doc.get("status") == "completed"
    assert doc.get("state_version") == 3
    assert doc.get("simulated") is True
    assert doc["state_transition_log"][-1].get("to_status") == "completed"


def test_process_deployment_exits_if_already_claimed():
    fake_db = FakeDB(
        deployments=[
            {
                "deployment_id": "dep-3",
                "status": "processing",
                "state_version": 4,
            }
        ],
        tasks=[],
    )
    _set_db(fake_db)

    payload = ua.DeploymentRequestModel(target_platform="linux", target_ip="10.0.0.20")
    asyncio.run(ua._process_deployment("dep-3", payload))

    doc = asyncio.run(fake_db.unified_deployments.find_one({"deployment_id": "dep-3"}))
    assert doc is not None
    assert doc.get("status") == "processing"
    assert doc.get("state_version") == 4
