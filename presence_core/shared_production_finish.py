from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from adapters.format_core.renderer import build_paragraph_semantic_content, render_semantic_asset


class SharedProductionFinishError(RuntimeError):
    """Raised when a canonical fulfilment cannot be packaged for review."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    return text.strip("-.") or "case"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def finish_fulfilment_for_review(
    *, state_root: Path, request: dict[str, Any], artifacts: list[dict[str, Any]]
) -> dict[str, Any]:
    """Run the universal Format Core and Production Studio review finish."""

    state_root = Path(state_root).resolve()
    case_id = _slug(request.get("case_id"))
    product_name = str(request.get("journey_product_id") or "Canonical product").strip()
    finish_dir = state_root / "fulfilment_outputs" / case_id / "shared_finish"
    format_dir = finish_dir / "format_core"
    rows = [
        {"paragraph_id": "P1", "text": f"{product_name} — Customer Review Package"},
        {"paragraph_id": "P2", "text": "HUMAN REVIEW REQUIRED"},
        {
            "paragraph_id": "P3",
            "text": (
                "The listed artifacts remain held. This package creates no release, "
                "publication, external-send, or spend authority."
            ),
        },
    ]
    for index, source in enumerate(artifacts, 1):
        rows.append(
            {
                "paragraph_id": f"A{index}",
                "text": (
                    f"Artifact {source['artifact_id']} — kind {source['kind']} — "
                    f"SHA-256 {source['sha256']} — release state HELD"
                ),
            }
        )
    semantic = build_paragraph_semantic_content(
        object_id=f"DIO-REVIEW-{case_id}",
        version="1.0.0",
        title=f"{product_name} — Customer Review Package",
        source_language="English",
        source_rows=rows,
        context={
            "product": product_name,
            "artifact_type": "canonical_customer_review_package",
            "audience": "customer reviewer",
        },
    )
    try:
        format_receipt = render_semantic_asset(
            semantic,
            format_dir,
            style_profile="dio_professional",
            delivery_profile="editable_review",
            language="English",
            channels=["html"],
            release_mode=False,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise SharedProductionFinishError(
            f"Format Core could not create the customer review package: {exc}"
        ) from exc
    if (
        format_receipt.get("status") != "rendered_review_candidate"
        or (format_receipt.get("qa") or {}).get("passed") is not True
    ):
        raise SharedProductionFinishError("Format Core did not produce a QA-passed review candidate")
    html_rows = [
        row for row in format_receipt.get("outputs") or [] if row.get("channel") == "html"
    ]
    if len(html_rows) != 1:
        raise SharedProductionFinishError("Format Core did not produce one HTML review artifact")
    html_path = format_dir / str(html_rows[0]["path"])
    if not html_path.is_file():
        raise SharedProductionFinishError("Format Core review artifact is missing")

    manifest = {
        "schema": "dio.production_studio.customer_review_manifest.v1",
        "case_id": str(request["case_id"]),
        "product_name": product_name,
        "fulfilment_request_sha256": str(request["fulfilment_request_sha256"]),
        "source_artifacts": artifacts,
        "format_core": {
            "status": format_receipt["status"],
            "semantic_source_hash": format_receipt["semantic_source_hash"],
            "qa_passed": True,
            "review_artifact_sha256": _sha256(html_path),
        },
        "review_state": "HELD_FOR_HUMAN_REVIEW",
        "release_authority": False,
        "external_send_authority": False,
        "publication_authority": False,
        "spend_authority": False,
        "authority_created": False,
    }
    manifest_path = finish_dir / "PRODUCTION_STUDIO_REVIEW_MANIFEST.json"
    _write_json(manifest_path, manifest)

    def artifact(path: Path, *, artifact_id: str, kind: str, mime_type: str) -> dict[str, Any]:
        relative_path = str(path.relative_to(state_root))
        return {
            "artifact_id": artifact_id,
            "kind": kind,
            "path": str(path),
            "file_name": relative_path,
            "mime_type": mime_type,
            "sha256": _sha256(path),
            "release_state": "HELD",
            "purpose": (
                "Give the customer a review-safe summary of the held fulfilment artifacts."
                if kind == "customer_review_summary"
                else "Record the exact Production Studio customer-review package."
            ),
            "customer_visibility": "CUSTOMER_REVIEW_CANDIDATE",
            "provenance": {
                "provider": "dio.shared.production_finish",
                "fulfilment_request_sha256": str(request["fulfilment_request_sha256"]),
            },
            "release_conditions": [
                "human_review",
                "exact_manifest_approval",
            ],
            "source_lineage": [
                {
                    "artifact_id": str(source["artifact_id"]),
                    "sha256": str(source["sha256"]),
                }
                for source in artifacts
            ],
            "release_authority": False,
            "external_send_authority": False,
            "authority_created": False,
        }

    return {
        "artifacts": [
            artifact(
                html_path,
                artifact_id=f"ART-{case_id}-FORMAT-CORE",
                kind="customer_review_summary",
                mime_type="text/html",
            ),
            artifact(
                manifest_path,
                artifact_id=f"ART-{case_id}-PRODUCTION-STUDIO",
                kind="production_studio_review_manifest",
                mime_type="application/json",
            ),
        ],
        "evidence_refs": [
            f"format-core:{_sha256(html_path)}",
            f"production-studio:{_sha256(manifest_path)}",
        ],
        "organ_steps": [
            {"organ": "format_core", "state": "PASS", "stage": "shared_customer_review_finish"},
            {"organ": "production_studio", "state": "PASS", "stage": "shared_customer_review_finish"},
        ],
    }

