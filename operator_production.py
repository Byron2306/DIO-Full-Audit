from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT, load_portfolio
from scripts.build_multichannel_campaign_factory import build_family

MATRIX_PATH = ROOT / "config" / "marketing_audience_matrix.json"
OUTPUT_ROOT = ROOT / "state" / "operator_production"
ALLOWED_OUTPUT_ROOTS = tuple(
    path.resolve()
    for path in (
        ROOT,
        Path("/home/byron/Downloads/KnowEdge_AutoRelease_Suite"),
        Path("/home/byron/Downloads/NicheFoundry_Phase11"),
        Path("/home/byron/KnowEdge_Microsoft_Mirror"),
    )
    if path.exists()
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _incarnation(name: str) -> dict[str, Any]:
    match = next(
        (row for row in load_portfolio()["incarnations"] if str(row.get("Incarnation") or "") == str(name or "")),
        None,
    )
    if not match:
        raise ValueError("Select a canonical imported portfolio incarnation")
    return match


def _relative_repo_path(raw: str, *, default: str = "") -> str:
    value = str(raw or default).strip()
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if resolved != ROOT.resolve() and ROOT.resolve() not in resolved.parents:
        raise ValueError("Marketing source/proof assets must currently live inside DIO-Full-Audit")
    if not resolved.exists():
        raise ValueError(f"Marketing source/proof asset does not exist: {resolved}")
    return str(resolved.relative_to(ROOT.resolve()))


def production_state() -> dict[str, Any]:
    portfolio = load_portfolio()
    matrix = _matrix()
    profiles = []
    for product in matrix.get("products") or []:
        profiles.append(
            {
                "id": product.get("id"),
                "name": product.get("name"),
                "short_name": product.get("short_name"),
                "proof_asset": product.get("proof_asset"),
                "source_image": product.get("source_image"),
                "audiences": product.get("audiences") or [],
                "outputs": [
                    "square_1080",
                    "landscape_1200x628",
                    "portrait_1080x1350",
                    "vertical_1080x1920",
                    "youtube_1280x720",
                    "channel_copy",
                    "reel_scenes",
                    "nichefoundry_reel",
                ],
            }
        )
    return {
        "schema": "dio.operator_production.state.v1",
        "portfolio": {
            "count": portfolio.get("canonical_incarnation_count", len(portfolio.get("incarnations") or [])),
            "incarnations": portfolio.get("incarnations") or [],
            "candidate_incarnations_imported": portfolio.get("candidate_incarnations_imported", 0),
        },
        "marketing": {
            "profiles": profiles,
            "channels": matrix.get("channels") or {},
            "publication": "operator_approval_required",
            "spend": "disabled",
        },
        "evidence_lanes": [
            {"id": "HOMS_EVIDEX", "families": ["HOMS", "Evidex"], "endpoint": "/api/control/product/action", "input": "existing governed product job", "actions": ["approve-intake", "process", "approve-output", "prepare-notification"]},
            {"id": "SOPHIA", "families": ["Sophia"], "endpoint": "/api/control/sophia/action", "input": "existing Sophia commercial job", "actions": ["run", "approve", "prepare-delivery"]},
            {"id": "VAMP", "families": ["VAMP"], "endpoint": "/api/control/vamp/action", "input": "existing VAMP commercial job", "actions": ["run", "approve", "prepare-delivery"]},
            {"id": "DOCUMENT_STUDIO", "families": ["Document Studio", "Format Core"], "endpoint": "/api/control/document-studio/action", "input": "existing Document Studio job", "actions": ["run", "approve", "prepare-delivery"]},
            {"id": "EVIDENCE_PACKAGE_GATE", "families": ["ALL_CANONICAL_INCARNATIONS"], "endpoint": "/api/business/production/evidence-gate", "input": "actual output path + execution/proof receipt", "actions": ["gate"]},
        ],
        "truth": {
            "marketing_asset_created_is_publication": False,
            "marketing_asset_created_is_market_validation": False,
            "evidence_gate_is_professional_certification": False,
            "authority_created": False,
        },
    }


def create_marketing_pack(spec: dict[str, Any]) -> dict[str, Any]:
    incarnation = _incarnation(str(spec.get("incarnation") or ""))
    matrix = _matrix()
    profile_id = str(spec.get("profile_id") or "").strip()
    selected_profile = next((row for row in matrix.get("products") or [] if row.get("id") == profile_id), None) if profile_id else None
    render_reel = spec.get("render_reel") is True

    if selected_profile:
        audience_id = str(spec.get("audience_id") or "")
        audience = next((row for row in selected_profile.get("audiences") or [] if row.get("id") == audience_id), None)
        if not audience:
            raise ValueError("Select an audience from the chosen verified marketing profile")
        product = dict(selected_profile)
        product["id"] = f"{selected_profile['id']}--{incarnation['incarnation']}"
        product["name"] = str(incarnation["Incarnation"])
        product["short_name"] = str(incarnation["Incarnation"])
    else:
        required = ("audience_name", "pain", "outcome", "cta", "marketing_statement")
        missing = [field for field in required if not str(spec.get(field) or "").strip()]
        if missing:
            raise ValueError("Custom portfolio marketing brief requires: " + ", ".join(missing))
        source_image = _relative_repo_path(str(spec.get("source_image") or ""), default="DIO.png")
        proof_asset = _relative_repo_path(str(spec.get("proof_asset") or "")) if spec.get("proof_asset") else "config/atlas/dio_meta_incarnation_crosswalk.csv"
        if render_reel and not spec.get("proof_asset"):
            raise ValueError("Rendered reel for a custom incarnation requires an actual product proof asset; static marketing assets can be created without one")
        product = {
            "id": "OPERATOR--" + "".join(ch if ch.isalnum() else "_" for ch in str(incarnation["Incarnation"]).upper()),
            "name": str(incarnation["Incarnation"]),
            "short_name": str(incarnation["Incarnation"]),
            "offer": "operator_defined_bounded_offer",
            "promise": str(spec["marketing_statement"]).strip(),
            "proof": (
                f"Portfolio evidence boundary: {incarnation.get('source_maturity') or 'unclassified'}; "
                f"execution truth class {incarnation.get('execution_truth_class') or 'unclassified'}."
            ),
            "cta": str(spec["cta"]).strip(),
            "landing_page": str(spec.get("landing_page") or ""),
            "proof_asset": proof_asset,
            "source_image": source_image,
            "accent": "#e4b85f",
        }
        audience = {
            "id": "operator_audience",
            "name": str(spec["audience_name"]).strip(),
            "pain": str(spec["pain"]).strip(),
            "outcome": str(spec["outcome"]).strip(),
        }

    run_id = "MKT-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3).upper()
    output_root = OUTPUT_ROOT / "marketing" / run_id
    family = build_family(product, audience, matrix["channels"], output_root, render_reel)
    receipt = {
        "schema": "dio.operator_production.marketing_receipt.v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "incarnation": incarnation["Incarnation"],
        "portfolio_truth_class": incarnation.get("execution_truth_class"),
        "marketing_profile": profile_id or "operator_bounded_custom",
        "render_reel_requested": render_reel,
        "family_id": family.get("family_id"),
        "output_dir": str(output_root),
        "family": family,
        "publication_authorized": False,
        "spend_authorized": False,
        "market_validation_claimed": False,
        "authority_created": False,
    }
    _write_json(output_root / "OPERATOR_MARKETING_RECEIPT.json", receipt)
    return receipt


def _resolve_output(raw: str) -> Path:
    if not str(raw or "").strip():
        raise ValueError("Evidence gate requires an actual output path")
    candidate = Path(str(raw)).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve()
    if not any(resolved == root or root in resolved.parents for root in ALLOWED_OUTPUT_ROOTS):
        raise ValueError("Evidence path is outside approved DIO output roots")
    if not resolved.exists():
        raise ValueError(f"Evidence path does not exist: {resolved}")
    return resolved


def _fingerprint(path: Path) -> str:
    if path.is_dir():
        entries = []
        for child in sorted(p for p in path.rglob("*") if p.is_file()):
            entries.append(str(child.relative_to(path)) + ":" + _fingerprint(child))
        raw = "\n".join(entries).encode("utf-8")
        return "sha256:" + hashlib.sha256(raw).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def run_evidence_gate(spec: dict[str, Any]) -> dict[str, Any]:
    incarnation = _incarnation(str(spec.get("incarnation") or ""))
    output = _resolve_output(str(spec.get("output_path") or ""))
    receipt_raw = str(spec.get("receipt_path") or "").strip()
    receipt = _resolve_output(receipt_raw) if receipt_raw else None
    if receipt is not None and receipt.is_dir():
        raise ValueError("Execution/proof receipt must be a file")

    run_id = "EVD-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3).upper()
    directory = OUTPUT_ROOT / "evidence" / run_id
    maturity = str(incarnation.get("source_maturity") or "")
    truth_class = str(incarnation.get("execution_truth_class") or "")
    strong_source = any(word in maturity.casefold() for word in ("proof", "implemented", "capability", "foundation", "core"))
    state = "EVIDENCE_PACKAGE_READY_FOR_HUMAN_REVIEW" if receipt is not None else "OUTPUT_BOUND_RECEIPT_REQUIRED"
    payload = {
        "schema": "dio.operator_production.evidence_gate_receipt.v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "incarnation": incarnation["Incarnation"],
        "suite": incarnation.get("suite"),
        "primary_family": incarnation.get("primary_family"),
        "source_maturity": maturity,
        "execution_truth_class": truth_class,
        "source_maturity_indicates_existing_proof_or_implementation": strong_source,
        "output": {"path": str(output), "sha256": _fingerprint(output)},
        "execution_receipt": {"path": str(receipt), "sha256": _fingerprint(receipt)} if receipt is not None else None,
        "state": state,
        "human_review_required": True,
        "professional_certification_claimed": False,
        "market_validation_claimed": False,
        "commercial_success_claimed": False,
        "authority_created": False,
    }
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "EVIDENCE_GATE_RECEIPT.json", payload)
    payload["receipt_path"] = str(directory / "EVIDENCE_GATE_RECEIPT.json")
    return payload
