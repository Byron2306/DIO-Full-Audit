"""M2 Phase 7 commercial settlement and BEAST market crystallisation.

This phase settles the source-bound controlled customer/payment lineage scenarios
proved in M2-6 against a fresh controlled world observation, then reuses BEAST's
existing CrystalChainLedger and CapabilityLearningLedger to record evidence-only
market crystals.

The crystals describe controlled evidence shapes. They do not prove real market
exposure, real payment, customer acceptance, willingness to pay, commercial
validation, repeatability or authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from adapters.beast.commercial_crystallisation import crystallize_commercial_settlement
from metamorphic.contracts import SettlementState, WorldSettlement, digest_payload, require_digest
from metamorphic.world_lease import build_controlled_world_snapshot

from .contracts import (
    CommercialSettlement,
    CommercialSettlementState,
    CustomerIndependence,
    EvidenceClaimState,
    SettlementOutcome,
)
from .lineage import M2_PHASE6_EXIT_TOKEN, phase6_customer_payment_lineage_receipt


M2_PHASE7_EXIT_TOKEN = "DIO_M2_COMMERCIAL_SETTLEMENT_READY"
DEFAULT_SETTLEMENT_CONFIG = "config/m2_phase7_commercial_settlement.json"
SETTLEMENT_BUNDLE_SCHEMA_FILE = "schemas/dio.commercial_settlement_bundle.v1.json"


class CommercialSettlementError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommercialSettlementBundle:
    scenario_id: str
    lineage_truth_digest: str
    world_settlement: WorldSettlement
    commercial_settlement: CommercialSettlement
    beast_market_crystal: Mapping[str, Any]
    evidence_scope: str = "controlled_fixture"
    real_market_evidence: bool = False
    authority_created: bool = False
    external_effects: bool = False
    schema: str = "dio.commercial_settlement_bundle.v1"

    def __post_init__(self) -> None:
        if not str(self.scenario_id or "").strip():
            raise ValueError("scenario_id is required")
        require_digest(self.lineage_truth_digest, field_name="lineage_truth_digest")
        if self.evidence_scope != "controlled_fixture" or self.real_market_evidence:
            raise ValueError("M2-7 reference settlement is controlled-fixture-only")
        if self.world_settlement.settlement_state is not SettlementState.SETTLED:
            raise ValueError("bundle requires SETTLED world settlement")
        if self.commercial_settlement.settlement_state is not CommercialSettlementState.SETTLED:
            raise ValueError("bundle requires SETTLED commercial settlement")
        if self.commercial_settlement.world_settlement_digest != self.world_settlement.settlement_digest:
            raise ValueError("commercial and world settlement lineage diverged")
        if self.beast_market_crystal.get("commercial_settlement_digest") != self.commercial_settlement.settlement_digest:
            raise ValueError("market crystal is not bound to commercial settlement")
        if self.beast_market_crystal.get("world_settlement_digest") != self.world_settlement.settlement_digest:
            raise ValueError("market crystal is not bound to world settlement")
        if self.beast_market_crystal.get("authority") != "evidence_only":
            raise ValueError("market crystal authority boundary changed")
        if self.authority_created or self.external_effects:
            raise ValueError("commercial settlement bundle may not create authority or external effects")

    @property
    def bundle_digest(self) -> str:
        return digest_payload(
            {
                "schema": self.schema,
                "scenario_id": self.scenario_id,
                "lineage_truth_digest": self.lineage_truth_digest,
                "world_settlement_digest": self.world_settlement.settlement_digest,
                "commercial_settlement_digest": self.commercial_settlement.settlement_digest,
                "market_crystal_block_hash": self.beast_market_crystal.get("crystal_block_hash"),
                "evidence_scope": self.evidence_scope,
                "real_market_evidence": False,
                "authority_created": False,
                "external_effects": False,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "scenario_id": self.scenario_id,
            "lineage_truth_digest": self.lineage_truth_digest,
            "world_settlement": self.world_settlement.to_dict(),
            "commercial_settlement": self.commercial_settlement.to_dict(),
            "beast_market_crystal": dict(self.beast_market_crystal),
            "evidence_scope": self.evidence_scope,
            "real_market_evidence": self.real_market_evidence,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "bundle_digest": self.bundle_digest,
        }


def _load_config(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_SETTLEMENT_CONFIG
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialSettlementError(f"cannot load M2-7 settlement config: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != "dio.m2.commercial_settlement_config.v1":
        raise CommercialSettlementError("unsupported M2-7 settlement config")
    expected = {
        "verified_payment_without_acceptance",
        "operator_self_paid_acceptance",
        "independent_acceptance_without_payment",
        "independent_paid_acceptance_structural_gate",
    }
    scenarios = value.get("scenarios")
    if not isinstance(scenarios, dict) or set(scenarios) != expected:
        raise CommercialSettlementError("M2-7 settlement scenario map is incomplete")
    if value.get("evidence_scope") != "controlled_fixture":
        raise CommercialSettlementError("M2-7 reference evidence scope must remain controlled_fixture")
    for field_name in (
        "real_market_evidence_claimed",
        "real_payment_claimed",
        "real_customer_acceptance_claimed",
        "willingness_to_pay_claimed",
        "commercial_validation_claimed",
        "repeatability_claimed",
    ):
        if value.get(field_name) is not False:
            raise CommercialSettlementError(f"M2-7 config may not claim {field_name}")
    return value


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommercialSettlementError(f"invalid settlement timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _build_world_settlement(
    root: Path,
    *,
    scenario_id: str,
    lineage_truth_digest: str,
    config: Mapping[str, Any],
) -> WorldSettlement:
    world_now = _parse_utc(str(config.get("world_snapshot_now") or ""))
    pre = build_controlled_world_snapshot(root, now=world_now)
    post = build_controlled_world_snapshot(root, now=world_now)
    world_facts_stable = digest_payload(pre.facts) == digest_payload(post.facts)
    world_identity_stable = (
        pre.snapshot_digest == post.snapshot_digest
        and pre.epoch_id == post.epoch_id
        and pre.policy_generation == post.policy_generation
    )
    if not world_facts_stable or not world_identity_stable:
        raise CommercialSettlementError("controlled commercial world drifted before settlement")
    if not pre.is_current(now=world_now) or not post.is_current(now=world_now):
        raise CommercialSettlementError("controlled commercial world snapshot is stale")

    effect = str(config.get("expected_effect") or "").strip()
    if not effect:
        raise CommercialSettlementError("M2-7 expected controlled effect is required")
    settlement_id = "settlement:commercial:" + digest_payload(
        {
            "scenario_id": scenario_id,
            "lineage_truth_digest": lineage_truth_digest,
            "pre_world_digest": pre.snapshot_digest,
            "post_world_digest": post.snapshot_digest,
            "expected_effect": effect,
        }
    ).split(":", 1)[1][:24]
    return WorldSettlement(
        settlement_id=settlement_id,
        episode_id=f"episode:commercial:{scenario_id}",
        pre_world_digest=pre.snapshot_digest,
        post_world_digest=post.snapshot_digest,
        expected_effects=(effect,),
        observed_effects=(effect,),
        sensorium_receipts=(),
        vns_receipts=(),
        arda_receipts=(),
        seraph_receipts=(),
        harmonic_before={
            "status": "not_observed_for_controlled_lineage_fixture",
            "authority": False,
        },
        harmonic_after={
            "status": "not_observed_for_controlled_lineage_fixture",
            "authority": False,
        },
        authority_preserved=True,
        unexpected_effects=(),
        settlement_state=SettlementState.SETTLED,
    )


def _build_commercial_settlement(
    *,
    row: Mapping[str, Any],
    world_settlement: WorldSettlement,
    config: Mapping[str, Any],
) -> CommercialSettlement:
    scenario_id = str(row.get("scenario_id") or "")
    outcome = SettlementOutcome(str((config.get("scenarios") or {}).get(scenario_id) or ""))
    observation_digests = tuple(str(value) for value in (row.get("observation_digests") or []))
    for value in observation_digests:
        require_digest(value, field_name="observation_digest")
    settlement_id = "COMMERCIAL-" + digest_payload(
        {
            "scenario_id": scenario_id,
            "context_digest": row.get("context_digest"),
            "lineage_truth_digest": row.get("truth_digest"),
            "world_settlement_digest": world_settlement.settlement_digest,
        }
    ).split(":", 1)[1][:24].upper()
    return CommercialSettlement(
        settlement_id=settlement_id,
        context_digest=str(row.get("context_digest") or ""),
        settled_at=str(config.get("settled_at") or ""),
        settlement_state=CommercialSettlementState.SETTLED,
        outcome=outcome,
        market_observation_digests=observation_digests,
        customer_independence=CustomerIndependence(str(row.get("customer_independence") or "")),
        verified_payment=EvidenceClaimState.UNPROVED,
        customer_acceptance=EvidenceClaimState.UNPROVED,
        willingness_to_pay=EvidenceClaimState.UNPROVED,
        repeatability=EvidenceClaimState.UNPROVED,
        validated_engagement_count=0,
        distinct_independent_customer_count=0,
        world_settlement_digest=world_settlement.settlement_digest,
        customer_lineage_digest=str(row.get("customer_lineage_digest") or ""),
        payment_lineage_digest=str(row.get("payment_lineage_digest") or ""),
        unexpected_effects=(),
        authority_preserved=True,
        authority_created=False,
    )


def settle_and_crystallize_controlled_commercial_evidence(
    repo_root: str | Path,
    *,
    state_root: str | Path,
) -> tuple[tuple[CommercialSettlementBundle, ...], dict[str, Any]]:
    root = Path(repo_root).resolve()
    state = Path(state_root).resolve()
    state.mkdir(parents=True, exist_ok=True)
    config = _load_config(root)
    parent = phase6_customer_payment_lineage_receipt(root)
    if parent.get("passed") is not True or parent.get("acceptance") != config.get("required_parent_acceptance"):
        raise CommercialSettlementError("M2-6 customer/payment lineage parent is not verified")
    if parent.get("real_payment_verified") is not False or parent.get("real_customer_acceptance_observed") is not False:
        raise CommercialSettlementError("M2-7 controlled parent unexpectedly contains real commercial evidence")
    if parent.get("real_willingness_to_pay_proved") is not False or parent.get("commercial_validation_proved") is not False:
        raise CommercialSettlementError("M2-7 controlled parent overclaims commercial truth")

    rows = parent.get("controlled_lineage_scenarios")
    if not isinstance(rows, list) or len(rows) != 4:
        raise CommercialSettlementError("M2-7 requires the four M2-6 controlled lineage scenarios")

    bundles: list[CommercialSettlementBundle] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise CommercialSettlementError("M2-6 lineage row must be an object")
        scenario_id = str(row.get("scenario_id") or "")
        lineage_truth_digest = str(row.get("truth_digest") or "")
        require_digest(lineage_truth_digest, field_name="lineage_truth_digest")
        world = _build_world_settlement(
            root,
            scenario_id=scenario_id,
            lineage_truth_digest=lineage_truth_digest,
            config=config,
        )
        commercial = _build_commercial_settlement(row=row, world_settlement=world, config=config)
        crystal = crystallize_commercial_settlement(
            root,
            commercial_settlement=commercial,
            world_settlement=world,
            scenario_id=scenario_id,
            lineage_truth_digest=lineage_truth_digest,
            structural_wtp_gate_satisfied=bool(row.get("structural_wtp_gate_satisfied")),
            state_root=state / "beast",
        )
        bundles.append(
            CommercialSettlementBundle(
                scenario_id=scenario_id,
                lineage_truth_digest=lineage_truth_digest,
                world_settlement=world,
                commercial_settlement=commercial,
                beast_market_crystal=crystal,
            )
        )

    return tuple(bundles), {
        "parent": parent,
        "config": config,
    }


def _run_phase7(repo_root: Path, work_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    bundles, evidence = settle_and_crystallize_controlled_commercial_evidence(
        repo_root,
        state_root=work_root / "commercial_settlement",
    )
    parent = evidence["parent"]
    by_id = {row.scenario_id: row for row in bundles}

    schema_valid = False
    schema_path = repo_root / SETTLEMENT_BUNDLE_SCHEMA_FILE
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_valid = (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema.get("$id") == "dio.commercial_settlement_bundle.v1"
        )

    world_settled = all(row.world_settlement.settlement_state is SettlementState.SETTLED for row in bundles)
    commercial_settled = all(
        row.commercial_settlement.settlement_state is CommercialSettlementState.SETTLED
        and row.commercial_settlement.market_crystal_eligible
        for row in bundles
    )
    crystals = [dict(row.beast_market_crystal) for row in bundles]
    crystals_valid = (
        all(row.get("beast_market_crystallization_executed") is True for row in crystals)
        and all(row.get("crystal_chain_valid") is True for row in crystals)
        and [int(row.get("crystal_chain_block_count") or 0) for row in crystals] == [1, 2, 3, 4]
    )
    lineage_bound = all(
        row.beast_market_crystal.get("lineage_truth_digest") == row.lineage_truth_digest
        for row in bundles
    )
    settlement_bound = all(
        row.beast_market_crystal.get("commercial_settlement_digest") == row.commercial_settlement.settlement_digest
        and row.beast_market_crystal.get("world_settlement_digest") == row.world_settlement.settlement_digest
        for row in bundles
    )
    truth_not_promoted = all(
        row.commercial_settlement.verified_payment is EvidenceClaimState.UNPROVED
        and row.commercial_settlement.customer_acceptance is EvidenceClaimState.UNPROVED
        and row.commercial_settlement.willingness_to_pay is EvidenceClaimState.UNPROVED
        and row.commercial_settlement.repeatability is EvidenceClaimState.UNPROVED
        for row in bundles
    )
    structural = by_id["independent_paid_acceptance_structural_gate"]
    structural_gate_preserved = (
        structural.beast_market_crystal.get("real_market_evidence") is False
        and structural.beast_market_crystal.get("willingness_to_pay_proved") is False
        and parent.get("independent_paid_acceptance_structural_wtp_gate") is True
    )

    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == config.get("required_parent_acceptance")
        and schema_valid
        and len(bundles) == 4
        and world_settled
        and commercial_settled
        and crystals_valid
        and lineage_bound
        and settlement_bound
        and truth_not_promoted
        and structural_gate_preserved
        and parent.get("real_payment_verified") is False
        and parent.get("real_customer_acceptance_observed") is False
        and parent.get("real_willingness_to_pay_proved") is False
        and parent.get("commercial_validation_proved") is False
        and parent.get("repeatability_proved") is False
        and all(row.authority_created is False and row.external_effects is False for row in bundles)
        and all(row.beast_market_crystal.get("authority") == "evidence_only" for row in bundles)
        and all(row.beast_market_crystal.get("direct_learning_to_execution") is False for row in bundles)
    )

    return {
        "phase": "M2-7",
        "acceptance": M2_PHASE7_EXIT_TOKEN if passed else "DIO_M2_COMMERCIAL_SETTLEMENT_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": parent.get("reference_product"),
        "context_digest": parent.get("context_digest"),
        "evidence_scope": config.get("evidence_scope"),
        "settlement_bundle_schema_valid": schema_valid,
        "commercial_settlement_count": len(bundles),
        "world_settlement_complete": world_settled,
        "commercial_settlement_complete": commercial_settled,
        "market_crystal_created": crystals_valid,
        "market_crystal_count": len(crystals),
        "market_crystal_chain_valid": all(row.get("crystal_chain_valid") is True for row in crystals),
        "market_crystal_final_block_count": int(crystals[-1].get("crystal_chain_block_count") or 0) if crystals else 0,
        "lineage_truth_bound_to_crystals": lineage_bound,
        "commercial_and_world_settlement_bound_to_crystals": settlement_bound,
        "all_market_crystals_evidence_only": all(row.get("authority") == "evidence_only" for row in crystals),
        "direct_learning_to_execution": False,
        "independent_paid_acceptance_structural_wtp_gate": parent.get("independent_paid_acceptance_structural_wtp_gate") is True,
        "structural_wtp_gate_preserved_without_real_wtp_claim": structural_gate_preserved,
        "real_market_evidence": False,
        "real_payment_verified": False,
        "real_customer_acceptance_observed": False,
        "real_willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "commercial_truth_promoted_from_controlled_fixture": False,
        "settlement_bundles": [row.to_dict() for row in bundles],
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


def phase7_commercial_settlement_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase7(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-m2-phase7-") as temp:
        return _run_phase7(root, Path(temp))


__all__ = [
    "CommercialSettlementBundle",
    "CommercialSettlementError",
    "DEFAULT_SETTLEMENT_CONFIG",
    "M2_PHASE7_EXIT_TOKEN",
    "SETTLEMENT_BUNDLE_SCHEMA_FILE",
    "phase7_commercial_settlement_receipt",
    "settle_and_crystallize_controlled_commercial_evidence",
]
