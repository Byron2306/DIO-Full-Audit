"""Hash-bound semantic finishing of native artifacts, held for human review."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from .artifact_content import extract_artifact_blocks

FORMAT_CORE_CAPABILITY = "format_core.semantic_finish"
PRODUCTION_STUDIO_CAPABILITY = "production_studio.customer_delivery"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: Any) -> str:
    text = str(value or "")
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError("a valid sha256 hash is required")
    return text


def _held_sources(artifacts: list[dict[str, Any]], state_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not artifacts:
        raise ValueError("shared professional finish requires held native artifacts")
    inventory: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("shared professional finish artifact must be an object")
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        digest = _digest(artifact.get("sha256"))
        if not artifact_id or artifact_id in seen or artifact.get("release_state") != "HELD":
            raise ValueError("shared professional finish requires unique hash-bound HELD route artifacts")
        seen.add(artifact_id)
        path = Path(str(artifact.get("path") or artifact.get("file_name") or ""))
        path = (path if path.is_absolute() else state_root / path).resolve()
        if not path.is_file():
            raise ValueError(f"native artifact is missing: {artifact_id}")
        if _sha256(path.read_bytes()) != digest:
            raise ValueError(f"native artifact hash mismatch: {artifact_id}")
        native = extract_artifact_blocks(path)
        inventory.append({
            "artifact_id": artifact_id, "kind": str(artifact.get("kind") or ""),
            "file_name": str(artifact.get("file_name") or path.name),
            "sha256": digest, "semantic_block_count": len(native),
            "binding_state": artifact.get("binding_state") or "CALLER_DECLARED_HASH_VERIFIED",
        })
        if native:
            blocks.append({"type": "heading", "level": 1, "text": path.name})
            for block in native:
                blocks.append({**block, "source_artifact_id": artifact_id, "source_sha256": digest})
    if not any(row["semantic_block_count"] for row in inventory):
        raise ValueError("no substantive semantic native artifact is available for finishing")
    return inventory, blocks


def _artifact(path: Path, artifact_id: str, kind: str, mime: str, lineage: list[str]) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id, "kind": kind, "file_name": path.name,
        "path": str(path), "mime_type": mime, "sha256": _sha256(path.read_bytes()),
        "release_state": "HELD", "purpose": kind, "customer_visibility": "review_only",
        "provenance": {"provider": "format_core" if mime != "application/json" else "production_studio"},
        "release_conditions": ["human_review", "exact_manifest_approval"], "source_lineage": lineage,
    }


def render_held_artifacts_for_review(
    *, state_root: Path, case_id: str, source_sha256: str, product_name: str,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Render native findings without inventing fulfilment or release truth.

    This entry point supports audit/customer-shaped execution as well as the
    fulfilment wrapper below. Source provenance is a packet/request hash; it
    never impersonates settlement or release authority.
    """
    from adapters.format_core.renderer import render_semantic_asset

    state_root = Path(state_root).resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    source_sha256 = _digest(source_sha256)
    if not str(case_id).strip() or not str(product_name).strip():
        raise ValueError("case identity and product name are required")
    inventory, native_blocks = _held_sources(artifacts, state_root)
    safe_case = re.sub(r"[^a-zA-Z0-9_-]", "-", str(case_id))[:90]
    prefix = f"{safe_case}-{source_sha256[:12]}"
    manifest_path = state_root / f"{prefix}-production-studio-review-manifest.json"
    source_lineage = [row["sha256"] for row in inventory]
    identity = {"case_id": case_id, "product_name": product_name, "source_sha256": source_sha256, "source_artifacts": inventory}
    identity_sha256 = _sha256(_canonical_bytes(identity))
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("identity_sha256") != identity_sha256:
            raise ValueError("shared professional finish would overwrite non-matching source artifacts")
        result = manifest["result"]
        for row in result["artifacts"]:
            path = state_root / row["file_name"]
            if path.parent != state_root or not path.is_file() or _sha256(path.read_bytes()) != row["sha256"]:
                raise ValueError("finished artifact hash mismatch or tampering")
        return _finish_result(result["artifacts"], manifest_path, source_lineage)

    blocks = [
        {"type": "paragraph", "text": "CONTROLLED REVIEW MATERIAL. Native findings are reproduced below; human review is required. This pack creates no delivery, publication, send or release authority."},
        *native_blocks,
        {"type": "heading", "level": 1, "text": "Source artifact inventory"},
        {"type": "table", "headers": ["Artifact", "File", "SHA-256"], "rows": [[r["artifact_id"], r["file_name"], r["sha256"]] for r in inventory]},
    ]
    for index, block in enumerate(blocks, 1):
        block["block_id"] = f"B{index:05d}"
    content = {
        "schema": "dio.semantic_content.v1", "object_id": prefix, "version": "1.0.0",
        "title": f"{product_name} — held review pack", "source_language": "en",
        "context": {"product": product_name, "artifact_type": "native_deliverable_review", "audience": "customer and human reviewer"},
        "blocks": blocks, "translations": {},
    }
    # Stage privately; keep the first complete renderer result to make replay
    # stable even though DOCX metadata and renderer timestamps are time-varying.
    with tempfile.TemporaryDirectory(prefix=".format-core-", dir=state_root) as directory:
        staging = Path(directory)
        receipt = render_semantic_asset(content, staging, channels=["docx", "html"], release_mode=False)
        if not receipt["qa"]["passed"] or receipt["status"] != "rendered_review_candidate":
            raise ValueError("Format Core semantic finishing did not pass QA")
        rendered = []
        for row in receipt["outputs"]:
            source = staging / row["path"]
            path = state_root / f"{prefix}-format-core-review.{row['channel']}"
            if path.exists():
                raise ValueError("unsealed Format Core output already exists; inspect before overwriting")
            path.write_bytes(source.read_bytes())
            rendered.append(dict(row, path=path.name))
        receipt["outputs"] = rendered
    outputs = [
        _artifact(state_root / row["path"], f"FORMAT-CORE-{source_sha256[:12]}-{row['channel'].upper()}", "customer_review_summary" if row["channel"] == "html" else "customer_review_document", "text/html" if row["channel"] == "html" else DOCX_MIME, source_lineage)
        for row in sorted(rendered, key=lambda r: r["channel"] == "docx")
    ]
    manifest = {
        "schema": "dio.production_studio.review_manifest.v2", "state": "HELD_FOR_REVIEW",
        **identity, "identity_sha256": identity_sha256, "route_artifacts": inventory,
        "format_core_html": {"file_name": outputs[0]["file_name"], "sha256": outputs[0]["sha256"]},
        "format_core": {"semantic_content": content, "receipt": receipt},
        "result": {"artifacts": outputs}, "release_authority_created": False,
        "external_send_authority": False, "authority_created": False,
    }
    manifest_path.write_bytes(_canonical_bytes(manifest))
    return _finish_result(outputs, manifest_path, source_lineage)


def _finish_result(outputs: list[dict[str, Any]], manifest_path: Path, source_lineage: list[str]) -> dict[str, Any]:
    manifest = _artifact(manifest_path, f"PRODUCTION-STUDIO-{_sha256(manifest_path.read_bytes())[:12]}", "production_studio_review_manifest", "application/json", [r["sha256"] for r in outputs] + source_lineage)
    return {
        "artifacts": [*outputs, manifest],
        "evidence_refs": [f"format-core:{outputs[0]['sha256']}", f"production-studio:{manifest['sha256']}"],
        "organ_steps": [
            {"organ": "format_core", "state": "PASS", "artifact": outputs[0]["file_name"], "provider": "adapters.format_core.renderer.render_semantic_asset"},
            {"organ": "production_studio", "state": "PASS", "artifact": manifest_path.name},
        ],
    }


def finish_fulfilment_for_review(state_root: Path, request: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    required = {str(row.get("capability_id") or "") for row in (request.get("execution_profile") or {}).get("executor_capabilities") or [] if isinstance(row, dict)}
    if required & {FORMAT_CORE_CAPABILITY, PRODUCTION_STUDIO_CAPABILITY} != {FORMAT_CORE_CAPABILITY, PRODUCTION_STUDIO_CAPABILITY}:
        raise ValueError("Format Core and Production Studio must be configured together")
    return render_held_artifacts_for_review(
        state_root=state_root, case_id=str(request.get("case_id") or ""),
        source_sha256=str(request.get("fulfilment_request_sha256") or ""),
        product_name=str(request.get("journey_product_id") or (request.get("execution_profile") or {}).get("journey_product_id") or "Held fulfilment"), artifacts=artifacts,
    )
