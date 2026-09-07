from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ATLAS_PRODUCT_MARKETING_PROOF_PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_ATLAS_PRODUCT_MARKETING_PROOF_PACK_V1"
ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY"
ATLAS_PRODUCT_MARKETING_PROOF_PACK_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ATLAS_PRODUCT_MARKETING_PROOF_PACK_REFUSED"


@dataclass(frozen=True)
class AtlasProductMarketingProofPackReceipt:
    pack_version: str
    status: str
    audience_morphology_gauntlet_status: str
    atlas_product_composition_status: str
    marketing_claim_tier: str
    product_evolution_marketing_language_authorized: bool
    adaptive_claim_authorized: bool
    product_composition_claim_authorized: bool
    higher_grade_product_composition_evidence: bool
    opportunities_processed: int
    atlas_work_maps_bound: int
    development_ready_specs_written: int
    static_product_baseline_mean_score: float
    adaptive_atlas_product_mean_score: float
    adaptive_atlas_minus_static_effect: float
    minimum_adaptive_atlas_product_score: float
    minimum_atlas_product_effect: float
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    atlas_product_claims_path: str
    atlas_product_copy_path: str
    audience_morphology_gauntlet_sha256: str
    atlas_product_composition_sha256: str
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
        "DIO may expand its own authority from product-composition evidence",
        "DIO's internal product-composition evidence equals external demand proof",
        "DIO can skip human review because a product spec scored well",
    ]


def _allowed_claims(morphology: dict, atlas: dict) -> list[str]:
    return [
        "DIO produced T10 candidate evidence of ATLAS-guided domain product composition in an internal controlled gauntlet.",
        "The ATLAS-guided route outperformed static product ideation under the tested harness.",
        (
            "The T10 gauntlet measured an adaptive ATLAS minus static product effect of "
            f"{float(atlas.get('adaptive_atlas_minus_static_effect', 0.0)):.4f}."
        ),
        (
            "The static product baseline scored "
            f"{float(atlas.get('static_product_baseline_mean_score', 0.0)):.4f}; the ATLAS-guided route scored "
            f"{float(atlas.get('adaptive_atlas_product_mean_score', 0.0)):.4f}."
        ),
        (
            "DIO composed "
            f"{int(atlas.get('development_ready_specs_written', 0))} higher-grade niche/domain product specifications from audience morphology, market signal pressure, domain topology, evidence spines, and authority gates."
        ),
        "The T10 evidence supports bounded language about adaptive product-composition orchestration, not product-market fit or commercial validation.",
        "The product-composition signal preserved human gates and blocked AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _write_copy(path: Path, allowed_claims: list[str], forbidden_claims: list[str], atlas: dict) -> None:
    lines = [
        "# DIO ATLAS Product Composition Marketing Proof Pack",
        "",
        "## Marketing-safe claim",
        "",
        (
            "DIO has internal controlled T10 candidate evidence of ATLAS-guided domain product composition: "
            "it used audience morphology, market signal pressure, domain topology, evidence spines, and authority gates "
            "to compose higher-grade niche/domain product specifications while preserving human gates and claim locks."
        ),
        "",
        "## Approved language",
        "",
    ]
    lines.extend(f"- {claim}" for claim in allowed_claims)
    lines.extend([
        "",
        "## Positioning line",
        "",
        (
            "DIO does not merely generate product ideas. It composes product incarnations from market pressure, "
            "audience morphology, ATLAS-style work topology, evidence requirements, and permission boundaries."
        ),
        "",
        "## Proof numbers",
        "",
        f"- Static product baseline: {float(atlas.get('static_product_baseline_mean_score', 0.0)):.4f}",
        f"- ATLAS-guided product score: {float(atlas.get('adaptive_atlas_product_mean_score', 0.0)):.4f}",
        f"- Adaptive ATLAS minus static effect: {float(atlas.get('adaptive_atlas_minus_static_effect', 0.0)):.4f}",
        f"- Product specs written: {int(atlas.get('development_ready_specs_written', 0))}",
        "",
        "## Required disclaimers",
        "",
        "- Internal controlled gauntlet evidence only.",
        "- Candidate product-composition evidence, not external demand proof.",
        "- Not product-market fit.",
        "- Not commercial validation.",
        "- Not AGI.",
        "- Not professional approval.",
        "- Not world-first status.",
        "- No autonomous development, external action, spending, publication, fulfilment, contact, or authority expansion.",
        "",
        "## Forbidden claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in forbidden_claims)
    path.write_text("\n".join(lines) + "\n")


def build_atlas_product_marketing_proof_pack(
    *,
    audience_morphology_gauntlet_path: Path,
    atlas_product_composition_path: Path,
    output_dir: Path,
) -> AtlasProductMarketingProofPackReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    morphology = _load_json(audience_morphology_gauntlet_path)
    atlas = _load_json(atlas_product_composition_path)

    claims_path = output_dir / "atlas_product_marketing_proof_claims.json"
    copy_path = output_dir / "atlas_product_marketing_safe_copy.md"
    receipt_path = output_dir / "atlas_product_marketing_proof_pack_receipt.json"

    morphology_ready = (
        morphology.get("status") == "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY"
        and morphology.get("audience_morphology_evidence") is True
        and morphology.get("adaptive_claim_authorized") is True
        and morphology.get("commercial_validation_claim_authorized") is False
        and morphology.get("world_first_claim_authorized") is False
        and morphology.get("agi_claim_authorized") is False
        and morphology.get("authority_expansion_authorized") is False
    )
    atlas_ready = (
        atlas.get("status") == "DIO_METAMORPHIC_ADAPTATION_ATLAS_GUIDED_PRODUCT_COMPOSITION_GAUNTLET_READY"
        and atlas.get("atlas_guided_product_composition_evidence") is True
        and atlas.get("higher_grade_product_composition_evidence") is True
        and atlas.get("product_composition_claim_authorized") is True
        and atlas.get("adaptive_claim_authorized") is True
        and atlas.get("commercial_validation_claim_authorized") is False
        and atlas.get("autonomous_development_authorized") is False
        and atlas.get("world_first_claim_authorized") is False
        and atlas.get("agi_claim_authorized") is False
        and atlas.get("authority_expansion_authorized") is False
    )
    ready = morphology_ready and atlas_ready

    forbidden_claims = _forbidden_claims()
    allowed_claims = _allowed_claims(morphology, atlas) if ready else []
    tier = "T10_MARKETING_SAFE_ATLAS_GUIDED_DOMAIN_PRODUCT_COMPOSITION" if ready else "T0_NO_PRODUCT_COMPOSITION_MARKETING_CLAIM"

    claims = {
        "pack_version": ATLAS_PRODUCT_MARKETING_PROOF_PACK_VERSION,
        "marketing_claim_tier": tier,
        "allowed_public_claims": allowed_claims,
        "forbidden_public_claims": forbidden_claims,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "T10 is candidate product-composition evidence, not product-market fit or commercial validation.",
            "No autonomous development, professional approval, world-first status, or authority expansion is authorized.",
        ],
        "proof_numbers": {
            "static_product_baseline_mean_score": float(atlas.get("static_product_baseline_mean_score", 0.0)),
            "adaptive_atlas_product_mean_score": float(atlas.get("adaptive_atlas_product_mean_score", 0.0)),
            "adaptive_atlas_minus_static_effect": float(atlas.get("adaptive_atlas_minus_static_effect", 0.0)),
            "opportunities_processed": int(atlas.get("opportunities_processed", 0)),
            "atlas_work_maps_bound": int(atlas.get("atlas_work_maps_bound", 0)),
            "development_ready_specs_written": int(atlas.get("development_ready_specs_written", 0)),
        },
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
    }
    claims_path.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n")
    if ready:
        _write_copy(copy_path, allowed_claims, forbidden_claims, atlas)
    else:
        copy_path.write_text(
            "# DIO ATLAS Product Composition Marketing Proof Pack\n\n"
            "Marketing proof language refused because the required T9/T10 evidence receipts were not ready.\n"
        )

    receipt = AtlasProductMarketingProofPackReceipt(
        pack_version=ATLAS_PRODUCT_MARKETING_PROOF_PACK_VERSION,
        status=ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN if ready else ATLAS_PRODUCT_MARKETING_PROOF_PACK_REFUSED_TOKEN,
        audience_morphology_gauntlet_status=str(morphology.get("status")),
        atlas_product_composition_status=str(atlas.get("status")),
        marketing_claim_tier=tier,
        product_evolution_marketing_language_authorized=ready,
        adaptive_claim_authorized=ready,
        product_composition_claim_authorized=ready,
        higher_grade_product_composition_evidence=bool(ready and atlas.get("higher_grade_product_composition_evidence") is True),
        opportunities_processed=int(atlas.get("opportunities_processed", 0)) if ready else 0,
        atlas_work_maps_bound=int(atlas.get("atlas_work_maps_bound", 0)) if ready else 0,
        development_ready_specs_written=int(atlas.get("development_ready_specs_written", 0)) if ready else 0,
        static_product_baseline_mean_score=float(atlas.get("static_product_baseline_mean_score", 0.0)) if ready else 0.0,
        adaptive_atlas_product_mean_score=float(atlas.get("adaptive_atlas_product_mean_score", 0.0)) if ready else 0.0,
        adaptive_atlas_minus_static_effect=float(atlas.get("adaptive_atlas_minus_static_effect", 0.0)) if ready else 0.0,
        minimum_adaptive_atlas_product_score=float(atlas.get("minimum_adaptive_atlas_product_score", 0.0)) if ready else 0.0,
        minimum_atlas_product_effect=float(atlas.get("minimum_atlas_product_effect", 0.0)) if ready else 0.0,
        allowed_public_claims_count=len(allowed_claims),
        forbidden_public_claims_count=len(forbidden_claims),
        atlas_product_claims_path=str(claims_path),
        atlas_product_copy_path=str(copy_path),
        audience_morphology_gauntlet_sha256=_sha256_path(audience_morphology_gauntlet_path),
        atlas_product_composition_sha256=_sha256_path(atlas_product_composition_path),
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
            "This ATLAS product marketing proof pack converts T10 candidate product-composition evidence into bounded, "
            "marketing-safe language. It authorizes only proof-bound public wording about internal controlled ATLAS-guided "
            "domain product composition and never authorizes commercial validation, product-market fit, autonomous development, "
            "professional approval, publication, spend, fulfilment, world-first status, AGI claims, autonomous consequential action, "
            "or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
