"""Unit tests for Loki ingestion router."""

import asyncio
import pathlib
import sys
import os
import types

# ensure tests dir is importable so local test utilities can be imported by name
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from test_utils import load_dependency, load_module_from_folder, load_service


def _load_router_module(mod_name: str):
    base = pathlib.Path(__file__).resolve().parents[1]
    routers_dir = base / "routers"
    return load_module_from_folder("routers", routers_dir, mod_name)


def _load_dependency(mod_name: str):
    base = pathlib.Path(__file__).resolve().parents[1]
    return load_dependency(mod_name, base)


def _load_service(mod_name: str):
    base = pathlib.Path(__file__).resolve().parents[1]
    return load_service(mod_name, base)


def _load_loki_module():
    _load_service("world_model")
    return _load_router_module("loki")


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


def test_loki_ingest_detection(monkeypatch):
    deps = _load_dependency("dependencies")
    set_database = deps.set_database
    fake = types.SimpleNamespace()
    fake.world_entities = FakeColl()
    fake.world_edges = FakeColl()
    fake.campaigns = FakeColl()
    set_database(fake)

    loki = _load_loki_module()
    payload = loki.LokiIngestRequest(
        kind="detection",
        id="d1",
        entity_type="detection",
        attributes={"sig": "x"},
    )
    r = asyncio.run(loki.ingest(payload, auth={"auth": "ok"}, db=fake))
    assert r["status"] == "ok"
    assert "d1" in fake.world_entities


def test_loki_ingest_edge_and_campaign(monkeypatch):
    deps = _load_dependency("dependencies")
    set_database = deps.set_database
    fake = types.SimpleNamespace()
    fake.world_entities = FakeColl()
    fake.world_edges = FakeColl()
    fake.campaigns = FakeColl()
    set_database(fake)

    loki = _load_loki_module()

    # edge
    edge_payload = loki.LokiIngestRequest(
        kind="edge",
        source="e1",
        target="e2",
        relation="observed",
    )
    r = asyncio.run(loki.ingest(edge_payload, auth={"auth": "ok"}, db=fake))
    assert r["status"] == "ok"
    assert any("e1->e2" in k for k in fake.world_edges.keys()) or len(fake.world_edges) > 0

    # campaign
    campaign_payload = loki.LokiIngestRequest(
        kind="campaign",
        id="c1",
        attributes={"stage": "initial"},
    )
    r = asyncio.run(loki.ingest(campaign_payload, auth={"auth": "ok"}, db=fake))
    assert r["status"] == "ok"
    assert "c1" in fake.world_entities
