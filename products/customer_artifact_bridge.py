from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from adapters.format_core.semantic_visual import (
    SEMANTIC_VISUAL_RENDERER_VERSION,
    SEMANTIC_VISUAL_SCHEMA,
    semantic_visual_to_composition,
    validate_semantic_visual,
)
from adapters.format_core.visual_composer import content_hash, write_visual_bundle


BRIDGE_SCHEMA = "dio.customer_artifact.semantic_visual_bridge.v1"
BRIDGE_RECEIPT = "CUSTOMER_ARTIFACT_VISUAL_BRIDGE_RECEIPT.json"
SEMANTIC_SPEC = "CUSTOMER_SEMANTIC_VISUAL.json"
COMPOSITION_SPEC = "CUSTOMER_VISUAL_COMPOSITION.json"

_KIND_TO_VISUAL = {
    "site": "research_workbench",
    "correspondence": "communication_outputs",
    "finance_readiness": "decision_landscape",
    "article": "evidence_network",
}


class CustomerArtifactBridgeError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _clean(value: Any, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _safe_id(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "product")).strip("-") or "product"


def _semantic_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = dict(manifest.get("artifact_contract") or {})
    job = dict(manifest.get("job") or {})
    kind = str(contract.get("kind") or "")
    studio_id = str(manifest.get("studio_id") or manifest.get("product_id") or manifest.get("name") or "product")
    buyer = _clean(job.get("buyer") or "customer", 160)
    request = _clean(job.get("request"), 320)

    if kind == "site":
        brand = dict(contract.get("brand") or {})
        positioning = dict(contract.get("positioning") or {})
        title = _clean(brand.get("title") or manifest.get("name") or studio_id, 120)
        summary = _clean(
            f"{positioning.get('buyer_problem', '')} {positioning.get('desired_outcome', '')}",
            320,
        )
        meaning = {
            "brand": title,
            "buyer": buyer,
            "category": _clean(positioning.get("category"), 120),
            "buyer_problem": _clean(positioning.get("buyer_problem"), 320),
            "desired_outcome": _clean(positioning.get("desired_outcome"), 320),
            "request": request,
        }
    elif kind == "correspondence":
        must_preserve = [_clean(row, 220) for row in contract.get("must_preserve") or []]
        title = _clean(f"Professional correspondence for {buyer}", 120)
        summary = _clean(request or "Prepare a bounded professional communication for human review.", 320)
        meaning = {
            "buyer": buyer,
            "request": request,
            "must_preserve": must_preserve,
            "target": _clean(contract.get("target") or contract.get("recipient"), 160),
            "subject": _clean(contract.get("subject"), 180),
        }
    elif kind == "finance_readiness":
        venture = dict(contract.get("venture") or {})
        title = _clean(venture.get("name") or manifest.get("name") or studio_id, 120)
        summary = _clean(
            f"{venture.get('funding_need', '')} Evidence readiness is separated from any lending decision.",
            320,
        )
        meaning = {
            "venture": title,
            "business_model": _clean(venture.get("business_model"), 260),
            "funding_need": _clean(venture.get("funding_need"), 240),
            "use_of_funds": [_clean(row, 160) for row in venture.get("use_of_funds") or []],
            "supplied_evidence": [
                {
                    "evidence_id": _clean(row.get("evidence_id"), 80),
                    "label": _clean(row.get("label"), 160),
                    "supports": list(row.get("supports") or []),
                    "state": _clean(row.get("state"), 80),
                }
                for row in contract.get("supplied_evidence_fixture") or []
                if isinstance(row, dict)
            ],
            "buyer": buyer,
        }
    elif kind == "article":
        title = _clean(contract.get("publication") or manifest.get("name") or studio_id, 120)
        summary = _clean(
            f"Publication draft for {contract.get('audience') or buyer}; supported and refused claims remain visibly distinct.",
            320,
        )
        meaning = {
            "publication": title,
            "audience": _clean(contract.get("audience") or buyer, 160),
            "claims": [
                {
                    "claim_id": _clean(row.get("claim_id"), 80),
                    "text": _clean(row.get("text"), 300),
                    "state": _clean(row.get("state"), 80),
                    "evidence_ids": list(row.get("evidence_ids") or []),
                }
                for row in contract.get("claim_fixture") or []
                if isinstance(row, dict)
            ],
            "sources": [
                {
                    "source_id": _clean(row.get("source_id") or row.get("evidence_id"), 80),
                    "citation": _clean(row.get("citation"), 240),
                }
                for row in contract.get("source_fixture") or []
                if isinstance(row, dict)
            ],
        }
    else:
        raise CustomerArtifactBridgeError(f"unsupported customer artifact kind: {kind or '(missing)'}")

    return {
        "studio_id": studio_id,
        "kind": kind,
        "title": title,
        "summary": summary,
        "meaning": meaning,
    }


def compile_customer_semantic_visual(manifest: dict[str, Any]) -> dict[str, Any]:
    payload = _semantic_payload(manifest)
    kind = payload["kind"]
    visual_kind = _KIND_TO_VISUAL[kind]
    core = {
        "schema": SEMANTIC_VISUAL_SCHEMA,
        "renderer_version": SEMANTIC_VISUAL_RENDERER_VERSION,
        "visual_id": f"CUSTOMER-{_safe_id(payload['studio_id'])}",
        "surface": "customer_artifact",
        "visual_kind": visual_kind,
        "semantic_intent": {
            "site": "show the customer's evidence work as a reviewable professional workbench",
            "correspondence": "show governed meaning projected into a professional communication held for human release",
            "finance_readiness": "show evidence, uncertainty and human decision boundary without implying lending approval",
            "article": "show claims, sources, tensions and human editorial review as an inspectable evidence network",
        }[kind],
        "title": payload["title"],
        "summary": payload["summary"],
        "entities": [],
        "relationships": [],
        "geometry_selector": "semantic_visual_kind_registry",
        "source": {
            "studio_id": payload["studio_id"],
            "artifact_kind": kind,
            "semantic_input_hash": content_hash(payload["meaning"]),
            "role_selects_geometry": False,
        },
        "governance": {
            "semantic_authority": "DIO_CUSTOMER_ARTIFACT_CONTRACT",
            "visual_semantic_compiler": "DIO_FORMAT_CORE",
            "geometry_authority": "DIO_FORMAT_CORE",
            "external_provider_layout_authority": "REFUSE",
            "authority_created": False,
            "external_effects": False,
        },
    }
    spec = {**core, "semantic_visual_hash": content_hash(core)}
    validation = validate_semantic_visual(spec)
    if not validation["passed"]:
        raise CustomerArtifactBridgeError("invalid semantic visual: " + "; ".join(validation["errors"]))
    return spec


def compose_customer_artifact_bridge(
    *,
    manifest: dict[str, Any],
    output_dir: Path,
    profile_id: str = "default",
) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    semantic_visual = compile_customer_semantic_visual(manifest)
    composition = semantic_visual_to_composition(
        semantic_visual,
        profile_id=profile_id,
        binding={
            "customer_artifact_bridge": BRIDGE_SCHEMA,
            "authority_created": False,
            "external_effects": False,
        },
    )

    semantic_path = output_dir / SEMANTIC_SPEC
    composition_path = output_dir / COMPOSITION_SPEC
    semantic_path.write_text(json.dumps(semantic_visual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    composition_path.write_text(json.dumps(composition, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    bundle = write_visual_bundle(
        composition,
        output_dir / "visual",
        basename="customer-semantic-visual",
        rasterize=False,
    )
    svg_path = Path(bundle["svg"]).resolve()
    composer_receipt_path = Path(bundle["receipt"]).resolve()

    receipt = {
        "schema": BRIDGE_SCHEMA,
        "state": "PASS",
        "studio_id": str(manifest.get("studio_id") or manifest.get("product_id") or manifest.get("name") or ""),
        "artifact_kind": str((manifest.get("artifact_contract") or {}).get("kind") or ""),
        "profile_id": profile_id,
        "visual_kind": semantic_visual["visual_kind"],
        "semantic_visual_hash": semantic_visual["semantic_visual_hash"],
        "semantic_input_hash": semantic_visual["source"]["semantic_input_hash"],
        "semantic_visual": SEMANTIC_SPEC,
        "semantic_visual_sha256": _file_hash(semantic_path),
        "composition": COMPOSITION_SPEC,
        "composition_hash": content_hash(composition),
        "composition_sha256": _file_hash(composition_path),
        "visual_svg": str(svg_path.relative_to(output_dir)),
        "visual_svg_hash": _file_hash(svg_path),
        "composer_receipt": str(composer_receipt_path.relative_to(output_dir)),
        "composer_receipt_sha256": _file_hash(composer_receipt_path),
        "authority_created": False,
        "external_effects": False,
        "automatic_publication": "REFUSE",
        "checks": {
            "semantic_visual_valid": True,
            "semantic_hash_bound": True,
            "composition_hash_bound": True,
            "deterministic_format_core_render": True,
            "human_release_boundary_preserved": True,
        },
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    receipt_path = output_dir / BRIDGE_RECEIPT
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**receipt, "receipt": str(receipt_path)}


def verify_customer_artifact_bridge(output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    receipt_path = output_dir / BRIDGE_RECEIPT
    errors: list[str] = []
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return {"passed": False, "errors": [f"bridge receipt unreadable: {exc}"]}

    if receipt.get("schema") != BRIDGE_SCHEMA:
        errors.append("bridge schema mismatch")
    if receipt.get("state") != "PASS":
        errors.append("bridge state is not PASS")
    if receipt.get("authority_created") is not False:
        errors.append("bridge created authority")
    if receipt.get("external_effects") is not False:
        errors.append("bridge created external effects")
    if receipt.get("automatic_publication") != "REFUSE":
        errors.append("automatic publication boundary missing")

    expected_fingerprint = receipt.get("receipt_fingerprint")
    fingerprint_payload = dict(receipt)
    fingerprint_payload.pop("receipt_fingerprint", None)
    if expected_fingerprint != _fingerprint(fingerprint_payload):
        errors.append("bridge receipt fingerprint mismatch")

    def resolve_file(key: str, hash_key: str) -> Path | None:
        rel = str(receipt.get(key) or "")
        if not rel:
            errors.append(f"{key} missing")
            return None
        path = (output_dir / rel).resolve()
        try:
            path.relative_to(output_dir)
        except ValueError:
            errors.append(f"{key} escapes bridge directory")
            return None
        if not path.is_file():
            errors.append(f"{key} file missing")
            return None
        if receipt.get(hash_key) != _file_hash(path):
            errors.append(f"{key} hash mismatch")
        return path

    semantic_path = resolve_file("semantic_visual", "semantic_visual_sha256")
    composition_path = resolve_file("composition", "composition_sha256")
    svg_path = resolve_file("visual_svg", "visual_svg_hash")
    composer_receipt_path = resolve_file("composer_receipt", "composer_receipt_sha256")

    semantic_visual: dict[str, Any] = {}
    composition: dict[str, Any] = {}
    if semantic_path:
        semantic_visual = json.loads(semantic_path.read_text(encoding="utf-8"))
        validation = validate_semantic_visual(semantic_visual)
        if not validation["passed"]:
            errors.extend(f"semantic visual: {row}" for row in validation["errors"])
        core = dict(semantic_visual)
        semantic_hash = core.pop("semantic_visual_hash", None)
        if semantic_hash != content_hash(core):
            errors.append("semantic visual content hash mismatch")
        if semantic_hash != receipt.get("semantic_visual_hash"):
            errors.append("semantic visual receipt hash mismatch")

    if composition_path:
        composition = json.loads(composition_path.read_text(encoding="utf-8"))
        if content_hash(composition) != receipt.get("composition_hash"):
            errors.append("composition content hash mismatch")
        binding = dict(composition.get("binding") or {})
        if binding.get("semantic_visual_hash") != receipt.get("semantic_visual_hash"):
            errors.append("composition is not bound to semantic visual hash")
        if binding.get("role_selects_geometry") is not False:
            errors.append("composition permits role-selected geometry")

    if composer_receipt_path:
        composer = json.loads(composer_receipt_path.read_text(encoding="utf-8"))
        if composer.get("state") != "PASS":
            errors.append("Format Core composer receipt is not PASS")
        if composer.get("composition_hash") != receipt.get("composition_hash"):
            errors.append("composer composition hash mismatch")
        if composer.get("svg_hash") != receipt.get("visual_svg_hash"):
            errors.append("composer SVG hash mismatch")
        if composer.get("authority_created") is not False:
            errors.append("composer created authority")
        if composer.get("automatic_publication") != "REFUSE":
            errors.append("composer publication boundary missing")

    if svg_path and svg_path.stat().st_size < 300:
        errors.append("semantic visual SVG is implausibly small")

    return {
        "passed": not errors,
        "errors": errors,
        "semantic_visual_hash": receipt.get("semantic_visual_hash"),
        "semantic_input_hash": receipt.get("semantic_input_hash"),
        "visual_svg_hash": receipt.get("visual_svg_hash"),
        "composition_hash": receipt.get("composition_hash"),
        "receipt_fingerprint": receipt.get("receipt_fingerprint"),
    }


__all__ = [
    "BRIDGE_RECEIPT",
    "BRIDGE_SCHEMA",
    "CustomerArtifactBridgeError",
    "compile_customer_semantic_visual",
    "compose_customer_artifact_bridge",
    "verify_customer_artifact_bridge",
]
