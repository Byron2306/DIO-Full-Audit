"""M2 Phase 6 customer/payment lineage and acceptance truth.

This phase proves that customer identity, payment evidence and acceptance evidence
remain distinct, source-bound lineages. It exercises four controlled fixture
worlds, including the exact structural conditions that would be required before
willingness-to-pay could become eligible for later real-world settlement.

Controlled fixtures never prove real payment, real customer acceptance, WTP,
commercial validation, repeatability, authority or external effects.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from metamorphic.contracts import digest_payload, require_digest
from products import commercial_proof_v1_1

from .contracts import (
    CustomerIndependence,
    CustomerLineage,
    MarketObservation,
    MarketObservationKind,
    PaymentLineage,
    PaymentState,
)
from .observation import phase5_market_observation_receipt


M2_PHASE6_EXIT_TOKEN = "DIO_M2_CUSTOMER_PAYMENT_LINEAGE_BOUND"
DEFAULT_LINEAGE_CONFIG = "config/m2_phase6_customer_payment_lineage.json"
LINEAGE_SCHEMA_FILE = "schemas/dio.commercial_lineage_evidence.v1.json"


class CommercialLineageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommercialLineageEvidence:
    scenario_id: str
    context_digest: str
    customer_lineage_digest: str
    payment_lineage_digest: str
    artifact_digest: str
    observation_digests: tuple[str, ...]
    customer_independence: str
    payment_state: str
    payment_verified_in_controlled_fixture: bool
    customer_acceptance_observed_in_controlled_fixture: bool
    structural_wtp_gate_satisfied: bool
    real_market_evidence: bool = False
    willingness_to_pay_proved: bool = False
    commercial_validation_proved: bool = False
    repeatability_proved: bool = False
    authority_created: bool = False
    external_effects: bool = False
    schema: str = "dio.commercial_lineage_evidence.v1"

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id is required")
        for field_name in (
            "context_digest",
            "customer_lineage_digest",
            "payment_lineage_digest",
            "artifact_digest",
        ):
            require_digest(getattr(self, field_name), field_name=field_name)
        if not self.observation_digests:
            raise ValueError("observation_digests are required")
        for value in self.observation_digests:
            require_digest(value, field_name="observation_digests[]")
        if self.customer_independence not in {row.value for row in CustomerIndependence}:
            raise ValueError("unsupported customer independence")
        if self.payment_state not in {row.value for row in PaymentState}:
            raise ValueError("unsupported payment state")
        if self.real_market_evidence:
            raise ValueError("M2-6 controlled fixtures may not claim real market evidence")
        if any(
            (
                self.willingness_to_pay_proved,
                self.commercial_validation_proved,
                self.repeatability_proved,
                self.authority_created,
                self.external_effects,
            )
        ):
            raise ValueError("M2-6 may not overclaim commercial truth or authority")

    @property
    def truth_digest(self) -> str:
        return digest_payload(
            {
                "schema": self.schema,
                "scenario_id": self.scenario_id,
                "context_digest": self.context_digest,
                "customer_lineage_digest": self.customer_lineage_digest,
                "payment_lineage_digest": self.payment_lineage_digest,
                "artifact_digest": self.artifact_digest,
                "observation_digests": list(self.observation_digests),
                "customer_independence": self.customer_independence,
                "payment_state": self.payment_state,
                "payment_verified_in_controlled_fixture": self.payment_verified_in_controlled_fixture,
                "customer_acceptance_observed_in_controlled_fixture": self.customer_acceptance_observed_in_controlled_fixture,
                "structural_wtp_gate_satisfied": self.structural_wtp_gate_satisfied,
                "real_market_evidence": False,
                "willingness_to_pay_proved": False,
                "commercial_validation_proved": False,
                "repeatability_proved": False,
                "authority_created": False,
                "external_effects": False,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "scenario_id": self.scenario_id,
            "context_digest": self.context_digest,
            "customer_lineage_digest": self.customer_lineage_digest,
            "payment_lineage_digest": self.payment_lineage_digest,
            "artifact_digest": self.artifact_digest,
            "observation_digests": list(self.observation_digests),
            "customer_independence": self.customer_independence,
            "payment_state": self.payment_state,
            "payment_verified_in_controlled_fixture": self.payment_verified_in_controlled_fixture,
            "customer_acceptance_observed_in_controlled_fixture": self.customer_acceptance_observed_in_controlled_fixture,
            "structural_wtp_gate_satisfied": self.structural_wtp_gate_satisfied,
            "real_market_evidence": self.real_market_evidence,
            "willingness_to_pay_proved": self.willingness_to_pay_proved,
            "commercial_validation_proved": self.commercial_validation_proved,
            "repeatability_proved": self.repeatability_proved,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "truth_digest": self.truth_digest,
        }


def _load_config(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_LINEAGE_CONFIG
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialLineageError(f"cannot load M2-6 lineage config: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != "dio.m2.customer_payment_lineage_config.v1":
        raise CommercialLineageError("unsupported M2-6 lineage config")
    scenarios = value.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 4:
        raise CommercialLineageError("M2-6 requires exactly four controlled lineage scenarios")
    expected = {
        "verified_payment_without_acceptance",
        "operator_self_paid_acceptance",
        "independent_acceptance_without_payment",
        "independent_paid_acceptance_structural_gate",
    }
    actual = {str(row.get("scenario_id") or "") for row in scenarios if isinstance(row, dict)}
    if actual != expected:
        raise CommercialLineageError("M2-6 controlled lineage scenarios are incomplete")
    for key in (
        "real_payment_claimed",
        "real_customer_acceptance_claimed",
        "willingness_to_pay_claimed",
        "commercial_validation_claimed",
    ):
        if value.get(key) is not False:
            raise CommercialLineageError(f"M2-6 controlled config may not claim {key}")
    return value


def _fixture_digest(config_digest: str, scenario: Mapping[str, Any]) -> str:
    return digest_payload(
        {
            "schema": "dio.m2.lineage_fixture.v1",
            "config_digest": config_digest,
            "scenario": dict(scenario),
        }
    )


def _artifact_digest(plan_digest: str, label: str) -> str:
    return digest_payload(
        {
            "schema": "dio.m2.controlled_reference_artifact.v1",
            "episode_plan_digest": plan_digest,
            "label": label,
            "controlled_fixture": True,
        }
    )


def _build_customer(context_digest: str, scenario: Mapping[str, Any], fixture: str, artifact: str) -> CustomerLineage:
    scenario_id = str(scenario["scenario_id"])
    independence = CustomerIndependence(str(scenario["customer_independence"]))
    subject = digest_payload(
        {
            "schema": "dio.m2.controlled_customer_subject.v1",
            "scenario_id": scenario_id,
            "subject": f"controlled:{scenario_id}",
        }
    )
    acceptance_refs = (artifact,) if bool(scenario.get("acceptance_observed")) else ()
    return CustomerLineage(
        customer_lineage_id=f"CUSTOMER-{scenario_id.upper()}",
        context_digest=context_digest,
        subject_digest=subject,
        independence=independence,
        source_refs=(fixture,),
        acceptance_refs=acceptance_refs,
    )


def _build_payment(
    context_digest: str,
    scenario: Mapping[str, Any],
    fixture: str,
    customer: CustomerLineage,
) -> PaymentLineage:
    scenario_id = str(scenario["scenario_id"])
    state = PaymentState(str(scenario["payment_state"]))
    verified = state == PaymentState.VERIFIED
    provider_event = digest_payload({"fixture": fixture, "kind": "provider_event"})
    live_order = digest_payload({"fixture": fixture, "kind": "authenticated_order_snapshot"})
    return PaymentLineage(
        payment_lineage_id=f"PAYMENT-{scenario_id.upper()}",
        context_digest=context_digest,
        order_id=f"ORDER-{scenario_id.upper()}",
        provider="CONTROLLED_DIO_EDGE_FIXTURE",
        amount_minor=int(scenario["amount_minor"]),
        currency=str(scenario["currency"]),
        payment_state=state,
        customer_lineage_id=customer.customer_lineage_id,
        provider_event_refs=(provider_event,) if verified else (),
        live_order_refs=(live_order,) if verified else (),
        verified_at=str(scenario["observed_at"]) if verified else None,
    )


def _payment_guard(payment: PaymentLineage, scenario: Mapping[str, Any]) -> dict[str, Any]:
    if payment.payment_state != PaymentState.VERIFIED:
        return {
            "evaluated": False,
            "verified_payment": commercial_proof_v1_1.PAYMENT_UNPROVED,
            "willingness_to_pay": commercial_proof_v1_1.WTP_UNPROVED,
        }
    transaction = {
        "mode": "real_payment",
        "order_id": payment.order_id,
        "customer_id": payment.customer_lineage_id,
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        "product_code": "FUNDING_PROPOSAL_STUDIO",
    }
    controlled_order = {
        "order_id": payment.order_id,
        "state": "paid",
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        "product_code": "FUNDING_PROPOSAL_STUDIO",
    }
    result = commercial_proof_v1_1.evaluate_payment(transaction, live_edge_order=controlled_order)
    return {
        "evaluated": True,
        "verified_payment": result.get("verified_payment"),
        "willingness_to_pay": result.get("willingness_to_pay"),
        "wtp_corroboration": result.get("wtp_corroboration"),
        "controlled_fixture_only": True,
    }


def _observations(
    *,
    context_digest: str,
    scenario: Mapping[str, Any],
    fixture: str,
    artifact: str,
    customer: CustomerLineage,
    payment: PaymentLineage,
    window: Mapping[str, Any],
) -> tuple[MarketObservation, ...]:
    scenario_id = str(scenario["scenario_id"])
    observed_at = str(scenario["observed_at"])
    rows: list[MarketObservation] = []
    if payment.payment_state == PaymentState.VERIFIED:
        rows.append(
            MarketObservation(
                observation_id=f"OBS-PAYMENT-{scenario_id.upper()}",
                context_digest=context_digest,
                observed_at=observed_at,
                kind=MarketObservationKind.PAYMENT,
                source="source_bound_controlled_fixture",
                source_ref=f"fixture:m2-phase6:{scenario_id}:payment",
                window_start=str(window["start"]),
                window_end=str(window["end"]),
                window_closed=True,
                evidence_refs=(fixture, payment.payment_lineage_digest),
                customer_lineage_id=customer.customer_lineage_id,
                payment_lineage_id=payment.payment_lineage_id,
            )
        )
    if bool(scenario.get("acceptance_observed")):
        rows.append(
            MarketObservation(
                observation_id=f"OBS-ACCEPTANCE-{scenario_id.upper()}",
                context_digest=context_digest,
                observed_at=observed_at,
                kind=MarketObservationKind.ACCEPTANCE,
                source="source_bound_controlled_fixture",
                source_ref=f"fixture:m2-phase6:{scenario_id}:acceptance",
                window_start=str(window["start"]),
                window_end=str(window["end"]),
                window_closed=True,
                evidence_refs=(fixture, artifact, customer.customer_lineage_digest),
                customer_lineage_id=customer.customer_lineage_id,
                payment_lineage_id=payment.payment_lineage_id if payment.payment_state == PaymentState.VERIFIED else None,
            )
        )
    if not rows:
        raise CommercialLineageError("lineage scenario created no observation")
    return tuple(rows)


def exercise_controlled_lineage_scenarios(repo_root: str | Path) -> tuple[tuple[CommercialLineageEvidence, ...], dict[str, Any]]:
    root = Path(repo_root).resolve()
    config = _load_config(root)
    parent = phase5_market_observation_receipt(root)
    if parent.get("passed") is not True or parent.get("acceptance") != config.get("required_parent_acceptance"):
        raise CommercialLineageError("M2-5 market observation parent is not verified")

    context_digest = str(parent.get("context_digest") or "")
    plan_digest = str(parent.get("episode_plan_digest") or "")
    require_digest(context_digest, field_name="context_digest")
    require_digest(plan_digest, field_name="episode_plan_digest")
    config_digest = digest_payload(config)
    artifact = _artifact_digest(plan_digest, str(config.get("reference_artifact_label") or ""))
    window = config.get("window") or {}

    evidence: list[CommercialLineageEvidence] = []
    raw: dict[str, Any] = {}
    for scenario in config["scenarios"]:
        fixture = _fixture_digest(config_digest, scenario)
        customer = _build_customer(context_digest, scenario, fixture, artifact)
        payment = _build_payment(context_digest, scenario, fixture, customer)
        observations = _observations(
            context_digest=context_digest,
            scenario=scenario,
            fixture=fixture,
            artifact=artifact,
            customer=customer,
            payment=payment,
            window=window,
        )
        payment_verified = payment.payment_state == PaymentState.VERIFIED
        acceptance_observed = bool(scenario.get("acceptance_observed"))
        structural_wtp = (
            payment_verified
            and acceptance_observed
            and customer.independence == CustomerIndependence.INDEPENDENT_EXTERNAL
        )
        guard = _payment_guard(payment, scenario)
        if payment_verified and guard.get("willingness_to_pay") != commercial_proof_v1_1.WTP_UNPROVED:
            raise CommercialLineageError("payment evaluator attempted to promote WTP without acceptance corroboration")

        row = CommercialLineageEvidence(
            scenario_id=str(scenario["scenario_id"]),
            context_digest=context_digest,
            customer_lineage_digest=customer.customer_lineage_digest,
            payment_lineage_digest=payment.payment_lineage_digest,
            artifact_digest=artifact,
            observation_digests=tuple(item.observation_digest for item in observations),
            customer_independence=customer.independence.value,
            payment_state=payment.payment_state.value,
            payment_verified_in_controlled_fixture=payment_verified,
            customer_acceptance_observed_in_controlled_fixture=acceptance_observed,
            structural_wtp_gate_satisfied=structural_wtp,
        )
        evidence.append(row)
        raw[row.scenario_id] = {
            "fixture_digest": fixture,
            "customer": customer.to_dict(),
            "payment": payment.to_dict(),
            "observations": [item.to_dict() for item in observations],
            "payment_guard": guard,
        }

    return tuple(evidence), {
        "parent": parent,
        "config_digest": config_digest,
        "artifact_digest": artifact,
        "rows": raw,
    }


def _run_phase6(repo_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    rows, evidence = exercise_controlled_lineage_scenarios(repo_root)
    parent = evidence["parent"]
    by_id = {row.scenario_id: row for row in rows}

    schema_valid = False
    schema_path = repo_root / LINEAGE_SCHEMA_FILE
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_valid = (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema.get("$id") == "dio.commercial_lineage_evidence.v1"
        )

    context_bound = all(row.context_digest == parent.get("context_digest") for row in rows)
    distinct_lineage = all(row.customer_lineage_digest != row.payment_lineage_digest for row in rows)
    artifact_bound = all(
        row.artifact_digest in evidence["rows"][row.scenario_id]["customer"]["acceptance_refs"]
        for row in rows
        if row.customer_acceptance_observed_in_controlled_fixture
    )
    payment_observations_bound = all(
        any(
            obs.get("kind") == "PAYMENT"
            and obs.get("payment_lineage_id") == evidence["rows"][row.scenario_id]["payment"]["payment_lineage_id"]
            for obs in evidence["rows"][row.scenario_id]["observations"]
        )
        for row in rows
        if row.payment_verified_in_controlled_fixture
    )
    acceptance_observations_bound = all(
        any(
            obs.get("kind") == "ACCEPTANCE"
            and obs.get("customer_lineage_id") == evidence["rows"][row.scenario_id]["customer"]["customer_lineage_id"]
            for obs in evidence["rows"][row.scenario_id]["observations"]
        )
        for row in rows
        if row.customer_acceptance_observed_in_controlled_fixture
    )
    payment_guarded = all(
        evidence["rows"][row.scenario_id]["payment_guard"].get("willingness_to_pay")
        == commercial_proof_v1_1.WTP_UNPROVED
        for row in rows
        if row.payment_verified_in_controlled_fixture
    )

    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == config.get("required_parent_acceptance")
        and schema_valid
        and len(rows) == 4
        and context_bound
        and distinct_lineage
        and artifact_bound
        and payment_observations_bound
        and acceptance_observations_bound
        and payment_guarded
        and by_id["verified_payment_without_acceptance"].structural_wtp_gate_satisfied is False
        and by_id["operator_self_paid_acceptance"].structural_wtp_gate_satisfied is False
        and by_id["independent_acceptance_without_payment"].structural_wtp_gate_satisfied is False
        and by_id["independent_paid_acceptance_structural_gate"].structural_wtp_gate_satisfied is True
        and all(row.real_market_evidence is False for row in rows)
        and all(row.willingness_to_pay_proved is False for row in rows)
        and all(row.commercial_validation_proved is False for row in rows)
        and all(row.repeatability_proved is False for row in rows)
        and all(row.authority_created is False and row.external_effects is False for row in rows)
    )

    return {
        "phase": "M2-6",
        "acceptance": M2_PHASE6_EXIT_TOKEN if passed else "DIO_M2_CUSTOMER_PAYMENT_LINEAGE_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": parent.get("reference_product"),
        "context_digest": parent.get("context_digest"),
        "episode_plan_digest": parent.get("episode_plan_digest"),
        "lineage_schema_valid": schema_valid,
        "controlled_lineage_scenario_count": len(rows),
        "controlled_lineage_scenarios": [row.to_dict() for row in rows],
        "customer_payment_lineage_distinct": distinct_lineage,
        "all_lineage_context_bound": context_bound,
        "acceptance_artifact_bound": artifact_bound,
        "payment_observations_lineage_bound": payment_observations_bound,
        "acceptance_observations_lineage_bound": acceptance_observations_bound,
        "commercial_proof_v1_1_payment_guard_reused": True,
        "verified_payment_still_wtp_unproved_without_acceptance": payment_guarded,
        "payment_only_wtp_gate": by_id["verified_payment_without_acceptance"].structural_wtp_gate_satisfied,
        "operator_self_payment_wtp_gate": by_id["operator_self_paid_acceptance"].structural_wtp_gate_satisfied,
        "independent_acceptance_without_payment_wtp_gate": by_id["independent_acceptance_without_payment"].structural_wtp_gate_satisfied,
        "independent_paid_acceptance_structural_wtp_gate": by_id["independent_paid_acceptance_structural_gate"].structural_wtp_gate_satisfied,
        "real_payment_verified": False,
        "real_customer_acceptance_observed": False,
        "real_willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "commercial_settlement_performed": False,
        "market_crystal_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


def phase6_customer_payment_lineage_receipt(repo_root: str | Path) -> dict[str, Any]:
    return _run_phase6(Path(repo_root).resolve())


__all__ = [
    "CommercialLineageError",
    "CommercialLineageEvidence",
    "DEFAULT_LINEAGE_CONFIG",
    "LINEAGE_SCHEMA_FILE",
    "M2_PHASE6_EXIT_TOKEN",
    "exercise_controlled_lineage_scenarios",
    "phase6_customer_payment_lineage_receipt",
]
