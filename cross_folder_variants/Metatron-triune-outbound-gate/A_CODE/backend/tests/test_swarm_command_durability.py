"""Durability tests for swarm command lifecycle transitions."""

import asyncio
import importlib.util
import sys
import types
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "backend" / "routers"


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

            def sort(self, field: str, direction: int):
                reverse = int(direction) < 0
                self.docs = sorted(self.docs, key=lambda d: d.get(field, ""), reverse=reverse)
                return self

            async def to_list(self, length: int):
                out = self.docs[:length]
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
    def __init__(self, command_docs: Optional[List[Dict[str, Any]]] = None):
        self.agent_commands = FakeCollection(command_docs)


def _set_db(fake_db: FakeDB):
    swarm.db = fake_db
    deps.db = fake_db


def test_send_command_initializes_state_version():
    fake_db = FakeDB(command_docs=[])
    _set_db(fake_db)

    response = asyncio.run(
        swarm.send_command_to_agent(
            "agent-1",
            swarm.AgentCommandRequest(type="scan", params={"scope": "quick"}, priority="normal"),
            current_user={"email": "tester@example.com", "role": "admin"},
        )
    )

    doc = asyncio.run(fake_db.agent_commands.find_one({"command_id": response["command_id"]}))
    assert doc is not None
    assert doc["status"] == "pending"
    assert doc["state_version"] == 1
    assert len(doc.get("state_transition_log") or []) == 1
    assert doc["state_transition_log"][0].get("to_status") == "pending"


def test_get_pending_commands_updates_only_pending_with_state_version():
    fake_db = FakeDB(
        command_docs=[
            {
                "command_id": "cmd-1",
                "agent_id": "agent-1",
                "status": "pending",
                "state_version": 1,
                "created_at": "2026-03-07T00:00:00+00:00",
            },
            {
                "command_id": "cmd-2",
                "agent_id": "agent-1",
                "status": "delivered",
                "state_version": 3,
                "created_at": "2026-03-07T00:00:01+00:00",
            },
        ]
    )
    _set_db(fake_db)

    response = asyncio.run(swarm.get_pending_commands("agent-1"))

    assert len(response["commands"]) == 1
    cmd1 = asyncio.run(fake_db.agent_commands.find_one({"command_id": "cmd-1"}))
    cmd2 = asyncio.run(fake_db.agent_commands.find_one({"command_id": "cmd-2"}))
    assert cmd1["status"] == "delivered"
    assert cmd1["state_version"] == 2
    assert cmd1["state_transition_log"][-1].get("from_status") == "pending"
    assert cmd1["state_transition_log"][-1].get("to_status") == "delivered"
    assert cmd2["status"] == "delivered"
    assert cmd2["state_version"] == 3


def test_acknowledge_command_conflicts_after_terminal_state():
    fake_db = FakeDB(
        command_docs=[
            {
                "command_id": "cmd-3",
                "agent_id": "agent-1",
                "status": "completed",
                "state_version": 7,
            }
        ]
    )
    _set_db(fake_db)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            swarm.acknowledge_command(
                "agent-1",
                "cmd-3",
                result={"success": True, "message": "already done"},
            )
        )

    assert exc.value.status_code == 409
    assert "already terminal" in str(exc.value.detail)
