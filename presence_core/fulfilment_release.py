from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .customer_cases import load_case, update_case
from .needs_you import load_needs_you
from .state import read_json, safe, write_json


AUTHORITY_SCHEMA = "dio.fulfilment_release_authority.v1"


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)
    return h.hexdigest()


def _authority_id(
    case_id: str,
    job_id: str,
    artifact_sha256: str,
    needs_you_id: str,
) -> str:
    material = (
        f"{case_id}:"
        f"{job_id}:"
        f"{artifact_sha256}:"
        f"{needs_you_id}"
    )

    digest = hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()[:20].upper()

    return f"FRA-{digest}"


def create_release_authority(
    state_root: Path,
    *,
    case_id: str,
    job_id: str,
    needs_you_id: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()

    case = load_case(
        state_root,
        case_id,
    )

    if case is None:
        raise ValueError(
            f"customer case not found: {case_id}"
        )

    needs = load_needs_you(
        state_root,
        needs_you_id,
    )

    if needs is None:
        raise ValueError(
            f"Needs You item not found: {needs_you_id}"
        )

    if str(needs.get("state") or "").lower() != "resolved":
        raise ValueError(
            "release approval is not resolved"
        )

    if str(needs.get("decision") or "").upper() != "APPROVE":
        raise ValueError(
            "release approval was not APPROVE"
        )

    if str(needs.get("reason") or "") != "fulfilment_release_review":
        raise ValueError(
            "Needs You item is not a fulfilment release review"
        )

    case_product = str(
        case.get("product_id") or ""
    ).strip()

    needs_product = str(
        needs.get("product") or ""
    ).strip()

    if (
        case_product
        and needs_product
        and case_product != needs_product
    ):
        raise ValueError(
            "Needs You product does not match customer case"
        )

    if str(artifact.get("kind") or "").lower() != "document":
        raise ValueError(
            "fulfilment release currently requires a document"
        )

    if str(artifact.get("mime_type") or "").lower() != "application/pdf":
        raise ValueError(
            "fulfilment release currently requires application/pdf"
        )

    declared_sha = str(
        artifact.get("sha256") or ""
    ).strip().lower()

    if len(declared_sha) != 64:
        raise ValueError(
            "artifact SHA-256 is required"
        )

    raw_path = str(
        artifact.get("path") or ""
    ).strip()

    if not raw_path:
        raise ValueError(
            "artifact path is required"
        )

    artifact_path = Path(raw_path)

    if not artifact_path.is_absolute():
        artifact_path = state_root.parent.parent / artifact_path

    artifact_path = artifact_path.resolve()

    if not artifact_path.is_file():
        raise ValueError(
            f"artifact not found: {artifact_path}"
        )

    actual_sha = _sha256(
        artifact_path
    )

    if actual_sha != declared_sha:
        raise ValueError(
            "artifact SHA-256 mismatch"
        )

    evidence_ref = str(
        needs.get("resolution_evidence_ref")
        or ""
    )

    if declared_sha not in evidence_ref.lower():
        raise ValueError(
            "human approval evidence is not bound "
            "to this artifact SHA-256"
        )

    authority_id = _authority_id(
        case_id,
        job_id,
        declared_sha,
        needs_you_id,
    )

    authority = {
        "schema": AUTHORITY_SCHEMA,
        "authority_id": authority_id,
        "case_id": case_id,
        "product_id": case.get("product_id"),
        "job_id": job_id,
        "needs_you_id": needs_you_id,
        "artifact": {
            "kind": "document",
            "path": str(artifact_path),
            "file_name": str(
                artifact.get("file_name")
                or artifact_path.name
            ),
            "mime_type": "application/pdf",
            "sha256": actual_sha,
            "bytes": artifact_path.stat().st_size,
        },
        "human_approval": {
            "decision": "APPROVE",
            "resolved_by": needs.get(
                "resolved_by"
            ),
            "resolved_at": needs.get(
                "resolved_at"
            ),
            "evidence_ref": evidence_ref,
        },
        "scope": {
            "external_action_type": (
                "customer_document_delivery"
            ),
            "single_artifact": True,
            "artifact_sha256": actual_sha,
        },
        "authority_created": True,
        "fulfilment_release_authorized": True,
        "external_send_authorized": True,
        "spend_authorized": False,
        "payment_authority": False,
        "attachment_processing_authorized": False,
        "consumed": False,
        "created_at": _now(),
    }

    path = (
        state_root
        / "customer_cases"
        / "release_authorities"
        / f"{safe(authority_id)}.json"
    )

    write_json(
        path,
        authority,
    )

    update_case(
        state_root,
        case,
        stage="RELEASE_APPROVAL",
        patch={
            "fulfilment": {
                "release_authority_id": authority_id,
                "release_authority": True,
                "external_send_authority": True,
            },
        },
        evidence_ref=f"release_authority:{authority_id}",
    )

    authority["authority_path"] = str(
        path
    )

    return authority


def project_outbound_artifact(
    authority: dict[str, Any],
) -> dict[str, Any]:
    if (
        authority.get("schema")
        != AUTHORITY_SCHEMA
    ):
        raise ValueError(
            "unsupported fulfilment release authority"
        )

    if authority.get(
        "fulfilment_release_authorized"
    ) is not True:
        raise ValueError(
            "fulfilment release is not authorized"
        )

    if authority.get(
        "external_send_authorized"
    ) is not True:
        raise ValueError(
            "external send is not authorized"
        )

    if authority.get("consumed") is True:
        raise ValueError(
            "release authority is already consumed"
        )

    artifact = dict(
        authority.get("artifact") or {}
    )

    path = Path(
        str(artifact.get("path") or "")
    ).resolve()

    if not path.is_file():
        raise ValueError(
            "authorized artifact no longer exists"
        )

    actual_sha = _sha256(path)

    if (
        actual_sha
        != str(
            artifact.get("sha256") or ""
        ).lower()
    ):
        raise ValueError(
            "authorized artifact changed after approval"
        )

    return {
        "kind": "document",
        "purpose": "product_fulfilment",
        "path": str(path),
        "file_name": str(
            artifact.get("file_name")
            or path.name
        ),
        "mime_type": "application/pdf",
        "sha256": actual_sha,
        "release_state": "APPROVED",
        "release_authority_id": authority[
            "authority_id"
        ],
    }

def consume_release_authority(
    state_root: Path,
    authority_id: str,
    *,
    delivery_receipt: dict[str, Any],
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()

    authority_id = str(
        authority_id or ""
    ).strip()

    if not authority_id:
        raise ValueError(
            "authority_id is required"
        )

    path = (
        state_root
        / "customer_cases"
        / "release_authorities"
        / f"{safe(authority_id)}.json"
    )

    if not path.is_file():
        raise ValueError(
            f"release authority not found: {authority_id}"
        )

    authority = read_json(path)

    if authority.get("schema") != AUTHORITY_SCHEMA:
        raise ValueError(
            "unsupported fulfilment release authority"
        )

    if authority.get("consumed") is True:
        raise ValueError(
            "release authority is already consumed"
        )

    if authority.get(
        "fulfilment_release_authorized"
    ) is not True:
        raise ValueError(
            "fulfilment release is not authorized"
        )

    if authority.get(
        "external_send_authorized"
    ) is not True:
        raise ValueError(
            "external send is not authorized"
        )

    receipt = dict(
        delivery_receipt or {}
    )

    delivered_sha = str(
        receipt.get("artifact_sha256") or ""
    ).strip().lower()

    authorized_sha = str(
        (
            authority.get("artifact")
            or {}
        ).get("sha256")
        or ""
    ).strip().lower()

    if not delivered_sha:
        raise ValueError(
            "delivery receipt artifact SHA-256 is required"
        )

    if delivered_sha != authorized_sha:
        raise ValueError(
            "delivery receipt artifact SHA-256 "
            "does not match release authority"
        )

    authority["consumed"] = True
    authority["consumed_at"] = _now()
    authority["delivery_receipt"] = receipt

    write_json(
        path,
        authority,
    )

    return authority

def record_successful_delivery(
    state_root: Path,
    authority_id: str,
    *,
    delivery_receipt: dict[str, Any],
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()

    consumed = consume_release_authority(
        state_root,
        authority_id,
        delivery_receipt=delivery_receipt,
    )

    case_id = str(
        consumed.get("case_id") or ""
    ).strip()

    if not case_id:
        raise ValueError(
            "release authority has no case_id"
        )

    case = load_case(
        state_root,
        case_id,
    )

    if case is None:
        raise ValueError(
            f"customer case not found: {case_id}"
        )

    updated = update_case(
        state_root,
        case,
        stage="DELIVERED",
        patch={
            "fulfilment": {
                "state": "delivered",
                "release_authority_id": (
                    consumed["authority_id"]
                ),
                "delivery_receipt": dict(
                    delivery_receipt
                ),
            },
        },
        evidence_ref=(
            f"release_authority:"
            f"{consumed['authority_id']}"
        ),
    )

    return {
        "authority": consumed,
        "case": updated,
    }
