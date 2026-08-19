from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_executor import BLOCKED, FAIL, PASS
from products.professional_evidence_prepared_executor import execute_prepared_customer_case
from products.professional_evidence_projection import load_packet, sha256, slug, write_json
from products.vesper_web_chat import bind_professional_customer_packet


SCHEMA = "dio.professional_evidence.vesper_front_door_receipt.v2"


def _case_root(output_root: Path, incarnation: str) -> Path:
    return output_root.resolve() / slug(incarnation)


def _source_files(packet: dict[str, Any]) -> list[Path]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    rows = []
    for item in packet["manifest"].get("files") or []:
        relative = str(item.get("path") or "")
        if not relative.startswith("SOURCES/"):
            continue
        path = (packet_dir / relative).resolve()
        if packet_dir not in path.parents or not path.is_file():
            raise RuntimeError(f"customer source path is invalid: {relative}")
        if sha256(path) != str(item.get("sha256") or ""):
            raise RuntimeError(f"customer source hash drifted before Vesper: {relative}")
        rows.append(path)
    if not rows:
        raise RuntimeError("professional customer packet contains no source files")
    return sorted(rows)


def _rehydrate_sources_from_quarantine(packet: dict[str, Any], chat_root: Path) -> list[dict[str, Any]]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    manifest_paths = sorted((chat_root / "state" / "vesper" / "quarantine").glob("*/ATTACHMENT_INTAKE.json"))
    if not manifest_paths:
        raise RuntimeError("Vesper produced no attachment quarantine manifests")

    quarantined: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for row in manifest.get("attachments") or []:
            key = (str(row.get("filename") or ""), str(row.get("sha256") or ""))
            quarantined.setdefault(key, []).append({**row, "manifest_path": manifest_path})

    bindings = []
    for source in _source_files(packet):
        source_sha = sha256(source)
        key = (source.name, source_sha)
        matches = quarantined.get(key) or []
        if not matches:
            raise RuntimeError(f"Vesper quarantine does not contain exact customer source bytes: {source.name}")
        row = matches.pop(0)
        quarantine_path = Path(str(row.get("quarantine_path") or "")).resolve()
        if not quarantine_path.is_file():
            raise RuntimeError(f"Vesper quarantined source is missing: {source.name}")
        quarantine_sha = sha256(quarantine_path)
        if quarantine_sha != source_sha or quarantine_sha != str(row.get("sha256") or ""):
            raise RuntimeError(f"Vesper quarantine hash mismatch: {source.name}")

        # This is the critical full-pipeline seam: the product-facing source path
        # is rewritten from Vesper's quarantined bytes before the executor starts.
        source.write_bytes(quarantine_path.read_bytes())
        if sha256(source) != quarantine_sha:
            raise RuntimeError(f"Vesper source rehydration failed: {source.name}")
        bindings.append(
            {
                "customer_packet_path": str(source.relative_to(packet_dir)),
                "customer_packet_sha256": source_sha,
                "attachment_id": row.get("attachment_id"),
                "source_ref": row.get("source_ref"),
                "quarantine_manifest": str(Path(row["manifest_path"]).relative_to(chat_root)),
                "quarantine_artifact": str(quarantine_path.relative_to(chat_root)),
                "quarantine_sha256": quarantine_sha,
                "rehydrated_into_product_packet": True,
            }
        )

    # Reloading verifies the original customer packet manifest still matches
    # after every SOURCES/* file was rewritten from quarantine bytes.
    rebound = load_packet(packet_dir)
    if rebound["packet_fingerprint"] != packet["packet_fingerprint"]:
        raise RuntimeError("customer packet fingerprint changed after Vesper quarantine rehydration")
    return bindings


def _prepare_vesper_front_door(incarnation: str, output_root: Path, *, now: str) -> tuple[dict[str, Any], Path]:
    case_root = _case_root(output_root, incarnation)
    if case_root.exists():
        shutil.rmtree(case_root)
    materialized = materialize_customer_packet(incarnation, output_root.resolve())
    packet_dir = Path(str(materialized["packet_dir"])).resolve()
    enrich_customer_packet(incarnation, packet_dir)
    packet = load_packet(packet_dir)

    chat_root = case_root / "VESPER_WEB_CHAT"
    binding = bind_professional_customer_packet(packet, incarnation, output_dir=chat_root, now=now)
    if binding.get("channel") != "web_chat":
        raise RuntimeError("professional front door did not use the Vesper web-chat channel")
    if binding.get("handoff_state") != "READY_FOR_PRODUCT_EXECUTION":
        raise RuntimeError("Vesper web-chat handoff is not ready for product execution")
    if binding.get("resolved_incarnation") != incarnation:
        raise RuntimeError("Vesper web-chat route drifted away from the requested canonical incarnation")
    if binding.get("examiner_data_used") is not False:
        raise RuntimeError("Vesper web-chat consumed withheld examiner data")
    if binding.get("whatsapp_used") is not False or binding.get("telegram_used") is not False:
        raise RuntimeError("professional Vesper proof must not depend on WhatsApp or Telegram")

    source_bindings = _rehydrate_sources_from_quarantine(packet, chat_root)
    binding = {
        **binding,
        "source_bindings": source_bindings,
        "source_binding_count": len(source_bindings),
        "all_product_source_bytes_rehydrated_from_vesper_quarantine": all(
            row.get("rehydrated_into_product_packet") is True for row in source_bindings
        ),
        "executor_may_rematerialize_packet": False,
    }
    binding["binding_fingerprint_after_rehydration"] = "sha256:" + __import__("hashlib").sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    write_json(chat_root / "VESPER_WEB_CHAT_BINDING.json", binding)
    return binding, case_root


def _vesper_artifacts(case_root: Path) -> list[dict[str, Any]]:
    copied_chat = case_root / "VESPER_WEB_CHAT"
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
        binding, case_root = _prepare_vesper_front_door(incarnation, output_root, now=now)
    except Exception as exc:
        case_root = _case_root(output_root, incarnation)
        if not case_root.exists():
            case_root.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": SCHEMA,
            "incarnation": incarnation,
            "status": FAIL,
            "product_pipeline_executed": False,
            "vesper_web_chat_front_door_verified": False,
            "chat_completed_before_product_execution": False,
            "product_consumed_vesper_quarantined_bytes": False,
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

    product_receipt = execute_prepared_customer_case(
        incarnation,
        case_root,
        operator_id=operator_id,
        now=now,
        online=online,
        prepared_by="vesper_web_chat",
    )
    packet_fingerprint = str(product_receipt.get("packet_fingerprint") or "")
    if packet_fingerprint != str(binding.get("packet_fingerprint") or ""):
        product_receipt = {
            **product_receipt,
            "status": FAIL,
            "error": "Vesper/customer product packet fingerprint mismatch",
        }

    binding_path = case_root / "VESPER_WEB_CHAT" / "VESPER_WEB_CHAT_BINDING.json"
    vesper_artifacts = _vesper_artifacts(case_root)
    source_bindings = list(binding.get("source_bindings") or [])
    quarantine_consumed = bool(source_bindings) and all(
        row.get("rehydrated_into_product_packet") is True for row in source_bindings
    )
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
        and packet_fingerprint == binding.get("packet_fingerprint")
        and binding.get("executor_may_rematerialize_packet") is False
        and product_receipt.get("rematerialized_by_executor") is False
        and quarantine_consumed
        and binding_path.is_file()
        and bool(vesper_artifacts)
    )
    if status == PASS and not front_door_verified:
        status = FAIL

    combined = {
        **product_receipt,
        "schema": SCHEMA,
        "status": status,
        "vesper_web_chat_front_door_verified": front_door_verified,
        "chat_completed_before_product_execution": True,
        "product_consumed_vesper_quarantined_bytes": quarantine_consumed,
        "executor_rematerialized_packet": product_receipt.get("rematerialized_by_executor") is not False,
        "channel": "web_chat",
        "vesper_conversation_id": binding.get("conversation_id"),
        "vesper_binding_fingerprint": binding.get("binding_fingerprint_after_rehydration") or binding.get("binding_fingerprint"),
        "vesper_binding_artifact": str(binding_path.relative_to(case_root)) if binding_path.is_file() else None,
        "vesper_binding_sha256": sha256(binding_path) if binding_path.is_file() else None,
        "vesper_handoff_state": binding.get("handoff_state"),
        "vesper_source_binding_count": len(source_bindings),
        "vesper_source_bindings": source_bindings,
        "vesper_artifact_count": len(vesper_artifacts),
        "vesper_artifacts": vesper_artifacts,
        "whatsapp_used": False,
        "telegram_used": False,
        "sequence": ["VESPER_WEB_CHAT_INTAKE", "VESPER_QUARANTINE_REHYDRATION", "PRODUCT_EXECUTION", "HUMAN_REVIEW_GATE"],
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
                "product_consumed_vesper_quarantined_bytes": quarantine_consumed,
                "channel": "web_chat",
                "vesper_conversation_id": binding.get("conversation_id"),
                "vesper_binding_fingerprint": binding.get("binding_fingerprint_after_rehydration") or binding.get("binding_fingerprint"),
                "vesper_source_binding_count": len(source_bindings),
                "whatsapp_used": False,
                "telegram_used": False,
            }
        )
        write_json(outer_path, outer)
    return combined


__all__ = ["SCHEMA", "execute_customer_case_via_vesper"]
