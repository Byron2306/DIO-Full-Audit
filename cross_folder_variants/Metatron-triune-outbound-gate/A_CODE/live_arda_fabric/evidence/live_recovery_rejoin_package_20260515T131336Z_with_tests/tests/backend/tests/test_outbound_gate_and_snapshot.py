import types
import pathlib

import pytest

from test_utils import ensure_package, load_module_from_folder, load_service
from backend.arda.ainur.dissonance import DissonantStateModel


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction):
        reverse = direction == -1
        def _k(d):
            cur = d
            for part in key.split("."):
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(part)
                if cur is None:
                    return None
            return cur
        self.docs = sorted(self.docs, key=lambda d: (_k(d) is None, _k(d)), reverse=reverse)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, n):
        return self.docs[:n]

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self.docs):
            raise StopAsyncIteration
        v = self.docs[self._i]
        self._i += 1
        return v


class FakeColl:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, q, u, upsert=False):
        d = await self.find_one(q)
        if d is None:
            if not upsert:
                return
            d = dict(q)
            self.docs.append(d)
        if "$set" in u:
            d.update(u["$set"])

    async def find_one(self, q, projection=None, sort=None):
        for d in self.docs:
            ok = True
            for k, v in (q or {}).items():
                if d.get(k) != v:
                    ok = False
                    break
            if ok:
                return d
        return None

    async def count_documents(self, q):
        return len(self.docs)

    def find(self, q=None, projection=None, sort=None, limit=0):
        out = list(self.docs)
        if q and "attributes.risk_score" in q:
            out = [d for d in out if d.get("attributes", {}).get("risk_score") is not None]
        if q and "attributes.trust_state" in q:
            out = [d for d in out if d.get("attributes", {}).get("trust_state") is not None]
        cur = FakeCursor(out)
        if sort:
            if isinstance(sort, list) and sort:
                key, direction = sort[0]
                cur.sort(key, direction)
        if limit:
            cur.limit(limit)
        return cur

    def aggregate(self, pipeline):
        # very small stub: group world_entities by sector with avg risk
        rows = []
        if self.docs:
            grouped = {}
            for d in self.docs:
                attrs = d.get("attributes", {})
                if "risk_score" not in attrs:
                    continue
                sector = attrs.get("sector", "unknown")
                grouped.setdefault(sector, []).append(attrs.get("risk_score", 0.0))
            for sector, vals in grouped.items():
                rows.append({"_id": sector, "avg_risk": sum(vals) / len(vals), "entities": len(vals)})
            rows.sort(key=lambda r: r["avg_risk"], reverse=True)
        return FakeCursor(rows)


def _bootstrap_triune(base):
    triune_dir = base / "triune"
    ensure_package("triune", str(triune_dir))
    load_module_from_folder("triune", triune_dir, "metatron")
    load_module_from_folder("triune", triune_dir, "michael")
    load_module_from_folder("triune", triune_dir, "loki")
    load_module_from_folder("triune", triune_dir, "__init__")


@pytest.mark.asyncio
async def test_outbound_gate_action_queueing_and_triune_snapshot_enrichment():
    base = pathlib.Path(__file__).resolve().parents[1]
    wm = load_service("world_model", base)
    _bootstrap_triune(base)
    triune = load_service("triune_orchestrator", base)
    gate_mod = load_service("outbound_gate", base)

    fake = types.SimpleNamespace(
        world_entities=FakeColl(),
        world_edges=FakeColl(),
        campaigns=FakeColl(),
        world_events=FakeColl(),
        response_history=FakeColl(),
        triune_outbound_queue=FakeColl(),
        triune_decisions=FakeColl(),
    )

    # seed world-state
    fake.world_entities.docs.append({"id": "host-1", "type": "host", "attributes": {"risk_score": 0.9, "trust_state": "degraded", "sector": "finance"}})
    fake.world_entities.docs.append({"id": "host-2", "type": "host", "attributes": {"risk_score": 0.4, "sector": "healthcare"}})
    fake.world_edges.docs.append({"source": "host-1", "target": "host-2", "relation": "connected", "created": "2026-03-15T00:00:00Z"})
    fake.campaigns.docs.append({"id": "camp-1", "name": "test", "first_detected": "2026-03-15T00:00:00Z"})
    fake.world_events.docs.append({"id": "we-1", "created": "2026-03-15T00:00:01Z", "type": "x"})
    fake.response_history.docs.append({"id": "resp-1", "status": "in_progress", "timestamp": "2026-03-15T00:00:02Z"})

    gate = gate_mod.OutboundGateService(fake)
    gate.fabric.known_peers["agent-1"] = {
        "id": "agent-1",
        "wg_pubkey": "peer-pubkey",
        "is_peer_verified": True,
        "influence_budget": DissonantStateModel(
            entity_id="agent-1",
            constitutional_state="stable",
            network_trust=1.0,
            behavioral_score=1.0,
        ),
    }
    gate.notation_tokens.resolve_enforcement_profile = lambda *args, **kwargs: {}
    gate.verify_transport_lock = lambda *_args, **_kwargs: True
    gate.environment = "production"
    gate_mod.world_manifold._current_manifold = types.SimpleNamespace(signature_valid=True)

    async def _notation_ok(*args, **kwargs):
        return {"valid": True, "checks": {}, "reasons": [], "enforcement_profile": {}}

    gate.notation_tokens.validate_notation_token = _notation_ok
    queued = await gate.gate_action(
        action_type="agent_command",
        actor="operator:test",
        payload={"command_id": "cmd-1", "command_type": "kill_process"},
        impact_level="critical",
        subject_id="agent-1",
        entity_refs=["cmd-1"],
        requires_triune=True,
    )

    assert queued["status"] == "queued"
    assert fake.triune_outbound_queue.docs
    assert fake.triune_decisions.docs

    orchestrator = triune.TriuneOrchestrator(fake)
    bundle = await orchestrator.handle_world_change(
        event_type="agent_command_created",
        entity_ids=["host-1"],
        context={"source": "test"},
    )

    assert bundle["final_verdict"] == "ALLOW_WITH_SCHEMA"
    assert bundle["router_mode"] == "deterministic_schema_routing"
    assert bundle["harmony_score"] == 1.0
    assert bundle["schema_route"]["challenge_type"]
    assert bundle["schema_route"]["schemas"]
    assert bundle["metatron"]["verdict"] != "VETO"
    assert bundle["michael"]["verdict"] == "ATTACH_SCHEMA"
    assert bundle["loki"]["verdict"] == "UNCHALLENGED"
