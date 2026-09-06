from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SEAL_SCHEMA = "dio.canon_extension.proof_seal.v1"
SEAL_FILENAME = "CANON_EXTENSION_PROOF_RECEIPT.json"
SEAL_TOKEN = "DIO_CANON_EXTENSION_PROOF_SEALS_WRITTEN"


class CanonExtensionProofSealError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonExtensionProofSealError(f"invalid generation receipt: {path}") from exc
    if not isinstance(value, dict):
        raise CanonExtensionProofSealError(f"generation receipt must be an object: {path}")
    return value


def _reports_failure(receipt: dict[str, Any]) -> bool:
    for key in ("status", "result", "acceptance_token", "verification"):
        value = receipt.get(key)
        if isinstance(value, str) and any(token in value.upper() for token in ("REFUSE", "FAIL", "BLOCKED", "ERROR")):
            return True
    return False


def seal_receipt_bound_extension(*, spec: dict[str, Any], root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = (root / str(spec["primary_artifact"])).resolve()
    generation_receipt = (root / str(spec["proof_receipt"])).resolve()
    if not artifact.is_relative_to(root) or not generation_receipt.is_relative_to(root):
        raise CanonExtensionProofSealError("unsafe canon-extension evidence path")
    if not artifact.is_file():
        raise CanonExtensionProofSealError(f"primary artifact missing: {artifact}")
    if not generation_receipt.is_file():
        raise CanonExtensionProofSealError(f"generation receipt missing: {generation_receipt}")

    generation_data = _load_json(generation_receipt)
    if _reports_failure(generation_data):
        raise CanonExtensionProofSealError(f"generation receipt reports failure: {generation_receipt}")

    seal_path = generation_receipt.parent / SEAL_FILENAME
    receipt: dict[str, Any] = {
        "schema": SEAL_SCHEMA,
        "status": "PASS",
        "canon_id": str(spec["canon_id"]),
        "name": str(spec["name"]),
        "slug": str(spec["slug"]),
        "primary_artifact": str(artifact.relative_to(root)),
        "current_artifact_sha256": _sha(artifact),
        "source_generation_receipt": str(generation_receipt.relative_to(root)),
        "source_generation_receipt_sha256": _sha(generation_receipt),
        "source_generation_receipt_schema": str(generation_data.get("schema") or "unknown"),
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "This receipt binds the current canon-extension artifact bytes to the preserved historical generation "
            "receipt. It proves provenance custody only; it does not create ProductGrade, buyer demand, payment, "
            "legal approval, publication authority or commercial validation."
        ),
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    seal_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def seal_all_receipt_bound_extensions(*, root: Path) -> dict[str, Any]:
    from products.canon_extension_product_grade import CANON_EXTENSIONS

    root = Path(root).resolve()
    seals: dict[str, Any] = {}
    failures: dict[str, str] = {}
    targets = [row for row in CANON_EXTENSIONS if row["proof_kind"] == "receipt_bound"]
    for spec in targets:
        try:
            seals[str(spec["slug"])] = seal_receipt_bound_extension(spec=spec, root=root)
        except CanonExtensionProofSealError as exc:
            failures[str(spec["slug"])] = str(exc)
    return {
        "schema": "dio.canon_extension.proof_seal_batch.v1",
        "acceptance_token": SEAL_TOKEN if not failures and len(seals) == len(targets) else "DIO_CANON_EXTENSION_PROOF_SEALS_REFUSE",
        "target_count": len(targets),
        "sealed_count": len(seals),
        "refuse_count": len(failures),
        "seals": seals,
        "failures": failures,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
