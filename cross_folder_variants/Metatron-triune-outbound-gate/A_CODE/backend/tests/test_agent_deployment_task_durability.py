"""Durability tests for deployment task lifecycle in agent_deployment service."""

import asyncio
import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = ROOT / "backend" / "services" / "agent_deployment.py"


def _load_service_module():
    spec = importlib.util.spec_from_file_location("agent_deployment_service", SERVICE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend/services/agent_deployment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


svc_mod = _load_service_module()
AgentDeploymentService = svc_mod.AgentDeploymentService


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
            actual = doc.get(key)
            if not cls._match_condition(actual, expected):
                return False
        return True

    async def insert_one(self, doc: Dict[str, Any]):
        self.docs.append(deepcopy(doc))

    async def find_one(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        for doc in self.docs:
            if self._matches(doc, query):
                result = deepcopy(doc)
                if projection:
                    include_keys = {k for k, v in projection.items() if v}
                    if include_keys:
                        result = {k: v for k, v in result.items() if k in include_keys}
                return result
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
                if "$setOnInsert" in update:
                    for key, value in update["$setOnInsert"].items():
                        next_doc.setdefault(key, deepcopy(value))
                self.docs[idx] = next_doc
                modified += 1
                break

        if matched == 0 and upsert:
            new_doc: Dict[str, Any] = {}
            for key, value in query.items():
                if not key.startswith("$") and not isinstance(value, dict):
                    new_doc[key] = deepcopy(value)
            if "$setOnInsert" in update:
                new_doc.update(deepcopy(update["$setOnInsert"]))
            if "$set" in update:
                new_doc.update(deepcopy(update["$set"]))
            if "$inc" in update:
                for key, delta in update["$inc"].items():
                    new_doc[key] = int(new_doc.get(key) or 0) + int(delta)
            if "$push" in update:
                for key, value in update["$push"].items():
                    new_doc[key] = [deepcopy(value)]
            self.docs.append(new_doc)
            matched = 1
            modified = 1

        return type("Result", (), {"matched_count": matched, "modified_count": modified})()


class FakeDB:
    def __init__(self, tasks: Optional[List[Dict[str, Any]]] = None, devices: Optional[List[Dict[str, Any]]] = None):
        self.deployment_tasks = FakeCollection(tasks)
        self.discovered_devices = FakeCollection(devices)


def test_queue_deployment_initializes_task_and_device_transition_metadata():
    db = FakeDB(devices=[{"ip_address": "10.0.0.2", "hostname": "host-2"}])
    svc = AgentDeploymentService(db, api_url="http://localhost:8001")

    task_id = asyncio.run(
        svc.queue_deployment(
            device_ip="10.0.0.2",
            device_hostname="host-2",
            os_type="linux",
            credentials={"username": "root", "password": "secret"},
        )
    )

    task_doc = asyncio.run(db.deployment_tasks.find_one({"task_id": task_id}))
    assert task_doc is not None
    assert task_doc["status"] == "pending"
    assert task_doc["state_version"] == 1
    assert (task_doc.get("state_transition_log") or [])[-1]["to_status"] == "pending"

    device_doc = asyncio.run(db.discovered_devices.find_one({"ip_address": "10.0.0.2"}))
    assert device_doc["deployment_status"] == "queued"
    assert device_doc["deployment_state_version"] == 1
    assert (device_doc.get("deployment_state_transition_log") or [])[-1]["to_status"] == "queued"


def test_deploy_agent_success_uses_guarded_transitions():
    db = FakeDB(devices=[{"ip_address": "10.0.0.3", "hostname": "host-3"}])
    svc = AgentDeploymentService(db, api_url="http://localhost:8001")

    async def _fake_ssh(_task):
        return True

    svc._deploy_via_ssh = _fake_ssh  # type: ignore[method-assign]

    task_id = asyncio.run(
        svc.queue_deployment(
            device_ip="10.0.0.3",
            device_hostname="host-3",
            os_type="linux",
            credentials={"username": "root", "password": "secret"},
        )
    )
    queued_task = asyncio.run(svc.deployment_queue.get())
    assert queued_task.task_id == task_id

    asyncio.run(svc._deploy_agent(queued_task))

    task_doc = asyncio.run(db.deployment_tasks.find_one({"task_id": task_id}))
    transitions = task_doc.get("state_transition_log") or []
    assert task_doc["status"] == "deployed"
    assert task_doc["state_version"] == 3
    assert [t.get("to_status") for t in transitions] == ["pending", "deploying", "deployed"]

    device_doc = asyncio.run(db.discovered_devices.find_one({"ip_address": "10.0.0.3"}))
    device_transitions = device_doc.get("deployment_state_transition_log") or []
    assert device_doc["deployment_status"] == "deployed"
    assert device_doc["deployment_state_version"] == 3
    assert [t.get("to_status") for t in device_transitions] == ["queued", "deploying", "deployed"]


def test_retry_failed_deployments_transitions_failed_to_pending_and_requeues():
    db = FakeDB(
        tasks=[
            {
                "task_id": "deploy-1",
                "device_ip": "10.0.0.4",
                "device_hostname": "host-4",
                "os_type": "linux",
                "method": "ssh",
                "status": "failed",
                "attempts": 3,
                "state_version": 2,
                "state_transition_log": [
                    {"to_status": "pending"},
                    {"to_status": "failed"},
                ],
            }
        ],
        devices=[
            {
                "ip_address": "10.0.0.4",
                "deployment_status": "failed",
                "deployment_state_version": 1,
                "deployment_state_transition_log": [{"to_status": "failed"}],
            }
        ],
    )
    svc = AgentDeploymentService(db, api_url="http://localhost:8001")

    count = asyncio.run(svc.retry_failed_deployments())
    assert count == 1

    task_doc = asyncio.run(db.deployment_tasks.find_one({"task_id": "deploy-1"}))
    assert task_doc["status"] == "pending"
    assert task_doc["attempts"] == 0
    assert task_doc["state_version"] == 3
    assert (task_doc.get("state_transition_log") or [])[-1].get("to_status") == "pending"

    device_doc = asyncio.run(db.discovered_devices.find_one({"ip_address": "10.0.0.4"}))
    assert device_doc["deployment_status"] == "queued"
    assert device_doc["deployment_state_version"] == 2
    assert (device_doc.get("deployment_state_transition_log") or [])[-1].get("to_status") == "queued"

    assert svc.deployment_queue.qsize() == 1
