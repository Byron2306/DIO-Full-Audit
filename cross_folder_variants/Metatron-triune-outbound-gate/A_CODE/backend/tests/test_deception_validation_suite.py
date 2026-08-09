import pytest

from backend.schemas.deception_models import DeceptionMode
from backend.services.deception_authority import DeceptionAuthorityService
from backend.services.disinformation_engine import DisinformationEngine
from backend.services.mystique_maze import MystiqueMaze


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, field, direction):
        reverse = int(direction) < 0
        self._docs.sort(key=lambda item: item.get(field), reverse=reverse)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return list(self._docs if length is None else self._docs[:length])


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def replace_one(self, filt, doc, upsert=False):
        key, value = next(iter(filt.items()))
        for idx, existing in enumerate(self.docs):
            if existing.get(key) == value:
                self.docs[idx] = dict(doc)
                return
        if upsert:
            self.docs.append(dict(doc))

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def find_one(self, filt):
        key, value = next(iter(filt.items()))
        for doc in self.docs:
            if doc.get(key) == value:
                return dict(doc)
        return None

    def find(self, filt=None, projection=None):
        filt = filt or {}
        matched = []
        for doc in self.docs:
            ok = True
            for key, value in filt.items():
                if doc.get(key) != value:
                    ok = False
                    break
            if ok:
                if projection:
                    out = {k: v for k, v in doc.items() if projection.get(k, 1) != 0}
                    matched.append(out)
                else:
                    matched.append(dict(doc))
        return _FakeCursor(matched)


class _FakeDB:
    def __init__(self):
        self.deception_cases = _FakeCollection()
        self.deception_events = _FakeCollection()
        self.disinformation_serves = _FakeCollection()
        self.maze_states = _FakeCollection()
        self.maze_sessions = _FakeCollection()
        self.agenticity_scores = _FakeCollection()


@pytest.mark.asyncio
async def test_disinformation_payloads_are_validator_clean_across_categories():
    authority = DeceptionAuthorityService()
    engine = DisinformationEngine()
    paths = [
        "/auth/login",
        "/network/map",
        "/scan/results",
        "/openapi/index",
        "/users/list",
        "/vault/records",
        "/audit/logs",
    ]
    for path in paths:
        payload, _ = engine.generate(
            path=path,
            session_id="sess-123",
            campaign_id="camp-123",
            risk_score=65,
            reasons=["route_decision:disinformation", "machine_like_timing"],
            behavior_flags={"inferred_intent": "recon"},
        )
        result = authority.validate_payload(payload)
        assert payload["_seraph_synthetic"] is True
        assert result.allowed is True, (path, result.collisions)


def test_disinformation_generation_is_multi_turn_coherent_for_same_probe():
    engine = DisinformationEngine()
    first_payload, _ = engine.generate(
        path="/users/list",
        session_id="sess-coherent",
        campaign_id="camp-coherent",
        behavior_flags={"inferred_intent": "credential_hunt"},
    )
    second_payload, _ = engine.generate(
        path="/users/list",
        session_id="sess-coherent",
        campaign_id="camp-coherent",
        behavior_flags={"inferred_intent": "credential_hunt"},
    )
    assert first_payload["category"] == second_payload["category"]
    assert first_payload["data"] == second_payload["data"]


@pytest.mark.asyncio
async def test_mirror_world_replay_and_restart_continuity_are_persistent():
    db = _FakeDB()
    maze_one = MystiqueMaze()
    maze_one.set_persistence(db)

    created = await maze_one.get_or_create_maze(
        session_id="sess-replay",
        campaign_id="camp-replay",
        agenticity_score=0.92,
        agenticity_classification="HIGH",
    )
    surface_before = maze_one.get_surface_nodes("sess-replay")
    payload, new_nodes = await maze_one.probe_node(
        session_id="sess-replay",
        node_id=surface_before[0]["node_id"],
        agenticity_score=0.92,
        cbr=820.0,
        tbcr=13.0,
    )

    maze_two = MystiqueMaze()
    maze_two.set_persistence(db)
    restored = await maze_two.get_or_create_maze(
        session_id="sess-replay",
        campaign_id="camp-replay",
        agenticity_score=0.92,
        agenticity_classification="HIGH",
    )
    surface_after = maze_two.get_surface_nodes("sess-replay")
    telemetry = maze_two.get_maze_telemetry("sess-replay")

    assert restored.maze_id == created.maze_id
    assert surface_after == surface_before
    assert telemetry["total_probes"] == 1
    assert telemetry["nodes_total"] >= len(surface_before) + len(new_nodes)
    assert payload["_seraph_synthetic"] is True


@pytest.mark.asyncio
async def test_evidence_chain_links_case_event_and_disinformation_serve():
    db = _FakeDB()
    authority = DeceptionAuthorityService(db)
    case, validation = await authority.create_case(
        session_id="sess-evidence",
        campaign_id="camp-evidence",
        source_ip="198.51.100.44",
        path="/auth/login",
        trigger_reason="route_decision:disinformation",
        triggering_signals=["route_decision:disinformation", "machine_like_timing"],
        desired_mode=DeceptionMode.DISINFORMATION,
        risk_score=78,
        behavior_flags={"machine_plausibility": 0.71, "agenticity_score": 0.66},
    )
    assert validation.allowed is True

    engine = DisinformationEngine()
    engine.set_db(db)
    payload, record = engine.generate(
        path="/auth/login",
        session_id="sess-evidence",
        campaign_id="camp-evidence",
        reasons=["route_decision:disinformation", "machine_like_timing"],
    )
    payload_validation = await authority.authorize_payload(case=case, payload=payload)
    assert payload_validation.allowed is True
    await engine.persist_serve(record=record, payload=payload, deception_case_id=case.deception_case_id)
    event_id = await authority.persist_event(
        deception_case_id=case.deception_case_id,
        event_type="disinformation_served",
        session_id="sess-evidence",
        campaign_id="camp-evidence",
        source_ip="198.51.100.44",
        details={"serve_id": record.serve_id},
    )

    stored_case = await db.deception_cases.find_one({"deception_case_id": case.deception_case_id})
    stored_event = await db.deception_events.find_one({"event_id": event_id})
    stored_serve = await db.disinformation_serves.find_one({"serve_id": record.serve_id})

    assert stored_case is not None
    assert stored_event["deception_case_id"] == case.deception_case_id
    assert stored_serve["deception_case_id"] == case.deception_case_id
    assert stored_serve["payload"]["_seraph_synthetic"] is True
