"""Explicitly authorized customer-portal package transport for Vesper releases."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def web_portal_transport(state_root: Path):
    """Return a deliver_manifest transport; caller must hold channel authority."""
    root = Path(state_root).resolve()

    def deliver(package: dict[str, Any]) -> dict[str, Any]:
        case_id = str(package.get("case_id") or "")
        if not case_id or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in case_id):
            return {"sent": False, "error": "invalid_case_identity"}
        if package.get("channel") != "web_portal":
            return {"sent": False, "error": "channel_mismatch"}
        artifacts = package.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return {"sent": False, "error": "empty_release_package"}
        if sum(int(row.get("bytes") or 0) for row in artifacts) > 100 * 1024 * 1024:
            return {"sent": False, "error": "portal_package_exceeds_100_mib_limit"}
        destination = root / "customer_cases" / "web_deliveries" / f"{case_id}.zip"
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{case_id}.", suffix=".zip", dir=destination.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                package_artifacts = []
                archive_names: set[str] = set()
                for row in artifacts:
                    source = Path(str(row.get("path") or "")).resolve()
                    if not source.is_file() or _sha(source) != str(row.get("sha256") or "").lower():
                        raise ValueError("approved release artifact changed before portal delivery")
                    name = Path(str(row.get("file_name") or source.name)).name
                    if not name or name in archive_names or name == "DIO_PACKAGE_MANIFEST.json":
                        raise ValueError("release package contains duplicate or reserved filenames")
                    archive_names.add(name)
                    archive.write(source, arcname=name)
                    package_artifacts.append({
                        "artifact_id": str(row.get("artifact_id") or ""),
                        "file_name": name,
                        "sha256": str(row["sha256"]).lower(),
                        "bytes": source.stat().st_size,
                    })
                manifest = {
                    "schema": "dio.web_customer_package.v1",
                    "case_id": case_id,
                    "manifest_id": str(package.get("manifest_id") or ""),
                    "manifest_sha256": str(package.get("manifest_sha256") or ""),
                    "artifacts": package_artifacts,
                }
                archive.writestr("DIO_PACKAGE_MANIFEST.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            package_sha = _sha(temporary)
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
            os.chmod(destination, 0o600)
            return {
                "sent": True,
                "provider_receipt": {
                    "transport": "vesper_web_portal",
                    "storage_ref": f"customer_cases/web_deliveries/{case_id}.zip",
                    "package_sha256": package_sha,
                    "package_bytes": destination.stat().st_size,
                },
            }
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    return deliver


def load_authorized_web_package(state_root: Path, case: dict[str, Any]) -> tuple[Path, str]:
    """Validate canonical delivered state and return the approved package path."""
    fulfilment = case.get("fulfilment") or {}
    receipt = fulfilment.get("delivery_receipt") or {}
    manifest = fulfilment.get("deliverable_manifest") or {}
    if str(case.get("stage") or "") != "DELIVERED":
        raise ValueError("customer package has not been released")
    if receipt.get("schema") != "dio.delivery_receipt.v2" or receipt.get("sent") is not True:
        raise ValueError("canonical delivery receipt is missing")
    if receipt.get("channel") != "web_portal":
        raise ValueError("release approval did not authorize portal delivery")
    if receipt.get("case_id") != case.get("case_id") or receipt.get("manifest_sha256") != manifest.get("manifest_sha256"):
        raise ValueError("delivery receipt does not match the canonical case manifest")
    expected_receipt = str(receipt.get("delivery_receipt_sha256") or "")
    basis = dict(receipt)
    basis.pop("delivery_receipt_sha256", None)
    actual_receipt = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if not expected_receipt or actual_receipt != expected_receipt:
        raise ValueError("delivery receipt hash mismatch")
    provider = receipt.get("provider_receipt") or {}
    if provider.get("transport") != "vesper_web_portal":
        raise ValueError("delivery receipt is not a portal package receipt")
    relative = Path(str(provider.get("storage_ref") or ""))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("portal package storage reference is invalid")
    root = Path(state_root).resolve()
    package = (root / relative).resolve()
    if root not in package.parents or not package.is_file():
        raise ValueError("released customer package is unavailable")
    if package.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("released customer package exceeds the portal transfer limit")
    actual_package = _sha(package)
    if actual_package != str(provider.get("package_sha256") or ""):
        raise ValueError("released customer package hash mismatch")
    return package, f"DIO-return-{case.get('case_id')}.zip"
