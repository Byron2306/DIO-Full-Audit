from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .customer_cases import load_case, update_case
from .journey_core import transition_case
from .needs_you import load_needs_you
from .state import read_json, safe, write_json


MANIFEST_SCHEMA = "dio.deliverable_manifest.v2"
AUTHORITY_SCHEMA = "dio.release_authority.v2"
DELIVERY_RECEIPT_SCHEMA = "dio.delivery_receipt.v2"
DELIVERY_ATTEMPT_SCHEMA = "dio.delivery_attempt.v2"

Transport = Callable[[dict[str, Any]], dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _required(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _plain_sha256(value: Any, label: str) -> str:
    text = _required(value, label).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError(f"{label} must be a SHA-256 hex digest")
    return text


def _manifest_path(root: Path, manifest_id: str) -> Path:
    return Path(root) / "customer_cases" / "deliverable_manifests" / f"{safe(manifest_id)}.json"


def _authority_path(root: Path, authority_id: str) -> Path:
    return Path(root) / "customer_cases" / "release_authorities_v2" / f"{safe(authority_id)}.json"


def _receipt_path(root: Path, receipt_id: str) -> Path:
    return Path(root) / "customer_cases" / "delivery_receipts_v2" / f"{safe(receipt_id)}.json"


def _validate_fulfilment_result(case: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy((case.get("fulfilment") or {}).get("result") or {})
    if result.get("schema") != "dio.fulfilment_result.v1":
        raise ValueError("canonical Phase 4 fulfilment result is required")
    if str(result.get("case_id") or "") != str(case.get("case_id") or ""):
        raise ValueError("fulfilment result case lineage mismatch")
    if str(result.get("journey_product_id") or "") != str(case.get("product_id") or ""):
        raise ValueError("fulfilment result product lineage mismatch")
    if str(result.get("status") or "").upper() != "COMPLETED":
        raise ValueError("completed fulfilment result is required")
    expected = _plain_sha256(result.get("fulfilment_result_sha256"), "fulfilment_result_sha256")
    basis = deepcopy(result)
    basis.pop("fulfilment_result_sha256", None)
    if _canonical_hash(basis) != expected:
        raise ValueError("fulfilment result hash mismatch")
    if any(bool(result.get(field)) for field in (
        "release_authority_created", "external_send_authority", "authority_created"
    )):
        raise ValueError("Phase 4 fulfilment result may not create release authority")
    return result


def _normalise_manifest_artifact(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("fulfilment artifact must be an object")
    artifact_id = _required(row.get("artifact_id"), "artifact_id")
    kind = _required(row.get("kind"), "artifact kind")
    declared_sha = _plain_sha256(row.get("sha256"), "artifact sha256")
    raw_path = _required(row.get("path"), "artifact path")
    path = Path(raw_path).resolve()
    if not path.is_file():
        raise ValueError(f"artifact not found: {path}")
    actual_sha = _file_sha256(path)
    if actual_sha != declared_sha:
        raise ValueError(f"artifact SHA-256 mismatch: {artifact_id}")
    if str(row.get("release_state") or "") != "HELD":
        raise ValueError("Phase 5 may manifest only HELD artifacts")
    if any(bool(row.get(field)) for field in (
        "release_authority", "external_send_authority", "authority_created"
    )):
        raise ValueError("artifact may not create release, send, or generic authority")

    release_conditions = deepcopy(row.get("release_conditions"))
    source_lineage = deepcopy(row.get("source_lineage"))
    provenance = deepcopy(row.get("provenance"))
    if not isinstance(release_conditions, list):
        raise ValueError("artifact release_conditions must be a list")
    if not isinstance(source_lineage, list):
        raise ValueError("artifact source_lineage must be a list")
    if not isinstance(provenance, dict):
        raise ValueError("artifact provenance must be an object")

    return {
        "artifact_id": artifact_id,
        "kind": kind,
        "path": str(path),
        "file_name": _required(row.get("file_name") or path.name, "artifact file_name"),
        "mime_type": _required(row.get("mime_type"), "artifact mime_type"),
        "sha256": actual_sha,
        "bytes": path.stat().st_size,
        "purpose": _required(row.get("purpose"), "artifact purpose"),
        "customer_visibility": _required(row.get("customer_visibility"), "customer_visibility"),
        "provenance": provenance,
        "release_conditions": release_conditions,
        "source_lineage": source_lineage,
        "release_state": "HELD",
        "release_authority": False,
        "external_send_authority": False,
        "authority_created": False,
    }


def build_deliverable_manifest(state_root: Path, case_id: str) -> dict[str, Any]:
    state_root = Path(state_root).resolve()
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    if str(case.get("stage") or "") != "REVIEW_READY":
        raise ValueError("customer case must be REVIEW_READY")

    result = _validate_fulfilment_result(case)
    rows = result.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("fulfilment result must contain at least one artifact")
    artifacts = [_normalise_manifest_artifact(row) for row in rows]
    if len({a["artifact_id"] for a in artifacts}) != len(artifacts):
        raise ValueError("artifact_id values must be unique within a manifest")

    manifest_seed = f"{case['case_id']}:{result['fulfilment_result_sha256']}"
    manifest_id = "DM-" + hashlib.sha256(manifest_seed.encode("utf-8")).hexdigest()[:20].upper()
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "manifest_id": manifest_id,
        "case_id": str(case["case_id"]),
        "journey_product_id": str(case.get("product_id") or ""),
        "fulfilment_request_sha256": str(result.get("fulfilment_request_sha256") or ""),
        "fulfilment_result_sha256": str(result["fulfilment_result_sha256"]),
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "release_state": "HELD",
        "release_authority_created": False,
        "external_send_authority": False,
        "authority_created": False,
    }
    manifest["manifest_sha256"] = _canonical_hash(manifest)
    write_json(_manifest_path(state_root, manifest_id), manifest)
    update_case(
        state_root,
        case,
        patch={
            "fulfilment": {
                "deliverable_manifest": deepcopy(manifest),
                "release_authority": False,
                "external_send_authority": False,
            },
            "authority_created": False,
        },
        evidence_ref=f"deliverable-manifest:{manifest['manifest_sha256']}",
    )
    return manifest


def _load_manifest_from_case(case: dict[str, Any]) -> dict[str, Any]:
    manifest = deepcopy((case.get("fulfilment") or {}).get("deliverable_manifest") or {})
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("canonical DeliverableManifest v2 is required")
    expected = _plain_sha256(manifest.get("manifest_sha256"), "manifest_sha256")
    basis = deepcopy(manifest)
    basis.pop("manifest_sha256", None)
    if _canonical_hash(basis) != expected:
        raise ValueError("deliverable manifest hash mismatch")
    return manifest


def create_manifest_release_authority(
    state_root: Path,
    *,
    case_id: str,
    needs_you_id: str,
    delivery_channels: list[str],
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    if str(case.get("stage") or "") != "REVIEW_READY":
        raise ValueError("customer case must be REVIEW_READY for release approval")
    manifest = _load_manifest_from_case(case)

    needs = load_needs_you(state_root, str(needs_you_id))
    if needs is None:
        raise ValueError(f"Needs You item not found: {needs_you_id}")
    if str(needs.get("state") or "").lower() != "resolved":
        raise ValueError("release approval is not resolved")
    if str(needs.get("decision") or "").upper() != "APPROVE":
        raise ValueError("release approval was not APPROVE")
    if str(needs.get("reason") or "") != "fulfilment_release_review":
        raise ValueError("Needs You item is not a fulfilment release review")
    if str(needs.get("product") or "") and str(needs.get("product")) != str(case.get("product_id") or ""):
        raise ValueError("Needs You product does not match customer case")
    evidence_ref = str(needs.get("resolution_evidence_ref") or "")
    if manifest["manifest_sha256"].lower() not in evidence_ref.lower():
        raise ValueError("human approval evidence is not bound to this manifest SHA-256")

    channels = sorted({_required(channel, "delivery channel").lower() for channel in delivery_channels})
    if not channels:
        raise ValueError("at least one delivery channel is required")

    authority_seed = (
        f"{case['case_id']}:{manifest['manifest_sha256']}:{needs_you_id}:{','.join(channels)}"
    )
    authority_id = "RA2-" + hashlib.sha256(authority_seed.encode("utf-8")).hexdigest()[:20].upper()
    authority = {
        "schema": AUTHORITY_SCHEMA,
        "authority_id": authority_id,
        "case_id": str(case["case_id"]),
        "journey_product_id": str(case.get("product_id") or ""),
        "manifest_id": str(manifest["manifest_id"]),
        "manifest_sha256": str(manifest["manifest_sha256"]),
        "needs_you_id": str(needs_you_id),
        "human_approval": {
            "decision": "APPROVE",
            "resolved_by": needs.get("resolved_by"),
            "resolved_at": needs.get("resolved_at"),
            "evidence_ref": evidence_ref,
        },
        "scope": {
            "external_action_type": "customer_manifest_delivery",
            "delivery_channels": channels,
            "one_use": True,
        },
        "fulfilment_release_authorized": True,
        "external_send_authorized": True,
        "payment_authority": False,
        "spend_authorized": False,
        "generic_authority": False,
        "consumed": False,
        "created_at": _now(),
    }
    authority["authority_sha256"] = _canonical_hash(authority)
    write_json(_authority_path(state_root, authority_id), authority)

    release_case = transition_case(
        state_root,
        str(case_id),
        "RELEASE_APPROVAL",
        evidence_ref=f"release-authority-v2:{authority_id}:{manifest['manifest_sha256']}",
    )
    update_case(
        state_root,
        release_case,
        patch={
            "fulfilment": {
                "release_authority_id": authority_id,
                "release_authority": True,
                "external_send_authority": True,
            }
        },
        evidence_ref=f"release-authority-v2:{authority_id}",
    )
    return authority


def _load_authority(state_root: Path, authority_id: str) -> dict[str, Any]:
    path = _authority_path(state_root, authority_id)
    if not path.is_file():
        raise ValueError(f"release authority not found: {authority_id}")
    authority = read_json(path)
    if authority.get("schema") != AUTHORITY_SCHEMA:
        raise ValueError("unsupported release authority schema")
    expected = _plain_sha256(authority.get("authority_sha256"), "authority_sha256")
    basis = deepcopy(authority)
    basis.pop("authority_sha256", None)
    if _canonical_hash(basis) != expected:
        raise ValueError("release authority hash mismatch")
    return authority


def _validate_manifest_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    package_artifacts: list[dict[str, Any]] = []
    for artifact in manifest.get("artifacts") or []:
        path = Path(_required(artifact.get("path"), "artifact path")).resolve()
        if not path.is_file():
            raise ValueError(f"authorized artifact no longer exists: {path}")
        actual_sha = _file_sha256(path)
        if actual_sha != str(artifact.get("sha256") or "").lower():
            raise ValueError(f"artifact changed after approval: {artifact.get('artifact_id')}")
        package_artifacts.append({
            "artifact_id": str(artifact["artifact_id"]),
            "kind": str(artifact["kind"]),
            "path": str(path),
            "file_name": str(artifact["file_name"]),
            "mime_type": str(artifact["mime_type"]),
            "sha256": actual_sha,
            "bytes": path.stat().st_size,
            "purpose": str(artifact["purpose"]),
            "customer_visibility": str(artifact["customer_visibility"]),
        })
    return package_artifacts


def deliver_manifest(
    state_root: Path,
    authority_id: str,
    *,
    channel: str,
    destination: str,
    transport: Transport,
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()
    authority = _load_authority(state_root, _required(authority_id, "authority_id"))
    if authority.get("consumed") is True:
        raise ValueError("release authority is already consumed")
    if authority.get("fulfilment_release_authorized") is not True or authority.get("external_send_authorized") is not True:
        raise ValueError("release authority does not authorize external delivery")

    channel = _required(channel, "channel").lower()
    destination = _required(destination, "destination")
    if channel not in set(authority.get("scope", {}).get("delivery_channels") or []):
        raise ValueError("delivery channel is not authorized by release authority")
    if not callable(transport):
        raise ValueError("transport must be callable")

    case = load_case(state_root, str(authority.get("case_id") or ""))
    if case is None:
        raise ValueError("release authority customer case not found")
    if str(case.get("stage") or "") != "RELEASE_APPROVAL":
        raise ValueError("customer case is not awaiting release delivery")
    manifest = _load_manifest_from_case(case)
    if manifest.get("manifest_sha256") != authority.get("manifest_sha256"):
        raise ValueError("release authority manifest does not match canonical case")

    artifacts = _validate_manifest_files(manifest)
    package = {
        "schema": "dio.delivery_package.v2",
        "case_id": str(case["case_id"]),
        "journey_product_id": str(case.get("product_id") or ""),
        "authority_id": str(authority["authority_id"]),
        "manifest_id": str(manifest["manifest_id"]),
        "manifest_sha256": str(manifest["manifest_sha256"]),
        "channel": channel,
        "destination": destination,
        "artifacts": artifacts,
    }
    raw = transport(deepcopy(package))
    if not isinstance(raw, dict):
        raise ValueError("delivery transport must return an object")

    attempt = {
        "schema": DELIVERY_ATTEMPT_SCHEMA,
        "authority_id": str(authority["authority_id"]),
        "manifest_sha256": str(manifest["manifest_sha256"]),
        "channel": channel,
        "destination": destination,
        "sent": raw.get("sent") is True,
        "error": raw.get("error"),
        "provider_receipt": deepcopy(raw.get("provider_receipt") or {}),
        "attempted_at": _now(),
    }
    attempt["delivery_attempt_sha256"] = _canonical_hash(attempt)

    if raw.get("sent") is not True:
        update_case(
            state_root,
            case,
            patch={"fulfilment": {"last_delivery_attempt": deepcopy(attempt)}},
            evidence_ref=f"delivery-attempt:{attempt['delivery_attempt_sha256']}",
        )
        return {"delivered": False, "delivery_receipt": None, "delivery_attempt": attempt}

    provider_receipt = deepcopy(raw.get("provider_receipt") or {})
    if not isinstance(provider_receipt, dict) or not provider_receipt:
        raise ValueError("successful delivery requires provider receipt evidence")

    receipt_seed = f"{authority['authority_id']}:{manifest['manifest_sha256']}:{channel}:{destination}"
    receipt_id = "DR2-" + hashlib.sha256(receipt_seed.encode("utf-8")).hexdigest()[:20].upper()
    receipt = {
        "schema": DELIVERY_RECEIPT_SCHEMA,
        "delivery_receipt_id": receipt_id,
        "case_id": str(case["case_id"]),
        "journey_product_id": str(case.get("product_id") or ""),
        "authority_id": str(authority["authority_id"]),
        "manifest_id": str(manifest["manifest_id"]),
        "manifest_sha256": str(manifest["manifest_sha256"]),
        "channel": channel,
        "destination": destination,
        "artifacts": [
            {
                "artifact_id": a["artifact_id"],
                "file_name": a["file_name"],
                "mime_type": a["mime_type"],
                "sha256": a["sha256"],
                "bytes": a["bytes"],
            }
            for a in artifacts
        ],
        "provider_receipt": provider_receipt,
        "delivered_at": _now(),
        "sent": True,
    }
    receipt["delivery_receipt_sha256"] = _canonical_hash(receipt)
    write_json(_receipt_path(state_root, receipt_id), receipt)

    authority["consumed"] = True
    authority["consumed_at"] = _now()
    authority["delivery_receipt_id"] = receipt_id
    authority["delivery_receipt_sha256"] = receipt["delivery_receipt_sha256"]
    authority.pop("authority_sha256", None)
    authority["authority_sha256"] = _canonical_hash(authority)
    write_json(_authority_path(state_root, str(authority["authority_id"])), authority)

    delivered = transition_case(
        state_root,
        str(case["case_id"]),
        "DELIVERED",
        evidence_ref=f"delivery-receipt-v2:{receipt['delivery_receipt_sha256']}",
    )
    delivered = update_case(
        state_root,
        delivered,
        patch={
            "fulfilment": {
                "state": "delivered",
                "last_delivery_attempt": deepcopy(attempt),
                "delivery_receipt": deepcopy(receipt),
                "release_authority": False,
                "external_send_authority": False,
            }
        },
        evidence_ref=f"delivery-receipt-v2:{receipt['delivery_receipt_sha256']}",
    )
    return {
        "delivered": True,
        "delivery_receipt": receipt,
        "delivery_attempt": attempt,
        "authority": authority,
        "case": delivered,
    }
