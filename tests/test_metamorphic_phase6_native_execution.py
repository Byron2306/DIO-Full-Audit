from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

import metamorphic.native_execution as native_execution
from metamorphic.native_execution import (
    PHASE6_EXIT_TOKEN,
    NativeExecutionError,
    execute_resolution,
    phase6_native_execution_receipt,
)
from metamorphic.registry import build_reference_registry
from metamorphic.resolver import build_reference_intent, resolve_intent
from metamorphic.world_lease import acquire_world_lease, build_controlled_world_snapshot


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase6_receipt(tmp_path_factory):
    return phase6_native_execution_receipt(
        REPO_ROOT,
        output_dir=tmp_path_factory.mktemp("phase6-native"),
    )


def _planned_context():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    intent, source_text, config = build_reference_intent(REPO_ROOT)
    snapshot = build_controlled_world_snapshot(REPO_ROOT, now=now)
    lease = acquire_world_lease(REPO_ROOT, snapshot=snapshot, composition_id=intent.intent_id)
    resolution = resolve_intent(
        REPO_ROOT,
        intent=intent,
        live_buyer_job_text=source_text,
        world_lease=lease,
        live_snapshot=snapshot,
        now=now,
        config=config,
    )
    return now, resolution, snapshot, lease


def test_phase6_receipt_executes_all_three_native_nodes(phase6_receipt):
    assert phase6_receipt["passed"] is True, phase6_receipt
    assert phase6_receipt["acceptance"] == PHASE6_EXIT_TOKEN
    assert phase6_receipt["composition_name"] == "Funding Proposal Studio"
    assert phase6_receipt["node_count"] == 3
    assert phase6_receipt["all_native_nodes_passed"] is True


def test_phase6_topological_order_and_dependency_chain_are_enforced(phase6_receipt):
    assert phase6_receipt["topological_order"] == [
        "readiness",
        "proposal_narrative",
        "submission_correspondence",
    ]
    rows = {row["node_id"]: row for row in phase6_receipt["node_receipts"]}
    assert rows["readiness"]["dependencies"] == []
    assert rows["proposal_narrative"]["dependencies"] == ["readiness"]
    assert rows["submission_correspondence"]["dependencies"] == ["proposal_narrative"]
    assert rows["proposal_narrative"]["dependency_receipts"]["readiness"] == rows["readiness"]["native_closure_fingerprint"]
    assert rows["submission_correspondence"]["dependency_receipts"]["proposal_narrative"] == rows["proposal_narrative"]["native_closure_fingerprint"]


def test_phase6_nodes_preserve_original_unit_and_executor_identity(phase6_receipt):
    registry = build_reference_registry(REPO_ROOT)
    for row in phase6_receipt["node_receipts"]:
        unit = registry.get(row["unit_id"])
        assert row["unit_digest"] == unit.unit_digest
        assert row["executor_id"] == unit.executor_id == "products.studio_native_closure.close_studio_case"
        assert row["executor_digest"] == unit.executor_digest
    assert phase6_receipt["same_unit_identity_preserved"] is True
    assert phase6_receipt["native_executors_only"] is True


def test_phase6_native_receipts_preserve_no_external_effect_boundary(phase6_receipt):
    for row in phase6_receipt["node_receipts"]:
        assert row["authority_created"] is False
        assert row["external_effects"] is False
        assert row["all_declared_capabilities_executed"] is True
        assert row["native_closure_fingerprint"].startswith("sha256:")
        assert row["proof_fingerprint"].startswith("sha256:")
        assert row["node_execution_digest"].startswith("sha256:")
    assert phase6_receipt["authority_widened"] is False
    assert phase6_receipt["external_effects"] is False


def test_phase6_sensorium_episode_is_native_evidence_only_and_complete(phase6_receipt):
    episode = phase6_receipt["sensorium_episode"]
    assert episode["beast_object_type"] == "runtime_episode"
    assert episode["authority"] == "evidence_only"
    assert episode["outcome"]["status"] == "PASS"
    assert episode["outcome"]["effect_hash"] == phase6_receipt["effect_hash"]
    assert episode["episode_hash"].startswith("sha256:")
    assert len(episode["event_ids"]) == 8
    assert len(set(episode["event_ids"])) == 8
    assert phase6_receipt["sensorium_episode_complete"] is True


def test_phase6_effect_hash_is_bound_to_node_execution_digests(phase6_receipt):
    from metamorphic.contracts import digest_payload
    expected = digest_payload(
        {
            "composition_digest": phase6_receipt["composition_digest"],
            "node_execution_digests": [
                row["node_execution_digest"] for row in phase6_receipt["node_receipts"]
            ],
        }
    )
    assert phase6_receipt["effect_hash"] == expected


def test_phase6_live_world_drift_refuses_before_native_node(monkeypatch, tmp_path):
    now, resolution, snapshot, lease = _planned_context()
    changed = replace(snapshot, facts={**snapshot.facts, "authority_ceiling": "execution_authority"})
    called = []

    def forbidden_executor(**kwargs):
        called.append(kwargs)
        raise AssertionError("native executor must not run after world drift")

    monkeypatch.setattr(native_execution, "close_studio_case", forbidden_executor)
    with pytest.raises(NativeExecutionError, match="world lease invalid before node"):
        execute_resolution(
            REPO_ROOT,
            resolution=resolution,
            world_lease=lease,
            live_snapshot=changed,
            output_dir=tmp_path,
            now=now,
        )
    assert called == []


def test_phase6_tampered_unit_identity_refuses_before_native_node(monkeypatch, tmp_path):
    now, resolution, snapshot, lease = _planned_context()
    hostile = deepcopy(resolution)
    hostile["composition"]["nodes"][0]["unit_digest"] = "sha256:" + "0" * 64
    called = []

    def forbidden_executor(**kwargs):
        called.append(kwargs)
        raise AssertionError("tampered unit must not execute")

    monkeypatch.setattr(native_execution, "close_studio_case", forbidden_executor)
    with pytest.raises(NativeExecutionError, match="unit identity drift"):
        execute_resolution(
            REPO_ROOT,
            resolution=hostile,
            world_lease=lease,
            live_snapshot=snapshot,
            output_dir=tmp_path,
            now=now,
        )
    assert called == []


def test_phase6_tampered_executor_identity_refuses_before_native_node(monkeypatch, tmp_path):
    now, resolution, snapshot, lease = _planned_context()
    hostile = deepcopy(resolution)
    hostile["composition"]["nodes"][0]["executor_id"] = "invented.executor"
    called = []

    def forbidden_executor(**kwargs):
        called.append(kwargs)
        raise AssertionError("tampered executor must not execute")

    monkeypatch.setattr(native_execution, "close_studio_case", forbidden_executor)
    with pytest.raises(NativeExecutionError, match="native executor identity drift"):
        execute_resolution(
            REPO_ROOT,
            resolution=hostile,
            world_lease=lease,
            live_snapshot=snapshot,
            output_dir=tmp_path,
            now=now,
        )
    assert called == []


def test_phase6_child_failure_is_not_laundered_as_composite_success(monkeypatch, tmp_path):
    now, resolution, snapshot, lease = _planned_context()
    calls = []

    def controlled_executor(*, manifest_path, output_dir, root):
        calls.append(manifest_path.name)
        if len(calls) == 2:
            raise RuntimeError("controlled native child failure")
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "output_dir": str(output_dir),
            "proof_manifest": {},
            "receipt": {
                "native_capability_closure": "PASS",
                "native_closure_fingerprint": "sha256:" + "1" * 64,
                "proof_fingerprint": "sha256:" + "2" * 64,
                "all_declared_capabilities_executed": True,
                "authority_created": False,
                "external_effects": False,
                "external_publication": "REFUSE",
                "external_send": "REFUSE",
                "media_spend": "REFUSE",
                "payment": "REFUSE",
            },
        }

    monkeypatch.setattr(native_execution, "close_studio_case", controlled_executor)
    monkeypatch.setattr(native_execution, "verify_native_closure_proof", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="controlled native child failure"):
        execute_resolution(
            REPO_ROOT,
            resolution=resolution,
            world_lease=lease,
            live_snapshot=snapshot,
            output_dir=tmp_path,
            now=now,
        )
    assert len(calls) == 2


def test_phase6_does_not_overclaim_content_level_composite_dataflow(phase6_receipt):
    assert phase6_receipt["dependency_order_enforced"] is True
    assert phase6_receipt["content_transform_dataflow_proved"] is False


def test_phase6_does_not_jump_to_learning_egress_execution_or_settlement(phase6_receipt):
    for key in (
        "beast_crystallization_executed",
        "harmonics_executed",
        "seraph_egress_executed",
        "arda_execution_performed",
        "world_settlement_performed",
        "market_feedback_learning_executed",
    ):
        assert phase6_receipt[key] is False
    assert phase6_receipt["new_engine_created"] is False
