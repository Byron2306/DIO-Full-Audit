from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from products.commercial_pricing_registry import build_commercial_pricing_registry

from .attachments import validate_and_store_attachment
from .customer_cases import load_case, update_case
from .deliverable_release_v2 import (
    build_deliverable_manifest,
    create_manifest_release_authority,
    deliver_manifest,
)
from .fulfilment_contract import build_fulfilment_request, dispatch_fulfilment
from .intake_scope_quote import (
    approve_operator_review_quote,
    assess_scope,
    open_intake,
    prepare_quote,
    record_intake_inputs,
)
from .journey_core import transition_case
from .needs_you import resolve_needs_you
from .organ_adapter_gauntlet import (
    ORGAN_FAMILIES,
    execute_verified_family,
    seal_native_execution,
)
from .settlement_truth import record_controlled_test_settlement
from .state import create_needs_you
from .vesper_journey_runtime import (
    build_vesper_journey_view,
    record_vesper_async_reentry,
    resolve_vesper_journey,
)


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
        raise ValueError(
            f"Phase 7 representative product missing from canonical 68-product registry: {product_name}"
        )
    return deepcopy(row)


def _capture_controlled_source(
    state_root: Path,
    *,
    family_id: str,
    product_name: str,
    conversation_id: str,
) -> dict[str, Any]:
    """Capture one customer-origin source object through the real quarantine boundary."""

    source_text = (
        f"Phase 7 controlled customer source for {product_name}.\n"
        f"Requested family: {family_id}.\n"
        "Purpose: prove source custody, scope lineage and bounded fulfilment without external effects.\n"
    )
    payload = source_text.encode("utf-8")
    sha256 = hashlib.sha256(payload).hexdigest()
    record = validate_and_store_attachment(
        state_root / "attachment_custody",
        conversation_id,
        {
            "file_name": f"phase7-{family_id}-customer-source.txt",
            "content_b64": base64.b64encode(payload).decode("ascii"),
            "file_size": len(payload),
            "sha256": sha256,
            "mime_type": "text/plain",
            "provider": "phase7_controlled_surface",
            "provider_file_id": f"source:{family_id}",
        },
        {"attachments": {"max_bytes": 1024 * 1024}},
    )
    if record["sha256"] != sha256 or record["state"] != "quarantined":
        raise ValueError("Phase 7 source custody did not preserve exact customer bytes")
    return record


def build_phase7_execution_profile(
    dio_root: Path,
    family_id: str,
    *,
    source_custody: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile the family-level Phase 7 execution profile.

    This is deliberately *not* a claim that all 68 commercial products already
    possess canonical Product Compiler manifests. Full per-incarnation
    product-manifest binding remains the Phase 8 gate. Phase 7 compiles only
    the frozen representative family binding needed to prove the common
    Journey seam against the real organ.
    """

    if family_id not in ORGAN_FAMILIES:
        raise ValueError(f"unknown Phase 7 organ family: {family_id}")
    product_name = FAMILY_PRODUCTS[family_id]
    product = _product(Path(dio_root), product_name)
    binding = ORGAN_FAMILIES[family_id]

    source_sha = str(source_custody.get("sha256") or "")
    if len(source_sha) != 64:
        raise ValueError("Phase 7 execution profile requires source-custody SHA-256")

    compilation_basis = {
        "schema": "dio.phase7_family_execution_profile_compilation.v1",
        "family_id": family_id,
        "commercial_product_id": product["product_id"],
        "commercial_product_name": product_name,
        "adapter_id": binding["adapter_id"],
        "adapter_version": binding["adapter_version"],
        "source_path": binding["source_path"],
        "execution_class": binding["execution_class"],
        "repository": binding.get("repository"),
        "repository_commit": binding.get("repository_commit"),
        "source_attachment_sha256": source_sha,
        "phase8_product_manifest_binding": "PENDING",
    }
    compilation_sha256 = _canonical_hash(compilation_basis)

    profile = {
        "schema": "dio.fulfilment_execution_profile.v1",
        "journey_product_id": product_name,
        "commercial_product_id": product["product_id"],
        "phase7_family_id": family_id,
        "profile_compiler": {
            "schema": "dio.phase7_family_profile_compiler.v1",
            "compilation_sha256": compilation_sha256,
            "commercial_registry": "products.commercial_pricing_registry.v1",
            "family_registry": "presence_core.organ_adapter_gauntlet.ORGAN_FAMILIES",
            "canonical_product_manifest_binding": "PHASE8_PENDING",
        },
        "adapter_id": str(binding["adapter_id"]),
        "adapter_version": str(binding["adapter_version"]),
        "execution_gate": {
            "state": "NEEDS_YOU",
            "reason": "Phase 7 controlled golden journey requires explicit bounded initiation.",
        },
        "executor_capabilities": [
            {
                "capability_id": f"phase7.organ.{family_id}",
                "resolution_state": "RESOLVED",
                "provider": {
                    "provider_id": binding["adapter_id"],
                    "provider_kind": binding["execution_class"],
                    "ref": binding["source_path"],
                    "execution_capable": True,
                    "product_scope": [product["product_id"]],
                    "repository": binding.get("repository"),
                    "repository_commit": binding.get("repository_commit"),
                },
            }
        ],
        "source_custody": [
            {
                "attachment_id": source_custody["attachment_id"],
                "sha256": source_sha,
                "size_bytes": int(source_custody["size_bytes"]),
                "mime_type": str(source_custody["mime_type"]),
                "state": str(source_custody["state"]),
                "quarantine_only": bool(source_custody["quarantine_only"]),
                "safe_to_execute": bool(source_custody["safe_to_execute"]),
            }
        ],
        "output_plan": {
            "schema": "dio.compiled_output_plan.v1",
            "outputs": [{"family_id": family_id, "release_state": "HELD"}],
        },
        "release_authority_created": False,
        "external_send_authority": False,
        "authority_created": False,
    }
    profile["execution_profile_sha256"] = _canonical_hash(profile)
    return profile


def build_golden_fulfilment_request(
    dio_root: Path,
    state_root: Path,
    family_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    dio_root = Path(dio_root).resolve()
    state_root = Path(state_root).resolve()
    if family_id not in FAMILY_PRODUCTS:
        raise ValueError(f"unknown Phase 7 golden-journey family: {family_id}")

    product_name = FAMILY_PRODUCTS[family_id]
    product = _product(dio_root, product_name)
    web_conversation = f"phase7-web-{family_id}"

    ingress = resolve_vesper_journey(
        state_root,
        surface="web",
        external_user_id=f"phase7-web-customer-{family_id}",
        conversation_id=web_conversation,
        product_id=product_name,
    )
    case_id = str(ingress["case_id"])
    if ingress["created"] is not True or ingress["view"]["stage"] != "NEW_LEAD":
        raise ValueError("Phase 7 web ingress did not create a canonical JourneyCase")

    cross_channel = resolve_vesper_journey(
        state_root,
        surface="telegram",
        external_user_id=f"phase7-telegram-customer-{family_id}",
        conversation_id=f"phase7-telegram-{family_id}",
        case_id=case_id,
        preferred_return=True,
    )
    if cross_channel["case_id"] != case_id:
        raise ValueError("Phase 7 cross-channel binding split the canonical case")

    source_custody = _capture_controlled_source(
        state_root,
        family_id=family_id,
        product_name=product_name,
        conversation_id=web_conversation,
    )
    case = load_case(state_root, case_id)
    if case is None:
        raise ValueError("Phase 7 canonical case disappeared after surface ingress")
    update_case(
        state_root,
        case,
        patch={
            "source_custody": {
                "schema": "dio.phase7_source_custody.v1",
                "attachments": [deepcopy(source_custody)],
                "source_sha256s": [source_custody["sha256"]],
                "authority_created": False,
            }
        },
        evidence_ref=f"source-attachment:{source_custody['sha256']}",
    )

    open_intake(dio_root, state_root, case_id)
    buyer_class = str((product.get("buyer_classes") or [None])[0] or "")
    if not buyer_class:
        raise ValueError(f"Phase 7 product has no governed buyer class: {product_name}")
    record_intake_inputs(
        dio_root,
        state_root,
        case_id,
        {
            "requested_outcome": f"Phase 7 controlled golden journey for {product_name}",
            "buyer_class": buyer_class,
            "scope_quantity": 1,
        },
        evidence_ref=f"source-attachment:{source_custody['sha256']}",
    )
    scope = assess_scope(dio_root, state_root, case_id)
    if scope["state"] != "SUFFICIENT":
        raise ValueError(f"Phase 7 representative scope is not sufficient: {family_id}")

    quote_result = prepare_quote(dio_root, state_root, case_id)
    if quote_result["decision"] == "NEEDS_YOU":
        quote_result = approve_operator_review_quote(
            dio_root,
            state_root,
            case_id,
            approved_by="human:phase7-controlled-gauntlet",
            approved_amount_zar=int(quote_result["pricing_reference"]["amount_zar"]),
            evidence_ref=f"phase7:operator-quote-approval:{family_id}",
        )
    if quote_result["decision"] != "ALLOW_PRESENTATION" or not quote_result.get("quote"):
        raise ValueError(f"Phase 7 representative quote was not canonically approved: {family_id}")

    record_controlled_test_settlement(
        state_root,
        case_id,
        receipt_id=f"PHASE7-{family_id.upper().replace('_', '-')}",
        authorized_by="operator:phase7-controlled-gauntlet",
        reason="Phase 7 golden journey integration proof; no external funds moved and no revenue recognised.",
    )

    profile = build_phase7_execution_profile(
        dio_root,
        family_id,
        source_custody=source_custody,
    )
    request = build_fulfilment_request(state_root, case_id, profile)
    context = {
        "ingress": ingress,
        "cross_channel": cross_channel,
        "source_custody": source_custody,
    }
    return request, profile, context


ExecutionEvidenceRunner = Callable[..., Mapping[str, Any]]


def run_golden_journey(
    dio_root: Path,
    state_root: Path,
    family_id: str,
    runner: ExecutionEvidenceRunner,
) -> dict[str, Any]:
    dio_root = Path(dio_root).resolve()
    state_root = Path(state_root).resolve()
    request, profile, context = build_golden_fulfilment_request(
        dio_root, state_root, family_id
    )
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

    reentry = record_vesper_async_reentry(
        state_root,
        request["case_id"],
        event_type="FULFILMENT_COMPLETED",
        payload={"fulfilment_result_sha256": result["fulfilment_result_sha256"]},
    )
    if (
        reentry["case_id"] != request["case_id"]
        or reentry["return_route"]["surface"] != "telegram"
        or reentry["view"]["stage"] != "REVIEW_READY"
    ):
        raise ValueError("Phase 7 Vesper async re-entry did not return to the canonical preferred journey")

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
    final_view = build_vesper_journey_view(closed)
    if final_view["stage"] != "CLOSED" or final_view["actions"]:
        raise ValueError("Phase 7 final Vesper view does not reflect canonical CLOSED truth")

    stored = load_case(state_root, request["case_id"]) or {}
    source_custody = context["source_custody"]
    receipt = {
        "schema": GOLDEN_JOURNEY_SCHEMA,
        "family_id": family_id,
        "representative_product": FAMILY_PRODUCTS[family_id],
        "case_id": request["case_id"],
        "surface_ingress": {
            "surface": context["ingress"]["binding"]["surface"],
            "binding_id": context["ingress"]["binding"]["binding_id"],
            "initial_view_sha256": context["ingress"]["view"]["view_sha256"],
        },
        "cross_channel_binding": {
            "surface": context["cross_channel"]["binding"]["surface"],
            "binding_id": context["cross_channel"]["binding"]["binding_id"],
            "same_case": context["cross_channel"]["case_id"] == request["case_id"],
        },
        "source_custody": {
            "attachment_id": source_custody["attachment_id"],
            "sha256": source_custody["sha256"],
            "state": source_custody["state"],
            "bound_into_execution_profile": (
                profile["source_custody"][0]["sha256"] == source_custody["sha256"]
            ),
        },
        "scope_receipt_sha256": stored["scope_receipt"]["scope_receipt_sha256"],
        "quote_truth_sha256": stored["commercial"]["quote_result"]["quote"]["quote_truth_sha256"],
        "settlement_receipt_sha256": stored["settlement"]["settlement_receipt_sha256"],
        "execution_profile_sha256": profile["execution_profile_sha256"],
        "fulfilment_request_sha256": request["fulfilment_request_sha256"],
        "fulfilment_result_sha256": result["fulfilment_result_sha256"],
        "vesper_async_reentry": {
            "event_id": reentry["event"]["event_id"],
            "return_surface": reentry["return_route"]["surface"],
            "review_ready_view_sha256": reentry["view"]["view_sha256"],
        },
        "manifest_sha256": manifest["manifest_sha256"],
        "release_authority_id": authority["authority_id"],
        "delivery_receipt_sha256": delivery_receipt["delivery_receipt_sha256"],
        "final_vesper_view_sha256": final_view["view_sha256"],
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
        source_refs = [
            f"source-attachment-sha256:{row['sha256']}"
            for row in execution_profile.get("source_custody") or []
        ]
        return seal_native_execution(
            family_id,
            fulfilment_request_sha256=str(request["fulfilment_request_sha256"]),
            execution_profile_sha256=str(execution_profile["execution_profile_sha256"]),
            artifacts=artifacts,
            evidence_refs=[*evidence_refs, *source_refs],
        )

    return run_golden_journey(dio_root, state_root, family_id, runner)
