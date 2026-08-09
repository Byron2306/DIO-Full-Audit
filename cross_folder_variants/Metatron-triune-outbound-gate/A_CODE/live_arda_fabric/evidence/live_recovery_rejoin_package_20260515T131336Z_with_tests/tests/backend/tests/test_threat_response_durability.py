"""Durability tests for threat response lifecycle transitions."""

import asyncio
import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
THREAT_RESPONSE_PATH = BACKEND_DIR / "threat_response.py"


class FakeCollection:
    def __init__(self):
        self.docs = []

    @staticmethod
    def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if doc.get(key) != expected:
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

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        matched = 0
        modified = 0

        for idx, doc in enumerate(self.docs):
            if not self._matches(doc, query):
                continue

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
    def __init__(self):
        self.response_history = FakeCollection()


def _load_module():
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    spec = importlib.util.spec_from_file_location("backend.threat_response", THREAT_RESPONSE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.threat_response")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.threat_response"] = module
    spec.loader.exec_module(module)
    return module


tr = _load_module()


def _success_result(action, message: str = "ok"):
    return tr.ResponseResult(
        action=action,
        status=tr.ResponseStatus.SUCCESS,
        message=message,
    )


def test_process_threat_persists_state_version_and_transition_log():
    fake_db = FakeDB()
    tr.response_engine.configure_db(fake_db)
    tr.response_engine.response_history = []
    tr.response_engine.attack_counter = {}

    tr.config.auto_block_enabled = True
    tr.config.critical_threat_threshold = 1
    tr.config.sms_alert_severity = []
    tr.config.openclaw_enabled = False

    async def _forensics(_context):
        return _success_result(tr.ResponseAction.COLLECT_FORENSICS, "forensics collected")

    async def _check_indicator(_itype, _value):
        return {"known": False, "data": {}}

    async def _share_indicator(_itype, _value, _threat_type, confidence: float = 0.8):
        return True

    async def _block_ip(_ip, reason: str = "", duration_hours: int = 24):
        return _success_result(tr.ResponseAction.BLOCK_IP, f"blocked: {reason}")

    tr.forensics.collect_incident_data = _forensics
    tr.threat_intel.check_indicator = _check_indicator
    tr.threat_intel.share_indicator = _share_indicator
    tr.firewall.block_ip = _block_ip

    context = tr.ThreatContext(
        threat_id="thrt-001",
        threat_type="intrusion",
        severity="high",
        source_ip="203.0.113.10",
    )

    results = asyncio.run(tr.response_engine.process_threat(context, auto_respond=True))

    assert len(results) >= 2
    assert len(fake_db.response_history.docs) == 1

    doc = fake_db.response_history.docs[0]
    assert doc["status"] == tr.ResponseStatus.SUCCESS.value
    assert doc["state_version"] == 3

    transition_log = doc.get("state_transition_log") or []
    assert len(transition_log) == 3
    assert transition_log[0].get("from_status") is None
    assert transition_log[0].get("to_status") == tr.ResponseStatus.PENDING.value
    assert transition_log[1].get("from_status") == tr.ResponseStatus.PENDING.value
    assert transition_log[1].get("to_status") == tr.ResponseStatus.EXECUTING.value
    assert transition_log[2].get("from_status") == tr.ResponseStatus.EXECUTING.value
    assert transition_log[2].get("to_status") == tr.ResponseStatus.SUCCESS.value


def test_manual_actions_record_durable_transitions():
    fake_db = FakeDB()
    tr.response_engine.configure_db(fake_db)
    tr.response_engine.response_history = []

    async def _block_ip(_ip, reason: str = "", duration_hours: int = 24):
        return _success_result(tr.ResponseAction.BLOCK_IP, f"blocked: {reason}")

    async def _unblock_ip(_ip):
        return _success_result(tr.ResponseAction.UNBLOCK_IP, "unblocked")

    tr.firewall.block_ip = _block_ip
    tr.firewall.unblock_ip = _unblock_ip

    block_result = asyncio.run(
        tr.manual_block_ip("198.51.100.7", "unit-test", duration_hours=2, actor="tester@example.com")
    )
    assert block_result.status == tr.ResponseStatus.SUCCESS

    unblock_result = asyncio.run(
        tr.manual_unblock_ip("198.51.100.7", actor="tester@example.com")
    )
    assert unblock_result.status == tr.ResponseStatus.SUCCESS

    assert len(fake_db.response_history.docs) == 2

    for doc in fake_db.response_history.docs:
        assert doc["status"] == tr.ResponseStatus.SUCCESS.value
        assert doc["state_version"] == 3
        transitions = doc.get("state_transition_log") or []
        assert len(transitions) == 3
        assert transitions[0].get("to_status") == tr.ResponseStatus.PENDING.value
        assert transitions[1].get("to_status") == tr.ResponseStatus.EXECUTING.value
        assert transitions[2].get("to_status") == tr.ResponseStatus.SUCCESS.value
        assert transitions[-1].get("actor") == "tester@example.com"
