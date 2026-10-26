from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from adapters.beast.metamorphic_crystallisation import crystallize_settled_composition
from products.funding_proposal_studio import (
    COMPOSITE_CAPABILITY,
    COMPOSITE_UNIT_ID,
    build_funding_proposal_metamorphic_unit,
)

from .boundary_closure import phase8_boundary_closure_receipt
from .contracts import MetamorphicRole
from .integration_inventory import validate_integration_inventory
from .registry import build_reference_registry, phase2_identity_receipt
from .semantic_law import phase3_semantic_receipt
from .settlement import settle_boundary_episode
from .world_lease import phase4_world_lease_receipt
from .resolver import phase5_resolver_receipt
from .contracts import phase1_contract_receipt


PHASE9_EXIT_TOKEN = "DIO_METAMORPHIC_SPINE_M1_VERIFIED"
M2_REQUIRED_TOKEN = "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED"


def _run_phase9(repo_root: Path, work_root: Path) -> dict[str, Any]:
    phase0 = validate_integration_inventory(repo_root)
    phase1 = phase1_contract_receipt(repo_root)
    phase2 = phase2_identity_receipt(repo_root)
    phase3 = phase3_semantic_receipt(repo_root)
    phase4 = phase4_world_lease_receipt(repo_root)
    phase5 = phase5_resolver_receipt(repo_root)

    boundary = phase8_boundary_closure_receipt(
        repo_root,
        work_root=work_root / "phase8_boundary",
    )
    settlement_result = settle_boundary_episode(
        repo_root,
        boundary_receipt=boundary,
    )
    crystal = crystallize_settled_composition(
        repo_root,
        settlement_result=settlement_result,
        boundary_receipt=boundary,
        state_root=work_root / "beast_crystal",
    )

    registry = build_reference_registry(repo_root)
    registry_count_before = len(registry.units())
    composite_unit = build_funding_proposal_metamorphic_unit(repo_root)
    registered = registry.register(composite_unit)
    product_view = registry.as_role(COMPOSITE_UNIT_ID, MetamorphicRole.PRODUCT)
    capability_view = registry.as_role(COMPOSITE_UNIT_ID, MetamorphicRole.CAPABILITY)
    providers = registry.providers_for(COMPOSITE_CAPABILITY)
    registry_count_after = len(registry.units())

    same_composite_identity = (
        registered is composite_unit
        and product_view is composite_unit
        and capability_view is composite_unit
        and product_view.unit_digest == capability_view.unit_digest == composite_unit.unit_digest
    )
    provider_reentry = any(unit is composite_unit for unit in providers)

    wrapper_path = repo_root / "products/funding_proposal_studio.py"
    wrapper_source = wrapper_path.read_text(encoding="utf-8")
    no_bespoke_duplicate_engine = (
        "resolve_intent(" in wrapper_source
        and "execute_resolution(" in wrapper_source
        and "close_studio_case(" not in wrapper_source
        and composite_unit.executor_id == "products.funding_proposal_studio.run_funding_proposal_studio"
    )

    phase3_units = list(phase3.get("units") or [])
    affordance_prohibition_bound = bool(
        phase3_units
        and all(int(row.get("affordance_count") or 0) > 0 for row in phase3_units)
        and all(int(row.get("prohibition_count") or 0) > 0 for row in phase3_units)
        and all(row.get("authority_prohibitions_complete") is True for row in phase3_units)
        and all(row.get("professional_claim_boundaries_complete") is True for row in phase3_units)
        and composite_unit.semantic_contract.get("affordances")
        and composite_unit.semantic_contract.get("prohibitions")
    )

    gates = {
        "METAMORPHIC_UNIT_SCHEMA_VALID": (
            phase1.get("passed") is True
            and composite_unit.schema == "dio.metamorphic_unit.v1"
        ),
        "SAME_UNIT_PRODUCT_AND_CAPABILITY": (
            phase2.get("same_unit_product_and_capability") is True
            and same_composite_identity
        ),
        "LINGUA_SEMANTIC_LAW_BOUND": (
            phase3.get("passed") is True
            and phase3.get("semantic_law_promoted") is True
        ),
        "AFFORDANCE_PROHIBITION_BOUND": affordance_prohibition_bound,
        "DETERMINISTIC_RESOLUTION": (
            phase5.get("passed") is True
            and phase5.get("resolver_deterministic") is True
        ),
        "COMPOSITION_DAG_VALID": phase5.get("composition_dag_implemented") is True,
        "WORLD_LEASE_CURRENT": (
            phase4.get("lease_current") is True
            and boundary.get("world_lease_digest") is not None
        ),
        "WORLD_STATE_DIGEST_BOUND": (
            phase4.get("exact_snapshot_digest_required") is True
            and str(boundary.get("pre_world_digest") or "").startswith("sha256:")
            and str(settlement_result.settlement.post_world_digest or "").startswith("sha256:")
        ),
        "NATIVE_EXECUTORS_ONLY": boundary.get("native_executors_only") is True,
        "NODE_RECEIPTS_COMPLETE": boundary.get("node_receipts_complete") is True,
        "LINEAGE_PRESERVED": (
            boundary.get("same_unit_identity_preserved") is True
            and same_composite_identity
        ),
        "NO_AUTHORITY_ESCALATION": (
            boundary.get("authority_widened") is False
            and boundary.get("learning_used_as_authority") is False
            and settlement_result.settlement.authority_preserved is True
            and crystal.get("authority_created") is False
        ),
        "QUALITY_CONTRACTS_PRESERVED": boundary.get("quality_contracts_preserved") is True,
        "SENSORIUM_EPISODE_COMPLETE": str(boundary.get("sensorium_episode_hash") or "").startswith("sha256:"),
        "VNS_WITNESS_EXPLICIT": (
            boundary.get("vns_witness_explicit") is True
            and boundary.get("vns_witness_state") == "NOT_APPLICABLE"
        ),
        "HARMONIC_STATE_BOUND": (
            boundary.get("harmonics_executed") is True
            and boundary.get("harmonic_state_is_authority") is False
        ),
        "SERAPH_EGRESS_BOUND": (
            boundary.get("seraph_egress_bound") is True
            and boundary.get("seraph_verdict") == "REFUSE"
        ),
        "ARDA_EXECUTION_EVIDENCE_BOUND": boundary.get("arda_execution_evidence_bound") is True,
        "WORLD_SETTLEMENT_COMPLETE": settlement_result.passed,
        "CRYSTALLISATION_GATED": (
            crystal.get("beast_crystallization_executed") is True
            and crystal.get("world_settlement_required") is True
            and crystal.get("crystal_chain_valid") is True
            and crystal.get("settlement_digest") == settlement_result.settlement.settlement_digest
        ),
        "COMPOSITE_PRODUCT_EMERGED": (
            composite_unit.unit_id == COMPOSITE_UNIT_ID
            and COMPOSITE_CAPABILITY in composite_unit.provides
            and MetamorphicRole.PRODUCT in composite_unit.roles
            and MetamorphicRole.CAPABILITY in composite_unit.roles
        ),
        "COMPOSITE_CAN_REENTER_REGISTRY": (
            registry_count_before == 3
            and registry_count_after == 4
            and same_composite_identity
            and provider_reentry
        ),
        "NO_BESPOKE_DUPLICATE_ENGINE": no_bespoke_duplicate_engine,
    }
    passed = (
        phase0.get("passed") is True
        and all(gates.values())
        and boundary.get("external_effects") is False
        and boundary.get("external_effects_authorized") is False
        and crystal.get("external_effects") is False
    )

    return {
        "phase": 9,
        "acceptance": PHASE9_EXIT_TOKEN if passed else "DIO_METAMORPHIC_SPINE_M1_BLOCKED",
        "passed": passed,
        "acceptance_gates": gates,
        "acceptance_gate_count": len(gates),
        "acceptance_gate_pass_count": sum(1 for value in gates.values() if value),
        "phase0_acceptance": phase0.get("acceptance"),
        "phase1_acceptance": phase1.get("acceptance"),
        "phase2_acceptance": phase2.get("acceptance"),
        "phase3_acceptance": phase3.get("acceptance"),
        "phase4_acceptance": phase4.get("acceptance"),
        "phase5_acceptance": phase5.get("acceptance"),
        "phase8_acceptance": boundary.get("acceptance"),
        "composition_name": boundary.get("composition_name"),
        "composition_digest": boundary.get("composition_digest"),
        "effect_hash": boundary.get("effect_hash"),
        "world_settlement": settlement_result.to_dict(),
        "world_settlement_complete": settlement_result.passed,
        "settlement_digest": settlement_result.settlement.settlement_digest,
        "beast_crystal": crystal,
        "beast_crystallization_executed": crystal.get("beast_crystallization_executed"),
        "composite_unit": {
            "unit_id": composite_unit.unit_id,
            "unit_digest": composite_unit.unit_digest,
            "roles": [role.value for role in composite_unit.roles],
            "provides": list(composite_unit.provides),
            "requires": list(composite_unit.requires),
            "executor_id": composite_unit.executor_id,
            "authority_ceiling": composite_unit.authority_ceiling,
            "maturity_state": composite_unit.maturity_state,
        },
        "registry_count_before": registry_count_before,
        "registry_count_after": registry_count_after,
        "expanded_registry_fingerprint": registry.registry_fingerprint,
        "same_composite_identity_across_roles": same_composite_identity,
        "composite_provider_reentry": provider_reentry,
        "no_bespoke_duplicate_engine": no_bespoke_duplicate_engine,
        "content_transform_dataflow_proved": bool(boundary.get("content_transform_dataflow_proved", False)),
        "authority_widened": False,
        "external_effects": False,
        "new_engine_created": False,
        "m2_required_next": True,
        "m2_required_acceptance": M2_REQUIRED_TOKEN,
        "m2_verified": False,
        "programme_complete": False,
    }


def phase9_m1_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase9(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-metamorphic-phase9-") as temp:
        return _run_phase9(root, Path(temp))
