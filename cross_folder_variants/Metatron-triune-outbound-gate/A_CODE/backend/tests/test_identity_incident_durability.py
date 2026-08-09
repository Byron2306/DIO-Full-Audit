"""Durability tests for identity incident status persistence transitions."""

import asyncio
import importlib.util
import sys
import types
from copy import deepcopy
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "backend" / "routers"


def _load_identity_module():
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(ROOT / "backend")]
    sys.modules.setdefault("backend", backend_pkg)

    routers_pkg = types.ModuleType("backend.routers")
    routers_pkg.__path__ = [str(ROUTERS_DIR)]
    sys.modules.setdefault("backend.routers", routers_pkg)

    dependencies_stub = types.ModuleType("backend.routers.dependencies")
    dependencies_stub._db = None
    dependencies_stub.get_db = lambda: dependencies_stub._db
    dependencies_stub.db = None
    dependencies_stub.logger = SimpleNamespace(debug=lambda *_a, **_k: None, info=lambda *_a, **_k: None, warning=lambda *_a, **_k: None, error=lambda *_a, **_k: None)

    async def _fake_get_current_user():
        return {"email": "tester@example.com", "role": "admin"}

    def _fake_check_permission(_permission):
        async def _dep():
            return {"email": "tester@example.com", "role": "admin"}

        return _dep

    dependencies_stub.get_current_user = _fake_get_current_user
    dependencies_stub.check_permission = _fake_check_permission
    sys.modules.setdefault("backend.routers.dependencies", dependencies_stub)

    module_path = ROUTERS_DIR / "identity.py"
    spec = importlib.util.spec_from_file_location("backend.routers.identity", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.routers.identity")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.routers.identity"] = module
    spec.loader.exec_module(module)
    return module, dependencies_stub

identity, deps = _load_identity_module()


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs or []

    @classmethod
    def _matches(cls, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(doc, option) for option in expected or []):
                    return False
                continue
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if actual not in expected["$in"]:
                        return False
                elif "$exists" in expected:
                    exists = key in doc
                    if exists != bool(expected["$exists"]):
                        return False
                else:
                    return False
            elif actual != expected:
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

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        matched = 0
        modified = 0
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                matched += 1
                next_doc = deepcopy(doc)
                if "$set" in update:
                    next_doc.update(deepcopy(update["$set"]))
                if "$setOnInsert" in update and matched == 0:
                    for key, value in update["$setOnInsert"].items():
                        next_doc.setdefault(key, deepcopy(value))
                if "$inc" in update:
                    for key, delta in update["$inc"].items():
                        next_doc[key] = int(next_doc.get(key) or 0) + int(delta)
                if "$push" in update:
                    for key, value in update["$push"].items():
                        arr = list(next_doc.get(key) or [])
                        arr.append(deepcopy(value))
                        next_doc[key] = arr
                self.docs[idx] = next_doc
                modified += 1
                break
        if matched == 0 and upsert:
            doc = {}
            if "$set" in update:
                doc.update(deepcopy(update["$set"]))
            if "$setOnInsert" in update:
                for key, value in update["$setOnInsert"].items():
                    doc.setdefault(key, deepcopy(value))
            self.docs.append(doc)
            matched = 1
            modified = 1
        return SimpleNamespace(matched_count=matched, modified_count=modified)

    def find(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        matched = [deepcopy(d) for d in self.docs if self._matches(d, query)]
        if projection:
            include_keys = {k for k, v in projection.items() if v}
            if include_keys:
                matched = [{k: v for k, v in d.items() if k in include_keys} for d in matched]
        class _Cursor:
            def __init__(self, docs):
                self.docs = docs
            async def to_list(self, length: int):
                return self.docs[:length]
        return _Cursor(matched)


class FakeDB:
    def __init__(self, incidents: Optional[List[Dict[str, Any]]] = None):
        self.identity_incidents = FakeCollection(incidents)
    def __getitem__(self, name: str):
        return getattr(self, name)


def _set_db(fake_db: FakeDB):
    deps._db = fake_db
    identity.get_db = lambda: fake_db


def test_persist_identity_incidents_initializes_state_fields():
    fake_db = FakeDB(incidents=[])
    _set_db(fake_db)
    threat = {
        "id": "incident-1",
        "attack_type": "kerberoasting",
        "severity": "high",
        "status": "active",
        "description": "Kerberoasting detected",
        "evidence": {"source_user": "alice"},
        "timestamp": "2026-03-07T00:00:00+00:00",
    }
    asyncio.run(identity._persist_identity_incidents([threat]))
    doc = asyncio.run(fake_db.identity_incidents.find_one({"id": "incident-1"}))
    assert doc is not None
    assert doc["status"] == "active"
    assert doc["state_version"] == 1
    transitions = doc.get("state_transition_log") or []
    assert len(transitions) == 1
    assert transitions[0]["to_status"] == "active"


def test_transition_incident_status_rejects_stale_state_version():
    fake_db = FakeDB(incidents=[{
        "id": "incident-2",
        "status": "active",
        "state_version": 3,
        "state_transition_log": [{"to_status": "active"}],
    }])
    _set_db(fake_db)
    transitioned = asyncio.run(identity._transition_incident_status(
        "incident-2",
        expected_statuses=["active"],
        next_status="resolved",
        actor="tester",
        reason="resolve",
        expected_state_version=2,
    ))
    assert transitioned is False


def test_update_identity_incident_status_persists_resolved_transition():
    fake_db = FakeDB(incidents=[{
        "id": "incident-3",
        "status": "active",
        "state_version": 1,
        "state_transition_log": [{
            "from_status": None,
            "to_status": "active",
            "actor": "system:identity",
            "reason": "incident discovered by identity engine",
        }],
        "evidence": {"source_user": "bob"},
    }])
    _set_db(fake_db)
    response = asyncio.run(identity.update_identity_incident_status(
        "incident-3",
        identity.IncidentStatusUpdate(
            status="resolved",
            reason="manually verified",
            updated_by="analyst-1",
        ),
    ))
    assert response["status"] == "resolved"
    doc = asyncio.run(fake_db.identity_incidents.find_one({"id": "incident-3"}))
    assert doc is not None
    assert doc["status"] == "resolved"
    assert doc["state_version"] == 2
    assert (doc.get("evidence") or {}).get("resolution_note") == "manually verified"
    transitions = doc.get("state_transition_log") or []
    assert transitions[-1]["from_status"] == "active"
    assert transitions[-1]["to_status"] == "resolved"


def test_update_identity_incident_status_rejects_terminal_transitions():
    fake_db = FakeDB(incidents=[{
        "id": "incident-4",
        "status": "resolved",
        "state_version": 2,
        "state_transition_log": [
            {"to_status": "active"},
            {"to_status": "resolved"},
        ],
        "evidence": {"source_user": "eve"},
    }])
    _set_db(fake_db)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(identity.update_identity_incident_status(
            "incident-4",
            identity.IncidentStatusUpdate(
                status="suppressed",
                reason="noisy",
                updated_by="analyst-2",
            ),
        ))
    assert exc.value.status_code == 409
    assert "terminal" in str(exc.value.detail).lower()
