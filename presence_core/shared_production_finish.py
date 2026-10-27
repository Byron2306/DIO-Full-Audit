"""Held professional finishing shared by every canonical fulfilment route."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any


FORMAT_CORE_CAPABILITY = "format_core.semantic_finish"
PRODUCTION_STUDIO_CAPABILITY = "production_studio.customer_delivery"


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _held_inventory(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not artifacts:
        raise ValueError("shared professional finish requires a held route artifact inventory")
    inventory: list[dict[str, str]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("shared professional finish artifact must be an object")
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        digest = str(artifact.get("sha256") or "").strip()
        if not artifact_id or len(digest) != 64 or artifact.get("release_state") != "HELD":
            raise ValueError("shared professional finish requires hash-bound HELD route artifacts")
        if artifact_id in seen:
            raise ValueError("shared professional finish route artifact ids must be unique")
        seen.add(artifact_id)
        inventory.append({
            "artifact_id": artifact_id,
            "kind": str(artifact.get("kind") or ""),
            "file_name": str(artifact.get("file_name") or ""),
            "sha256": digest,
        })
    return inventory


def _required_capabilities(request: dict[str, Any]) -> set[str]:
    profile = request.get("execution_profile") or {}
    return {
        str(row.get("capability_id") or "")
        for row in profile.get("executor_capabilities") or []
        # Execution profiles already contain only required capabilities. Older
        # Phase 4 projections do not retain the source-plan boolean.
        if isinstance(row, dict)
    }


def _write_once(path: Path, payload: bytes) -> None:
    if path.exists() and path.read_bytes() != payload:
        raise ValueError(f"shared professional finish would overwrite non-matching artifact: {path.name}")
    path.write_bytes(payload)


def finish_fulfilment_for_review(
    state_root: Path,
    request: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create review-only finishing artifacts from a route adapter's held inventory.

    The finisher has no route-specific behavior and creates neither delivery nor
    publication authority. It is deliberately invoked only after native-route
    execution has produced held, hash-bound artifacts.
    """
    required = _required_capabilities(request)
    configured = required & {FORMAT_CORE_CAPABILITY, PRODUCTION_STUDIO_CAPABILITY}
    if configured != {FORMAT_CORE_CAPABILITY, PRODUCTION_STUDIO_CAPABILITY}:
        raise ValueError("Format Core and Production Studio must be configured together")

    state_root = Path(state_root).resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    inventory = _held_inventory(artifacts)
    case_id = str(request.get("case_id") or "").strip()
    request_hash = str(request.get("fulfilment_request_sha256") or "").strip()
    if not case_id or len(request_hash) != 64:
        raise ValueError("shared professional finish requires a canonical fulfilment request")
    prefix = f"{case_id}-{request_hash[:12]}"
    html_path = state_root / f"{prefix}-format-core-review.html"
    manifest_path = state_root / f"{prefix}-production-studio-review-manifest.json"

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['artifact_id'])}</td>"
        f"<td>{html.escape(item['kind'])}</td>"
        f"<td>{html.escape(item['file_name'])}</td>"
        f"<td><code>{html.escape(item['sha256'])}</code></td>"
        "</tr>"
        for item in inventory
    )
    html_payload = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>DIO held fulfilment review</title></head><body>"
        "<h1>Held fulfilment review</h1>"
        f"<p>Case: <code>{html.escape(case_id)}</code></p>"
        f"<p>Request: <code>{html.escape(request_hash)}</code></p>"
        "<p>This summary is review material only. It grants no delivery, publication, send, or release authority.</p>"
        "<table><thead><tr><th>Artifact</th><th>Kind</th><th>File</th><th>SHA-256</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    ).encode("utf-8")
    _write_once(html_path, html_payload)
    html_digest = _sha256(html_payload)
    manifest = {
        "schema": "dio.production_studio.review_manifest.v1",
        "state": "HELD_FOR_REVIEW",
        "case_id": case_id,
        "fulfilment_request_sha256": request_hash,
        "route_artifacts": inventory,
        "format_core_html": {"file_name": html_path.name, "sha256": html_digest},
        "release_authority_created": False,
        "external_send_authority": False,
        "authority_created": False,
    }
    manifest_payload = _canonical_bytes(manifest)
    _write_once(manifest_path, manifest_payload)
    manifest_digest = _sha256(manifest_payload)
    return {
        "artifacts": [
            {
                "artifact_id": f"FORMAT-CORE-{request_hash[:12]}",
                "kind": "customer_review_summary",
                "file_name": html_path.name,
                "path": str(html_path),
                "mime_type": "text/html",
                "sha256": html_digest,
                "release_state": "HELD",
                "purpose": "format_core_review_summary",
                "customer_visibility": "review_only",
                "provenance": {"provider": "format_core", "request_sha256": request_hash},
                "release_conditions": ["human_review", "exact_manifest_approval"],
                "source_lineage": [item["sha256"] for item in inventory],
            },
            {
                "artifact_id": f"PRODUCTION-STUDIO-{request_hash[:12]}",
                "kind": "production_studio_review_manifest",
                "file_name": manifest_path.name,
                "path": str(manifest_path),
                "mime_type": "application/json",
                "sha256": manifest_digest,
                "release_state": "HELD",
                "purpose": "production_studio_review_manifest",
                "customer_visibility": "review_only",
                "provenance": {"provider": "production_studio", "request_sha256": request_hash},
                "release_conditions": ["human_review", "exact_manifest_approval"],
                "source_lineage": [html_digest, *[item["sha256"] for item in inventory]],
            },
        ],
        "evidence_refs": [f"format-core:{html_digest}", f"production-studio:{manifest_digest}"],
        "organ_steps": [
            {"organ": "format_core", "state": "PASS", "artifact": html_path.name},
            {"organ": "production_studio", "state": "PASS", "artifact": manifest_path.name},
        ],
    }
