from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from metamorphic.registry import build_reference_registry
from metamorphic.world_lease import (
    DEFAULT_CONFIG,
    PHASE4_EXIT_TOKEN,
    WorldLeaseBindingError,
    acquire_world_lease,
    build_controlled_world_snapshot,
    phase4_world_lease_receipt,
    require_world_lease_current,
    validate_world_lease,
    world_anchor_digests,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = datetime(2026, 8, 18, 21, 30, tzinfo=timezone.utc)


def _config():
    return json.loads((REPO_ROOT / DEFAULT_CONFIG).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _refs():
    registry = build_reference_registry(REPO_ROOT)
    caps = tuple(unit.unit_digest for unit in registry.units())
    cfg = _config()
    from metamorphic.contracts import digest_payload
    auth = (
        digest_payload(
            {
                "authority_ceiling": cfg["authority_ceiling"],
                "external_effects_authority": cfg["external_effects_authority"],
            }
        ),
    )
    return caps, auth


def _lease_and_snapshot():
    snapshot = build_controlled_world_snapshot(REPO_ROOT, now=FIXED_NOW)
    caps, auth = _refs()
    lease = acquire_world_lease(
        REPO_ROOT,
        snapshot=snapshot,
        composition_id="phase4-test-composition",
        capability_refs=caps,
        authority_refs=auth,
    )
    return lease, snapshot, caps, auth


def test_phase4_receipt_binds_existing_world_state_without_new_engine():
    receipt = phase4_world_lease_receipt(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE4_EXIT_TOKEN
    assert receipt["dai_world_state_reused"] is True
    assert receipt["operational_world_manifold_anchor_bound"] is True
    assert receipt["operational_world_manifold_executed"] is False
    assert receipt["new_world_state_engine_created"] is False
    assert receipt["authority_widened"] is False


def test_phase4_snapshot_is_canonical_beast_dai_world_state_snapshot():
    snapshot = build_controlled_world_snapshot(REPO_ROOT, now=FIXED_NOW)
    assert snapshot.__class__.__name__ == "WorldStateSnapshot"
    assert snapshot.__class__.__module__ == "app.kernel.dai.contracts"
    assert snapshot.snapshot_digest.startswith("sha256:")
    assert snapshot.is_current(now=FIXED_NOW) is True


def test_phase4_world_anchor_digests_bind_current_repo_bytes():
    cfg = _config()
    anchors = world_anchor_digests(REPO_ROOT, cfg)
    assert len(anchors) == 5
    for key, digest in anchors.items():
        assert digest == _sha(REPO_ROOT / cfg[key])


def test_phase4_lease_binds_exact_snapshot_epoch_policy_facts_capability_and_authority():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    validation = validate_world_lease(
        lease,
        live_snapshot=snapshot,
        live_capability_refs=caps,
        live_authority_refs=auth,
        now=FIXED_NOW,
    )
    assert validation.valid is True
    assert all(validation.gates.values())
    assert lease.snapshot_digest == snapshot.snapshot_digest
    assert lease.epoch_id == snapshot.epoch_id
    assert lease.policy_generation == snapshot.policy_generation


def test_phase4_same_inputs_produce_same_lease_identity():
    snapshot = build_controlled_world_snapshot(REPO_ROOT, now=FIXED_NOW)
    caps, auth = _refs()
    first = acquire_world_lease(REPO_ROOT, snapshot=snapshot, composition_id="same-job", capability_refs=caps, authority_refs=auth)
    second = acquire_world_lease(REPO_ROOT, snapshot=snapshot, composition_id="same-job", capability_refs=caps, authority_refs=auth)
    assert first.lease_id == second.lease_id
    assert first.lease_digest == second.lease_digest


def test_phase4_world_fact_drift_invalidates_lease():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    changed = replace(snapshot, facts={**snapshot.facts, "external_effects_authority": "ALLOW"})
    validation = validate_world_lease(lease, live_snapshot=changed, live_capability_refs=caps, live_authority_refs=auth, now=FIXED_NOW)
    assert validation.valid is False
    assert "snapshot_digest_exact" in validation.red_gates
    assert "facts_exact" in validation.red_gates


def test_phase4_epoch_drift_invalidates_lease():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    changed = replace(snapshot, epoch_id="different-epoch")
    validation = validate_world_lease(lease, live_snapshot=changed, live_capability_refs=caps, live_authority_refs=auth, now=FIXED_NOW)
    assert validation.valid is False
    assert "epoch_exact" in validation.red_gates
    assert "snapshot_digest_exact" in validation.red_gates


def test_phase4_policy_generation_drift_invalidates_lease():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    changed = replace(snapshot, policy_generation="new-policy-generation")
    validation = validate_world_lease(lease, live_snapshot=changed, live_capability_refs=caps, live_authority_refs=auth, now=FIXED_NOW)
    assert validation.valid is False
    assert "policy_generation_exact" in validation.red_gates


def test_phase4_expired_lease_is_refused():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    expired_now = datetime.fromisoformat(lease.expires_at) + timedelta(seconds=1)
    validation = validate_world_lease(lease, live_snapshot=snapshot, live_capability_refs=caps, live_authority_refs=auth, now=expired_now)
    assert validation.valid is False
    assert "lease_not_expired" in validation.red_gates
    with pytest.raises(WorldLeaseBindingError):
        require_world_lease_current(lease, live_snapshot=snapshot, live_capability_refs=caps, live_authority_refs=auth, now=expired_now)


def test_phase4_cannot_acquire_from_expired_snapshot():
    snapshot = build_controlled_world_snapshot(REPO_ROOT, now=FIXED_NOW)
    expired = replace(
        snapshot,
        observed_at=(FIXED_NOW - timedelta(minutes=30)).isoformat(),
        expires_at=(FIXED_NOW - timedelta(minutes=15)).isoformat(),
    )
    caps, auth = _refs()
    with pytest.raises(WorldLeaseBindingError):
        acquire_world_lease(REPO_ROOT, snapshot=expired, composition_id="expired", capability_refs=caps, authority_refs=auth)


def test_phase4_capability_reference_drift_invalidates_lease():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    changed_caps = caps[:-1]
    validation = validate_world_lease(lease, live_snapshot=snapshot, live_capability_refs=changed_caps, live_authority_refs=auth, now=FIXED_NOW)
    assert validation.valid is False
    assert "capability_refs_exact" in validation.red_gates


def test_phase4_authority_reference_drift_invalidates_lease():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    validation = validate_world_lease(lease, live_snapshot=snapshot, live_capability_refs=caps, live_authority_refs=("sha256:" + "0" * 64,), now=FIXED_NOW)
    assert validation.valid is False
    assert "authority_refs_exact" in validation.red_gates


def test_phase4_copied_snapshot_digest_cannot_hide_changed_facts():
    lease, snapshot, caps, auth = _lease_and_snapshot()

    class ForgedLiveSnapshot:
        snapshot_digest = snapshot.snapshot_digest
        epoch_id = snapshot.epoch_id
        policy_generation = snapshot.policy_generation
        facts = {**snapshot.facts, "forged_narrative": "same digest, different reality"}
        expires_at = snapshot.expires_at

        @staticmethod
        def is_current(now=None):
            return True

    validation = validate_world_lease(lease, live_snapshot=ForgedLiveSnapshot(), live_capability_refs=caps, live_authority_refs=auth, now=FIXED_NOW)
    assert validation.valid is False
    assert validation.gates["snapshot_digest_exact"] is True
    assert validation.gates["facts_exact"] is False


def test_phase4_semantically_similar_new_snapshot_does_not_refresh_old_lease():
    lease, snapshot, caps, auth = _lease_and_snapshot()
    new_snapshot = replace(
        snapshot,
        snapshot_id=snapshot.snapshot_id + "-narrative-refresh",
        observed_at=(FIXED_NOW + timedelta(seconds=1)).isoformat(),
        expires_at=(FIXED_NOW + timedelta(minutes=15, seconds=1)).isoformat(),
    )
    assert new_snapshot.facts == snapshot.facts
    validation = validate_world_lease(lease, live_snapshot=new_snapshot, live_capability_refs=caps, live_authority_refs=auth, now=FIXED_NOW + timedelta(seconds=1))
    assert validation.valid is False
    assert "snapshot_digest_exact" in validation.red_gates


def test_phase4_does_not_jump_ahead_to_resolver_or_composition():
    receipt = phase4_world_lease_receipt(REPO_ROOT)
    assert receipt["resolver_policy_implemented"] is False
    assert receipt["composition_dag_implemented"] is False
    assert receipt["semantic_or_narrative_refresh_authorized"] is False
