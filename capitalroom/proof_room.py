from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CAPITALROOM_SCHEMA = "dio.capitalroom.proof_room.v1"
MANIFEST_SCHEMA = "dio.capitalroom.manifest.v1"

EXPECTED_WAVE_STATES = {
    1: "FUSION_WAVE1_READY",
    2: "FUSION_WAVE2_READY",
    3: "FUSION_WAVE3_READY",
    4: "FUSION_WAVE4_READY",
    5: "FUSION_WAVE5_READY",
    6: "FUSION_WAVE6_READY",
    7: "FUSION_WAVE7_READY",
    8: "FUSION_WAVE8_READY",
}

PRODUCT_IDS = (
    "dio_assurance",
    "dio_agent_authority",
    "dio_vendorproof",
    "dio_accreditation",
    "dio_tenderproof",
    "dio_grantproof",
    "dio_research_integrity",
    "dio_regops",
    "dio_capitalroom",
)

ALLOWED_PROOF_STATES = {
    "PROVEN",
    "LOCKED",
    "REGISTERED_NOT_PROVEN",
    "INTERNAL_PROOF_PRODUCT",
    "NOT_PROVEN",
    "NOT_EXECUTED",
}


class ProofRoomError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _now(value: str | None) -> str:
    return value or datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _redact_string(value: str) -> str:
    if value.startswith("/"):
        return "<redacted-local-path>"
    if "/home/" in value:
        return value[: value.find("/home/")] + "<redacted-local-path>"
    return value


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"receipt", "path", "source_path", "case_path", "source_job_path"} and isinstance(item, str):
                result[key] = "<redacted-local-path>"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _receipt_proof(wave: int, receipt: dict[str, Any]) -> dict[str, Any]:
    expected = EXPECTED_WAVE_STATES[wave]
    if receipt.get("state") != expected:
        raise ProofRoomError(f"Wave {wave} is not locally accepted: {receipt.get('state')}")
    if receipt.get("blockers") not in ([], None):
        raise ProofRoomError(f"Wave {wave} receipt contains blockers.")
    redacted = _redact(copy.deepcopy(receipt))
    return {
        "wave": wave,
        "expected_state": expected,
        "observed_state": receipt.get("state"),
        "status": "PROVEN",
        "receipt_sha256": _fingerprint(receipt),
        "receipt_snapshot": redacted,
    }


def _portfolio_products(portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    if portfolio.get("schema") != "dio.product_portfolio.v1":
        raise ProofRoomError("Unsupported DIO product portfolio schema.")
    by_id = {str(item.get("id")): item for item in portfolio.get("products") or []}
    missing = sorted(set(PRODUCT_IDS) - set(by_id))
    if missing:
        raise ProofRoomError(f"CapitalRoom product proof is missing governed product profiles: {missing}")

    result: list[dict[str, Any]] = []
    for product_id in PRODUCT_IDS:
        item = by_id[product_id]
        proof_state = "INTERNAL_PROOF_PRODUCT" if product_id == "dio_capitalroom" else "REGISTERED_NOT_PROVEN"
        result.append(
            {
                "id": product_id,
                "name": item.get("name"),
                "category": item.get("category"),
                "portfolio_status": item.get("status"),
                "runtime_mode": item.get("runtime_mode"),
                "customer_facing": item.get("customer_facing"),
                "campaign_enabled": item.get("campaign_enabled"),
                "proof_state": proof_state,
                "risk_boundary": item.get("risk_boundary"),
                "activation_gates": copy.deepcopy(item.get("activation_gates") or []),
            }
        )
    return result


def _executor_proof(registry: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if registry.get("schema") != "dio.vertical_executors.registry.v1":
        raise ProofRoomError("Unsupported vertical executor registry schema.")
    locked: list[dict[str, Any]] = []
    bound: list[dict[str, Any]] = []
    for executor in registry.get("executors") or []:
        for capability in executor.get("capabilities") or []:
            row = {
                "executor_id": executor.get("executor_id"),
                "capability": capability.get("capability"),
                "binding_state": capability.get("binding_state"),
                "external_side_effect": capability.get("external_side_effect"),
                "consequence_class": capability.get("consequence_class"),
            }
            if capability.get("binding_state") == "locked":
                row["status"] = "LOCKED"
                row["lock_reason"] = capability.get("lock_reason")
                locked.append(row)
            elif capability.get("binding_state") == "bound":
                row["status"] = "PROVEN"
                row["execution_status"] = "NOT_EXECUTED"
                row["entrypoint_kind"] = capability.get("entrypoint_kind")
                row["entrypoint_ref"] = capability.get("entrypoint_ref")
                bound.append(row)
    locked.sort(key=lambda item: (str(item["executor_id"]), str(item["capability"])))
    bound.sort(key=lambda item: (str(item["executor_id"]), str(item["capability"])))
    return bound, locked


def build_capitalroom(
    *,
    phase0_snapshot: dict[str, Any],
    incarnation_receipt: dict[str, Any],
    wave_receipts: dict[int, dict[str, Any]],
    product_portfolio: dict[str, Any],
    vertical_registry: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    if phase0_snapshot.get("overall_state") != "READY":
        raise ProofRoomError("Phase 0 source truth is not READY.")
    if incarnation_receipt.get("state") != "READY_FOR_FUSION":
        raise ProofRoomError("Incarnation is not READY_FOR_FUSION.")
    if set(wave_receipts) != set(EXPECTED_WAVE_STATES):
        raise ProofRoomError("CapitalRoom requires exactly Fusion Wave receipts 1 through 8.")

    receipt_proofs = [_receipt_proof(wave, wave_receipts[wave]) for wave in sorted(wave_receipts)]
    products = _portfolio_products(product_portfolio)
    bound_capabilities, locked_capabilities = _executor_proof(vertical_registry)

    wave4 = wave_receipts[4]
    wave5 = wave_receipts[5]
    wave6 = wave_receipts[6]
    wave7 = wave_receipts[7]
    wave8 = wave_receipts[8]

    architecture_claims = [
        {
            "claim": "Canonical source truth snapshot is READY.",
            "status": "PROVEN",
            "source": "phase0_snapshot",
            "source_sha256": _fingerprint(phase0_snapshot),
        },
        {
            "claim": "The DIO organism reached READY_FOR_FUSION before fusion waves began.",
            "status": "PROVEN",
            "source": "incarnation_receipt",
            "source_sha256": _fingerprint(incarnation_receipt),
        },
        {
            "claim": "Fusion Waves 1 through 8 are host-accepted.",
            "status": "PROVEN",
            "source": "fusion_receipt_chain",
            "source_sha256": _fingerprint(receipt_proofs),
        },
        {
            "claim": "Valinor is preserved as sole kernel authority.",
            "status": "PROVEN" if wave4.get("kernel_authority") == "Valinor" and wave8.get("kernel_authority") == "Valinor" else "NOT_PROVEN",
            "source": "wave4_and_wave8_receipts",
        },
        {
            "claim": "ARDA is execution identity/attestation authority, not kernel authority.",
            "status": "PROVEN" if wave4.get("execution_identity_authority") == "ARDA" and wave8.get("execution_identity_authority") == "ARDA" else "NOT_PROVEN",
            "source": "wave4_and_wave8_receipts",
        },
        {
            "claim": "Cross-organ composition creates no authority.",
            "status": "PROVEN" if wave6.get("composition_authority") is False else "NOT_PROVEN",
            "source": "wave6_receipt",
        },
        {
            "claim": "The Evidence & Authority Twin and Loki Mirror Maze create no authority or execution.",
            "status": "PROVEN" if wave7.get("twin_authority") is False and wave7.get("loki_mirror_authority") is False and wave7.get("loki_mirror_execution") is False else "NOT_PROVEN",
            "source": "wave7_receipt",
        },
        {
            "claim": "Continuous Assurance creates no authority or execution.",
            "status": "PROVEN" if wave8.get("continuous_assurance_authority") is False and wave8.get("continuous_assurance_execution") is False else "NOT_PROVEN",
            "source": "wave8_receipt",
        },
    ]

    operational_proof = {
        "host_acceptance_chain": receipt_proofs,
        "wave_count": len(receipt_proofs),
        "automatic_external_actions": wave5.get("automatic_external_actions"),
        "automatic_external_notifications": wave8.get("automatic_external_notifications"),
        "bound_capability_count": len(bound_capabilities),
        "bound_capabilities": bound_capabilities,
        "truth_boundary": {
            "production_deployment_proven": False,
            "external_customer_validation_proven": False,
            "revenue_proven": False,
            "product_market_fit_proven": False,
            "bound_entrypoint_does_not_mean_executed": True,
        },
    }

    refusal_proof = {
        "locked_capability_count": len(locked_capabilities),
        "locked_capabilities": locked_capabilities,
        "automatic_external_actions": 0 if wave5.get("automatic_external_actions") == 0 else wave5.get("automatic_external_actions"),
        "automatic_external_notifications": 0 if wave8.get("automatic_external_notifications") == 0 else wave8.get("automatic_external_notifications"),
        "status": "PROVEN" if locked_capabilities else "NOT_PROVEN",
    }

    product_proof = {
        "product_profile_count": len(products),
        "products": products,
        "portfolio_truth_boundary": product_portfolio.get("truth_boundary"),
        "commercial_truth": {
            "registered_product_means_product_proven": False,
            "revenue_proven": False,
            "product_market_fit_proven": False,
            "external_customer_validation_proven": False,
            "production_deployment_proven": False,
        },
    }

    body = {
        "schema": CAPITALROOM_SCHEMA,
        "generated_at": _now(generated_at),
        "mode": "internal_only",
        "proof_sections": {
            "architecture_proof": architecture_claims,
            "operational_proof": operational_proof,
            "refusal_proof": refusal_proof,
            "product_proof": product_proof,
        },
        "authority": {
            "capitalroom_has_authority": False,
            "capitalroom_can_execute": False,
            "external_release_authorized": False,
            "kernel_authority": "Valinor",
            "execution_identity_authority": "ARDA",
        },
        "laws": {
            "proof_must_be_source_bound": True,
            "registered_is_not_product_proven": True,
            "ci_is_not_production_deployment": True,
            "bound_is_not_executed": True,
            "locked_is_not_available": True,
            "capitalroom_never_mints_authority": True,
            "capitalroom_never_executes": True,
            "external_release_requires_separate_human_authority": True,
            "local_paths_are_redacted": True,
        },
    }
    body["fingerprint"] = _fingerprint(body)
    body["room_id"] = f"CAPITALROOM-{body['fingerprint'][:16].upper()}"
    validate_capitalroom(body)
    return body


def validate_capitalroom(room: dict[str, Any]) -> None:
    if room.get("schema") != CAPITALROOM_SCHEMA:
        raise ProofRoomError("Unsupported CapitalRoom schema.")
    if room.get("mode") != "internal_only":
        raise ProofRoomError("CapitalRoom must remain internal-only in Fusion Wave 9.")
    authority = room.get("authority") or {}
    if authority.get("capitalroom_has_authority") is not False:
        raise ProofRoomError("CapitalRoom must not possess authority.")
    if authority.get("capitalroom_can_execute") is not False:
        raise ProofRoomError("CapitalRoom must not execute.")
    if authority.get("external_release_authorized") is not False:
        raise ProofRoomError("CapitalRoom external release is not authorized by Fusion Wave 9.")
    if authority.get("kernel_authority") != "Valinor":
        raise ProofRoomError("Valinor must remain sole kernel authority.")
    if authority.get("execution_identity_authority") != "ARDA":
        raise ProofRoomError("ARDA must remain execution identity authority.")

    sections = room.get("proof_sections") or {}
    if set(sections) != {"architecture_proof", "operational_proof", "refusal_proof", "product_proof"}:
        raise ProofRoomError("CapitalRoom proof-section set drifted.")

    for claim in sections["architecture_proof"]:
        if claim.get("status") not in ALLOWED_PROOF_STATES:
            raise ProofRoomError("CapitalRoom architecture claim contains unsupported proof state.")

    chain = sections["operational_proof"].get("host_acceptance_chain") or []
    if len(chain) != 8:
        raise ProofRoomError("CapitalRoom must expose exactly eight Fusion Wave receipts.")
    for expected_wave, row in enumerate(chain, start=1):
        if row.get("wave") != expected_wave or row.get("status") != "PROVEN":
            raise ProofRoomError("CapitalRoom Fusion receipt chain is incomplete or unordered.")
        if row.get("observed_state") != EXPECTED_WAVE_STATES[expected_wave]:
            raise ProofRoomError("CapitalRoom Fusion receipt state mismatch.")

    products = sections["product_proof"].get("products") or []
    if {row.get("id") for row in products} != set(PRODUCT_IDS):
        raise ProofRoomError("CapitalRoom product proof must expose exactly the nine governed product IDs.")
    for row in products:
        if row.get("id") == "dio_capitalroom":
            if row.get("proof_state") != "INTERNAL_PROOF_PRODUCT":
                raise ProofRoomError("CapitalRoom product profile must remain internal proof product.")
        elif row.get("proof_state") != "REGISTERED_NOT_PROVEN":
            raise ProofRoomError("Commercial product profile was promoted beyond registered-not-proven.")

    commercial = sections["product_proof"].get("commercial_truth") or {}
    forbidden_true = {
        "registered_product_means_product_proven",
        "revenue_proven",
        "product_market_fit_proven",
        "external_customer_validation_proven",
        "production_deployment_proven",
    }
    if any(commercial.get(key) is not False for key in forbidden_true):
        raise ProofRoomError("CapitalRoom commercial proof boundary was overclaimed.")

    serialized = json.dumps(room, sort_keys=True)
    if "/home/" in serialized:
        raise ProofRoomError("CapitalRoom leaked an absolute local home path.")

    payload = copy.deepcopy(room)
    fingerprint = payload.pop("fingerprint", None)
    room_id = payload.pop("room_id", None)
    expected = _fingerprint(payload)
    if fingerprint != expected or room_id != f"CAPITALROOM-{expected[:16].upper()}":
        raise ProofRoomError("CapitalRoom fingerprint mismatch.")


def render_capitalroom_readme(room: dict[str, Any]) -> str:
    validate_capitalroom(room)
    sections = room["proof_sections"]
    architecture = sections["architecture_proof"]
    refusals = sections["refusal_proof"]
    products = sections["product_proof"]["products"]
    operational = sections["operational_proof"]

    lines = [
        "# DIO CapitalRoom",
        "",
        f"**Room:** `{room['room_id']}`",
        f"**Generated:** `{room['generated_at']}`",
        "**Mode:** `internal_only`",
        "",
        "> This is a proof room, not a fundraising claim generator. Every PROVEN claim is source-bound. Registered products are not represented as market-validated products, and bound executors are not represented as executed actions.",
        "",
        "## Architecture Proof",
        "",
    ]
    for row in architecture:
        lines.append(f"- **{row['status']}** — {row['claim']}")
    lines.extend(
        [
            "",
            "## Operational Proof",
            "",
            f"- Host-accepted Fusion waves: **{operational['wave_count']} / 8**",
            f"- Bound capability contracts: **{operational['bound_capability_count']}**",
            f"- Automatic external actions: **{operational.get('automatic_external_actions')}**",
            f"- Automatic external notifications: **{operational.get('automatic_external_notifications')}**",
            "",
            "## Refusal Proof",
            "",
            f"- Explicitly locked capabilities: **{refusals['locked_capability_count']}**",
        ]
    )
    for row in refusals["locked_capabilities"]:
        lines.append(f"- `LOCKED` — `{row['capability']}`: {row.get('lock_reason')}")
    lines.extend(["", "## Product Proof", ""])
    for row in products:
        lines.append(f"- **{row['name']}** — `{row['proof_state']}` — portfolio status `{row.get('portfolio_status')}`")
    lines.extend(
        [
            "",
            "## Truth Boundary",
            "",
            "- Revenue proven: **false**",
            "- Product-market fit proven: **false**",
            "- External customer validation proven: **false**",
            "- Production deployment proven: **false**",
            "- CapitalRoom authority: **false**",
            "- CapitalRoom execution: **false**",
            "- External release authorized: **false**",
            "",
            "Valinor remains sole kernel authority. ARDA remains execution identity/attestation authority.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_capitalroom(room: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    validate_capitalroom(room)
    out_dir.mkdir(parents=True, exist_ok=True)

    section_files = {
        "ARCHITECTURE_PROOF.json": room["proof_sections"]["architecture_proof"],
        "OPERATIONAL_PROOF.json": room["proof_sections"]["operational_proof"],
        "REFUSAL_PROOF.json": room["proof_sections"]["refusal_proof"],
        "PRODUCT_PROOF.json": room["proof_sections"]["product_proof"],
    }
    _write_json(out_dir / "PROOF_ROOM.json", room)
    for name, payload in section_files.items():
        _write_json(out_dir / name, payload)
    (out_dir / "README.md").write_text(render_capitalroom_readme(room), encoding="utf-8")

    file_hashes: dict[str, str] = {}
    for path in sorted(out_dir.iterdir(), key=lambda item: item.name):
        if path.name == "MANIFEST.json" or not path.is_file():
            continue
        file_hashes[path.name] = _sha256_bytes(path.read_bytes())

    manifest_body = {
        "schema": MANIFEST_SCHEMA,
        "room_id": room["room_id"],
        "room_fingerprint": room["fingerprint"],
        "generated_at": room["generated_at"],
        "mode": room["mode"],
        "files": file_hashes,
        "external_release_authorized": False,
        "capitalroom_has_authority": False,
        "capitalroom_can_execute": False,
    }
    manifest_body["fingerprint"] = _fingerprint(manifest_body)
    _write_json(out_dir / "MANIFEST.json", manifest_body)
    return manifest_body


def validate_manifest(out_dir: Path, manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ProofRoomError("Unsupported CapitalRoom manifest schema.")
    payload = copy.deepcopy(manifest)
    fingerprint = payload.pop("fingerprint", None)
    if fingerprint != _fingerprint(payload):
        raise ProofRoomError("CapitalRoom manifest fingerprint mismatch.")
    for name, expected in (manifest.get("files") or {}).items():
        path = out_dir / name
        if not path.is_file():
            raise ProofRoomError(f"CapitalRoom manifest file is missing: {name}")
        if _sha256_bytes(path.read_bytes()) != expected:
            raise ProofRoomError(f"CapitalRoom manifest hash mismatch: {name}")
