from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_MARKETING_PROOF_PACK_READY"
REQUIRED_DRY_RUN_STATUS = "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_READY"
PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_MARKETING_PROOF_PACK_V1"
MARKETING_CLAIM_TIER = "T18_MARKETING_SAFE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN"


@dataclass(frozen=True)
class HumanGatedDryRunMarketingProofPackReceipt:
    status: str
    pack_version: str
    marketing_claim_tier: str
    human_gated_product_capability_dry_run_status: str
    human_gated_product_capability_dry_run_sha256: str
    selected_product: str
    synthetic_inputs_processed: int
    draft_dossiers_written: int
    dry_run_receipts_written: int
    boundary_checks_passed: int
    human_gate_checks_written: int
    controlled_dry_run_mean_score: float
    static_dry_run_baseline_mean_score: float
    controlled_dry_run_minus_static_effect: float
    synthetic_dry_run_evidence: bool
    product_capability_dry_run_marketing_language_authorized: bool
    product_capability_dry_run_claim_authorized: bool
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
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    boundary: str
    dry_run_marketing_claims_path: str
    dry_run_marketing_copy_path: str


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _approved_claims(dry_run: dict[str, Any]) -> list[str]:
    selected_product = str(dry_run.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    synthetic = int(dry_run.get("synthetic_inputs_processed", 0))
    dossiers = int(dry_run.get("draft_dossiers_written", 0))
    receipts = int(dry_run.get("dry_run_receipts_written", 0))
    checks = int(dry_run.get("boundary_checks_passed", 0))
    human_gates = int(dry_run.get("human_gate_checks_written", 0))
    effect = float(dry_run.get("controlled_dry_run_minus_static_effect", 0.0))
    baseline = float(dry_run.get("static_dry_run_baseline_mean_score", 0.0))
    score = float(dry_run.get("controlled_dry_run_mean_score", 0.0))
    return [
        "DIO produced T18 candidate evidence of a human-gated product capability dry run in an internal controlled gauntlet.",
        f"DIO invoked the accepted starter scaffold for {selected_product} on {synthetic} synthetic internal inputs under the tested harness.",
        f"DIO wrote {dossiers} draft dossier artifacts and {receipts} dry-run receipts while preserving human approval gates.",
        f"DIO recorded {checks} boundary checks passed and {human_gates} human-gate checks written during the dry run.",
        f"The T18 gauntlet measured a controlled-dry-run minus static-dry-run effect of {effect:.4f}; the static baseline scored {baseline:.4f} and the controlled dry-run route scored {score:.4f}.",
        "The T18 evidence supports bounded language about synthetic, human-gated dry-run behavior, not actual product execution, external use, product-market fit, or commercial validation.",
        "The dry-run signal preserved human gates and blocked actual-execution, product-capability-execution, external-use, AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _forbidden_claims() -> list[str]:
    return [
        "DIO executed selected-product capabilities in the real world",
        "DIO externally used, published, or deployed the dry-run outputs",
        "DIO completed a production implementation",
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees viable products, sales, revenue, or buyer outcomes",
        "DIO can autonomously build, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO has world-first status",
        "DIO can skip human review because a dry run completed",
    ]


def _copy(dry_run: dict[str, Any], approved: list[str], forbidden: list[str]) -> str:
    selected_product = str(dry_run.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    synthetic = int(dry_run.get("synthetic_inputs_processed", 0))
    dossiers = int(dry_run.get("draft_dossiers_written", 0))
    receipts = int(dry_run.get("dry_run_receipts_written", 0))
    checks = int(dry_run.get("boundary_checks_passed", 0))
    human_gates = int(dry_run.get("human_gate_checks_written", 0))
    baseline = float(dry_run.get("static_dry_run_baseline_mean_score", 0.0))
    score = float(dry_run.get("controlled_dry_run_mean_score", 0.0))
    effect = float(dry_run.get("controlled_dry_run_minus_static_effect", 0.0))
    approved_md = "\n".join(f"- {claim}" for claim in approved)
    forbidden_md = "\n".join(f"- {claim}" for claim in forbidden)
    return f"""# DIO Human-Gated Product Capability Dry Run Marketing Proof Pack

## Marketing-safe claim

DIO has internal controlled T18 candidate evidence of a human-gated product capability dry run: it invoked the accepted starter scaffold for {selected_product} on synthetic internal inputs, wrote draft dossier artifacts, emitted dry-run receipts, and preserved human approval gates while keeping actual product execution, external use, product-market fit, commercial validation, and deployment unauthorized.

## Approved language

{approved_md}

## Positioning line

DIO does not merely verify starter code. It can run a synthetic, human-gated dry run that produces draft dossier artifacts and receipts while keeping real-world product execution and external use unauthorized.

## Proof numbers

- Static dry-run baseline: {baseline:.4f}
- Controlled dry-run score: {score:.4f}
- Controlled dry-run minus static effect: {effect:.4f}
- Synthetic internal inputs processed: {synthetic}
- Draft dossiers written: {dossiers}
- Dry-run receipts written: {receipts}
- Boundary checks passed: {checks}
- Human-gate checks written: {human_gates}

## Required disclaimers

- Internal controlled gauntlet evidence only.
- Candidate human-gated dry-run evidence, not actual product execution.
- No actual product execution.
- No external use.
- Not product capability execution.
- Not autonomous development.
- Not production implementation.
- Not product-market fit.
- Not commercial validation.
- Not AGI.
- Not professional approval.
- Not world-first status.
- No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.

## Forbidden claims

{forbidden_md}
"""


def build_human_gated_product_capability_dry_run_marketing_proof_pack(
    human_gated_product_capability_dry_run: Path,
    output_dir: Path,
) -> HumanGatedDryRunMarketingProofPackReceipt:
    dry_run = _load_json(human_gated_product_capability_dry_run)
    if dry_run.get("status") != REQUIRED_DRY_RUN_STATUS:
        raise ValueError(
            "expected human gated product capability dry run receipt status "
            f"{REQUIRED_DRY_RUN_STATUS}, got {dry_run.get('status')!r}"
        )

    approved = _approved_claims(dry_run)
    forbidden = _forbidden_claims()
    claims_path = output_dir / "human_gated_product_capability_dry_run_marketing_proof_claims.json"
    copy_path = output_dir / "human_gated_product_capability_dry_run_marketing_safe_copy.md"
    receipt_path = output_dir / "human_gated_product_capability_dry_run_marketing_proof_pack_receipt.json"

    claims_payload = {
        "marketing_claim_tier": MARKETING_CLAIM_TIER,
        "approved_public_claims": approved,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "Candidate human-gated dry-run evidence, not actual product execution.",
            "No actual product execution.",
            "No external use.",
            "Not product capability execution.",
            "Not autonomous development.",
            "Not production implementation.",
            "Not product-market fit.",
            "Not commercial validation.",
            "Not AGI.",
            "Not professional approval.",
            "Not world-first status.",
            "No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
        ],
    }
    _write_json(claims_path, claims_payload)
    _write_markdown(copy_path, _copy(dry_run, approved, forbidden))

    receipt = HumanGatedDryRunMarketingProofPackReceipt(
        status=READY_TOKEN,
        pack_version=PACK_VERSION,
        marketing_claim_tier=MARKETING_CLAIM_TIER,
        human_gated_product_capability_dry_run_status=str(dry_run.get("status")),
        human_gated_product_capability_dry_run_sha256=_sha256_path(human_gated_product_capability_dry_run),
        selected_product=str(dry_run.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO")),
        synthetic_inputs_processed=int(dry_run.get("synthetic_inputs_processed", 0)),
        draft_dossiers_written=int(dry_run.get("draft_dossiers_written", 0)),
        dry_run_receipts_written=int(dry_run.get("dry_run_receipts_written", 0)),
        boundary_checks_passed=int(dry_run.get("boundary_checks_passed", 0)),
        human_gate_checks_written=int(dry_run.get("human_gate_checks_written", 0)),
        controlled_dry_run_mean_score=float(dry_run.get("controlled_dry_run_mean_score", 0.0)),
        static_dry_run_baseline_mean_score=float(dry_run.get("static_dry_run_baseline_mean_score", 0.0)),
        controlled_dry_run_minus_static_effect=float(dry_run.get("controlled_dry_run_minus_static_effect", 0.0)),
        synthetic_dry_run_evidence=bool(dry_run.get("synthetic_dry_run_evidence", False)),
        product_capability_dry_run_marketing_language_authorized=True,
        product_capability_dry_run_claim_authorized=bool(dry_run.get("product_capability_dry_run_claim_authorized", False)),
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
        allowed_public_claims_count=len(approved),
        forbidden_public_claims_count=len(forbidden),
        boundary="This human-gated product capability dry-run marketing proof pack converts T18 candidate synthetic dry-run evidence into bounded, marketing-safe language. It authorizes only proof-bound public wording about synthetic, internal, human-gated dry-run behavior and never authorizes actual product execution, product capability execution, external use, autonomous development, product-market fit, commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claims, autonomous consequential action, or authority expansion.",
        dry_run_marketing_claims_path=str(claims_path),
        dry_run_marketing_copy_path=str(copy_path),
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
