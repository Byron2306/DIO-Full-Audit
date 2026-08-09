"""Integration tests for /loki/ingest/async enqueue vs fallback behavior."""

import asyncio
import pathlib
import sys
import os
import types
from test_utils import load_module_from_folder, load_service, load_dependency


def _load_router_module(mod_name: str, base_dir: pathlib.Path):
    routers_dir = base_dir / "routers"
    return load_module_from_folder("routers", routers_dir, mod_name)


def test_loki_ingest_async_fallback():
    base = pathlib.Path(__file__).resolve().parents[1]
    # load deps and services
    deps = load_dependency("dependencies", base)
    set_database = deps.set_database
    # ensure services.world_model is loaded for router imports
    load_service("world_model", base)

    fake = types.SimpleNamespace()
    class FakeColl(dict):
        def __bool__(self):
            return True

        async def insert_one(self, doc):
            if "id" in doc:
                self[doc["id"]] = doc
            else:
                key = doc.get("source", "") + "->" + doc.get("target", "")
                self[key] = doc
        async def update_one(self, q, u, upsert=False):
            _id = q.get("id")
            self[_id] = {**self.get(_id, {}), **(u.get("$set", {}))}
        async def find_one(self, q, sort=None):
            return self.get(q.get("id"))
        async def count_documents(self, q):
            return len(self)
        async def find(self, q=None, sort=None, limit=None):
            for v in self.values():
                yield v

    fake.world_entities = FakeColl()
    fake.world_edges = FakeColl()
    fake.campaigns = FakeColl()
    set_database(fake)

    loki = _load_router_module("loki", base)
    payload = {"kind": "detection", "id": "d_async", "entity_type": "detection", "attributes": {"sig": "x"}}
    j = asyncio.run(loki.ingest_async(payload, auth={"auth": "ok"}, db=fake))
    # fallback should run inline and return completed/result
    assert j.get("status") in {"completed", "ok"}
    # ensure entity persisted in fake DB
    assert "d_async" in fake.world_entities


def test_loki_ingest_async_enqueue(monkeypatch):
    base = pathlib.Path(__file__).resolve().parents[1]
    deps = load_dependency("dependencies", base)
    set_database = deps.set_database
    # ensure services.world_model is loaded for router imports
    load_service("world_model", base)

    fake = types.SimpleNamespace()
    class FakeColl(dict):
        def __bool__(self):
            return True

        async def insert_one(self, doc):
            if "id" in doc:
                self[doc["id"]] = doc
            else:
                key = doc.get("source", "") + "->" + doc.get("target", "")
                self[key] = doc
        async def update_one(self, q, u, upsert=False):
            _id = q.get("id")
            self[_id] = {**self.get(_id, {}), **(u.get("$set", {}))}
        async def find_one(self, q, sort=None):
            return self.get(q.get("id"))
        async def count_documents(self, q):
            return len(self)
        async def find(self, q=None, sort=None, limit=None):
            for v in self.values():
                yield v

    fake.world_entities = FakeColl()
    fake.world_edges = FakeColl()
    fake.campaigns = FakeColl()
    set_database(fake)

    # monkeypatch the backend.tasks.triune_tasks.loki_ingest to simulate Celery Task
    import sys
    # inject a fake module object to simulate Celery task availability
    mod_name = "backend.tasks.triune_tasks"
    dummy_mod = types.ModuleType(mod_name)

    class DummyTask:
        def delay(self, payload):
            class Res:
                id = "task-123"
            return Res()

    dummy_mod.loki_ingest = DummyTask()
    sys.modules[mod_name] = dummy_mod

    loki = _load_router_module("loki", base)
    payload = {"kind": "detection", "id": "d_enqueue", "entity_type": "detection", "attributes": {"sig": "y"}}
    j = asyncio.run(loki.ingest_async(payload, auth={"auth": "ok"}, db=fake))
    assert j.get("status") == "enqueued"
    assert j.get("task_id") == "task-123"
    # enqueue should not have run inline; DB remains empty
    assert "d_enqueue" not in fake.world_entities
