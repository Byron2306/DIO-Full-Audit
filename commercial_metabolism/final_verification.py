"""M2 Phase 9 repeatability gauntlet and final commercial-metabolism verification.

This phase verifies the metabolism, not commercial success. It composes the
previous M2 receipts, attacks the epistemic boundaries around willingness to pay
and repeatability, maps the programme's sixteen frozen acceptance gates, and may
mint the final M2 verification token only when authority and truth remain intact.

A controlled fixture can prove that DIO knows how to observe, bind, settle,
crystallize and adapt commercial evidence. It cannot prove that the market wants
the product. Those are deliberately different propositions.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from metamorphic.contracts import digest_payload, require_digest

from .authority import M2_PHASE3_EXIT_TOKEN, phase3_authority_receipt
from .constitution import M2_PHASE0_EXIT_TOKEN, validate_commercial_constitution
from .contracts import (
    CommercialSettlement,
    CommercialSettlementState,
    CustomerIndependence,
    EvidenceClaimState,
    M2_PHASE1_EXIT_TOKEN,
    MarketObservation,
    MarketObservationKind,
    SettlementOutcome,
    phase1_contract_receipt,
)
from .episode import M2_PHASE4_EXIT_TOKEN, phase4_market_episode_receipt
from .learning import M2_PHASE8_EXIT_TOKEN, phase8_projection_adaptation_receipt
from .lineage import M2_PHASE6_EXIT_TOKEN, phase6_customer_payment_lineage_receipt
from .observation import M2_PHASE5_EXIT_TOKEN, phase5_market_observation_receipt
from .projection import M2_PHASE2_EXIT_TOKEN, phase2_projection_receipt
from .settlement import M2_PHASE7_EXIT_TOKEN, phase7_commercial_settlement_receipt


M2_PHASE9_EXIT_TOKEN = "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED"
M2_PHASE9_BLOCKED_TOKEN = "DIO_M2_COMMERCIAL_METABOLISM_BLOCKED"
DEFAULT_FINAL_CONFIG = "config/m2_phase9_final_verification.json"
FINAL_RECEIPT_SCHEMA_FILE = "schemas/dio.commercial_metabolism_final_receipt.v1.json"
FINAL_RECEIPT_SCHEMA_ID = "dio.commercial_metabolism_final_receipt.v1"

FINAL_GATES = (
    "COMMERCIAL_CONTEXT_BOUND",
    "MARKET_CRYSTAL_SCHEMA_VALID",
    "CLAIM_EVIDENCE_BOUND",
    "UNPROVEN_CLAIMS_REFUSED",
    "CHANNEL_AUTHORITY_SEPARATE",
    "SPEND_AUTHORITY_SEPARATE",
    "PAYMENT_LINEAGE_BOUND",
    "CUSTOMER_LINEAGE_BOUND",
    "MARKET_RESPONSE_OBSERVED",
    "NO_RESPONSE_CAN_BE_RECORDED",
    "LOSS_CAN_BE_RECORDED",
    "WORLD_SETTLEMENT_COMPLETE",
    "LINGUA_PROJECTION_CAN_UPDATE",
    "NEGATIVE_MARKET_LEARNING_CONTEXT_BOUND",
    "NO_AUTHORITY_FROM_COMMERCIAL_SUCCESS",
    "REPEATABILITY_NOT_OVERCLAIMED",
)

EXPECTED_PHASE_ACCEPTANCES = {
    "M2-0": M2_PHASE0_EXIT_TOKEN,
    "M2-1": M2_PHASE1_EXIT_TOKEN,
    "M2-2": M2_PHASE2_EXIT_TOKEN,
    "M2-3": M2_PHASE3_EXIT_TOKEN,
    "M2-4": M2_PHASE4_EXIT_TOKEN,
    "M2-5": M2_PHASE5_EXIT_TOKEN,
    "M2-6": M2_PHASE6_EXIT_TOKEN,
    "M2-7": M2_PHASE7_EXIT_TOKEN,
    "M2-8": M2_PHASE8_EXIT_TOKEN,
}


class CommercialMetabolismFinalVerificationError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialMetabolismFinalVerificationError(f"cannot load M2-9 source: {path}") from exc
    if not isinstance(value, dict):
        raise CommercialMetabolismFinalVerificationError(f"M2-9 source must be an object: {path}")
    return value


def _load_config(root: Path) -> dict[str, Any]:
    value = _load_json(root / DEFAULT_FINAL_CONFIG)
    if value.get("schema") != "dio.m2.final_verification_config.v1":
        raise CommercialMetabolismFinalVerificationError("unsupported M2-9 final verification config")
    if value.get("required_parent_acceptance") != M2_PHASE8_EXIT_TOKEN:
        raise CommercialMetabolismFinalVerificationError("M2-9 parent acceptance diverged")
    if value.get("final_acceptance") != M2_PHASE9_EXIT_TOKEN:
        raise CommercialMetabolismFinalVerificationError("M2-9 final acceptance token diverged")
    if tuple(value.get("required_gates") or ()) != FINAL_GATES:
        raise CommercialMetabolismFinalVerificationError("M2-9 frozen gate set or ordering diverged")
    if value.get("commercial_success_required_for_metabolism_verification") is not False:
        raise CommercialMetabolismFinalVerificationError("M2-9 must separate framework verification from commercial success")
    if value.get("controlled_fixture_may_prove_market_validation") is not False:
        raise CommercialMetabolismFinalVerificationError("controlled fixture may not prove market validation")
    if value.get("controlled_fixture_may_prove_repeatability") is not False:
        raise CommercialMetabolismFinalVerificationError("controlled fixture may not prove repeatability")
    if value.get("content_transform_dataflow_required_for_m2") is not False:
        raise CommercialMetabolismFinalVerificationError("M3 content-dataflow proof may not be smuggled into M2")
    if value.get("content_transform_dataflow_reserved_for_m3") is not True:
        raise CommercialMetabolismFinalVerificationError("M2-9 must preserve the M3 content-dataflow boundary")
    adversary = value.get("repeatability_adversary")
    if not isinstance(adversary, dict):
        raise CommercialMetabolismFinalVerificationError("repeatability adversary config is required")
    if int(adversary.get("controlled_replay_count") or 0) != 3:
        raise CommercialMetabolismFinalVerificationError("repeatability adversary requires three controlled replays")
    if int(adversary.get("minimum_distinct_independent_customers_for_structural_repeatability") or 0) != 3:
        raise CommercialMetabolismFinalVerificationError("repeatability structural threshold diverged")
    return value


def _schema_valid(root: Path) -> bool:
    path = root / FINAL_RECEIPT_SCHEMA_FILE
    if not path.is_file():
        return False
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        and schema.get("$id") == FINAL_RECEIPT_SCHEMA_ID
    )


def _phase_chain(root: Path, work_root: Path) -> dict[str, dict[str, Any]]:
    """Re-run each proof surface once for final-gate evidence.

    Individual phase implementations also verify their own parent chains. The
    duplication is intentional here: M2-9 is an adversarial gauntlet, not a cached
    summary of earlier success.
    """
    return {
        "M2-0": validate_commercial_constitution(root),
        "M2-1": phase1_contract_receipt(root),
        "M2-2": phase2_projection_receipt(root, work_root=work_root / "phase2"),
        "M2-3": phase3_authority_receipt(root, work_root=work_root / "phase3"),
        "M2-4": phase4_market_episode_receipt(root, work_root=work_root / "phase4"),
        "M2-5": phase5_market_observation_receipt(root, work_root=work_root / "phase5"),
        "M2-6": phase6_customer_payment_lineage_receipt(root),
        "M2-7": phase7_commercial_settlement_receipt(root, work_root=work_root / "phase7"),
        "M2-8": phase8_projection_adaptation_receipt(root, work_root=work_root / "phase8"),
    }


def _phase_chain_valid(receipts: Mapping[str, Mapping[str, Any]]) -> bool:
    return all(
        phase in receipts
        and receipts[phase].get("passed") is True
        and receipts[phase].get("acceptance") == expected
        for phase, expected in EXPECTED_PHASE_ACCEPTANCES.items()
    )


def _loss_observation(context_digest: str) -> MarketObservation:
    require_digest(context_digest, field_name="context_digest")
    return MarketObservation(
        observation_id="M2-P9-CONTROLLED-LOSS",
        context_digest=context_digest,
        observed_at="2026-08-18T06:00:00+00:00",
        kind=MarketObservationKind.LOSS,
        source="m2_phase9_controlled_adversary",
        source_ref="m2:p9:loss-recordability",
        window_start="2026-08-18T05:00:00+00:00",
        window_end="2026-08-18T06:00:00+00:00",
        window_closed=True,
        evidence_refs=(digest_payload({"fixture": "m2-p9-controlled-loss"}),),
    )


def _contract_refuses_underpowered_repeatability(context_digest: str) -> bool:
    require_digest(context_digest, field_name="context_digest")
    digests = {
        name: digest_payload({"m2_phase9": name})
        for name in ("observation", "world", "customer", "payment")
    }
    try:
        CommercialSettlement(
            settlement_id="M2-P9-UNDERPOWERED-REPEATABILITY",
            context_digest=context_digest,
            settled_at="2026-08-18T07:00:00+00:00",
            settlement_state=CommercialSettlementState.SETTLED,
            outcome=SettlementOutcome.GAIN,
            market_observation_digests=(digests["observation"],),
            customer_independence=CustomerIndependence.INDEPENDENT_EXTERNAL,
            verified_payment=EvidenceClaimState.PROVED,
            customer_acceptance=EvidenceClaimState.PROVED,
            willingness_to_pay=EvidenceClaimState.PROVED,
            repeatability=EvidenceClaimState.PROVED,
            validated_engagement_count=1,
            distinct_independent_customer_count=1,
            world_settlement_digest=digests["world"],
            customer_lineage_digest=digests["customer"],
            payment_lineage_digest=digests["payment"],
            authority_preserved=True,
            authority_created=False,
        )
    except ValueError:
        return True
    return False


def _repeatability_adversary(
    *,
    config: Mapping[str, Any],
    phase5: Mapping[str, Any],
    phase6: Mapping[str, Any],
    phase7: Mapping[str, Any],
    phase8: Mapping[str, Any],
    phase3: Mapping[str, Any],
) -> dict[str, Any]:
    rows = phase6.get("controlled_lineage_scenarios")
    if not isinstance(rows, list) or len(rows) != 4:
        raise CommercialMetabolismFinalVerificationError("M2-9 requires four M2-6 controlled lineage scenarios")
    by_id = {str(row.get("scenario_id") or ""): row for row in rows if isinstance(row, Mapping)}
    structural = by_id.get("independent_paid_acceptance_structural_gate") or {}
    structural_truth = str(structural.get("truth_digest") or "")
    require_digest(structural_truth, field_name="structural_truth_digest")
    replay_count = int((config.get("repeatability_adversary") or {}).get("controlled_replay_count") or 0)
    replayed_truth = [structural_truth for _ in range(replay_count)]
    distinct_replayed_truth = len(set(replayed_truth))

    loss = _loss_observation(str(phase8.get("context_digest") or ""))
    non_authority = phase3.get("non_authority_influence_check") or {}
    cases = {
        "single_structural_gain_not_repeatability": (
            structural.get("structural_wtp_gate_satisfied") is True
            and structural.get("repeatability_proved") is False
            and phase7.get("repeatability_proved") is False
        ),
        "same_controlled_fixture_replay_not_distinct_market_repeatability": (
            replay_count == 3
            and distinct_replayed_truth == 1
            and phase7.get("real_market_evidence") is False
            and phase7.get("repeatability_proved") is False
        ),
        "payment_without_acceptance_not_wtp": (
            by_id.get("verified_payment_without_acceptance", {}).get("structural_wtp_gate_satisfied") is False
            and phase6.get("payment_only_wtp_gate") is False
        ),
        "acceptance_without_payment_not_wtp": (
            by_id.get("independent_acceptance_without_payment", {}).get("structural_wtp_gate_satisfied") is False
            and phase6.get("independent_acceptance_without_payment_wtp_gate") is False
        ),
        "operator_self_paid_acceptance_not_wtp": (
            by_id.get("operator_self_paid_acceptance", {}).get("structural_wtp_gate_satisfied") is False
            and phase6.get("operator_self_payment_wtp_gate") is False
        ),
        "closed_silence_recordable_without_global_failure": (
            phase5.get("no_response_observed_in_controlled_fixture") is True
            and phase5.get("no_response_window_closed") is True
            and phase5.get("silence_globally_invalidates_product") is False
        ),
        "loss_recordable_without_global_failure": (
            loss.kind is MarketObservationKind.LOSS
            and loss.window_closed is True
            and phase5.get("negative_response_globally_invalidates_product") is False
        ),
        "commercial_success_does_not_create_authority": (
            non_authority.get("authority_created") is False
            and non_authority.get("authority_widened") is False
            and non_authority.get("any_effect_allowed") is False
            and phase7.get("all_market_crystals_evidence_only") is True
            and phase8.get("authority_created") is False
        ),
    }
    configured_cases = tuple((config.get("repeatability_adversary") or {}).get("cases") or ())
    if tuple(cases) != configured_cases:
        raise CommercialMetabolismFinalVerificationError("repeatability adversary case set or ordering diverged")
    underpowered_refused = _contract_refuses_underpowered_repeatability(str(phase8.get("context_digest") or ""))
    passed_count = sum(value is True for value in cases.values())
    return {
        "case_count": len(cases),
        "passed_case_count": passed_count,
        "all_cases_passed": passed_count == len(cases) and underpowered_refused,
        "cases": cases,
        "controlled_replay_count": replay_count,
        "distinct_replayed_truth_count": distinct_replayed_truth,
        "same_fixture_replay_is_repeatability": False,
        "contract_refuses_underpowered_repeatability": underpowered_refused,
    }


def _acceptance_gates(
    receipts: Mapping[str, Mapping[str, Any]],
    adversary: Mapping[str, Any],
) -> tuple[dict[str, bool], dict[str, Any]]:
    p1 = receipts["M2-1"]
    p2 = receipts["M2-2"]
    p3 = receipts["M2-3"]
    p4 = receipts["M2-4"]
    p5 = receipts["M2-5"]
    p6 = receipts["M2-6"]
    p7 = receipts["M2-7"]
    p8 = receipts["M2-8"]

    hostile = p2.get("hostile_guard_results") or {}
    unproved_claims_refused = (
        int(p8.get("held_market_claim_count") or 0) == 6
        and p8.get("market_claim_upgrade_performed") is False
        and isinstance(hostile, Mapping)
        and bool(hostile)
        and all(isinstance(row, Mapping) and row.get("safe_by_configured_guard") is False for row in hostile.values())
    )
    claim_evidence_bound = (
        p2.get("projection_schema_valid") is True
        and str(p2.get("m1_projection_proof_anchor") or "").startswith("sha256:")
        and int(p2.get("supported_claim_count") or 0) >= 5
        and p2.get("deterministic_phrase_guard_only") is True
    )
    market_crystal_schema_valid = (
        p7.get("settlement_bundle_schema_valid") is True
        and p7.get("market_crystal_created") is True
        and p7.get("market_crystal_chain_valid") is True
        and int(p7.get("market_crystal_count") or 0) == 4
        and all(
            isinstance(bundle, Mapping)
            and (bundle.get("beast_market_crystal") or {}).get("schema") == "dio.m2.beast_market_crystal.v1"
            for bundle in (p7.get("settlement_bundles") or [])
        )
    )
    gates = {
        "COMMERCIAL_CONTEXT_BOUND": (
            p1.get("world_binding_required") is True
            and str(p2.get("context_digest") or "").startswith("sha256:")
            and p6.get("all_lineage_context_bound") is True
            and p8.get("negative_learning_context_bound") is True
        ),
        "MARKET_CRYSTAL_SCHEMA_VALID": market_crystal_schema_valid,
        "CLAIM_EVIDENCE_BOUND": claim_evidence_bound,
        "UNPROVEN_CLAIMS_REFUSED": unproved_claims_refused,
        "CHANNEL_AUTHORITY_SEPARATE": (
            p3.get("capability_is_authority") is False
            and p3.get("effect_authority_slots_separate") is True
            and p3.get("all_external_effects_refused") is True
            and p3.get("seraph_owns_external_effect_authority") is True
        ),
        "SPEND_AUTHORITY_SEPARATE": (
            p3.get("conversion_is_spend_authority") is False
            and p4.get("market_command_automatic_spend") == "off"
            and int(p4.get("market_command_budget_cap_minor") or 0) == 0
            and p4.get("activation_performed") is False
        ),
        "PAYMENT_LINEAGE_BOUND": (
            p6.get("customer_payment_lineage_distinct") is True
            and p6.get("payment_observations_lineage_bound") is True
            and p6.get("verified_payment_still_wtp_unproved_without_acceptance") is True
        ),
        "CUSTOMER_LINEAGE_BOUND": (
            p6.get("customer_payment_lineage_distinct") is True
            and p6.get("acceptance_observations_lineage_bound") is True
            and p6.get("acceptance_artifact_bound") is True
        ),
        "MARKET_RESPONSE_OBSERVED": (
            p5.get("controlled_market_response_paths_exercised") is True
            and p5.get("positive_response_observed_in_controlled_fixture") is True
            and p5.get("negative_response_observed_in_controlled_fixture") is True
            and p5.get("real_market_response_observed") is False
        ),
        "NO_RESPONSE_CAN_BE_RECORDED": (
            p1.get("no_response_requires_closed_window") is True
            and p5.get("no_response_observed_in_controlled_fixture") is True
            and p5.get("no_response_window_closed") is True
        ),
        "LOSS_CAN_BE_RECORDED": adversary.get("cases", {}).get("loss_recordable_without_global_failure") is True,
        "WORLD_SETTLEMENT_COMPLETE": (
            p1.get("market_crystal_requires_settlement") is True
            and p7.get("world_settlement_complete") is True
            and p7.get("commercial_settlement_complete") is True
            and p7.get("commercial_and_world_settlement_bound_to_crystals") is True
        ),
        "LINGUA_PROJECTION_CAN_UPDATE": (
            p8.get("lingua_existing_organ_reused") is True
            and p8.get("lingua_projection_can_update") is True
            and p8.get("market_claim_upgrade_performed") is False
        ),
        "NEGATIVE_MARKET_LEARNING_CONTEXT_BOUND": (
            p8.get("negative_learning_context_bound") is True
            and int(p8.get("negative_learning_activation_threshold") or 0) == 3
            and int(p8.get("active_negative_match_count") or 0) == 0
            and p8.get("product_globally_invalidated") is False
        ),
        "NO_AUTHORITY_FROM_COMMERCIAL_SUCCESS": (
            adversary.get("cases", {}).get("commercial_success_does_not_create_authority") is True
            and p7.get("all_market_crystals_evidence_only") is True
            and p8.get("direct_learning_to_execution") is False
            and all(receipt.get("authority_created") is False for receipt in receipts.values())
            and all(receipt.get("authority_widened") is False for receipt in receipts.values())
        ),
        "REPEATABILITY_NOT_OVERCLAIMED": (
            adversary.get("all_cases_passed") is True
            and p6.get("repeatability_proved") is False
            and p7.get("repeatability_proved") is False
            and p8.get("repeatability_proved") is False
            and adversary.get("same_fixture_replay_is_repeatability") is False
            and adversary.get("contract_refuses_underpowered_repeatability") is True
        ),
    }
    evidence = {
        "COMMERCIAL_CONTEXT_BOUND": {"world_binding_required": p1.get("world_binding_required"), "lineage_context_bound": p6.get("all_lineage_context_bound"), "negative_learning_context_bound": p8.get("negative_learning_context_bound")},
        "MARKET_CRYSTAL_SCHEMA_VALID": {"market_crystal_count": p7.get("market_crystal_count"), "market_crystal_chain_valid": p7.get("market_crystal_chain_valid")},
        "CLAIM_EVIDENCE_BOUND": {"m1_projection_proof_anchor": p2.get("m1_projection_proof_anchor"), "supported_claim_count": p2.get("supported_claim_count")},
        "UNPROVEN_CLAIMS_REFUSED": {"held_market_claim_count": p8.get("held_market_claim_count"), "market_claim_upgrade_performed": p8.get("market_claim_upgrade_performed")},
        "CHANNEL_AUTHORITY_SEPARATE": {"effect_authority_slots_separate": p3.get("effect_authority_slots_separate"), "all_external_effects_refused": p3.get("all_external_effects_refused")},
        "SPEND_AUTHORITY_SEPARATE": {"automatic_spend": p4.get("market_command_automatic_spend"), "budget_cap_minor": p4.get("market_command_budget_cap_minor")},
        "PAYMENT_LINEAGE_BOUND": {"payment_observations_lineage_bound": p6.get("payment_observations_lineage_bound"), "payment_only_wtp_gate": p6.get("payment_only_wtp_gate")},
        "CUSTOMER_LINEAGE_BOUND": {"acceptance_observations_lineage_bound": p6.get("acceptance_observations_lineage_bound"), "acceptance_artifact_bound": p6.get("acceptance_artifact_bound")},
        "MARKET_RESPONSE_OBSERVED": {"scope": "controlled_fixture", "real_market_response_observed": p5.get("real_market_response_observed")},
        "NO_RESPONSE_CAN_BE_RECORDED": {"window_closed": p5.get("no_response_window_closed"), "scope": p5.get("no_response_scope")},
        "LOSS_CAN_BE_RECORDED": {"scope": "controlled_contract_adversary", "global_product_failure": False},
        "WORLD_SETTLEMENT_COMPLETE": {"world_settlement_complete": p7.get("world_settlement_complete"), "commercial_settlement_complete": p7.get("commercial_settlement_complete")},
        "LINGUA_PROJECTION_CAN_UPDATE": {"lingua_semantic_object_id": p8.get("lingua_semantic_object_id"), "claim_upgrade_performed": p8.get("market_claim_upgrade_performed")},
        "NEGATIVE_MARKET_LEARNING_CONTEXT_BOUND": {"threshold": p8.get("negative_learning_activation_threshold"), "active_match_count": p8.get("active_negative_match_count")},
        "NO_AUTHORITY_FROM_COMMERCIAL_SUCCESS": {"all_market_crystals_evidence_only": p7.get("all_market_crystals_evidence_only"), "direct_learning_to_execution": p8.get("direct_learning_to_execution")},
        "REPEATABILITY_NOT_OVERCLAIMED": adversary,
    }
    return gates, evidence


def _run_phase9(repo_root: Path, work_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    schema_valid = _schema_valid(repo_root)
    receipts = _phase_chain(repo_root, work_root / "phase_chain")
    parent = receipts["M2-8"]
    chain_valid = _phase_chain_valid(receipts)
    adversary = _repeatability_adversary(
        config=config,
        phase5=receipts["M2-5"],
        phase6=receipts["M2-6"],
        phase7=receipts["M2-7"],
        phase8=receipts["M2-8"],
        phase3=receipts["M2-3"],
    )
    gates, gate_evidence = _acceptance_gates(receipts, adversary)
    passed_gate_count = sum(value is True for value in gates.values())
    m1_verified = (
        receipts["M2-0"].get("m1_parent_verified") is True
        and receipts["M2-0"].get("m1_parent_acceptance") == config.get("required_m1_acceptance")
        and receipts["M2-2"].get("m1_parent_verified") is True
    )
    truth_preserved = (
        parent.get("real_market_evidence") is False
        and parent.get("real_payment_verified") is False
        and parent.get("real_customer_acceptance_observed") is False
        and parent.get("real_willingness_to_pay_proved") is False
        and parent.get("commercial_validation_proved") is False
        and parent.get("repeatability_proved") is False
        and parent.get("controlled_or_simulated_evidence_excluded_from_reusable_learning") is True
    )
    authority_preserved = (
        all(receipt.get("authority_created") is False for receipt in receipts.values())
        and all(receipt.get("authority_widened") is False for receipt in receipts.values())
        and all(receipt.get("external_effects") is False for receipt in receipts.values())
        and all(receipt.get("new_runtime_engine_created") is False for receipt in receipts.values())
    )
    m3_boundary_preserved = receipts["M2-2"].get("content_transform_dataflow_proved") is False
    passed = (
        schema_valid
        and chain_valid
        and parent.get("passed") is True
        and parent.get("acceptance") == config.get("required_parent_acceptance")
        and parent.get("reference_product") == config.get("reference_product")
        and tuple(gates) == FINAL_GATES
        and passed_gate_count == len(FINAL_GATES)
        and adversary.get("all_cases_passed") is True
        and m1_verified
        and truth_preserved
        and authority_preserved
        and m3_boundary_preserved
    )
    phase_acceptances = {phase: str(receipts[phase].get("acceptance") or "") for phase in EXPECTED_PHASE_ACCEPTANCES}
    final_gate_digest = digest_payload(
        {
            "schema": "dio.m2.final_gate_digest.v1",
            "reference_product": config.get("reference_product"),
            "phase_acceptances": phase_acceptances,
            "acceptance_gates": gates,
            "repeatability_adversary_cases": adversary.get("cases"),
            "m1_verified": m1_verified,
            "truth_preserved": truth_preserved,
            "authority_preserved": authority_preserved,
            "m3_boundary_preserved": m3_boundary_preserved,
        }
    )
    return {
        "schema": FINAL_RECEIPT_SCHEMA_ID,
        "phase": "M2-9",
        "acceptance": M2_PHASE9_EXIT_TOKEN if passed else M2_PHASE9_BLOCKED_TOKEN,
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": config.get("reference_product"),
        "gate_count": len(gates),
        "passed_gate_count": passed_gate_count,
        "acceptance_gates": gates,
        "gate_evidence": gate_evidence,
        "phase_acceptances": phase_acceptances,
        "repeatability_adversary": adversary,
        "real_market_evidence": False,
        "real_payment_verified": False,
        "real_customer_acceptance_observed": False,
        "real_willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "commercial_success_required_for_metabolism_verification": False,
        "commercial_success_proved": False,
        "commercial_metabolism_verified": passed,
        "content_transform_dataflow_proved": False,
        "m3_boundary_preserved": m3_boundary_preserved,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m1_verified": m1_verified,
        "m2_final_verified": passed,
        "programme_complete": passed and m1_verified,
        "final_gate_digest": final_gate_digest,
    }


def phase9_final_verification_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase9(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-m2-phase9-") as temp:
        return _run_phase9(root, Path(temp))


__all__ = [
    "CommercialMetabolismFinalVerificationError",
    "DEFAULT_FINAL_CONFIG",
    "EXPECTED_PHASE_ACCEPTANCES",
    "FINAL_GATES",
    "FINAL_RECEIPT_SCHEMA_FILE",
    "M2_PHASE9_BLOCKED_TOKEN",
    "M2_PHASE9_EXIT_TOKEN",
    "phase9_final_verification_receipt",
]
