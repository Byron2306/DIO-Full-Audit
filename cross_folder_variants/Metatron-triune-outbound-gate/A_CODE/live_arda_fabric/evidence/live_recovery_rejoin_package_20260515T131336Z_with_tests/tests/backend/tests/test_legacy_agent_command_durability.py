"""Durability tests for legacy /api/agent-commands lifecycle."""

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


def _load_agent_commands_module():
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
    dependencies_stub.get_db = lambda: None
    dependencies_stub.db = None
    dependencies_stub.logger = SimpleNamespace(debug=lambda *_a, **_k: None)
    sys.modules.setdefault("backend.routers.dependencies", dependencies_stub)

    module_path = ROUTERS_DIR / "agent_commands.py"
    spec = importlib.util.spec_from_file_location("backend.routers.agent_commands", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.routers.agent_commands")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.routers.agent_commands"] = module
    spec.loader.exec_module(module)
    return module


ac = _load_agent_commands_module()


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs or []

    @staticmethod
    def _match_condition(actual: Any, expected: Any) -> bool:
        if isinstance(expected, dict):
            if "$in" in expected:
                return actual in expected["$in"]
            if "$exists" in expected:
                exists = actual is not None
                return exists == bool(expected["$exists"])
            return False
        return actual == expected

    @classmethod
    def _matches(cls, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                options = expected or []
                if not any(cls._matches(doc, opt) for opt in options):
                    return False
                continue
            if key not in doc:
                actual = None
            else:
                actual = doc.get(key)
            if not cls._match_condition(actual, expected):
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

        if projection:
            include_keys = {k for k, v in projection.items() if v}
            if include_keys:
                matched = [{k: v for k, v in d.items() if k in include_keys} for d in matched]

        class _Cursor:
            def __init__(self, docs):
                self.docs = docs

            def sort(self, field: str, direction: int):
                reverse = int(direction) < 0
                self.docs = sorted(self.docs, key=lambda d: d.get(field, ""), reverse=reverse)
                return self

            async def to_list(self, length: int):
                return self.docs[:length]

        return _Cursor(matched)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
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
            self.docs.append(doc)
            matched = 1
            modified = 1
        return SimpleNamespace(matched_count=matched, modified_count=modified)


class FakeDB:
    def __init__(self, command_docs: Optional[List[Dict[str, Any]]] = None):
        self.agent_commands = FakeCollection(command_docs)
        self.command_queue = FakeCollection([])
        self.connected_agents = FakeCollection([])
        self.agent_scan_results = FakeCollection([])
        self.agent_alerts = FakeCollection([])
        self.agent_status = FakeCollection([])


def _set_db(fake_db: FakeDB):
    ac.get_db = lambda: fake_db


def test_create_command_sets_state_version_and_transition_log():
    fake_db = FakeDB([])
    _set_db(fake_db)

    payload = ac.CommandRequest(
        agent_id="agent-1",
        command_type="full_scan",
        parameters={"scan_types": ["process"]},
        priority="high",
    )
    response = asyncio.run(ac.create_command(payload, current_user={"email": "admin@example.com"}))

    doc = asyncio.run(fake_db.agent_commands.find_one({"command_id": response["command_id"]}))
    assert doc is not None
    assert doc["status"] == "pending_approval"
    assert doc["state_version"] == 1
    assert len(doc.get("state_transition_log") or []) == 1
    assert doc["state_transition_log"][0]["to_status"] == "pending_approval"


def test_approve_command_uses_guarded_transitions_to_queue():
    fake_db = FakeDB(
        [
            {
                "command_id": "cmd-1",
                "agent_id": "agent-1",
                "command_type": "full_scan",
                "parameters": {},
                "status": "pending_approval",
                "state_version": 1,
                "state_transition_log": [{"to_status": "pending_approval"}],
            }
        ]
    )
    _set_db(fake_db)
    ac.connected_agents.clear()

    response = asyncio.run(
        ac.approve_command(
            "cmd-1",
            ac.CommandApproval(approved=True, notes="LGTM"),
            current_user={"email": "admin@example.com"},
        )
    )

    assert response["status"] == "approved"
    doc = asyncio.run(fake_db.agent_commands.find_one({"command_id": "cmd-1"}))
    assert doc["status"] == "queued_for_pickup"
    assert doc["state_version"] == 3
    transitions = doc.get("state_transition_log") or []
    assert transitions[-2]["to_status"] == "approved"
    assert transitions[-1]["to_status"] == "queued_for_pickup"
    queued = asyncio.run(fake_db.command_queue.find_one({"command_id": "cmd-1"}))
    assert queued is not None
    assert queued["status"] == "pending"


def test_report_command_result_rejects_duplicate_terminal_update():
    fake_db = FakeDB(
        [
            {
                "command_id": "cmd-terminal",
                "status": "completed",
                "state_version": 5,
                "state_transition_log": [{"to_status": "completed"}],
            }
        ]
    )
    _set_db(fake_db)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ac.report_command_result(
                "cmd-terminal",
                result={"success": True, "detail": "done"},
                current_user={"email": "agent@example.com"},
            )
        )

    assert exc.value.status_code == 409
    assert "already terminal" in str(exc.value.detail)


def test_connection_session_rollover_is_monotonic_and_logged():
    fake_db = FakeDB([])
    fake_db.connected_agents = FakeCollection(
        [
            {
                "agent_id": "agent-1",
                "status": "connected",
                "session_id": "sess-old",
                "connection_state_version": 3,
                "connection_transition_log": [{"to_status": "connected", "session_id": "sess-old"}],
            }
        ]
    )

    transitioned = asyncio.run(
        ac._register_connected_session(fake_db, agent_id="agent-1", session_id="sess-new")
    )
    assert transitioned is True

    doc = asyncio.run(fake_db.connected_agents.find_one({"agent_id": "agent-1"}))
    assert doc is not None
    assert doc["status"] == "connected"
    assert doc["session_id"] == "sess-new"
    assert doc["connection_state_version"] == 4
    transitions = doc.get("connection_transition_log") or []
    assert transitions[-1]["from_status"] == "connected"
    assert transitions[-1]["to_status"] == "connected"
    assert transitions[-1]["session_id"] == "sess-new"
    assert transitions[-1].get("metadata", {}).get("previous_session_id") == "sess-old"


def test_stale_disconnect_is_rejected_for_rotated_session():
    fake_db = FakeDB([])
    fake_db.connected_agents = FakeCollection(
        [
            {
                "agent_id": "agent-1",
                "status": "connected",
                "session_id": "sess-current",
                "connection_state_version": 5,
                "connection_transition_log": [{"to_status": "connected", "session_id": "sess-current"}],
            }
        ]
    )

    disconnected = asyncio.run(
        ac._mark_session_disconnected(
            fake_db,
            agent_id="agent-1",
            session_id="sess-stale",
        )
    )
    assert disconnected is False

    doc = asyncio.run(fake_db.connected_agents.find_one({"agent_id": "agent-1"}))
    assert doc is not None
    assert doc["status"] == "connected"
    assert doc["session_id"] == "sess-current"
    assert doc["connection_state_version"] == 5


def test_stale_heartbeat_is_rejected_for_rotated_session():
    fake_db = FakeDB([])
    fake_db.connected_agents = FakeCollection(
        [
            {
                "agent_id": "agent-1",
                "status": "connected",
                "session_id": "sess-current",
                "connection_state_version": 7,
                "connection_transition_log": [{"to_status": "connected", "session_id": "sess-current"}],
            }
        ]
    )

    updated = asyncio.run(
        ac._record_session_heartbeat(
            fake_db,
            agent_id="agent-1",
            session_id="sess-stale",
        )
    )
    assert updated is False

    doc = asyncio.run(fake_db.connected_agents.find_one({"agent_id": "agent-1"}))
    assert doc is not None
    assert doc["status"] == "connected"
    assert doc["session_id"] == "sess-current"
    assert doc["connection_state_version"] == 7


def test_active_heartbeat_advances_connection_version_and_log():
    fake_db = FakeDB([])
    fake_db.connected_agents = FakeCollection(
        [
            {
                "agent_id": "agent-1",
                "status": "connected",
                "session_id": "sess-1",
                "connection_state_version": 2,
                "connection_transition_log": [{"to_status": "connected", "session_id": "sess-1"}],
            }
        ]
    )

    updated = asyncio.run(
        ac._record_session_heartbeat(
            fake_db,
            agent_id="agent-1",
            session_id="sess-1",
        )
    )
    assert updated is True

    doc = asyncio.run(fake_db.connected_agents.find_one({"agent_id": "agent-1"}))
    assert doc is not None
    assert doc["connection_state_version"] == 3
    assert doc["status"] == "connected"
    assert doc["session_id"] == "sess-1"
    transitions = doc.get("connection_transition_log") or []
    assert transitions[-1]["to_status"] == "connected"
    assert transitions[-1]["session_id"] == "sess-1"
    assert transitions[-1]["reason"] == "websocket heartbeat"


def test_stale_agent_status_snapshot_is_rejected_for_rotated_session():
    fake_db = FakeDB([])
    fake_db.agent_status = FakeCollection(
        [
            {
                "agent_id": "agent-1",
                "status": "snapshot",
                "last_session_id": "sess-current",
                "state_version": 4,
                "state_transition_log": [{"to_status": "snapshot", "session_id": "sess-current"}],
                "hostname": "host-current",
            }
        ]
    )

    updated = asyncio.run(
        ac._record_agent_status_snapshot(
            fake_db,
            agent_id="agent-1",
            session_id="sess-stale",
            snapshot={
                "hostname": "host-stale",
                "os": "linux",
                "ip_address": "10.0.0.20",
                "security_status": {"risk": "high"},
                "last_scan": None,
            },
        )
    )
    assert updated is False

    doc = asyncio.run(fake_db.agent_status.find_one({"agent_id": "agent-1"}))
    assert doc is not None
    assert doc["last_session_id"] == "sess-current"
    assert doc["hostname"] == "host-current"
    assert doc["state_version"] == 4


def test_active_agent_status_snapshot_advances_version_and_log():
    fake_db = FakeDB([])
    fake_db.agent_status = FakeCollection(
        [
            {
                "agent_id": "agent-1",
                "status": "snapshot",
                "last_session_id": "sess-1",
                "state_version": 2,
                "state_transition_log": [{"to_status": "snapshot", "session_id": "sess-1"}],
                "hostname": "old-host",
            }
        ]
    )

    updated = asyncio.run(
        ac._record_agent_status_snapshot(
            fake_db,
            agent_id="agent-1",
            session_id="sess-1",
            snapshot={
                "hostname": "new-host",
                "os": "linux",
                "ip_address": "10.0.0.25",
                "security_status": {"risk": "low"},
                "last_scan": "2026-03-07T00:00:00+00:00",
            },
        )
    )
    assert updated is True

    doc = asyncio.run(fake_db.agent_status.find_one({"agent_id": "agent-1"}))
    assert doc is not None
    assert doc["hostname"] == "new-host"
    assert doc["last_session_id"] == "sess-1"
    assert doc["state_version"] == 3
    transitions = doc.get("state_transition_log") or []
    assert transitions[-1]["from_status"] == "snapshot"
    assert transitions[-1]["to_status"] == "snapshot"
    assert transitions[-1]["session_id"] == "sess-1"
