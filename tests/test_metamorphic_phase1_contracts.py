import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from metamorphic.contracts import (
    LayerWitnessState,
    MetamorphicRole,
    MetamorphicUnit,
    PHASE1_EXIT_TOKEN,
    SettlementState,
    WorldLease,
    WorldSettlement,
    digest_payload,
    phase1_contract_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
D1 = "sha256:" + "1" * 64
D2 = "sha256:" + "2" * 64
D3 = "sha256:" + "3" * 64


def _unit(**overrides):
    payload = dict(
        unit_id="professional_correspondence_studio",
        version="1.0.0",
        source_digest=D1,
        roles=(MetamorphicRole.PRODUCT, MetamorphicRole.CAPABILITY),
        provides=("professional_correspondence", "submission_email"),
        requires=(),
        executor_id="professional_correspondence_studio.native",
        executor_version="1",
        executor_digest=D2,
        input_contract={"kind": "messy_source_material"},
        output_contract={"kind": "governed_correspondence"},
        evidence_contract={"native_receipts_required": True},
        quality_contract={"product_grade_required": True},
        semantic_contract={
            "denotation": ["governed professional correspondence capability"],
            "affordances": ["draft correspondence from supplied facts"],
            "prohibitions": ["do not invent customer facts"],
            "projections": {"buyer": "Professional correspondence from your source material."},
        },
        buyer_projection={"default": "Professional Correspondence Studio", "variants": {}},
        maturity_state="professionally_proven",
        authority_ceiling="controlled_artifact_only",
        applicability_fingerprints={
            "policy": (), "audience": (), "curriculum": (),
            "privacy": (), "market": (), "runtime": (),
        },
        promotion_rules={"human_authority_preserved": True},
    )
    payload.update(overrides)
    return MetamorphicUnit(**payload)


def _lease(**overrides):
    payload = dict(
        lease_id="lease:test:001",
        composition_id="composition:test:001",
        snapshot_digest=D1,
        epoch_id="epoch:test:001",
        observed_at="2099-01-01T00:00:00+00:00",
        expires_at="2099-01-01T00:05:00+00:00",
        policy_generation="metamorphic-phase1-policy",
        facts_refs=("facts:test",),
        market_state_refs=(),
        network_state_refs=(),
        capability_refs=("capability:test",),
        authority_refs=("authority:test",),
        customer_refs=(),
    )
    payload.update(overrides)
    return WorldLease(**payload)


def _settlement(**overrides):
    payload = dict(
        settlement_id="settlement:test:001",
        episode_id="episode:test:001",
        pre_world_digest=D1,
        post_world_digest=D2,
        expected_effects=("controlled_artifact_created",),
        observed_effects=("controlled_artifact_created",),
        sensorium_receipts=("sensorium:test",),
        vns_receipts=(),
        arda_receipts=("arda:test",),
        seraph_receipts=(),
        harmonic_before={"state": "NORMAL_FLOW"},
        harmonic_after={"state": "NORMAL_FLOW"},
        authority_preserved=True,
        unexpected_effects=(),
        settlement_state=SettlementState.SETTLED,
    )
    payload.update(overrides)
    return WorldSettlement(**payload)


def test_phase1_schema_files_parse_and_receipt_is_ready():
    receipt = phase1_contract_receipt(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE1_EXIT_TOKEN
    assert receipt["schema_count"] == 3
    for relative in receipt["schemas"]:
        payload = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_metamorphic_unit_digest_is_deterministic_and_role_stable():
    left = _unit()
    right = _unit()
    assert left.unit_digest == right.unit_digest
    assert left.to_dict()["roles"] == ["product", "capability"]
    assert left.to_dict()["unit_digest"] == left.unit_digest


def test_metamorphic_unit_content_change_changes_digest():
    baseline = _unit()
    changed = _unit(authority_ceiling="observation_only")
    assert baseline.unit_digest != changed.unit_digest


def test_metamorphic_unit_rejects_malformed_digest_and_duplicate_role():
    with pytest.raises(ValueError):
        _unit(source_digest="not-a-digest")
    with pytest.raises(ValueError):
        _unit(roles=(MetamorphicRole.PRODUCT, MetamorphicRole.PRODUCT))


def test_contract_objects_are_immutable():
    unit = _unit()
    with pytest.raises(FrozenInstanceError):
        unit.unit_id = "mutated"  # type: ignore[misc]


def test_world_lease_digest_binds_authority_refs_and_expiry():
    baseline = _lease()
    changed = _lease(authority_refs=("authority:changed",))
    assert baseline.lease_digest != changed.lease_digest
    assert baseline.is_current(now=datetime(2099, 1, 1, 0, 1, tzinfo=timezone.utc)) is True
    assert baseline.is_current(now=datetime(2099, 1, 1, 0, 6, tzinfo=timezone.utc)) is False


def test_world_lease_rejects_non_forward_expiry():
    with pytest.raises(ValueError):
        _lease(expires_at="2099-01-01T00:00:00+00:00")


def test_world_settlement_digest_is_deterministic_and_state_is_closed():
    left = _settlement()
    right = _settlement()
    assert left.settlement_digest == right.settlement_digest
    assert left.to_dict()["settlement_state"] == "SETTLED"
    with pytest.raises(ValueError):
        _settlement(settlement_state="MAGIC_SUCCESS")


def test_layer_witness_vocabulary_is_exact_and_closed():
    assert tuple(state.value for state in LayerWitnessState) == (
        "EXERCISED",
        "CORROBORATED",
        "ARMED",
        "NOT_APPLICABLE",
        "MISSING",
        "FAILED",
    )
    with pytest.raises(ValueError):
        LayerWitnessState("SILENT_BUT_FINE")


def test_canonical_digest_is_order_insensitive_for_mapping_keys():
    assert digest_payload({"b": 2, "a": 1}) == digest_payload({"a": 1, "b": 2})
