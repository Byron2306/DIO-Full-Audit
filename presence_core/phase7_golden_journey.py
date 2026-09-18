from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from products.commercial_pricing_registry import build_commercial_pricing_registry

from .customer_cases import load_case
from .deliverable_release_v2 import (
    build_deliverable_manifest,
    create_manifest_release_authority,
    deliver_manifest,
)
from .fulfilment_contract import (
    build_fulfilment_request,
    dispatch_fulfilment,
    project_execution_profile,
)
from .intake_scope_quote import (
    approve_operator_review_quote,
    assess_scope,
    open_intake,
    prepare_quote,
    record_intake_inputs,
)
from .journey_core import create_journey_case, transition_case
from .needs_you import resolve_needs_you
from .organ_adapter_gauntlet import (
    ORGAN_FAMILIES,
    execute_verified_family,
    seal_native_execution,
)
from .settlement_truth import record_controlled_test_settlement
from .state import create_needs_you


GOLDEN_JOURNEY_SCHEMA = "dio.customer_journey.phase7_golden.v1"

FAMILY_PRODUCTS: dict[str, str] = {
    "sophia_review": "Sophia Review",
    "evidex_evidence": "Evidex EvidenceOps",
    "vamp_snapshot": "VAMP Performance",
    "homs_assessment": "HOMS Assess",
    "homs_learning": "HOMS Learning Studio",
    "document_studio": "Document Studio Edit",
    "nichefoundry_campaign": "Campaign Lab",
    "obligation_assurance": "GrantProof",
}


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _product(root: Path, product_name: str) -> dict[str, Any]:
    registry = build_commercial_pricing_registry(Path(root))
    row = next((item for item in registry["products"] if item["name"] == product_name), None)
    if row is None:
        raise ValueError(f"Phase 7 representative product missing from canonical 68-product registry: {product_name}")
    return deepcopy(row)


def build_phase7_execution_profile(
    dio_root: Path,
    family_id: str,
) -> dict[str, Any]:
    if family_id not in ORGAN_FAMILIES:
        raise ValueError(f"unknown Phase 7 organ family: {family_id}")
    product_name = FAMILY_PRODUCTS[family_id]
    product = _product(Path(dio_root), product_name)
    binding = ORGAN_FAMILIES[family_id]

    composition_basis = {
        "phase": 7,
        "family_id": family_id,
        "product_id": product["product_id"],
        "adapter_id": binding["adapter_id"],
        "adapter_version": binding["adapter_version"],
    }
    compilation_basis = {
        **composition_basis,
        "source_path": binding["source_path"],
        "execution_class": binding["execution_class"],
        "repository": binding.get("repository"),
        "repository_commit": binding.get("repository_commit"),
    }

    # Phase 4 explicitly permits a compatibility projection while the final
    # 68-product compiler identity binding remains Phase 8 work. This object
    # therefore supplies only the canonical fields consumed by the frozen
    # Phase 4 execution-profile projector and creates no new authority.
    compiled = {
        "schema": "dio.compiled_product.v1",
        "compiler_version": "phase7-compatibility-projection",
        "product_id": product["product_id"],
        "name": product_name,
        "composition_fingerprint": "sha256:" + _canonical_hash(composition_basis),
        "compilation_fingerprint": "sha256:" + _canonical_hash(compilation_basis),
        "capability_plan": [
            {
                "capability_id": f"phase7.organ.{family_id}",
                "required": True,
                "execution_required": True,
                "resolution_state": "RESOLVED",
                "provider": {
                    "provider_id": binding["adapter_id"],
                    "provider_kind": binding["execution_class"],
                    "ref": binding["source_path"],
                    "execution_capable": True,
                    "product_scope": [product["product_id"]],
                },
                "reason": "Phase 7 pinned representative-organ execution binding.",
            }
        ],
        "gates": {
            "execution": {
                "state": "NEEDS_YOU",
                "reason": "Phase 7 controlled golden journey requires explicit bounded initiation.",
            }
        },
        "output_plan": {
            "schema": "dio.compiled_output_plan.v1",
            "outputs": [{"family_id": family_id, "release_state": "HELD"}],
        },
    }
    return project_execution_profile(
        compiled,
        adapter_id=str(binding["adapter_id"]),
        adapter_version=str(binding["adapter_version"]),
    )


def build_golden_fulfilment_request(
    dio_root: Path,
    state_root: Path,
    family_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    dio_root = Path(dio_root).resolve()
    state_root = Path(state_root).resolve()
    if family_id not in FAMILY_PRODUCTS:
        raise ValueError(f"unknown Phase 7 golden-journey family: {family_id}")

    product_name = FAMILY_PRODUCTS[family_id]
    product = _product(dio_root, product_name)
    case = create_journey_case(state_root, product_id=product_name)

    open_intake(dio_root, state_root, case["case_id"])
    buyer_class = str((product.get("buyer_classes") or [None])[0] or "")
    if not buyer_class:
        raise ValueError(f"Phase 7 product has no governed buyer class: {product_name}")
    record_intake_inputs(
        dio_root,
        state_root,
        case["case_id"],
        {
            "requested_outcome": f"Phase 7 controlled golden journey for {product_name}",
            "buyer_class": buyer_class,
            "scope_quantity": 1,
        },
        evidence_ref=f"phase7:typed-intake:{family_id}",
    )
    scope = assess_scope(dio_root, state_root, case["case_id"])
    if scope["state"] != "SUFFICIENT":
        raise ValueError(f"Phase 7 representative scope is not sufficient: {family_id}")

    quote_result = prepare_quote(dio_root, state_root, case["case_id"])
    if quote_result["decision"] == "NEEDS_YOU":
        quote_result = approve_operator_review_quote(
            dio_root,
            state_root,
            case["case_id"],
            approved_by="human:phase7-controlled-gauntlet",
            approved_amount_zar=int(quote_result["pricing_reference"]["amount_zar"]),
            evidence_ref=f"phase7:operator-quote-approval:{family_id}",
        )
    if quote_result["decision"] != "ALLOW_PRESENTATION" or not quote_result.get("quote"):
        raise ValueError(f"Phase 7 representative quote was not canonically approved: {family_id}")

    record_controlled_test_settlement(
        state_root,
        case["case_id"],
        receipt_id=f"PHASE7-{family_id.upper().replace('_', '-')}",
        authorized_by="operator:phase7-controlled-gauntlet",
        reason="Phase 7 golden journey integration proof; no external funds moved and no revenue recognised.",
    )

    profile = build_phase7_execution_profile(dio_root, family_id)
    request = build_fulfilment_request(state_root, case["case_id"], profile)
    return request, profile


ExecutionEvidenceRunner = Callable[..., Mapping[str, Any]]


def run_golden_journey(
    dio_root: Path,
    state_root: Path,
    family_id: str,
    runner: ExecutionEvidenceRunner,
) -> dict[str, Any]:
    dio_root = Path(dio_root).resolve()
    state_root = Path(state_root).resolve()
    request, profile = build_golden_fulfilment_request(dio_root, state_root, family_id)
    binding = ORGAN_FAMILIES[family_id]

    def adapter(req: dict[str, Any], execution_profile: dict[str, Any]) -> dict[str, Any]:
        return execute_verified_family(
            family_id,
            request=req,
            execution_profile=execution_profile,
            runner=runner,
        )

    result = dispatch_fulfilment(
        state_root,
        request,
        {str(binding["adapter_id"]): adapter},
    )
    manifest = build_deliverable_manifest(state_root, request["case_id"])

    needs = create_needs_you(
        state_root,
        reason="fulfilment_release_review",
        conversation_id=f"phase7:{request['case_id']}",
        product=FAMILY_PRODUCTS[family_id],
        summary=f"Approve exact Phase 7 manifest SHA-256 {manifest['manifest_sha256']}",
    )
    resolved = resolve_needs_you(
        state_root,
        needs["needs_you_id"],
        decision="APPROVE",
        resolved_by="human:phase7-controlled-gauntlet",
        evidence_ref=f"manifest-sha256:{manifest['manifest_sha256']}",
    )
    authority = create_manifest_release_authority(
        state_root,
        case_id=request["case_id"],
        needs_you_id=resolved["needs_you_id"],
        delivery_channels=["controlled_test"],
    )

    def controlled_transport(package: dict[str, Any]) -> dict[str, Any]:
        package_receipt = {
            "transport": "phase7_injected_controlled_test",
            "case_id": package["case_id"],
            "manifest_sha256": package["manifest_sha256"],
            "artifact_count": len(package["artifacts"]),
            "external_network_send": False,
            "external_effects": False,
        }
        package_receipt["package_receipt_sha256"] = _canonical_hash(package_receipt)
        return {"sent": True, "provider_receipt": package_receipt}

    delivered = deliver_manifest(
        state_root,
        authority["authority_id"],
        channel="controlled_test",
        destination=f"phase7://controlled/{family_id}",
        transport=controlled_transport,
    )
    if delivered.get("delivered") is not True or not delivered.get("delivery_receipt"):
        raise ValueError(f"Phase 7 controlled delivery failed: {family_id}")

    delivery_receipt = delivered["delivery_receipt"]
    closed = transition_case(
        state_root,
        request["case_id"],
        "CLOSED",
        evidence_ref=f"phase7-golden-journey:{delivery_receipt['delivery_receipt_sha256']}",
    )
    if closed["stage"] != "CLOSED":
        raise ValueError(f"Phase 7 golden journey did not close: {family_id}")

    receipt = {
        "schema": GOLDEN_JOURNEY_SCHEMA,
        "family_id": family_id,
        "representative_product": FAMILY_PRODUCTS[family_id],
        "case_id": request["case_id"],
        "scope_receipt_sha256": (load_case(state_root, request["case_id"]) or {})["scope_receipt"]["scope_receipt_sha256"],
        "quote_truth_sha256": (load_case(state_root, request["case_id"]) or {})["commercial"]["quote_result"]["quote"]["quote_truth_sha256"],
        "settlement_receipt_sha256": (load_case(state_root, request["case_id"]) or {})["settlement"]["settlement_receipt_sha256"],
        "execution_profile_sha256": profile["execution_profile_sha256"],
        "fulfilment_request_sha256": request["fulfilment_request_sha256"],
        "fulfilment_result_sha256": result["fulfilment_result_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "release_authority_id": authority["authority_id"],
        "delivery_receipt_sha256": delivery_receipt["delivery_receipt_sha256"],
        "final_stage": closed["stage"],
        "settlement_class": "CONTROLLED_TEST_SETTLEMENT",
        "external_funds_moved": False,
        "revenue_recognised": False,
        "external_network_send": False,
        "golden_journey_proved": True,
        "authority_created": False,
    }
    receipt["golden_journey_sha256"] = _canonical_hash(receipt)
    return receipt


def run_golden_journey_from_artifacts(
    dio_root: Path,
    state_root: Path,
    family_id: str,
    *,
    artifacts: Sequence[Mapping[str, Any]],
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    def runner(
        *,
        family: str,
        binding: Mapping[str, Any],
        request: Mapping[str, Any],
        execution_profile: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del binding
        if family != family_id:
            raise ValueError("Phase 7 runner family mismatch")
        return seal_native_execution(
            family_id,
            fulfilment_request_sha256=str(request["fulfilment_request_sha256"]),
            execution_profile_sha256=str(execution_profile["execution_profile_sha256"]),
            artifacts=artifacts,
            evidence_refs=evidence_refs,
        )

    return run_golden_journey(dio_root, state_root, family_id, runner)
