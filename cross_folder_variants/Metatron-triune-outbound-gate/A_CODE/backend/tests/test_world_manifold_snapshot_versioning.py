from types import SimpleNamespace

import pytest

from backend.services.world_manifold import WorldManifoldService


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, query=None, projection=None, sort=None):
        if not self.docs:
            return None
        docs = list(self.docs)
        if sort:
            field, direction = sort[0]
            reverse = int(direction) < 0
            docs = sorted(docs, key=lambda d: d.get(field, 0), reverse=reverse)
        return docs[0]

    async def insert_one(self, doc):
        self.docs.append(doc)


class FakeDB:
    def __init__(self):
        self.world_manifolds = FakeCollection([{"manifold_id": "manifold-prev", "snapshot_version": 2}])


@pytest.mark.asyncio
async def test_build_manifold_snapshot_persists_immutable_versioned_record(monkeypatch):
    db = FakeDB()
    service = WorldManifoldService(db)

    service.verifier = SimpleNamespace(
        get_truth=lambda: SimpleNamespace(
            boot_truth_ref="boot-1",
            formation_truth_id="truth-1",
            sealed_identity_seed="seed-1",
            status="lawful",
        ),
        verify_formation=lambda: None,
    )
    service.formation_order = SimpleNamespace(
        get_order=lambda: SimpleNamespace(formation_order_id="order-1", status="lawful", order_score=0.96),
        validate_formation_order=lambda: None,
    )
    service.genesis = SimpleNamespace(
        get_score=lambda: SimpleNamespace(
            genesis_score_id="score-1",
            genesis_epoch="epoch-1",
            genre_mode="siege",
            strictness=0.9,
        ),
        load_genesis_score=lambda: None,
    )
    service.covenant_service = SimpleNamespace(
        get_covenant=lambda: SimpleNamespace(covenant_id="covenant-1", status="lawful"),
        seal_covenant=lambda: None,
    )
    service.herald = SimpleNamespace(get_state=lambda: SimpleNamespace(current_epoch="epoch-1"))
    service.resonance = SimpleNamespace(
        get_current_state=lambda: SimpleNamespace(
            resonance_id="res-1",
            cluster_health=SimpleNamespace(collective_score=0.97, is_fully_lawful=True),
        ),
        refresh_collective_resonance=lambda: None,
    )
    service.quorum_engine = SimpleNamespace(
        get_last_decision=lambda: SimpleNamespace(
            status=SimpleNamespace(value="resonant"),
            nodes_resonant=3,
            nodes_silent=0,
            nodes_dissonant=0,
        )
    )
    service.telemetry = SimpleNamespace(ingest_event=lambda **kwargs: None)
    service.world_model = SimpleNamespace(set_governance_placeholders=lambda **kwargs: None)

    lineage_service = SimpleNamespace(
        audit_lineage_integrity=lambda: None,
        get_active_protected_count=lambda: 5,
        active_interceptors=["ebpf_exec", "seccomp", "lsm"],
    )

    async def _integrity():
        return 0.95

    lineage_service.audit_lineage_integrity = _integrity

    monkeypatch.setattr(
        "backend.services.process_lineage_service.get_process_lineage_service",
        lambda _db: lineage_service,
    )
    monkeypatch.setattr(
        "backend.services.world_manifold.quantum_security.sign_manifold_snapshot",
        lambda payload: {"signature_ref": "sig-ref", "algorithm": "mock", "signature": "sig"},
    )
    monkeypatch.setattr(
        "backend.services.world_manifold.quantum_security.verify_manifold_snapshot_signature",
        lambda *args, **kwargs: True,
    )

    manifold = await service.build_manifold_snapshot()

    assert manifold.snapshot_version == 3
    assert manifold.previous_manifold_ref == "manifold-prev"
    assert manifold.immutable is True
    assert manifold.authoritative_control_state["snapshot_version"] == 3
    assert manifold.authoritative_evidence["formation_truth"]["ref"] == "truth-1"
    assert manifold.authoritative_evidence["formation_truth"]["verification"]["mode"] == "live_verified"
    assert manifold.authoritative_evidence["quorum"]["verification"]["verified"] is True
    assert manifold.authoritative_control_state["verification_summary"]["kernel_lineage"] == "live_verified"
    assert manifold.strategic_narrative["trust_zone_state"]["sovereignty"] == "substrate_enforced"
    assert db.world_manifolds.docs[-1]["manifold_id"] == manifold.manifold_id
