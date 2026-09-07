from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


PRODUCT_INCARNATION_MARKETING_PROOF_PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_MARKETING_PROOF_PACK_V1"
PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY"
PRODUCT_INCARNATION_MARKETING_PROOF_PACK_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_MARKETING_PROOF_PACK_REFUSED"


@dataclass(frozen=True)
class ProductIncarnationMarketingProofPackReceipt:
    pack_version: str
    status: str
    product_incarnation_gauntlet_status: str
    marketing_claim_tier: str
    starter_incarnation_marketing_language_authorized: bool
    adaptive_claim_authorized: bool
    product_composition_claim_authorized: bool
    starter_implementation_claim_authorized: bool
    product_incarnation_development_evidence: bool
    candidate_products_loaded: int
    starter_incarnations_written: int
    manifests_written: int
    evidence_contracts_written: int
    acceptance_test_plans_written: int
    readmes_written: int
    static_scaffold_baseline_mean_score: float
    governed_incarnation_mean_score: float
    governed_incarnation_minus_static_effect: float
    minimum_governed_incarnation_score: float
    minimum_incarnation_development_effect: float
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    product_incarnation_claims_path: str
    product_incarnation_copy_path: str
    product_incarnation_gauntlet_sha256: str
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    autonomous_development_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbidden_claims() -> list[str]:
    return [
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees viable products, sales, revenue, or buyer outcomes",
        "DIO can autonomously develop, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO is enterprise-proven",
        "DIO has world-first status",
        "DIO may expand its own authority from starter-incarnation evidence",
        "DIO's internal starter-incarnation evidence equals external demand proof",
        "DIO can skip human review because a starter implementation scaffold scored well",
    ]


def _allowed_claims(gauntlet: dict) -> list[str]:
    return [
        "DIO produced T11 candidate evidence of governed product-incarnation development in an internal controlled gauntlet.",
        "DIO converted ATLAS-guided product compositions into governed starter product scaffolds under the tested harness.",
        (
            "The T11 gauntlet measured a governed-incarnation minus static-scaffold effect of "
            f"{float(gauntlet.get('governed_incarnation_minus_static_effect', 0.0)):.4f}."
        ),
        (
            "The static scaffold baseline scored "
            f"{float(gauntlet.get('static_scaffold_baseline_mean_score', 0.0)):.4f}; the governed incarnation route scored "
            f"{float(gauntlet.get('governed_incarnation_mean_score', 0.0)):.4f}."
        ),
        (
            "DIO wrote "
            f"{int(gauntlet.get('starter_incarnations_written', 0))} governed starter incarnation folders with manifests, evidence contracts, acceptance test plans, and READMEs."
        ),
        "The T11 evidence supports bounded language about governed starter-incarnation scaffolding, not autonomous development or product-market fit.",
        "The starter-incarnation signal preserved human gates and blocked AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _write_copy(path: Path, allowed: list[str], forbidden: list[str], gauntlet: dict) -> None:
    lines = [
        "# DIO Product Incarnation Marketing Proof Pack",
        "",
        "## Marketing-safe claim",
        "",
        (
            "DIO has internal controlled T11 candidate evidence of governed product-incarnation development: "
            "it converted ATLAS-guided domain product compositions into starter scaffolds with manifests, evidence "
            "contracts, acceptance test plans, READMEs, and human gates while preserving claim locks."
        ),
        "",
        "## Approved language",
        "",
    ]
    lines.extend(f"- {claim}" for claim in allowed)
    lines.extend([
        "",
        "## Positioning line",
        "",
        (
            "DIO does not merely compose product specifications. It can incarnate them into governed starter "
            "product scaffolds with proof contracts, acceptance paths, and permission boundaries."
        ),
        "",
        "## Proof numbers",
        "",
        f"- Static scaffold baseline: {float(gauntlet.get('static_scaffold_baseline_mean_score', 0.0)):.4f}",
        f"- Governed incarnation score: {float(gauntlet.get('governed_incarnation_mean_score', 0.0)):.4f}",
        f"- Governed incarnation minus static effect: {float(gauntlet.get('governed_incarnation_minus_static_effect', 0.0)):.4f}",
        f"- Starter incarnation folders written: {int(gauntlet.get('starter_incarnations_written', 0))}",
        f"- Manifests written: {int(gauntlet.get('manifests_written', 0))}",
        f"- Evidence contracts written: {int(gauntlet.get('evidence_contracts_written', 0))}",
        f"- Acceptance test plans written: {int(gauntlet.get('acceptance_test_plans_written', 0))}",
        f"- READMEs written: {int(gauntlet.get('readmes_written', 0))}",
        "",
        "## Required disclaimers",
        "",
        "- Internal controlled gauntlet evidence only.",
        "- Candidate starter-incarnation evidence, not external demand proof.",
        "- Not product-market fit.",
        "- Not commercial validation.",
        "- Not autonomous development.",
        "- Not AGI.",
        "- Not professional approval.",
        "- Not world-first status.",
        "- No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
        "",
        "## Forbidden claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in forbidden)
    path.write_text("\n".join(lines) + "\n")


def build_product_incarnation_marketing_proof_pack(
    *,
    product_incarnation_gauntlet_path: Path,
    output_dir: Path,
) -> ProductIncarnationMarketingProofPackReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    gauntlet = _load_json(product_incarnation_gauntlet_path)
    claims_path = output_dir / "product_incarnation_marketing_proof_claims.json"
    copy_path = output_dir / "product_incarnation_marketing_safe_copy.md"
    receipt_path = output_dir / "product_incarnation_marketing_proof_pack_receipt.json"

    ready = (
        gauntlet.get("status") == "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_DEVELOPMENT_GAUNTLET_READY"
        and gauntlet.get("product_incarnation_development_evidence") is True
        and gauntlet.get("starter_implementation_claim_authorized") is True
        and gauntlet.get("adaptive_claim_authorized") is True
        and gauntlet.get("commercial_validation_claim_authorized") is False
        and gauntlet.get("product_market_fit_claim_authorized") is False
        and gauntlet.get("autonomous_development_authorized") is False
        and gauntlet.get("authority_expansion_authorized") is False
    )

    forbidden = _forbidden_claims()
    allowed = _allowed_claims(gauntlet) if ready else []
    tier = "T11_MARKETING_SAFE_GOVERNED_PRODUCT_INCARNATION_DEVELOPMENT" if ready else "T0_NO_PRODUCT_INCARNATION_MARKETING_CLAIM"
    status = PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY_TOKEN if ready else PRODUCT_INCARNATION_MARKETING_PROOF_PACK_REFUSED_TOKEN

    claims = {
        "pack_version": PRODUCT_INCARNATION_MARKETING_PROOF_PACK_VERSION,
        "marketing_claim_tier": tier,
        "allowed_public_claims": allowed,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "Candidate starter-incarnation evidence, not external demand proof.",
            "No product-market fit, commercial validation, autonomous development, or authority expansion is authorized.",
        ],
        "claim_locks": {
            "commercial_validation_claim_authorized": False,
            "product_market_fit_claim_authorized": False,
            "autonomous_development_authorized": False,
            "professional_approval_claim_authorized": False,
            "publication_authorized": False,
            "spend_authorized": False,
            "fulfilment_authorized": False,
            "world_first_claim_authorized": False,
            "agi_claim_authorized": False,
            "autonomous_action_claim_authorized": False,
            "authority_expansion_authorized": False,
        },
        "proof_numbers": {
            "candidate_products_loaded": int(gauntlet.get("candidate_products_loaded", 0)),
            "starter_incarnations_written": int(gauntlet.get("starter_incarnations_written", 0)),
            "manifests_written": int(gauntlet.get("manifests_written", 0)),
            "evidence_contracts_written": int(gauntlet.get("evidence_contracts_written", 0)),
            "acceptance_test_plans_written": int(gauntlet.get("acceptance_test_plans_written", 0)),
            "readmes_written": int(gauntlet.get("readmes_written", 0)),
            "static_scaffold_baseline_mean_score": float(gauntlet.get("static_scaffold_baseline_mean_score", 0.0)),
            "governed_incarnation_mean_score": float(gauntlet.get("governed_incarnation_mean_score", 0.0)),
            "governed_incarnation_minus_static_effect": float(gauntlet.get("governed_incarnation_minus_static_effect", 0.0)),
        },
    }
    claims_path.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n")
    _write_copy(copy_path, allowed, forbidden, gauntlet)

    receipt = ProductIncarnationMarketingProofPackReceipt(
        pack_version=PRODUCT_INCARNATION_MARKETING_PROOF_PACK_VERSION,
        status=status,
        product_incarnation_gauntlet_status=str(gauntlet.get("status")),
        marketing_claim_tier=tier,
        starter_incarnation_marketing_language_authorized=ready,
        adaptive_claim_authorized=ready,
        product_composition_claim_authorized=bool(ready and gauntlet.get("product_composition_claim_authorized") is True),
        starter_implementation_claim_authorized=bool(ready and gauntlet.get("starter_implementation_claim_authorized") is True),
        product_incarnation_development_evidence=bool(ready and gauntlet.get("product_incarnation_development_evidence") is True),
        candidate_products_loaded=int(gauntlet.get("candidate_products_loaded", 0)) if ready else 0,
        starter_incarnations_written=int(gauntlet.get("starter_incarnations_written", 0)) if ready else 0,
        manifests_written=int(gauntlet.get("manifests_written", 0)) if ready else 0,
        evidence_contracts_written=int(gauntlet.get("evidence_contracts_written", 0)) if ready else 0,
        acceptance_test_plans_written=int(gauntlet.get("acceptance_test_plans_written", 0)) if ready else 0,
        readmes_written=int(gauntlet.get("readmes_written", 0)) if ready else 0,
        static_scaffold_baseline_mean_score=float(gauntlet.get("static_scaffold_baseline_mean_score", 0.0)) if ready else 0.0,
        governed_incarnation_mean_score=float(gauntlet.get("governed_incarnation_mean_score", 0.0)) if ready else 0.0,
        governed_incarnation_minus_static_effect=float(gauntlet.get("governed_incarnation_minus_static_effect", 0.0)) if ready else 0.0,
        minimum_governed_incarnation_score=float(gauntlet.get("minimum_governed_incarnation_score", 0.0)) if ready else 0.0,
        minimum_incarnation_development_effect=float(gauntlet.get("minimum_incarnation_development_effect", 0.0)) if ready else 0.0,
        allowed_public_claims_count=len(allowed),
        forbidden_public_claims_count=len(forbidden),
        product_incarnation_claims_path=str(claims_path),
        product_incarnation_copy_path=str(copy_path),
        product_incarnation_gauntlet_sha256=_sha256_path(product_incarnation_gauntlet_path),
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        autonomous_development_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This product-incarnation marketing proof pack converts T11 candidate starter-incarnation evidence "
            "into bounded, marketing-safe language. It authorizes only proof-bound public wording about internal "
            "controlled governed product-incarnation scaffolding and never authorizes commercial validation, "
            "product-market fit, autonomous development, professional approval, publication, spend, fulfilment, "
            "world-first status, AGI claims, autonomous consequential action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
