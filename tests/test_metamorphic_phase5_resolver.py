from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from metamorphic.composition import CompositionError
from metamorphic.registry import build_reference_registry
from metamorphic.resolver import (
    PHASE5_EXIT_TOKEN,
    LinguaIntent,
    LinguaOutcome,
    ResolverError,
    build_reference_intent,
    phase5_resolver_receipt,
    resolve_intent,
)
from metamorphic.semantic_law import build_reference_semantic_laws
from metamorphic.world_lease import acquire_world_lease, build_controlled_world_snapshot


REPO_ROOT = Path(__file__).resolve().parents[1]


def _context():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    intent, source_text, config = build_reference_intent(REPO_ROOT)
    snapshot = build_controlled_world_snapshot(REPO_ROOT, now=now)
    lease = acquire_world_lease(REPO_ROOT, snapshot=snapshot, composition_id=intent.intent_id)
    return now, intent, source_text, config, snapshot, lease


def _resolve(**overrides):
    now, intent, source_text, config, snapshot, lease = _context()
    args = {
        "intent": intent,
        "live_buyer_job_text": source_text,
        "world_lease": lease,
        "live_snapshot": snapshot,
        "now": now,
        "config": config,
    }
    args.update(overrides)
    return resolve_intent(REPO_ROOT, **args)


def test_phase5_receipt_proves_reference_funding_proposal_composition():
    receipt = phase5_resolver_receipt(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE5_EXIT_TOKEN
    assert receipt["reference_composite_name"] == "Funding Proposal Studio"
    assert receipt["selected_unit_count"] == 3
    assert receipt["topological_order"] == ["readiness", "proposal_narrative", "submission_correspondence"]
    assert receipt["edge_count"] == 2


def test_phase5_intent_is_bound_to_exact_buyer_job_source():
    now, intent, source_text, config, snapshot, lease = _context()
    assert intent.autonomous_natural_language_inference_claimed is False
    with pytest.raises(ResolverError, match="buyer-job source changed"):
        resolve_intent(
            REPO_ROOT,
            intent=intent,
            live_buyer_job_text=source_text + " changed after binding",
            world_lease=lease,
            live_snapshot=snapshot,
            now=now,
            config=config,
        )


def test_phase5_every_selected_capability_is_supported_by_phase3_semantic_law():
    result = _resolve()
    laws = build_reference_semantic_laws(REPO_ROOT)
    for row in result["selected_units"]:
        law = laws[row["unit_id"]]
        assert row["semantic_law_digest"] == law.law_digest
        assert any(
            affordance.get("scope") == "exported_metamorphic_capability"
            and affordance.get("capability") == row["capability"]
            and affordance.get("claim_state") == "SUPPORTED"
            for affordance in law.affordances
        )


def test_phase5_selected_nodes_preserve_phase2_unit_identity_and_native_executor():
    result = _resolve()
    registry = build_reference_registry(REPO_ROOT)
    for node in result["composition"]["nodes"]:
        unit = registry.get(node["unit_id"])
        assert node["unit_digest"] == unit.unit_digest
        assert node["executor_id"] == unit.executor_id
        assert node["executor_digest"] == unit.executor_digest
    assert {node["executor_id"] for node in result["composition"]["nodes"]} == {
        "products.studio_native_closure.close_studio_case"
    }


def test_phase5_same_bound_inputs_produce_same_resolution_and_composition_digest():
    now, intent, source_text, config, snapshot, lease = _context()
    kwargs = dict(
        intent=intent,
        live_buyer_job_text=source_text,
        world_lease=lease,
        live_snapshot=snapshot,
        now=now,
        config=config,
    )
    first = resolve_intent(REPO_ROOT, **kwargs)
    second = resolve_intent(REPO_ROOT, **kwargs)
    assert first["resolution_digest"] == second["resolution_digest"]
    assert first["composition"]["composition_digest"] == second["composition"]["composition_digest"]
    assert first["composition"]["topological_order"] == second["composition"]["topological_order"]


def test_phase5_expired_world_lease_refuses_resolution():
    now, intent, source_text, config, snapshot, lease = _context()
    after_expiry = datetime.fromisoformat(lease.expires_at) + timedelta(seconds=1)
    with pytest.raises(ResolverError, match="world lease invalid"):
        resolve_intent(
            REPO_ROOT,
            intent=intent,
            live_buyer_job_text=source_text,
            world_lease=lease,
            live_snapshot=snapshot,
            now=after_expiry,
            config=config,
        )


def test_phase5_live_world_fact_drift_refuses_resolution_before_dag():
    now, intent, source_text, config, snapshot, lease = _context()
    changed = replace(snapshot, facts={**snapshot.facts, "external_effects_authority": "ALLOW"})
    with pytest.raises(ResolverError, match="world lease invalid"):
        resolve_intent(
            REPO_ROOT,
            intent=intent,
            live_buyer_job_text=source_text,
            world_lease=lease,
            live_snapshot=changed,
            now=now,
            config=config,
        )


def test_phase5_unknown_capability_is_never_invented():
    now, intent, source_text, config, snapshot, lease = _context()
    rows = list(intent.required_outcomes)
    rows[0] = replace(rows[0], capability="guaranteed_funding_approval")
    hostile = replace(intent, required_outcomes=tuple(rows))
    with pytest.raises(ResolverError, match="no eligible semantically-supported provider"):
        resolve_intent(
            REPO_ROOT,
            intent=hostile,
            live_buyer_job_text=source_text,
            world_lease=lease,
            live_snapshot=snapshot,
            now=now,
            config=config,
        )


def test_phase5_active_negative_capability_excludes_provider():
    now, intent, source_text, config, snapshot, lease = _context()
    with pytest.raises(ResolverError, match="finance_readiness"):
        resolve_intent(
            REPO_ROOT,
            intent=intent,
            live_buyer_job_text=source_text,
            world_lease=lease,
            live_snapshot=snapshot,
            now=now,
            active_negative_unit_ids=("finance_readiness_studio",),
            config=config,
        )


def test_phase5_stale_eligibility_excludes_provider():
    now, intent, source_text, config, snapshot, lease = _context()
    with pytest.raises(ResolverError, match="article_publication"):
        resolve_intent(
            REPO_ROOT,
            intent=intent,
            live_buyer_job_text=source_text,
            world_lease=lease,
            live_snapshot=snapshot,
            now=now,
            stale_unit_ids=("article_publication_studio",),
            config=config,
        )


def test_phase5_ambiguous_eligible_providers_fail_closed():
    now, intent, source_text, config, snapshot, lease = _context()
    registry = build_reference_registry(REPO_ROOT)
    laws = build_reference_semantic_laws(REPO_ROOT)
    original = registry.get("finance_readiness_studio")
    clone = replace(original, unit_id="finance_readiness_studio_shadow")
    registry.register(clone)
    laws = dict(laws)
    laws[clone.unit_id] = replace(
        laws[original.unit_id],
        unit_id=clone.unit_id,
        unit_digest=clone.unit_digest,
    )
    # The original Phase 4 lease did not bind the newly injected capability ref,
    # so acquire a test lease against the expanded live registry contract.
    expanded_caps = tuple(unit.unit_digest for unit in registry.units())
    expanded_lease = replace(lease, capability_refs=expanded_caps)
    with pytest.raises(ResolverError, match="ambiguous eligible providers"):
        resolve_intent(
            REPO_ROOT,
            intent=intent,
            live_buyer_job_text=source_text,
            world_lease=expanded_lease,
            live_snapshot=snapshot,
            now=now,
            registry=registry,
            semantic_laws=laws,
            config=config,
        )


def test_phase5_dependency_cycle_is_refused():
    now, intent, source_text, config, snapshot, lease = _context()
    rows = list(intent.required_outcomes)
    rows[0] = replace(rows[0], depends_on=("submission_correspondence",))
    hostile = replace(intent, required_outcomes=tuple(rows))
    with pytest.raises(CompositionError, match="cycle"):
        resolve_intent(
            REPO_ROOT,
            intent=hostile,
            live_buyer_job_text=source_text,
            world_lease=lease,
            live_snapshot=snapshot,
            now=now,
            config=config,
        )


def test_phase5_missing_dependency_is_rejected_at_lingua_intent_contract():
    with pytest.raises(ValueError, match="missing dependencies"):
        LinguaIntent(
            intent_id="hostile-intent",
            buyer_job_id="job",
            buyer_job_digest="sha256:" + "0" * 64,
            buyer="buyer",
            required_outcomes=(
                LinguaOutcome(
                    outcome_id="one",
                    capability="finance_readiness",
                    meaning="test",
                    depends_on=("ghost",),
                ),
            ),
            extraction_mode="test",
            autonomous_natural_language_inference_claimed=False,
        )


def test_phase5_authority_is_intersection_only_and_all_external_effects_refuse():
    result = _resolve()
    authority = result["authority"]
    assert authority["effective_ceiling"] == "controlled_artifact_only"
    assert authority["authority_widened"] is False
    assert authority["learning_used_as_authority"] is False
    assert authority["external_effects_authorized"] is False
    assert authority["human_gate"] == "NEEDS_YOU"
    assert authority["effect_decisions"] == {
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
    }


def test_phase5_dag_is_plan_only_and_does_not_launder_future_phases():
    receipt = phase5_resolver_receipt(REPO_ROOT)
    assert receipt["composition_dag_implemented"] is True
    assert receipt["native_execution_performed"] is False
    assert receipt["sensorium_episode_started"] is False
    assert receipt["beast_crystallization_executed"] is False
    assert receipt["harmonics_executed"] is False
    assert receipt["seraph_egress_executed"] is False
    assert receipt["arda_execution_performed"] is False
    assert receipt["world_settlement_performed"] is False
    assert receipt["market_feedback_learning_executed"] is False
    assert receipt["new_engine_created"] is False
    assert receipt["authority_widened"] is False
