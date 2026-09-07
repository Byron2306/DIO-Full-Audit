from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_V1"
PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY"
PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_REFUSED"


@dataclass(frozen=True)
class ProductPortfolioMarketingProofPackReceipt:
    pack_version: str
    status: str
    product_portfolio_prioritization_status: str
    marketing_claim_tier: str
    portfolio_prioritization_marketing_language_authorized: bool
    adaptive_claim_authorized: bool
    next_build_selection_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    autonomous_development_authorized: bool
    autonomous_action_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    authority_expansion_authorized: bool
    next_build_candidate_selected: str
    candidate_products_inspected: int
    prioritized_products_written: int
    static_priority_baseline_mean_score: float
    governed_priority_mean_score: float
    governed_priority_minus_static_effect: float
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    portfolio_claims_path: str
    portfolio_copy_path: str
    product_portfolio_prioritization_sha256: str
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
        "DIO can autonomously choose, build, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO is enterprise-proven",
        "DIO has world-first status",
        "DIO may expand its own authority from prioritization evidence",
        "DIO's internal prioritization evidence equals external demand proof",
        "DIO can skip human review because a product ranked first",
    ]


def _allowed_claims(priority: dict) -> list[str]:
    selected = str(priority.get("next_build_candidate_selected", "UNKNOWN"))
    return [
        "DIO produced T12 candidate evidence of governed product-portfolio prioritization in an internal controlled gauntlet.",
        "DIO inspected governed starter product incarnations and ranked next-build priority under the tested harness.",
        (
            "The T12 gauntlet measured a governed-priority minus static-priority effect of "
            f"{float(priority.get('governed_priority_minus_static_effect', 0.0)):.4f}."
        ),
        (
            "The static priority baseline scored "
            f"{float(priority.get('static_priority_baseline_mean_score', 0.0)):.4f}; the governed priority route scored "
            f"{float(priority.get('governed_priority_mean_score', 0.0)):.4f}."
        ),
        f"DIO selected {selected} as the governed next-build candidate under the internal prioritization rules.",
        "The T12 evidence supports bounded language about evidence-aware portfolio prioritization, not product-market fit or commercial validation.",
        "The prioritization signal preserved human gates and blocked AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _write_copy(path: Path, priority: dict, allowed: list[str], forbidden: list[str]) -> None:
    lines = [
        "# DIO Product Portfolio Prioritization Marketing Proof Pack",
        "",
        "## Marketing-safe claim",
        "",
        (
            "DIO has internal controlled T12 candidate evidence of governed product-portfolio prioritization: "
            "it inspected starter product incarnations, ranked next-build priority by evidence readiness, scaffold "
            "readiness, buyer clarity, build complexity, authority risk, and human-gate dependency, then selected a "
            "bounded next-build candidate while preserving claim locks."
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
        "DIO does not merely scaffold product incarnations. It can rank a governed product portfolio and select a next-build candidate through evidence, risk, readiness, and permission boundaries.",
        "",
        "## Proof numbers",
        "",
        f"- Static priority baseline: {float(priority.get('static_priority_baseline_mean_score', 0.0)):.4f}",
        f"- Governed priority score: {float(priority.get('governed_priority_mean_score', 0.0)):.4f}",
        f"- Governed priority minus static effect: {float(priority.get('governed_priority_minus_static_effect', 0.0)):.4f}",
        f"- Candidate products inspected: {int(priority.get('candidate_products_inspected', 0))}",
        f"- Prioritized products written: {int(priority.get('prioritized_products_written', 0))}",
        f"- Next-build candidate selected: {priority.get('next_build_candidate_selected', 'UNKNOWN')}",
        "",
        "## Required disclaimers",
        "",
        "- Internal controlled gauntlet evidence only.",
        "- Candidate portfolio-prioritization evidence, not external demand proof.",
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


def build_product_portfolio_marketing_proof_pack(
    *,
    product_portfolio_prioritization_path: Path,
    output_dir: Path,
) -> ProductPortfolioMarketingProofPackReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    priority = _load_json(product_portfolio_prioritization_path)
    claims_path = output_dir / "product_portfolio_marketing_proof_claims.json"
    copy_path = output_dir / "product_portfolio_marketing_safe_copy.md"
    receipt_path = output_dir / "product_portfolio_marketing_proof_pack_receipt.json"

    ready = (
        priority.get("status") == "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY"
        and priority.get("portfolio_prioritization_evidence") is True
        and priority.get("next_build_selection_claim_authorized") is True
        and priority.get("adaptive_claim_authorized") is True
        and priority.get("product_market_fit_claim_authorized") is False
        and priority.get("commercial_validation_claim_authorized") is False
        and priority.get("autonomous_development_authorized") is False
        and priority.get("authority_expansion_authorized") is False
    )

    forbidden = _forbidden_claims()
    allowed = _allowed_claims(priority) if ready else []
    tier = "T12_MARKETING_SAFE_GOVERNED_PRODUCT_PORTFOLIO_PRIORITIZATION" if ready else "T0_NO_PORTFOLIO_MARKETING_CLAIM"
    status = PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN if ready else PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_REFUSED_TOKEN

    claims = {
        "pack_version": PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_VERSION,
        "marketing_claim_tier": tier,
        "allowed_public_claims": allowed,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "T12 is candidate portfolio-prioritization evidence, not external demand proof.",
            "No product-market fit, commercial validation, autonomous development, world-first status, or authority expansion is authorized.",
        ],
        "proof_numbers": {
            "static_priority_baseline_mean_score": float(priority.get("static_priority_baseline_mean_score", 0.0)),
            "governed_priority_mean_score": float(priority.get("governed_priority_mean_score", 0.0)),
            "governed_priority_minus_static_effect": float(priority.get("governed_priority_minus_static_effect", 0.0)),
            "candidate_products_inspected": int(priority.get("candidate_products_inspected", 0)),
            "prioritized_products_written": int(priority.get("prioritized_products_written", 0)),
            "next_build_candidate_selected": str(priority.get("next_build_candidate_selected", "UNKNOWN")),
        },
        "claim_locks": {
            "product_market_fit_claim_authorized": False,
            "commercial_validation_claim_authorized": False,
            "autonomous_development_authorized": False,
            "autonomous_action_claim_authorized": False,
            "professional_approval_claim_authorized": False,
            "publication_authorized": False,
            "spend_authorized": False,
            "fulfilment_authorized": False,
            "world_first_claim_authorized": False,
            "agi_claim_authorized": False,
            "authority_expansion_authorized": False,
        },
    }
    claims_path.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n")
    if ready:
        _write_copy(copy_path, priority, allowed, forbidden)
    else:
        copy_path.write_text("# DIO Product Portfolio Prioritization Marketing Proof Pack\n\nMarketing proof language refused because the T12 receipt was not ready.\n")

    receipt = ProductPortfolioMarketingProofPackReceipt(
        pack_version=PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_VERSION,
        status=status,
        product_portfolio_prioritization_status=str(priority.get("status")),
        marketing_claim_tier=tier,
        portfolio_prioritization_marketing_language_authorized=ready,
        adaptive_claim_authorized=ready,
        next_build_selection_claim_authorized=ready,
        product_market_fit_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        autonomous_development_authorized=False,
        autonomous_action_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        authority_expansion_authorized=False,
        next_build_candidate_selected=str(priority.get("next_build_candidate_selected", "UNKNOWN")) if ready else "NONE",
        candidate_products_inspected=int(priority.get("candidate_products_inspected", 0)) if ready else 0,
        prioritized_products_written=int(priority.get("prioritized_products_written", 0)) if ready else 0,
        static_priority_baseline_mean_score=float(priority.get("static_priority_baseline_mean_score", 0.0)) if ready else 0.0,
        governed_priority_mean_score=float(priority.get("governed_priority_mean_score", 0.0)) if ready else 0.0,
        governed_priority_minus_static_effect=float(priority.get("governed_priority_minus_static_effect", 0.0)) if ready else 0.0,
        allowed_public_claims_count=len(allowed),
        forbidden_public_claims_count=len(forbidden),
        portfolio_claims_path=str(claims_path),
        portfolio_copy_path=str(copy_path),
        product_portfolio_prioritization_sha256=_sha256_path(product_portfolio_prioritization_path),
        boundary=(
            "This product portfolio marketing proof pack converts T12 candidate prioritization evidence into bounded, "
            "marketing-safe language. It authorizes only proof-bound public wording about internal controlled portfolio "
            "prioritization and next-build selection, and never authorizes product-market fit, commercial validation, "
            "autonomous development, professional approval, publication, spend, fulfilment, world-first status, AGI claims, "
            "autonomous consequential action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
