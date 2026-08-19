from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_executor import BLOCKED, FAIL, PASS, execute_customer_case
from products.professional_evidence_projection import load_packet, sha256, slug, write_json
from products.vesper_web_chat import bind_professional_customer_packet


SCHEMA = "dio.professional_evidence.vesper_front_door_receipt.v1"


def _case_root(output_root: Path, incarnation: str) -> Path:
    return output_root.resolve() / slug(incarnation)


def _prepare_vesper_preflight(incarnation: str, output_root: Path, *, now: str) -> tuple[dict[str, Any], Path]:
    preflight_root = output_root.resolve() / "_vesper_front_door"
    preflight_case = preflight_root / slug(incarnation)
    if preflight_case.exists():
        shutil.rmtree(preflight_case)
    materialized = materialize_customer_packet(incarnation, preflight_root)
    packet = load_packet(Path(str(materialized["packet_dir"])))
    chat_root = preflight_case / "VESPER_WEB_CHAT"
    binding = bind_professional_customer_packet(packet, incarnation, output_dir=chat_root, now=now)
    if binding.get("channel") != "web_chat":
        raise RuntimeError("professional front door did not use the Vesper web-chat channel")
    if binding.get("handoff_state") != "READY_FOR_PRODUCT_EXECUTION":
        raise RuntimeError("Vesper web-chat handoff is not ready for product execution")
    if binding.get("resolved_incarnation") != incarnation:
        raise RuntimeError("Vesper web-chat route drifted away from the requested canonical incarnation")
    if binding.get("examiner_data_used") is not False:
        raise RuntimeError("Vesper web-chat preflight consumed withheld examiner data")
    if binding.get("whatsapp_used") is not False or binding.get("telegram_used") is not False:
        raise RuntimeError("professional Vesper proof must not depend on WhatsApp or Telegram")
    return binding, chat_root


def _vesper_artifacts(case_root: Path, copied_chat: Path) -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(copied_chat.rglob("*")):
        if not path.is_file():
            continue
        artifacts.append(
            {
                "path": str(path.relative_to(case_root)),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "proof_role": "vesper_web_chat_front_door",
            }
        )
    if not artifacts:
        raise RuntimeError("Vesper web-chat proof directory is empty")
    return artifacts


def execute_customer_case_via_vesper(
    incarnation: str,
    output_root: Path,
    *,
    operator_id: str,
    now: str,
    online: bool = False,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        binding, chat_root = _prepare_vesper_preflight(incarnation, output_root, now=now)
    except Exception as exc:
        case_root = _case_root(output_root, incarnation)
        if case_root.exists():
            shutil.rmtree(case_root)
        case_root.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": SCHEMA,
            "incarnation": incarnation,
            "status": FAIL,
            "product_pipeline_executed": False,
            "vesper_web_chat_front_door_verified": False,
            "chat_completed_before_product_execution": False,
            "channel": "web_chat",
            "whatsapp_used": False,
            "telegram_used": False,
            "golden_fixture_used": False,
            "examiner_data_used_during_execution": False,
            "human_review_required": True,
            "external_publication": "REFUSE",
            "external_send": "REFUSE",
            "media_spend": "REFUSE",
            "payment": "REFUSE",
            "market_validation_claimed": False,
            "authority_created": False,
            "external_effects": False,
            "error": f"VESPER_FRONT_DOOR_ERROR {type(exc).__name__}: {exc}",
        }
        write_json(case_root / "VESPER_ROUTED_PROFESSIONAL_RECEIPT.json", receipt)
        return receipt

    product_receipt = execute_customer_case(
        incarnation,
        output_root,
        operator_id=operator_id,
        now=now,
        online=online,
    )
    case_root = _case_root(output_root, incarnation)
    if not case_root.is_dir():
        raise RuntimeError("product executor returned without a professional case root")
    product_packet_fingerprint = str(product_receipt.get("packet_fingerprint") or "")
    if product_packet_fingerprint != str(binding.get("packet_fingerprint") or ""):
        product_receipt = {
            **product_receipt,
            "status": FAIL,
            "error": "Vesper/customer product packet fingerprint mismatch",
        }

    copied_chat = case_root / "VESPER_WEB_CHAT"
    if copied_chat.exists():
        shutil.rmtree(copied_chat)
    shutil.copytree(chat_root, copied_chat)
    binding_path = copied_chat / "VESPER_WEB_CHAT_BINDING.json"
    vesper_artifacts = _vesper_artifacts(case_root, copied_chat)
    if not binding_path.is_file():
        product_receipt = {
            **product_receipt,
            "status": FAIL,
            "error": "Vesper binding artifact was not preserved into the professional case",
        }

    status = str(product_receipt.get("status") or FAIL)
    if status not in {PASS, FAIL, BLOCKED}:
        status = FAIL
    front_door_verified = (
        binding.get("handoff_state") == "READY_FOR_PRODUCT_EXECUTION"
        and binding.get("resolved_incarnation") == incarnation
        and binding.get("channel") == "web_chat"
        and binding.get("examiner_data_used") is False
        and binding.get("whatsapp_used") is False
        and binding.get("telegram_used") is False
        and product_packet_fingerprint == binding.get("packet_fingerprint")
        and binding_path.is_file()
        and bool(vesper_artifacts)
    )
    if status == PASS and not front_door_verified:
        status = FAIL

    product_artifacts = list(product_receipt.get("artifacts") or [])
    combined_artifacts = product_artifacts + vesper_artifacts
    combined = {
        **product_receipt,
        "schema": SCHEMA,
        "status": status,
        "vesper_web_chat_front_door_verified": front_door_verified,
        "chat_completed_before_product_execution": True,
        "channel": "web_chat",
        "vesper_conversation_id": binding.get("conversation_id"),
        "vesper_binding_fingerprint": binding.get("binding_fingerprint"),
        "vesper_binding_artifact": str(binding_path.relative_to(case_root)) if binding_path.is_file() else None,
        "vesper_binding_sha256": sha256(binding_path) if binding_path.is_file() else None,
        "vesper_handoff_state": binding.get("handoff_state"),
        "vesper_artifact_count": len(vesper_artifacts),
        "vesper_artifacts": vesper_artifacts,
        "artifacts": combined_artifacts,
        "whatsapp_used": False,
        "telegram_used": False,
        "sequence": ["VESPER_WEB_CHAT_INTAKE", "PRODUCT_EXECUTION", "HUMAN_REVIEW_GATE"],
        "human_review_required": True,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "market_validation_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
    write_json(case_root / "VESPER_ROUTED_PROFESSIONAL_RECEIPT.json", combined)
    outer_path = case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json"
    if outer_path.is_file():
        outer = json.loads(outer_path.read_text(encoding="utf-8"))
        outer.update(
            {
                "status": status,
                "vesper_web_chat_front_door_verified": front_door_verified,
                "chat_completed_before_product_execution": True,
                "channel": "web_chat",
                "vesper_conversation_id": binding.get("conversation_id"),
                "vesper_binding_fingerprint": binding.get("binding_fingerprint"),
                "vesper_artifact_count": len(vesper_artifacts),
                "vesper_artifacts": vesper_artifacts,
                "artifacts": list(outer.get("artifacts") or []) + vesper_artifacts,
                "whatsapp_used": False,
                "telegram_used": False,
            }
        )
        write_json(outer_path, outer)
    # The copied Vesper bytes are now part of the final case; the preflight copy
    # is disposable and must not become a second source of truth.
    preflight_case = output_root / "_vesper_front_door" / slug(incarnation)
    if preflight_case.exists():
        shutil.rmtree(preflight_case)
    return combined


__all__ = ["SCHEMA", "execute_customer_case_via_vesper"]
