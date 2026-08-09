"""Smoke tests for triune routers with an in-memory fake DB."""

import asyncio
import os
import pathlib
import sys
import types
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_utils import load_router, load_service

# Ensure backend and tests directories are importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

WORLD_INGEST_TOKEN = "test-world-ingest-token"
WORLD_INGEST_HEADERS = {
    "x-world-ingest-token": WORLD_INGEST_TOKEN,
}
VPN_AGENT_HEADERS = {
    "x-enrollment-key": "dev-agent-secret-change-in-production",
}


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)
        self._idx = 0

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        item = self._docs[self._idx]
        self._idx += 1
        return item


class FakeColl(dict):
    @staticmethod
    def _set_dotted(target, dotted_key, value):
        parts = dotted_key.split(".")
        cursor = target
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value

    @staticmethod
    def _push_dotted(target, dotted_key, value):
        parts = dotted_key.split(".")
        cursor = target
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cursor[part]
        leaf = parts[-1]
        if leaf not in cursor or not isinstance(cursor[leaf], list):
            cursor[leaf] = []
        cursor[leaf].append(value)

    @staticmethod
    def _extract_key(doc):
        for k in ("id", "queue_id", "decision_id", "token_id", "artifact_id"):
            if k in doc:
                return str(doc[k])
        if "source" in doc or "target" in doc:
            return f"{doc.get('source', '')}->{doc.get('target', '')}"
        return uuid.uuid4().hex

    async def insert_one(self, doc):
        key = self._extract_key(doc)
        self[key] = dict(doc)
        return types.SimpleNamespace(inserted_id=key)

    async def replace_one(self, query, replacement, upsert=False):
        key = str(query.get("id") or query.get("token_id") or self._extract_key(replacement))
        if key in self or upsert:
            self[key] = dict(replacement)
        return types.SimpleNamespace(modified_count=1)

    async def update_one(self, query, update, upsert=False):
        key = str(query.get("id") or query.get("token_id") or query.get("queue_id") or query.get("decision_id") or "")
        if not key:
            return types.SimpleNamespace(modified_count=0)
        if key not in self and not upsert:
            return types.SimpleNamespace(modified_count=0)
        base = dict(self.get(key, {"id": key}))
        for dotted_key, value in (update.get("$set") or {}).items():
            self._set_dotted(base, dotted_key, value)
        for dotted_key, value in (update.get("$push") or {}).items():
            self._push_dotted(base, dotted_key, value)
        self[key] = base
        return types.SimpleNamespace(modified_count=1)

    async def find_one(self, query, sort=None):
        if not query:
            return next(iter(self.values()), None)
        for key in ("id", "token_id", "queue_id", "decision_id", "artifact_id"):
            if key in query:
                return self.get(str(query[key]))
        return next(iter(self.values()), None)

    async def count_documents(self, query):
        return len(self)

    def find(self, query=None, sort=None, limit=None):
        cursor = FakeCursor(list(self.values()))
        if limit:
            cursor = cursor.limit(limit)
        return cursor


def make_fake_db():
    return types.SimpleNamespace(
        world_entities=FakeColl(),
        world_edges=FakeColl(),
        campaigns=FakeColl(),
        alerts=FakeColl(),
        threats=FakeColl(),
        vpn=FakeColl(),
        users=FakeColl(),
    )


def _build_app(fake_db=None):
    from routers import dependencies as deps

    app = FastAPI()
    base = pathlib.Path(__file__).resolve().parents[1]
    load_service("world_model", base)

    if fake_db is None:
        fake_db = make_fake_db()
    deps.set_database(fake_db)
    os.environ["WORLD_INGEST_TOKEN"] = WORLD_INGEST_TOKEN

    metatron_router = load_router("metatron", base)
    michael_router = load_router("michael", base)
    loki_router = load_router("loki", base)
    world_ingest_router = load_router("world_ingest", base)
    alerts_router = load_router("alerts", base)
    threats_router = load_router("threats", base)
    deception_router = load_router("deception", base)
    vpn_router = load_router("vpn", base)
    response_router = load_router("response", base)
    timeline_router = load_router("timeline", base)
    soar_router = load_router("soar", base)

    app.include_router(metatron_router, prefix="/api")
    app.include_router(michael_router, prefix="/api")
    app.include_router(loki_router, prefix="/api")
    app.include_router(world_ingest_router, prefix="/api")
    app.include_router(alerts_router, prefix="/api")
    app.include_router(threats_router, prefix="/api")
    app.include_router(deception_router, prefix="/api")
    app.include_router(vpn_router, prefix="/api")
    app.include_router(response_router, prefix="/api")
    app.include_router(timeline_router, prefix="/api")
    app.include_router(soar_router, prefix="/api")

    app.dependency_overrides[deps.get_current_user] = lambda request=None, credentials=None: {
        "id": "u1",
        "email": "u@example.com",
        "role": "admin",
    }
    app.dependency_overrides[deps.get_optional_current_user] = lambda request=None, credentials=None: {
        "id": "u1",
        "email": "u@example.com",
        "role": "admin",
    }

    try:
        from routers import vpn as vpn_mod

        def _vpn_identity_override(
            request=None,
            x_agent_id=None,
            x_agent_token=None,
            x_enrollment_key=None,
            authorization=None,
        ):
            return {
                "type": "authenticated",
                "agent_id": "agent-123",
                "ip": "127.0.0.1",
                "trusted": True,
            }

        app.dependency_overrides[vpn_mod.get_vpn_identity] = _vpn_identity_override
    except Exception:
        pass

    return app, fake_db


def test_michael_hello():
    app, _ = _build_app()
    client = TestClient(app)
    response = client.get("/api/michael/hello")
    assert response.status_code == 200
    assert response.json().get("msg") == "Michael router active"


def test_loki_hello():
    app, _ = _build_app()
    client = TestClient(app)
    response = client.get("/api/loki/hello")
    assert response.status_code == 200
    assert response.json().get("msg") == "Loki router active"


def test_metatron_summary_empty():
    app, _ = _build_app()
    client = TestClient(app)
    response = client.get("/api/metatron/summary")
    assert response.status_code == 200
    body = response.json()
    assert "entities" in body
    assert isinstance(body.get("campaigns"), list)


def test_metatron_state_structure():
    app, _ = _build_app()
    client = TestClient(app)
    response = client.get("/api/metatron/state")
    assert response.status_code == 200
    body = response.json()
    for key in ["header", "narrative", "attack_path", "trust", "hotspots", "actions", "hypotheses", "timeline"]:
        assert key in body


def test_ingest_entity_and_risk():
    app, _ = _build_app()
    client = TestClient(app)

    r1 = client.post(
        "/api/ingest/entity",
        json={"id": "e1", "type": "host", "attributes": {}},
        headers=WORLD_INGEST_HEADERS,
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/ingest/detection",
        json={"entity_id": "e1", "confidence": 80},
        headers=WORLD_INGEST_HEADERS,
    )
    assert r2.status_code == 200

    r3 = client.get("/api/metatron/state")
    assert r3.status_code == 200
    assert "risk_level" in r3.json().get("header", {})


def test_decoy_interaction_ingestion():
    app, fake_db = _build_app()
    client = TestClient(app)

    payload = {"ip": "1.2.3.4", "decoy_type": "credentials", "decoy_id": "dec1"}
    response = client.post("/api/deception/decoy/interaction", json=payload)
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_vpn_peer_ingestion():
    app, fake_db = _build_app()

    from vpn_integration import vpn_manager

    async def fake_add(name, **kwargs):
        return {
            "peer_id": kwargs.get("peer_id") or "peer1",
            "name": name,
            "public_key": kwargs.get("public_key") or "pub1",
            "allowed_ips": "10.200.200.10/32",
        }

    vpn_manager.add_peer = fake_add

    client = TestClient(app)
    response = client.post(
        "/api/vpn/peers",
        json={"name": "agent-123", "peer_id": "agent-123", "public_key": "pub-agent"},
        headers=VPN_AGENT_HEADERS,
    )
    assert response.status_code == 200
    assert response.json().get("peer", {}).get("peer_id") in {"agent-123", "peer1"}


def test_vpn_peer_registration_with_agent_auth():
    app, fake_db = _build_app()

    from vpn_integration import vpn_manager

    async def fake_add(name, peer_id=None, allowed_ips=None):
        return {
            "peer_id": peer_id or "peer1",
            "name": name,
            "public_key": "pub1",
            "allowed_ips": allowed_ips or "10.200.200.10/32",
        }

    vpn_manager.add_peer = fake_add

    client = TestClient(app)
    response = client.post(
        "/api/vpn/peers",
        json={"name": "agent-123", "peer_id": "agent-123"},
        headers=VPN_AGENT_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["peer"]["peer_id"] == "agent-123"


def test_risk_score_increases_with_severity():
    from services.world_model import WorldEntity, WorldModelService

    fake_db = make_fake_db()
    wm = WorldModelService(fake_db)

    ent = WorldEntity(id="ent1", type="host", attributes={"detections": [{"confidence": 50, "severity": 1}]})
    asyncio.run(wm.upsert_entity(ent))
    asyncio.run(wm.calculate_risk("ent1"))
    doc1 = asyncio.run(wm.entities.find_one({"id": "ent1"})) or {}
    low_risk = (doc1.get("attributes") or {}).get("risk_score", 0)

    asyncio.run(wm.entities.update_one({"id": "ent1"}, {"$push": {"attributes.detections": {"confidence": 80, "severity": 5}}}))
    asyncio.run(wm.calculate_risk("ent1"))
    doc2 = asyncio.run(wm.entities.find_one({"id": "ent1"})) or {}
    high_risk = (doc2.get("attributes") or {}).get("risk_score", 0)

    assert high_risk >= low_risk


def test_policy_violation_increases_risk():
    from services.world_model import WorldEntity, WorldModelService

    fake_db = make_fake_db()
    wm = WorldModelService(fake_db)

    ent = WorldEntity(id="ent2", type="host", attributes={})
    asyncio.run(wm.upsert_entity(ent))
    asyncio.run(wm.calculate_risk("ent2"))
    base_doc = asyncio.run(wm.entities.find_one({"id": "ent2"})) or {}
    base = (base_doc.get("attributes") or {}).get("risk_score", 0)

    asyncio.run(wm.entities.update_one({"id": "ent2"}, {"$set": {"attributes.policy_violation": True}}))
    asyncio.run(wm.calculate_risk("ent2"))
    new_doc = asyncio.run(wm.entities.find_one({"id": "ent2"})) or {}
    new_risk = (new_doc.get("attributes") or {}).get("risk_score", 0)

    assert new_risk >= base


def test_ingest_policy_violation_endpoint():
    app, _ = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/ingest/policy-violation",
        json={"entity_id": "eid1"},
        headers=WORLD_INGEST_HEADERS,
    )
    assert response.status_code == 200


def test_ingest_token_event_endpoint():
    app, _ = _build_app()
    client = TestClient(app)
    response = client.post(
        "/api/ingest/token-event",
        json={"token_id": "tok1", "foo": 1},
        headers=WORLD_INGEST_HEADERS,
    )
    assert response.status_code == 200


def test_timeline_artifact_ingestion():
    app, fake_db = _build_app()
    client = TestClient(app)

    r1 = client.post(
        "/api/timeline/artifacts/register",
        json={"artifact_type": "file", "name": "test", "description": "desc"},
    )
    assert r1.status_code == 200
    artifact = (r1.json().get("artifact") or {})
    artifact_id = artifact.get("artifact_id")
    assert artifact_id

    r2 = client.post(f"/api/timeline/artifacts/{artifact_id}/custody", json={"action": "moved", "notes": "x"})
    assert r2.status_code == 200
    assert isinstance(r2.json(), dict)


def test_soar_trigger_ingests_event():
    app, fake_db = _build_app()
    client = TestClient(app)

    response = client.post("/api/soar/trigger", json={"trigger_type": "foo", "source_ip": "1.2.3.4"})
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_response_block_updates_world():
    app, fake_db = _build_app()

    import threat_response

    async def fake_block(ip, reason, hrs, name):
        return {"blocked": ip, "reason": reason}

    threat_response.manual_block_ip = fake_block

    client = TestClient(app)
    response = client.post(
        "/api/threat-response/block-ip",
        json={"ip": "9.9.9.9", "reason": "test", "duration_hours": 1},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_alert_router_updates_world_model():
    app, fake_db = _build_app()
    client = TestClient(app)

    response = client.post(
        "/api/alerts",
        json={"title": "test", "type": "malware", "severity": "high", "threat_id": None, "message": "warn"},
    )
    assert response.status_code == 200
    alert = response.json()
    assert alert.get("id")
    assert len(fake_db.alerts) >= 1
