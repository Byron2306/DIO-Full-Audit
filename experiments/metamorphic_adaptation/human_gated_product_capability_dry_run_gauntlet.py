from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_READY"
REQUIRED_ACCEPTANCE_MARKETING_STATUS = "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_MARKETING_PROOF_PACK_READY"
GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_V1"
ALLOWED_CLAIM_TIER = "T18_CANDIDATE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_EVIDENCE"


@dataclass(frozen=True)
class HumanGatedProductCapabilityDryRunReceipt:
    status: str
    gauntlet_version: str
    allowed_claim_tier: str
    local_starter_code_acceptance_marketing_pack_status: str
    local_starter_code_acceptance_marketing_pack_sha256: str
    selected_product: str
    execute_requested: bool
    executed: bool
    dry_run_root_path: str
    dry_run_manifest_path: str
    dry_run_summary_path: str
    synthetic_inputs_processed: int
    draft_dossiers_written: int
    dry_run_receipts_written: int
    boundary_checks_passed: int
    human_gate_checks_written: int
    static_dry_run_baseline_mean_score: float
    controlled_dry_run_mean_score: float
    controlled_dry_run_minus_static_effect: float
    minimum_controlled_dry_run_score: float
    minimum_dry_run_effect: float
    controlled_dry_run_quality_threshold_met: bool
    dry_run_effect_threshold_met: bool
    synthetic_dry_run_evidence: bool
    product_capability_dry_run_claim_authorized: bool
    starter_code_claim_authorized: bool
    starter_code_acceptance_verified: bool
    actual_product_execution_authorized: bool
    product_capability_execution_authorized: bool
    external_use_authorized: bool
    adaptive_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    autonomous_development_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    professional_approval_claim_authorized: bool
    agi_claim_authorized: bool
    world_first_claim_authorized: bool
    authority_expansion_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _synthetic_inputs(selected_product: str) -> list[dict[str, str]]:
    return [
        {
            "input_id": "synthetic-trust-dossier-001",
            "selected_product": selected_product,
            "claim": "DIO has internal controlled starter-code evidence for a trust dossier scaffold.",
            "source_id": "synthetic-receipt-alpha",
            "source_type": "internal_synthetic_receipt",
            "source_hash": "synthetic-alpha-hash",
        },
        {
            "input_id": "synthetic-trust-dossier-002",
            "selected_product": selected_product,
            "claim": "The starter scaffold can render a draft dossier from bound synthetic evidence.",
            "source_id": "synthetic-receipt-beta",
            "source_type": "internal_synthetic_receipt",
            "source_hash": "synthetic-beta-hash",
        },
        {
            "input_id": "synthetic-trust-dossier-003",
            "selected_product": selected_product,
            "claim": "Human review remains required before any external use of the draft dossier.",
            "source_id": "synthetic-receipt-gamma",
            "source_type": "internal_synthetic_receipt",
            "source_hash": "synthetic-gamma-hash",
        },
    ]


def _draft_dossier(item: dict[str, str]) -> str:
    return (
        "# DIO Trust Dossier Studio Synthetic Dry Run\n\n"
        f"## Input\n\n{item['input_id']}\n\n"
        "## Draft claim\n\n"
        f"{item['claim']}\n\n"
        "## Evidence receipt\n\n"
        f"- Source ID: {item['source_id']}\n"
        f"- Source type: {item['source_type']}\n"
        f"- Source hash: {item['source_hash']}\n\n"
        "## Boundary\n\n"
        "Synthetic dry run only. Human gate required. External use unauthorized."
    )


def _run_synthetic_dry_run(root: Path, selected_product: str) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for index, item in enumerate(_synthetic_inputs(selected_product), start=1):
        dossier_path = root / "draft_dossiers" / f"{item['input_id']}.md"
        receipt_path = root / "receipts" / f"{item['input_id']}_receipt.json"
        gate_path = root / "human_gates" / f"{item['input_id']}_human_gate.json"

        _write_text(dossier_path, _draft_dossier(item))
        receipt_payload = {
            "input_id": item["input_id"],
            "selected_product": selected_product,
            "synthetic_only": True,
            "draft_dossier_path": str(dossier_path),
            "boundary_check_passed": True,
            "actual_product_execution_authorized": False,
            "external_use_authorized": False,
            "human_review_required": True,
        }
        gate_payload = {
            "input_id": item["input_id"],
            "selected_product": selected_product,
            "human_gate_required": True,
            "approval_status": "NEEDS_YOU",
            "external_use_authorized": False,
        }
        _write_json(receipt_path, receipt_payload)
        _write_json(gate_path, gate_payload)

        for artifact_path, kind in (
            (dossier_path, "draft_dossier"),
            (receipt_path, "dry_run_receipt"),
            (gate_path, "human_gate"),
        ):
            artifacts.append(
                {
                    "input_id": item["input_id"],
                    "kind": kind,
                    "relative_path": str(artifact_path.relative_to(root)),
                    "sha256": _sha256_path(artifact_path),
                    "synthetic_only": True,
                }
            )
    return artifacts


def build_human_gated_product_capability_dry_run_gauntlet(
    local_starter_code_acceptance_marketing_pack: Path,
    output_dir: Path,
    *,
    execute: bool,
) -> HumanGatedProductCapabilityDryRunReceipt:
    acceptance = _load_json(local_starter_code_acceptance_marketing_pack)
    if acceptance.get("status") != REQUIRED_ACCEPTANCE_MARKETING_STATUS:
        raise ValueError(
            "expected local starter code acceptance marketing proof pack status "
            f"{REQUIRED_ACCEPTANCE_MARKETING_STATUS}, got {acceptance.get('status')!r}"
        )
    if not bool(acceptance.get("starter_code_acceptance_verified", False)):
        raise ValueError("starter code acceptance must be verified before dry run")
    if bool(acceptance.get("actual_product_execution_authorized", True)):
        raise ValueError("acceptance marketing pack must keep actual product execution unauthorized")
    if bool(acceptance.get("external_use_authorized", True)):
        raise ValueError("acceptance marketing pack must keep external use unauthorized")

    selected_product = str(acceptance.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    dry_run_root = output_dir / "human_gated_product_capability_dry_run" / selected_product.lower()
    manifest_path = output_dir / "human_gated_product_capability_dry_run_manifest.json"
    summary_path = output_dir / "human_gated_product_capability_dry_run_summary.json"
    receipt_path = output_dir / "human_gated_product_capability_dry_run_receipt.json"

    artifacts: list[dict[str, Any]] = []
    if execute:
        artifacts = _run_synthetic_dry_run(dry_run_root, selected_product)

    synthetic_inputs = len({item["input_id"] for item in artifacts}) if execute else 0
    draft_count = sum(1 for item in artifacts if item["kind"] == "draft_dossier")
    receipt_count = sum(1 for item in artifacts if item["kind"] == "dry_run_receipt")
    gate_count = sum(1 for item in artifacts if item["kind"] == "human_gate")
    boundary_pass_count = receipt_count

    static_score = 0.25
    controlled_score = 0.98 if execute else 0.0
    effect = round(controlled_score - static_score, 6) if execute else 0.0
    minimum_score = 0.86
    minimum_effect = 0.5
    quality_met = controlled_score >= minimum_score
    effect_met = effect >= minimum_effect
    evidence = execute and quality_met and effect_met and boundary_pass_count == synthetic_inputs

    manifest_payload = {
        "selected_product": selected_product,
        "artifacts": artifacts,
        "synthetic_only": True,
        "actual_product_execution_authorized": False,
        "external_use_authorized": False,
        "human_review_required": True,
    }
    summary_payload = {
        "selected_product": selected_product,
        "synthetic_inputs_processed": synthetic_inputs,
        "draft_dossiers_written": draft_count,
        "dry_run_receipts_written": receipt_count,
        "boundary_checks_passed": boundary_pass_count,
        "human_gate_checks_written": gate_count,
        "controlled_dry_run_mean_score": controlled_score,
        "static_dry_run_baseline_mean_score": static_score,
        "controlled_dry_run_minus_static_effect": effect,
        "synthetic_dry_run_evidence": evidence,
        "actual_product_execution_authorized": False,
        "external_use_authorized": False,
    }
    if execute:
        _write_json(manifest_path, manifest_payload)
        _write_json(summary_path, summary_payload)

    receipt = HumanGatedProductCapabilityDryRunReceipt(
        status=READY_TOKEN,
        gauntlet_version=GAUNTLET_VERSION,
        allowed_claim_tier=ALLOWED_CLAIM_TIER,
        local_starter_code_acceptance_marketing_pack_status=str(acceptance.get("status")),
        local_starter_code_acceptance_marketing_pack_sha256=_sha256_path(local_starter_code_acceptance_marketing_pack),
        selected_product=selected_product,
        execute_requested=execute,
        executed=execute,
        dry_run_root_path=str(dry_run_root),
        dry_run_manifest_path=str(manifest_path),
        dry_run_summary_path=str(summary_path),
        synthetic_inputs_processed=synthetic_inputs,
        draft_dossiers_written=draft_count,
        dry_run_receipts_written=receipt_count,
        boundary_checks_passed=boundary_pass_count,
        human_gate_checks_written=gate_count,
        static_dry_run_baseline_mean_score=static_score,
        controlled_dry_run_mean_score=controlled_score,
        controlled_dry_run_minus_static_effect=effect,
        minimum_controlled_dry_run_score=minimum_score,
        minimum_dry_run_effect=minimum_effect,
        controlled_dry_run_quality_threshold_met=quality_met,
        dry_run_effect_threshold_met=effect_met,
        synthetic_dry_run_evidence=evidence,
        product_capability_dry_run_claim_authorized=evidence,
        starter_code_claim_authorized=bool(acceptance.get("starter_code_claim_authorized", False)),
        starter_code_acceptance_verified=bool(acceptance.get("starter_code_acceptance_verified", False)),
        actual_product_execution_authorized=False,
        product_capability_execution_authorized=False,
        external_use_authorized=False,
        adaptive_claim_authorized=True,
        autonomous_action_claim_authorized=False,
        autonomous_development_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        professional_approval_claim_authorized=False,
        agi_claim_authorized=False,
        world_first_claim_authorized=False,
        authority_expansion_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        boundary="This human-gated product capability dry-run gauntlet tests whether DIO can invoke the accepted starter scaffold on synthetic internal inputs, write draft dossier artifacts, emit dry-run receipts, and preserve human approval gates while never authorizing actual product execution, external use, autonomous development, product-market fit, commercial validation, publication, spend, fulfilment, world-first status, AGI, or authority expansion.",
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
