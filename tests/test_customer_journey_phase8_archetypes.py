from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from market_command.intelligence import IntelligenceStore
from products.commercial_pricing_registry import build_commercial_pricing_registry
from presence_core.attachments import validate_and_store_attachment
from presence_core.customer_cases import load_case, update_case
from presence_core.deliverable_release_v2 import (
    build_deliverable_manifest,
    create_manifest_release_authority,
    deliver_manifest,
)
from presence_core.fulfilment_contract import (
    build_fulfilment_request,
    dispatch_fulfilment,
)
from presence_core.intake_scope_quote import (
    approve_operator_review_quote,
    assess_scope,
    open_intake,
    prepare_quote,
    record_intake_inputs,
)
from presence_core.journey_core import transition_case
from presence_core.needs_you import resolve_needs_you
from presence_core.product_binding_registry import (
    PHASE7_ACCEPTANCE,
    build_phase8_execution_profile,
    compile_product_journey_binding,
)
from presence_core.settlement_truth import record_controlled_test_settlement
from presence_core.state import create_needs_you
from presence_core.vesper_journey_runtime import (
    build_vesper_journey_view,
    record_vesper_async_reentry,
    resolve_vesper_journey,
)


ROOT = Path(__file__).resolve().parents[1]

AdapterFactory = Callable[[Path, dict[str, Any]], Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _product_row(product_name: str) -> dict[str, Any]:
    registry = build_commercial_pricing_registry(ROOT)
    return next(row for row in registry["products"] if row["name"] == product_name)


def _capture_source(
    state_root: Path,
    *,
    conversation_id: str,
    product_name: str,
) -> dict[str, Any]:
    payload = (
        f"Phase 8 controlled customer source for {product_name}.\n"
        "Purpose: prove full Customer Journey Spine binding.\n"
    ).encode("utf-8")
    return validate_and_store_attachment(
        state_root / "attachment_custody",
        conversation_id,
        {
            "file_name": "phase8-source.txt",
            "content_b64": base64.b64encode(payload).decode("ascii"),
            "file_size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "mime_type": "text/plain",
            "provider": "phase8_controlled_surface",
            "provider_file_id": "phase8-source",
        },
        {"attachments": {"max_bytes": 1024 * 1024}},
    )


def _artifact(
    path: Path,
    *,
    artifact_id: str,
    binding: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "kind": "application/json",
        "path": str(path.resolve()),
        "file_name": path.name,
        "mime_type": "application/json",
        "sha256": _sha256(path),
        "purpose": "primary_customer_output",
        "customer_visibility": "VISIBLE",
        "provenance": {
            "phase": 8,
            "product_name": binding["product_name"],
            "route_id": binding["fulfilment_profile"]["route_id"],
            "route_fingerprint": binding["fulfilment_profile"]["route_fingerprint"],
        },
        "release_conditions": list(binding["release_profile"]["conditions"]),
        "source_lineage": [
            f"fulfilment-request:{request['fulfilment_request_sha256']}",
            f"phase8-binding:{binding['binding_sha256']}",
        ],
        "release_state": "HELD",
        "release_authority": False,
        "external_send_authority": False,
        "authority_created": False,
    }


def _prepare_case(
    state_root: Path,
    product_name: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    web_conversation = "phase8-web-" + product_name.lower().replace(" ", "-")
    ingress = resolve_vesper_journey(
        state_root,
        surface="web",
        external_user_id="phase8-web-user-" + product_name.lower().replace(" ", "-"),
        conversation_id=web_conversation,
        product_id=product_name,
    )
    case_id = ingress["case_id"]

    telegram = resolve_vesper_journey(
        state_root,
        surface="telegram",
        external_user_id="phase8-tg-user-" + product_name.lower().replace(" ", "-"),
        conversation_id="phase8-tg-" + product_name.lower().replace(" ", "-"),
        case_id=case_id,
        preferred_return=True,
    )
    assert telegram["case_id"] == case_id

    custody = _capture_source(
        state_root,
        conversation_id=web_conversation,
        product_name=product_name,
    )
    case = load_case(state_root, case_id)
    assert case is not None
    update_case(
        state_root,
        case,
        patch={
            "source_custody": {
                "schema": "dio.phase8_source_custody.v1",
                "attachments": [custody],
                "authority_created": False,
            }
        },
        evidence_ref=f"source-attachment:{custody['sha256']}",
    )

    open_intake(ROOT, state_root, case_id)
    product = _product_row(product_name)
    record_intake_inputs(
        ROOT,
        state_root,
        case_id,
        {
            "requested_outcome": f"Controlled Phase 8 journey for {product_name}",
            "buyer_class": product["buyer_classes"][0],
            "scope_quantity": 1,
        },
        evidence_ref=f"source-attachment:{custody['sha256']}",
    )
    scope = assess_scope(ROOT, state_root, case_id)
    assert scope["state"] == "SUFFICIENT"

    quote = prepare_quote(ROOT, state_root, case_id)
    if quote["decision"] == "NEEDS_YOU":
        quote = approve_operator_review_quote(
            ROOT,
            state_root,
            case_id,
            approved_by="human:phase8-controlled-gauntlet",
            approved_amount_zar=int(quote["pricing_reference"]["amount_zar"]),
            evidence_ref=f"phase8:operator-quote:{product_name}",
        )
    assert quote["decision"] == "ALLOW_PRESENTATION"

    settlement = record_controlled_test_settlement(
        state_root,
        case_id,
        receipt_id="PHASE8-" + product["product_id"].upper(),
        authorized_by="operator:phase8-controlled-gauntlet",
        reason="Phase 8 archetype proof; no external funds moved and no revenue recognised.",
    )
    assert settlement["external_funds_moved"] is False
    assert settlement["revenue_recognised"] is False

    profile = build_phase8_execution_profile(ROOT, product_name)
    request = build_fulfilment_request(state_root, case_id, profile)
    return request, profile, {
        "ingress": ingress,
        "telegram": telegram,
        "custody": custody,
    }


def _finish_case(
    state_root: Path,
    product_name: str,
    request: dict[str, Any],
    adapter: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    result = dispatch_fulfilment(
        state_root,
        request,
        {request["adapter_id"]: adapter},
    )
    reentry = record_vesper_async_reentry(
        state_root,
        request["case_id"],
        event_type="FULFILMENT_COMPLETED",
        payload={"fulfilment_result_sha256": result["fulfilment_result_sha256"]},
    )
    assert reentry["return_route"]["surface"] == "telegram"
    assert reentry["view"]["stage"] == "REVIEW_READY"

    manifest = build_deliverable_manifest(state_root, request["case_id"])
    needs = create_needs_you(
        state_root,
        reason="fulfilment_release_review",
        conversation_id=f"phase8:{request['case_id']}",
        product=product_name,
        summary=f"Approve exact Phase 8 manifest SHA-256 {manifest['manifest_sha256']}",
    )
    resolved = resolve_needs_you(
        state_root,
        needs["needs_you_id"],
        decision="APPROVE",
        resolved_by="human:phase8-controlled-gauntlet",
        evidence_ref=f"manifest-sha256:{manifest['manifest_sha256']}",
    )
    authority = create_manifest_release_authority(
        state_root,
        case_id=request["case_id"],
        needs_you_id=resolved["needs_you_id"],
        delivery_channels=["controlled_test"],
    )

    delivered = deliver_manifest(
        state_root,
        authority["authority_id"],
        channel="controlled_test",
        destination="phase8://controlled/" + product_name.lower().replace(" ", "-"),
        transport=lambda package: {
            "sent": True,
            "provider_receipt": {
                "transport": "phase8_controlled_test",
                "case_id": package["case_id"],
                "manifest_sha256": package["manifest_sha256"],
                "external_network_send": False,
                "external_effects": False,
            },
        },
    )
    assert delivered["delivered"] is True
    receipt = delivered["delivery_receipt"]

    closed = transition_case(
        state_root,
        request["case_id"],
        "CLOSED",
        evidence_ref=f"phase8-delivery:{receipt['delivery_receipt_sha256']}",
    )
    final_view = build_vesper_journey_view(closed)
    assert final_view["stage"] == "CLOSED"
    assert final_view["actions"] == []

    return {
        "schema": "dio.customer_journey.phase8_archetype_proof.v1",
        "product_name": product_name,
        "case_id": request["case_id"],
        "fulfilment_result_sha256": result["fulfilment_result_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "delivery_receipt_sha256": receipt["delivery_receipt_sha256"],
        "final_stage": closed["stage"],
        "external_network_send": False,
        "external_funds_moved": False,
        "revenue_recognised": False,
        "authority_created": False,
        "proved": True,
    }


def _market_adapter(
    state_root: Path,
    binding: dict[str, Any],
) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    def adapter(
        request: dict[str, Any],
        execution_profile: dict[str, Any],
    ) -> dict[str, Any]:
        store = IntelligenceStore(
            state_root / "phase8_market_intelligence.sqlite",
            state_root / "phase8_market_events.jsonl",
        )
        snapshot = store.record_snapshot(
            {
                "channel_id": "PHASE8_CONTROLLED_RESEARCH",
                "external_campaign_id": "PHASE8-MARKET-RADAR",
                "window_start": "2026-09-01",
                "window_end": "2026-09-18",
                "impressions": 120,
                "reach": 100,
                "views": 80,
                "clicks": 12,
                "spend_minor": 0,
                "conversion_value_minor": 0,
                "source_mode": "controlled_test",
                "evidence_grade": "controlled_test",
            }
        )
        payload = {
            "schema": "dio.phase8.market_intelligence_pack.v1",
            "snapshot": snapshot,
            "scoreboard": store.portfolio_scoreboard(),
            "write_authority": "blocked_by_design",
            "outreach_authority": False,
            "spend_authority": False,
        }
        path = state_root / "market-radar-intelligence.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "COMPLETED",
            "artifacts": [
                _artifact(
                    path,
                    artifact_id="market-radar-intelligence",
                    binding=binding,
                    request=request,
                )
            ],
            "evidence_refs": [
                "native:market_command.intelligence.IntelligenceStore",
                f"phase8-binding:{binding['binding_sha256']}",
            ],
            "organ_steps": [
                "record_controlled_market_snapshot",
                "build_read_only_portfolio_scoreboard",
            ],
            "release_authority": False,
            "external_send_authority": False,
            "authority_created": False,
        }

    return adapter


def _vesper_adapter(
    state_root: Path,
    binding: dict[str, Any],
) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    def adapter(
        request: dict[str, Any],
        execution_profile: dict[str, Any],
    ) -> dict[str, Any]:
        case = load_case(state_root, request["case_id"])
        assert case is not None
        view = build_vesper_journey_view(case)
        assert view["stage"] == "PROCESSING"
        assert view["authority_created"] is False
        path = state_root / "vesper-case-service-view.json"
        path.write_text(
            json.dumps(view, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "COMPLETED",
            "artifacts": [
                _artifact(
                    path,
                    artifact_id="vesper-case-service-view",
                    binding=binding,
                    request=request,
                )
            ],
            "evidence_refs": [
                "native:presence_core.vesper_journey_runtime",
                f"phase8-binding:{binding['binding_sha256']}",
            ],
            "organ_steps": [
                "project_canonical_processing_state",
                "preserve_action_authority_boundary",
            ],
            "release_authority": False,
            "external_send_authority": False,
            "authority_created": False,
        }

    return adapter


def _run_native_phase8_journey(
    tmp_path: Path,
    product_name: str,
    adapter_factory: AdapterFactory,
) -> dict[str, Any]:
    state_root = tmp_path / product_name.lower().replace(" ", "_")
    request, profile, context = _prepare_case(state_root, product_name)
    binding = compile_product_journey_binding(ROOT, product_name)

    assert request["execution_profile_sha256"] == profile["execution_profile_sha256"]
    assert context["ingress"]["view"]["stage"] == "NEW_LEAD"
    assert context["telegram"]["case_id"] == request["case_id"]
    assert context["custody"]["state"] == "quarantined"

    adapter = adapter_factory(state_root, binding)
    return _finish_case(state_root, product_name, request, adapter)


def test_archetype_f_market_radar_runs_real_market_intelligence_golden_journey(
    tmp_path: Path,
) -> None:
    binding = compile_product_journey_binding(ROOT, "Market Radar")
    assert binding["journey_archetype"]["id"] == "F"
    assert binding["fulfilment_profile"]["route_id"] == "market_intelligence"

    receipt = _run_native_phase8_journey(
        tmp_path,
        "Market Radar",
        _market_adapter,
    )
    assert receipt["proved"] is True
    assert receipt["final_stage"] == "CLOSED"
    assert receipt["external_network_send"] is False
    assert receipt["external_funds_moved"] is False
    assert receipt["revenue_recognised"] is False


def test_archetype_h_vesper_desk_runs_real_presence_case_service_golden_journey(
    tmp_path: Path,
) -> None:
    binding = compile_product_journey_binding(ROOT, "Vesper Desk")
    assert binding["journey_archetype"]["id"] == "H"
    assert binding["fulfilment_profile"]["route_id"] == "vesper_case_service"

    receipt = _run_native_phase8_journey(
        tmp_path,
        "Vesper Desk",
        _vesper_adapter,
    )
    assert receipt["proved"] is True
    assert receipt["final_stage"] == "CLOSED"
    assert receipt["authority_created"] is False


def test_eight_archetypes_have_a_complete_proof_ledger(tmp_path: Path) -> None:
    market = _run_native_phase8_journey(
        tmp_path,
        "Market Radar",
        _market_adapter,
    )
    vesper = _run_native_phase8_journey(
        tmp_path,
        "Vesper Desk",
        _vesper_adapter,
    )

    ledger = {
        "A": {
            "product": "HOMS Assess",
            "route": "homs_assessment",
            "proof": PHASE7_ACCEPTANCE,
        },
        "B": {
            "product": "Sophia Review",
            "route": "sophia_review",
            "proof": PHASE7_ACCEPTANCE,
        },
        "C": {
            "product": "VAMP Performance",
            "route": "vamp_snapshot",
            "proof": PHASE7_ACCEPTANCE,
        },
        "D": {
            "product": "GrantProof",
            "route": "obligation_assurance",
            "proof": PHASE7_ACCEPTANCE,
        },
        "E": {
            "product": "Document Studio Edit",
            "route": "document_studio",
            "proof": PHASE7_ACCEPTANCE,
        },
        "F": {
            "product": "Market Radar",
            "route": "market_intelligence",
            "proof": market,
        },
        "G": {
            "product": "Campaign Lab",
            "route": "nichefoundry_campaign",
            "proof": PHASE7_ACCEPTANCE,
        },
        "H": {
            "product": "Vesper Desk",
            "route": "vesper_case_service",
            "proof": vesper,
        },
    }

    assert set(ledger) == set("ABCDEFGH")
    for archetype, row in ledger.items():
        binding = compile_product_journey_binding(ROOT, row["product"])
        assert binding["journey_archetype"]["id"] == archetype
        assert binding["fulfilment_profile"]["route_id"] == row["route"]

    for archetype in ("A", "B", "C", "D", "E", "G"):
        assert ledger[archetype]["proof"]["token"] == (
            "DIO_CUSTOMER_JOURNEY_PHASE7_ORGAN_ADAPTER_GAUNTLET_VERIFIED"
        )
    assert ledger["F"]["proof"]["proved"] is True
    assert ledger["H"]["proof"]["proved"] is True
