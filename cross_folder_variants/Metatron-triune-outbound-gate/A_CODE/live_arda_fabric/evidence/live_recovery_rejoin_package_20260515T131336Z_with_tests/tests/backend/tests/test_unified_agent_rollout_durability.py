"""Durability tests for EDM rollout governance state transitions.

These tests enforce restart/scale-safe behavior by asserting rollout transitions
use optimistic concurrency guards and reject stale concurrent updates.
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
    def __init__(
        self,
        docs: Optional[List[Dict[str, Any]]] = None,
        fail_stage_transition_once: bool = False,
    ):
        self.docs = docs or []
        self.fail_stage_transition_once = fail_stage_transition_once

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
        # Simulate a stale-write race exactly once for stage transitions.
        if self.fail_stage_transition_once and "stage_index" in query and "status" in query:
            self.fail_stage_transition_once = False
            return SimpleNamespace(matched_count=0, modified_count=0)

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

    async def create_index(self, *_args, **_kwargs):
        return None


class FakeDB:
    def __init__(
        self,
        dataset_docs: Optional[List[Dict[str, Any]]] = None,
        rollout_docs: Optional[List[Dict[str, Any]]] = None,
        fail_stage_transition_once: bool = False,
    ):
        self._collections = {
            ua.EDM_DATASET_COLLECTION: FakeCollection(dataset_docs),
            ua.EDM_HITS_COLLECTION: FakeCollection([]),
            ua.EDM_ROLLOUT_COLLECTION: FakeCollection(
                rollout_docs,
                fail_stage_transition_once=fail_stage_transition_once,
            ),
        }

    def __getitem__(self, key: str):
        return self._collections[key]


async def _noop_dispatch(*_args, **_kwargs):
    return {
        "matched_agents": 0,
        "dispatched": 0,
        "sent": 0,
        "queued": 0,
        "results": [],
    }


async def _noop_indexes():
    return None


def _build_client(
    dataset_docs: Optional[List[Dict[str, Any]]] = None,
    rollout_docs: Optional[List[Dict[str, Any]]] = None,
    fail_stage_transition_once: bool = False,
) -> TestClient:
    fake_db = FakeDB(
        dataset_docs=dataset_docs,
        rollout_docs=rollout_docs,
        fail_stage_transition_once=fail_stage_transition_once,
    )
    ua.db = fake_db
    deps.db = fake_db
    ua._dispatch_edm_dataset_to_targets = _noop_dispatch
    ua._ensure_edm_indexes = _noop_indexes

    async def _no_spike_readiness(_rollout):
        return {
            "has_spike": False,
            "cohort": {"rate_per_agent_min": 0.0},
            "control": {"rate_per_agent_min": 0.0},
            "threshold": {"rate_per_agent_min": 0.1},
        }

    ua._compute_rollout_readiness = _no_spike_readiness

    app = FastAPI()
    app.include_router(ua.router, prefix="/api")
    app.dependency_overrides[ua.get_current_user] = lambda: {
        "email": "tester@example.com",
        "role": "admin",
    }
    return TestClient(app)


def _valid_dataset() -> Dict[str, Any]:
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


def _base_rollout_doc(status: str = "active") -> Dict[str, Any]:
    return {
        "rollout_id": "edm-rollout-abc",
        "dataset_id": "demo",
        "target_version": 2,
        "previous_version": 1,
        "status": status,
        "stages": [5, 25, 100],
        "stage_index": 0,
        "eligible_agent_ids": ["agent-1", "agent-2", "agent-3"],
        "applied_agent_ids": ["agent-1"],
        "policy": {"auto_rollback": True},
        "state_version": 1,
        "state_transition_log": [],
        "stage_history": [],
        "updated_at": "2026-03-07T00:00:00Z",
    }


def test_advance_rollout_rejects_stale_state_transition_conflict():
    dataset_docs = [
        {
            "dataset_id": "demo",
            "version": 2,
            "dataset": _valid_dataset(),
            "checksum": "abc",
            "signature": "sig",
            "published_at": "2026-03-07T00:00:00Z",
        }
    ]
    client = _build_client(
        dataset_docs=dataset_docs,
        rollout_docs=[_base_rollout_doc(status="active")],
        fail_stage_transition_once=True,
    )

    resp = client.post("/api/unified/edm/rollouts/edm-rollout-abc/advance", json={})

    assert resp.status_code == 409
    assert "changed concurrently" in str(resp.json().get("detail", ""))


def test_manual_rollback_is_single_claim_operation():
    dataset_docs = [
        {
            "dataset_id": "demo",
            "version": 1,
            "dataset": _valid_dataset(),
            "checksum": "abc",
            "signature": "sig",
            "published_at": "2026-03-07T00:00:00Z",
        }
    ]
    client = _build_client(
        dataset_docs=dataset_docs,
        rollout_docs=[_base_rollout_doc(status="active")],
    )

    first = client.post(
        "/api/unified/edm/rollouts/edm-rollout-abc/rollback",
        json={"rollback_version": 1, "reason": "manual"},
    )
    assert first.status_code == 200
    assert first.json().get("rolled_back") is True

    rollout = client.get("/api/unified/edm/rollouts/edm-rollout-abc")
    assert rollout.status_code == 200
    transition_log = rollout.json().get("state_transition_log") or []
    assert any(entry.get("to_status") == "rolling_back" for entry in transition_log)
    assert any(entry.get("to_status") == "rolled_back" for entry in transition_log)

    second = client.post(
        "/api/unified/edm/rollouts/edm-rollout-abc/rollback",
        json={"rollback_version": 1, "reason": "manual-again"},
    )
    assert second.status_code == 409
    assert "changed concurrently" in str(second.json().get("detail", ""))


def test_manual_rollback_rejects_non_transitionable_state():
    dataset_docs = [
        {
            "dataset_id": "demo",
            "version": 1,
            "dataset": _valid_dataset(),
            "checksum": "abc",
            "signature": "sig",
            "published_at": "2026-03-07T00:00:00Z",
        }
    ]
    client = _build_client(
        dataset_docs=dataset_docs,
        rollout_docs=[_base_rollout_doc(status="rolling_back")],
    )

    resp = client.post(
        "/api/unified/edm/rollouts/edm-rollout-abc/rollback",
        json={"rollback_version": 1, "reason": "manual"},
    )

    assert resp.status_code == 409
    assert "changed concurrently" in str(resp.json().get("detail", ""))
