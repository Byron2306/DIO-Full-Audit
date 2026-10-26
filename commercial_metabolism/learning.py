"""M2 Phase 8 LINGUA projection adaptation and context-bound negative learning.

This phase turns settled M2-7 market evidence into a source-bound LINGUA review
candidate and records bounded BEAST learning observations. Controlled fixtures are
explicitly excluded from positive reuse, market-claim upgrades, semantic credits
and active negative suppression. Learning remains evidence-only and cannot publish,
spend, execute, widen authority or globally invalidate a product.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

from adapters.lingua.lifecycle import register_product_source
from metamorphic.contracts import digest_payload, require_digest

from .settlement import M2_PHASE7_EXIT_TOKEN, phase7_commercial_settlement_receipt


M2_PHASE8_EXIT_TOKEN = "DIO_M2_PROJECTION_ADAPTATION_READY"
DEFAULT_ADAPTATION_CONFIG = "config/m2_phase8_projection_adaptation.json"
ADAPTATION_SCHEMA_FILE = "schemas/dio.commercial_projection_adaptation_candidate.v1.json"


class CommercialLearningError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommercialProjectionAdaptationCandidate:
    candidate_id: str
    product_id: str
    context_digest: str
    projection_config_digest: str
    market_truth_anchor_digests: tuple[str, ...]
    lingua_semantic_object_id: str
    lingua_source_document_hash: str
    held_market_claim_ids: tuple[str, ...]
    positive_reuse_state: str = "CONTROLLED_EVIDENCE_EXCLUDED_PENDING_REAL_EVIDENCE"
    negative_learning_state: str = "OBSERVING_CONTEXT_BOUND"
    operator_approval_required: bool = True
    operator_approval_recorded: bool = False
    real_market_evidence: bool = False
    claim_upgrade_performed: bool = False
    reusable_credit_created: bool = False
    semantic_crystal_created: bool = False
    direct_learning_to_execution: bool = False
    authority_created: bool = False
    external_effects: bool = False
    schema: str = "dio.commercial_projection_adaptation_candidate.v1"

    def __post_init__(self) -> None:
        for field_name in ("candidate_id", "product_id", "lingua_semantic_object_id"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        for field_name in ("context_digest", "projection_config_digest", "lingua_source_document_hash"):
            require_digest(getattr(self, field_name), field_name=field_name)
        if not self.market_truth_anchor_digests:
            raise ValueError("market_truth_anchor_digests are required")
        for value in self.market_truth_anchor_digests:
            require_digest(value, field_name="market_truth_anchor_digests[]")
        if not self.held_market_claim_ids or len(set(self.held_market_claim_ids)) != len(self.held_market_claim_ids):
            raise ValueError("held_market_claim_ids must be non-empty and unique")
        if self.positive_reuse_state != "CONTROLLED_EVIDENCE_EXCLUDED_PENDING_REAL_EVIDENCE":
            raise ValueError("controlled evidence may not become positive reusable truth")
        if self.negative_learning_state != "OBSERVING_CONTEXT_BOUND":
            raise ValueError("M2-8 controlled negative learning must remain context-bound observing")
        if self.operator_approval_required is not True or self.operator_approval_recorded is not False:
            raise ValueError("positive commercial reuse requires a future operator approval")
        if any(
            (
                self.real_market_evidence,
                self.claim_upgrade_performed,
                self.reusable_credit_created,
                self.semantic_crystal_created,
                self.direct_learning_to_execution,
                self.authority_created,
                self.external_effects,
            )
        ):
            raise ValueError("M2-8 candidate may not promote controlled evidence or create authority/execution")

    @property
    def candidate_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "candidate_id": self.candidate_id,
            "product_id": self.product_id,
            "context_digest": self.context_digest,
            "projection_config_digest": self.projection_config_digest,
            "market_truth_anchor_digests": list(self.market_truth_anchor_digests),
            "lingua_semantic_object_id": self.lingua_semantic_object_id,
            "lingua_source_document_hash": self.lingua_source_document_hash,
            "held_market_claim_ids": list(self.held_market_claim_ids),
            "positive_reuse_state": self.positive_reuse_state,
            "negative_learning_state": self.negative_learning_state,
            "operator_approval_required": self.operator_approval_required,
            "operator_approval_recorded": self.operator_approval_recorded,
            "real_market_evidence": self.real_market_evidence,
            "claim_upgrade_performed": self.claim_upgrade_performed,
            "reusable_credit_created": self.reusable_credit_created,
            "semantic_crystal_created": self.semantic_crystal_created,
            "direct_learning_to_execution": self.direct_learning_to_execution,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "candidate_digest": self.candidate_digest,
        }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialLearningError(f"cannot load M2-8 source: {path}") from exc
    if not isinstance(value, dict):
        raise CommercialLearningError(f"M2-8 source must be an object: {path}")
    return value


def _load_config(root: Path) -> dict[str, Any]:
    value = _load_json(root / DEFAULT_ADAPTATION_CONFIG)
    if value.get("schema") != "dio.m2.projection_adaptation_config.v1":
        raise CommercialLearningError("unsupported M2-8 projection adaptation config")
    for field_name in (
        "controlled_evidence_only",
        "operator_approval_required",
    ):
        if value.get(field_name) is not True:
            raise CommercialLearningError(f"M2-8 requires {field_name}=true")
    for field_name in (
        "operator_approval_recorded",
        "real_market_evidence_claimed",
        "claim_upgrade_allowed",
        "reusable_credit_allowed",
        "semantic_crystal_allowed",
        "direct_learning_to_execution",
        "product_global_invalidation_allowed",
    ):
        if value.get(field_name) is not False:
            raise CommercialLearningError(f"M2-8 requires {field_name}=false")
    negative = value.get("negative_scenarios")
    expected = {
        "verified_payment_without_acceptance",
        "independent_acceptance_without_payment",
    }
    if not isinstance(negative, dict) or set(negative) != expected:
        raise CommercialLearningError("M2-8 negative scenario map is incomplete")
    return value


def _load_projection_config(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    projection = _load_json(root / str(config.get("projection_config") or ""))
    if projection.get("schema") != "dio.m2.commercial_projection_config.v1":
        raise CommercialLearningError("M2-8 projection config anchor is invalid")
    if projection.get("reference_product") != config.get("reference_product"):
        raise CommercialLearningError("M2-8 projection config product diverged")
    return projection


def _load_beast_learning_organs(root: Path):
    beast_root = root / "cross_folder_variants/EdgeK-BEAST/A_CODE"
    if not beast_root.is_dir():
        raise CommercialLearningError(f"BEAST root missing: {beast_root}")
    path = str(beast_root)
    if path not in sys.path:
        sys.path.insert(0, path)
    learning = importlib.import_module("app.kernel.compute.capability_learning")
    negative = importlib.import_module("app.kernel.storage.outcome_evidence")
    return learning.CapabilityLearningLedger, negative.NegativeCapabilityStore, negative.OutcomeEvidence


def _held_market_claim_ids(projection: Mapping[str, Any]) -> tuple[str, ...]:
    rows = projection.get("claims")
    if not isinstance(rows, list):
        raise CommercialLearningError("projection claims are missing")
    values = sorted(
        str(row.get("id") or "")
        for row in rows
        if isinstance(row, Mapping) and str(row.get("rule") or "").startswith("m2_")
    )
    expected = {
        "market.demand",
        "market.customer_acceptance",
        "market.willingness_to_pay",
        "market.commercial_validation",
        "market.repeatability",
        "market.roi",
    }
    if set(values) != expected:
        raise CommercialLearningError("M2-8 expected market claim set diverged")
    return tuple(values)


def _market_truth_anchors(parent: Mapping[str, Any]) -> tuple[dict[str, str], tuple[str, ...]]:
    bundles = parent.get("settlement_bundles")
    if not isinstance(bundles, list) or len(bundles) != 4:
        raise CommercialLearningError("M2-8 requires four M2-7 settlement bundles")
    anchors: dict[str, str] = {}
    for bundle in bundles:
        if not isinstance(bundle, Mapping):
            raise CommercialLearningError("M2-7 settlement bundle must be an object")
        scenario_id = str(bundle.get("scenario_id") or "")
        commercial = bundle.get("commercial_settlement") or {}
        world = bundle.get("world_settlement") or {}
        crystal = bundle.get("beast_market_crystal") or {}
        if bundle.get("evidence_scope") != "controlled_fixture" or bundle.get("real_market_evidence") is not False:
            raise CommercialLearningError("M2-8 refuses non-controlled reference evidence in this proof")
        if commercial.get("settlement_state") != "SETTLED" or world.get("settlement_state") != "SETTLED":
            raise CommercialLearningError("M2-8 requires settled commercial and world evidence")
        if crystal.get("authority") != "evidence_only" or crystal.get("real_market_evidence") is not False:
            raise CommercialLearningError("M2-8 market crystal authority/evidence boundary changed")
        anchor = digest_payload(
            {
                "schema": "dio.m2.market_truth_anchor.v1",
                "scenario_id": scenario_id,
                "evidence_scope": "controlled_fixture",
                "lineage_truth_digest": bundle.get("lineage_truth_digest"),
                "commercial_settlement_digest": commercial.get("settlement_digest"),
                "commercial_outcome": commercial.get("outcome"),
                "world_settlement_digest": world.get("settlement_digest"),
                "market_observation_digests": commercial.get("market_observation_digests") or [],
                "customer_independence": commercial.get("customer_independence"),
                "real_market_evidence": False,
                "willingness_to_pay_proved": False,
                "commercial_validation_proved": False,
                "repeatability_proved": False,
                "authority": "evidence_only",
            }
        )
        anchors[scenario_id] = anchor
    ordered = tuple(anchors[key] for key in sorted(anchors))
    return anchors, ordered


def _candidate_identity(
    *,
    product_id: str,
    context_digest: str,
    projection_config_digest: str,
    market_truth_anchors: tuple[str, ...],
) -> str:
    return "M2P8-" + digest_payload(
        {
            "product_id": product_id,
            "context_digest": context_digest,
            "projection_config_digest": projection_config_digest,
            "market_truth_anchors": list(market_truth_anchors),
        }
    ).split(":", 1)[1][:20].upper()


def _register_lingua_candidate(
    *,
    state_root: Path,
    candidate_id: str,
    product_id: str,
    context_digest: str,
    projection: Mapping[str, Any],
    truth_anchors: Mapping[str, str],
    held_claims: tuple[str, ...],
    source_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reference = projection.get("reference_context") or {}
    source_rows = [
        {
            "unit_id": "TITLE",
            "unit_type": "title",
            "text": "Funding Proposal Studio commercial projection adaptation candidate",
        },
        {
            "unit_id": "CONTEXT",
            "unit_type": "commercial_context",
            "text": f"Exact commercial context: {context_digest}",
        },
        {
            "unit_id": "CONTROLLED_GAIN",
            "unit_type": "market_evidence",
            "text": (
                "Controlled settled GAIN evidence exists for the independent-paid-acceptance structural gate at "
                f"{truth_anchors['independent_paid_acceptance_structural_gate']}. It is not real market evidence."
            ),
        },
        {
            "unit_id": "NEGATIVE_ACCEPTANCE",
            "unit_type": "negative_market_evidence",
            "text": (
                "Controlled mixed evidence for payment without acceptance remains exact-context learning evidence only: "
                f"{truth_anchors['verified_payment_without_acceptance']}."
            ),
        },
        {
            "unit_id": "NEGATIVE_PAYMENT",
            "unit_type": "negative_market_evidence",
            "text": (
                "Controlled mixed evidence for independent acceptance without verified payment remains exact-context learning evidence only: "
                f"{truth_anchors['independent_acceptance_without_payment']}."
            ),
        },
        {
            "unit_id": "SELF_PAYMENT_BOUNDARY",
            "unit_type": "proof_boundary",
            "text": (
                "Operator/self-paid acceptance is not independent demand and cannot establish willingness to pay: "
                f"{truth_anchors['operator_self_paid_acceptance']}."
            ),
        },
        {
            "unit_id": "CLAIM_BOUNDARY",
            "unit_type": "proof_boundary",
            "text": "Market claims remain HELD_UNPROVED: " + ", ".join(held_claims) + ".",
        },
        {
            "unit_id": "LEARNING_BOUNDARY",
            "unit_type": "learning_boundary",
            "text": (
                "Controlled evidence creates a review candidate only. Positive reuse requires real source-bound evidence plus operator approval; "
                "negative patterns remain observing until three distinct scoped negative observations."
            ),
        },
        {
            "unit_id": "AUTHORITY_BOUNDARY",
            "unit_type": "authority_boundary",
            "text": "Learning cannot publish, activate, spend, execute, create authority, or globally invalidate the product.",
        },
    ]
    return register_product_source(
        state_root=state_root,
        object_id=candidate_id,
        source_version=source_version,
        source_language="English",
        source_rows=source_rows,
        origin={
            "product": product_id,
            "artifact_type": "commercial_projection_adaptation_candidate",
            "artifact_id": candidate_id,
            "audience": str(reference.get("buyer_segment_id") or ""),
            "channel": str(reference.get("channel_id") or ""),
            "privacy_domain": "controlled_reference",
        },
        domain="Governed commercial projection learning",
    )


def _negative_learning(
    *,
    root: Path,
    work_root: Path,
    config: Mapping[str, Any],
    projection: Mapping[str, Any],
    context_digest: str,
    truth_anchors: Mapping[str, str],
):
    CapabilityLearningLedger, NegativeCapabilityStore, OutcomeEvidence = _load_beast_learning_organs(root)
    reference = projection.get("reference_context") or {}
    product_id = str(projection.get("reference_product") or "")
    scope = {
        "provider": str(reference.get("buyer_segment_id") or ""),
        "model": product_id,
        "tool": str(reference.get("offer_id") or ""),
        "route": str(reference.get("channel_id") or ""),
        "transform_type": context_digest,
    }
    store = NegativeCapabilityStore(
        work_root / "negative_market_capability.json",
        ttl_days=int(config.get("negative_ttl_days") or 14),
    )
    records: list[dict[str, Any]] = []
    for scenario_id, spec in sorted((config.get("negative_scenarios") or {}).items()):
        evidence = OutcomeEvidence.create(
            capability_id=product_id,
            task_class="commercial_market_response",
            outcome="failure",
            failure_category=str(spec.get("failure_category") or ""),
            failure_code=str(spec.get("failure_code") or ""),
            scope=scope,
            observed_at=str(config.get("learning_observed_at") or ""),
            evidence_id="market_" + truth_anchors[scenario_id].split(":", 1)[1][:24],
            detail=str(spec.get("detail") or ""),
        )
        record = store.record(evidence)
        if record is None:
            raise CommercialLearningError("negative learning record was not materialised")
        row = record.to_dict()
        records.append(
            {
                "record_id": row["record_id"],
                "capability_id": row["capability_id"],
                "task_class": row["task_class"],
                "failure_count": row["failure_count"],
                "clean_success_count": row["clean_success_count"],
                "confidence": row["confidence"],
                "state": row["state"],
                "scope": dict(row["scope"]),
                "scope_digest": digest_payload(row["scope"]),
                "scenario_id": scenario_id,
                "truth_anchor_digest": truth_anchors[scenario_id],
            }
        )
    active = store.active_matches(
        {
            "capability_id": product_id,
            "task_class": "commercial_market_response",
            "scope": scope,
        }
    )
    ledger = CapabilityLearningLedger(work_root / "commercial_projection_learning.jsonl")
    return CapabilityLearningLedger, NegativeCapabilityStore, ledger, records, active, scope


def exercise_projection_adaptation(
    repo_root: str | Path,
    *,
    work_root: str | Path,
    parent_receipt: Mapping[str, Any] | None = None,
) -> tuple[CommercialProjectionAdaptationCandidate, dict[str, Any]]:
    root = Path(repo_root).resolve()
    state = Path(work_root).resolve()
    state.mkdir(parents=True, exist_ok=True)
    config = _load_config(root)
    projection = _load_projection_config(root, config)
    parent = (
        dict(parent_receipt)
        if parent_receipt is not None
        else phase7_commercial_settlement_receipt(root, work_root=state / "phase7_parent")
    )
    if parent.get("passed") is not True or parent.get("acceptance") != config.get("required_parent_acceptance"):
        raise CommercialLearningError("M2-7 commercial settlement parent is not verified")
    if parent.get("reference_product") != config.get("reference_product"):
        raise CommercialLearningError("M2-8 parent product diverged")
    if parent.get("real_market_evidence") is not False or parent.get("commercial_truth_promoted_from_controlled_fixture") is not False:
        raise CommercialLearningError("M2-8 controlled parent unexpectedly contains promoted market truth")

    context_digest = str(parent.get("context_digest") or "")
    require_digest(context_digest, field_name="context_digest")
    projection_config_digest = digest_payload(projection)
    truth_by_scenario, ordered_truth = _market_truth_anchors(parent)
    held_claims = _held_market_claim_ids(projection)
    candidate_id = _candidate_identity(
        product_id=str(config["reference_product"]),
        context_digest=context_digest,
        projection_config_digest=projection_config_digest,
        market_truth_anchors=ordered_truth,
    )
    semantic_object, lingua_receipt = _register_lingua_candidate(
        state_root=state / "lingua",
        candidate_id=candidate_id,
        product_id=str(config["reference_product"]),
        context_digest=context_digest,
        projection=projection,
        truth_anchors=truth_by_scenario,
        held_claims=held_claims,
        source_version=str(config.get("candidate_source_version") or ""),
    )
    source_hash = str(semantic_object.get("source", {}).get("document_hash") or "")
    require_digest(source_hash, field_name="lingua_source_document_hash")

    _LearningLedger, NegativeStore, ledger, negative_records, active_negative, negative_scope = _negative_learning(
        root=root,
        work_root=state / "beast_learning",
        config=config,
        projection=projection,
        context_digest=context_digest,
        truth_anchors=truth_by_scenario,
    )

    candidate = CommercialProjectionAdaptationCandidate(
        candidate_id=candidate_id,
        product_id=str(config["reference_product"]),
        context_digest=context_digest,
        projection_config_digest=projection_config_digest,
        market_truth_anchor_digests=ordered_truth,
        lingua_semantic_object_id=candidate_id,
        lingua_source_document_hash=source_hash,
        held_market_claim_ids=held_claims,
    )

    observed_at = str(config.get("learning_observed_at") or "")
    ledger.record(
        event_type="commercial_projection_adaptation_candidate_recorded",
        capability_type="commercial_projection_candidate",
        capability_id=candidate.product_id,
        lifecycle_state="candidate_pending_real_evidence_and_operator_approval",
        authority="evidence_only",
        evidence_digest=candidate.candidate_digest,
        receipt_digest=candidate.lingua_source_document_hash,
        metadata={
            "context_digest": candidate.context_digest,
            "candidate_id": candidate.candidate_id,
            "real_market_evidence": False,
            "claim_upgrade_performed": False,
            "operator_approval_recorded": False,
            "direct_learning_to_execution": False,
        },
        observed_at=observed_at,
    )
    ledger.record(
        event_type="controlled_gain_excluded_from_positive_reuse",
        capability_type="commercial_market_learning",
        capability_id=candidate.product_id,
        lifecycle_state="controlled_evidence_excluded",
        authority="evidence_only",
        evidence_digest=truth_by_scenario["independent_paid_acceptance_structural_gate"],
        receipt_digest=candidate.candidate_digest,
        metadata={
            "context_digest": candidate.context_digest,
            "positive_reuse_created": False,
            "real_market_evidence": False,
            "operator_approval_required": True,
        },
        observed_at=observed_at,
    )
    for record in negative_records:
        ledger.record(
            event_type="commercial_negative_pattern_observed",
            capability_type="commercial_negative_market_pattern",
            capability_id=candidate.product_id,
            lifecycle_state="observing",
            authority="evidence_only",
            evidence_digest=str(record["truth_anchor_digest"]),
            receipt_digest=candidate.candidate_digest,
            metadata={
                "context_digest": candidate.context_digest,
                "negative_record_id": record["record_id"],
                "negative_state": record["state"],
                "negative_scope_digest": record["scope_digest"],
                "product_globally_invalidated": False,
                "direct_learning_to_execution": False,
            },
            observed_at=observed_at,
        )
    learning_report = ledger.report(limit=20)

    return candidate, {
        "parent": parent,
        "config": config,
        "projection": projection,
        "projection_config_digest": projection_config_digest,
        "truth_anchors": truth_by_scenario,
        "semantic_object": semantic_object,
        "lingua_receipt": lingua_receipt,
        "negative_records": negative_records,
        "active_negative_matches": active_negative,
        "negative_scope": negative_scope,
        "negative_activation_threshold": int(NegativeStore.ACTIVATION_FAILURES),
        "learning_report": learning_report,
    }


def _run_phase8(repo_root: Path, work_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    candidate, evidence = exercise_projection_adaptation(repo_root, work_root=work_root)
    parent = evidence["parent"]
    projection = evidence["projection"]
    negative_records = evidence["negative_records"]
    active_negative = evidence["active_negative_matches"]
    doctrine_path = repo_root / str(config.get("learning_doctrine") or "")
    doctrine = doctrine_path.read_text(encoding="utf-8") if doctrine_path.is_file() else ""

    schema_valid = False
    schema_path = repo_root / ADAPTATION_SCHEMA_FILE
    if schema_path.is_file():
        schema = _load_json(schema_path)
        schema_valid = (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema.get("$id") == "dio.commercial_projection_adaptation_candidate.v1"
        )
    reference = projection.get("reference_context") or {}
    context_bound_negative = (
        len(negative_records) == 2
        and all(row.get("state") == "observing" for row in negative_records)
        and all(int(row.get("failure_count") or 0) == 1 for row in negative_records)
        and all(row.get("scope", {}).get("transform_type") == candidate.context_digest for row in negative_records)
        and all(row.get("scope", {}).get("route") == reference.get("channel_id") for row in negative_records)
        and all(row.get("scope", {}).get("tool") == reference.get("offer_id") for row in negative_records)
        and all(row.get("scope", {}).get("model") == candidate.product_id for row in negative_records)
        and all(row.get("scope", {}).get("provider") == reference.get("buyer_segment_id") for row in negative_records)
    )
    doctrine_checks = {
        "no_direct_learning_to_execution": "There is **no direct learning → execution path**." in doctrine,
        "positive_reuse_requires_operator_approval": "An operator must approve the candidate" in doctrine,
        "negative_requires_three_distinct_observations": "three distinct negative observations" in doctrine,
        "negative_not_global_product_failure": "not a claim that the underlying product or channel can never work" in doctrine,
        "simulated_demo_excluded_from_learning": "Simulated or demo observations are excluded from learning." in doctrine,
    }
    learning_report = evidence["learning_report"]
    held_claims = set(candidate.held_market_claim_ids)
    expected_held = {
        "market.demand",
        "market.customer_acceptance",
        "market.willingness_to_pay",
        "market.commercial_validation",
        "market.repeatability",
        "market.roi",
    }
    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == M2_PHASE7_EXIT_TOKEN
        and schema_valid
        and candidate.product_id == config.get("reference_product")
        and held_claims == expected_held
        and len(candidate.market_truth_anchor_digests) == 4
        and evidence["lingua_receipt"].get("schema") == "dio.lingua.product_registration_receipt.v1"
        and context_bound_negative
        and not active_negative
        and int(evidence["negative_activation_threshold"]) == 3
        and int(learning_report.get("event_count") or 0) == 4
        and all(doctrine_checks.values())
        and candidate.operator_approval_required is True
        and candidate.operator_approval_recorded is False
        and candidate.real_market_evidence is False
        and candidate.claim_upgrade_performed is False
        and candidate.reusable_credit_created is False
        and candidate.semantic_crystal_created is False
        and candidate.direct_learning_to_execution is False
        and candidate.authority_created is False
        and candidate.external_effects is False
    )
    return {
        "phase": "M2-8",
        "acceptance": M2_PHASE8_EXIT_TOKEN if passed else "DIO_M2_PROJECTION_ADAPTATION_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": candidate.product_id,
        "context_digest": candidate.context_digest,
        "projection_config_digest": candidate.projection_config_digest,
        "projection_adaptation_candidate": candidate.to_dict(),
        "projection_adaptation_schema_valid": schema_valid,
        "lingua_existing_organ_reused": True,
        "lingua_projection_can_update": True,
        "lingua_semantic_object_id": candidate.lingua_semantic_object_id,
        "lingua_source_document_hash": candidate.lingua_source_document_hash,
        "market_truth_anchor_count": len(candidate.market_truth_anchor_digests),
        "volatile_crystal_receipts_excluded_from_projection_identity": True,
        "held_market_claim_count": len(candidate.held_market_claim_ids),
        "held_market_claims": list(candidate.held_market_claim_ids),
        "market_claim_upgrade_performed": False,
        "positive_reuse_state": candidate.positive_reuse_state,
        "controlled_gain_positive_reuse_created": False,
        "operator_approval_required_for_positive_reuse": True,
        "operator_approval_recorded": False,
        "negative_learning_record_count": len(negative_records),
        "negative_learning_records": negative_records,
        "negative_learning_state": candidate.negative_learning_state,
        "negative_learning_context_bound": context_bound_negative,
        "negative_learning_activation_threshold": evidence["negative_activation_threshold"],
        "active_negative_match_count": len(active_negative),
        "negative_pattern_activated_from_single_observation": False,
        "product_globally_invalidated": False,
        "beast_negative_capability_store_reused": True,
        "beast_capability_learning_ledger_reused": True,
        "beast_learning_event_count": int(learning_report.get("event_count") or 0),
        "beast_learning_ledger_digest": learning_report.get("ledger_digest"),
        "learning_doctrine_checks": doctrine_checks,
        "controlled_or_simulated_evidence_excluded_from_reusable_learning": True,
        "real_market_evidence": False,
        "real_payment_verified": False,
        "real_customer_acceptance_observed": False,
        "real_willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "semantic_crystal_created": False,
        "direct_learning_to_execution": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


def phase8_projection_adaptation_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase8(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-m2-phase8-") as temp:
        return _run_phase8(root, Path(temp))


__all__ = [
    "ADAPTATION_SCHEMA_FILE",
    "CommercialLearningError",
    "CommercialProjectionAdaptationCandidate",
    "DEFAULT_ADAPTATION_CONFIG",
    "M2_PHASE8_EXIT_TOKEN",
    "exercise_projection_adaptation",
    "phase8_projection_adaptation_receipt",
]
