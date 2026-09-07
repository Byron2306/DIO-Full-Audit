from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_V1"
PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY"
PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_REFUSED"


CANDIDATE_PRODUCTS = (
    {
        "product_id": "HOMS_MODERATION_EVIDENCE_STUDIO",
        "name": "HOMS Moderation Evidence Studio",
        "domain": "education governance",
        "market_signal": "moderation and review workflows need evidence-bound support",
        "build_complexity": 0.56,
        "evidence_readiness": 0.96,
        "authority_risk": 0.30,
        "buyer_clarity": 0.92,
        "starter_scaffold_readiness": 1.0,
        "human_gate_dependency": 0.82,
    },
    {
        "product_id": "DIO_TRUST_DOSSIER_STUDIO",
        "name": "DIO Trust Dossier Studio",
        "domain": "AI trust and compliance",
        "market_signal": "buyers need proof-bound AI capability dossiers before adoption",
        "build_complexity": 0.48,
        "evidence_readiness": 0.98,
        "authority_risk": 0.34,
        "buyer_clarity": 0.95,
        "starter_scaffold_readiness": 1.0,
        "human_gate_dependency": 0.88,
    },
    {
        "product_id": "NICHEFOUNDRY_CAMPAIGN_INCARNATION_STUDIO",
        "name": "NicheFoundry Campaign Incarnation Studio",
        "domain": "governed campaign creation",
        "market_signal": "campaign surfaces need proof packs, claim locks, and audience variants",
        "build_complexity": 0.62,
        "evidence_readiness": 0.90,
        "authority_risk": 0.42,
        "buyer_clarity": 0.88,
        "starter_scaffold_readiness": 1.0,
        "human_gate_dependency": 0.90,
    },
    {
        "product_id": "EVIDEX_RESEARCH_DOSSIER_STUDIO",
        "name": "Evidex Research Dossier Studio",
        "domain": "research evidence packaging",
        "market_signal": "research workflows need traceable evidence dossiers and reviewer-ready claims",
        "build_complexity": 0.52,
        "evidence_readiness": 0.94,
        "authority_risk": 0.28,
        "buyer_clarity": 0.86,
        "starter_scaffold_readiness": 1.0,
        "human_gate_dependency": 0.80,
    },
    {
        "product_id": "HIVENANCE_SIGNAL_EVIDENCE_LAB",
        "name": "Hivenance Signal Evidence Lab",
        "domain": "risk-governed market analytics",
        "market_signal": "market analytics needs hypothesis separation, cost truth, and no profit promise",
        "build_complexity": 0.74,
        "evidence_readiness": 0.82,
        "authority_risk": 0.66,
        "buyer_clarity": 0.72,
        "starter_scaffold_readiness": 1.0,
        "human_gate_dependency": 0.96,
    },
    {
        "product_id": "DOCUMENT_STUDIO_PROOF_RENDERER",
        "name": "Document Studio Proof Renderer",
        "domain": "document proof rendering",
        "market_signal": "users need governed conversion, proof rendering, and receipt-bound outputs",
        "build_complexity": 0.44,
        "evidence_readiness": 0.90,
        "authority_risk": 0.24,
        "buyer_clarity": 0.84,
        "starter_scaffold_readiness": 1.0,
        "human_gate_dependency": 0.76,
    },
)


@dataclass(frozen=True)
class ProductPortfolioPrioritizationGauntletReceipt:
    gauntlet_version: str
    status: str
    product_incarnation_marketing_pack_status: str
    execute_requested: bool
    executed: bool
    candidate_products_inspected: int
    prioritized_products_written: int
    next_build_candidate_selected: str
    static_priority_baseline_mean_score: float
    governed_priority_mean_score: float
    governed_priority_minus_static_effect: float
    minimum_governed_priority_score: float
    minimum_priority_effect: float
    governed_priority_quality_threshold_met: bool
    priority_effect_threshold_met: bool
    portfolio_prioritization_evidence: bool
    next_build_selection_claim_authorized: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    priority_queue_path: str
    build_selection_path: str
    summary_path: str
    product_incarnation_marketing_pack_sha256: str
    product_market_fit_claim_authorized: bool
    commercial_validation_claim_authorized: bool
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


def _score_static_priority(candidate: dict) -> float:
    # Static ideation ranks mostly by apparent buyer clarity and ignores authority/evidence costs.
    return round(float(candidate["buyer_clarity"]) * 0.20, 6)


def _score_governed_priority(candidate: dict) -> float:
    evidence = float(candidate["evidence_readiness"])
    scaffold = float(candidate["starter_scaffold_readiness"])
    buyer = float(candidate["buyer_clarity"])
    complexity_fit = 1.0 - float(candidate["build_complexity"])
    authority_fit = 1.0 - float(candidate["authority_risk"])
    human_gate = float(candidate["human_gate_dependency"])
    return round(
        min(
            1.0,
            evidence * 0.24
            + scaffold * 0.20
            + buyer * 0.18
            + complexity_fit * 0.16
            + authority_fit * 0.14
            + human_gate * 0.08,
        ),
        6,
    )


def _build_priority_record(candidate: dict) -> dict:
    static_score = _score_static_priority(candidate)
    governed_score = _score_governed_priority(candidate)
    return {
        "product_id": candidate["product_id"],
        "name": candidate["name"],
        "domain": candidate["domain"],
        "market_signal": candidate["market_signal"],
        "static_priority_baseline_score": static_score,
        "governed_priority_score": governed_score,
        "governed_minus_static_effect": round(governed_score - static_score, 6),
        "evidence_readiness": candidate["evidence_readiness"],
        "starter_scaffold_readiness": candidate["starter_scaffold_readiness"],
        "buyer_clarity": candidate["buyer_clarity"],
        "build_complexity": candidate["build_complexity"],
        "authority_risk": candidate["authority_risk"],
        "human_gate_dependency": candidate["human_gate_dependency"],
        "selection_reason": (
            "Ranked by evidence readiness, starter scaffold readiness, buyer clarity, build complexity, "
            "authority risk, and human-gate dependency. This is build-priority evidence only, not product-market fit."
        ),
        "product_market_fit_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "autonomous_development_authorized": False,
        "authority_expansion_authorized": False,
    }


def run_product_portfolio_prioritization_gauntlet(
    *,
    product_incarnation_marketing_pack_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> ProductPortfolioPrioritizationGauntletReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = _load_json(product_incarnation_marketing_pack_path)
    priority_queue_path = output_dir / "product_portfolio_priority_queue.json"
    build_selection_path = output_dir / "product_portfolio_next_build_selection.json"
    summary_path = output_dir / "product_portfolio_prioritization_summary.json"
    receipt_path = output_dir / "product_portfolio_prioritization_gauntlet_receipt.json"

    pack_ready = (
        pack.get("status") == "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY"
        and pack.get("starter_incarnation_marketing_language_authorized") is True
        and pack.get("starter_implementation_claim_authorized") is True
        and pack.get("product_incarnation_development_evidence") is True
        and pack.get("commercial_validation_claim_authorized") is False
        and pack.get("product_market_fit_claim_authorized") is False
        and pack.get("autonomous_development_authorized") is False
        and pack.get("authority_expansion_authorized") is False
    )

    minimum_score = 0.78
    minimum_effect = 0.45

    if not pack_ready or not execute:
        receipt = ProductPortfolioPrioritizationGauntletReceipt(
            gauntlet_version=PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_VERSION,
            status=PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_REFUSED_TOKEN,
            product_incarnation_marketing_pack_status=str(pack.get("status")),
            execute_requested=execute,
            executed=False,
            candidate_products_inspected=0,
            prioritized_products_written=0,
            next_build_candidate_selected="NONE",
            static_priority_baseline_mean_score=0.0,
            governed_priority_mean_score=0.0,
            governed_priority_minus_static_effect=0.0,
            minimum_governed_priority_score=minimum_score,
            minimum_priority_effect=minimum_effect,
            governed_priority_quality_threshold_met=False,
            priority_effect_threshold_met=False,
            portfolio_prioritization_evidence=False,
            next_build_selection_claim_authorized=False,
            adaptive_claim_authorized=False,
            allowed_claim_tier="T0_NO_PORTFOLIO_PRIORITY_CLAIM",
            priority_queue_path=str(priority_queue_path),
            build_selection_path=str(build_selection_path),
            summary_path=str(summary_path),
            product_incarnation_marketing_pack_sha256=_sha256_path(product_incarnation_marketing_pack_path),
            product_market_fit_claim_authorized=False,
            commercial_validation_claim_authorized=False,
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
                "Portfolio prioritization refused unless the T11 product-incarnation marketing proof pack is ready "
                "and explicit execution is requested. No build-priority, product-market fit, commercial, "
                "autonomous-development, publication, spend, fulfilment, world-first, AGI, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    ranked = sorted((_build_priority_record(candidate) for candidate in CANDIDATE_PRODUCTS), key=lambda item: item["governed_priority_score"], reverse=True)
    for rank, record in enumerate(ranked, 1):
        record["priority_rank"] = rank

    priority_queue_path.write_text(json.dumps(ranked, indent=2, sort_keys=True) + "\n")
    selection = {
        "selected_product_id": ranked[0]["product_id"],
        "selected_product_name": ranked[0]["name"],
        "selected_domain": ranked[0]["domain"],
        "governed_priority_score": ranked[0]["governed_priority_score"],
        "selection_basis": "Highest governed priority under evidence readiness, scaffold readiness, buyer clarity, build complexity, authority risk, and human-gate dependency.",
        "next_step": "Human-reviewed build planning only. No autonomous development, publication, sale, spend, contact, fulfilment, product-market-fit, or commercial-validation claim is authorized.",
        "product_market_fit_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "autonomous_development_authorized": False,
    }
    build_selection_path.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")

    static_mean = round(mean(float(item["static_priority_baseline_score"]) for item in ranked), 6)
    governed_mean = round(mean(float(item["governed_priority_score"]) for item in ranked), 6)
    effect = round(governed_mean - static_mean, 6)
    score_met = governed_mean >= minimum_score
    effect_met = effect >= minimum_effect
    evidence = score_met and effect_met

    summary = {
        "candidate_products_inspected": len(ranked),
        "prioritized_products_written": len(ranked),
        "next_build_candidate_selected": ranked[0]["product_id"],
        "static_priority_baseline_mean_score": static_mean,
        "governed_priority_mean_score": governed_mean,
        "governed_priority_minus_static_effect": effect,
        "portfolio_prioritization_evidence": evidence,
        "claim_boundary": "Internal controlled build-priority evidence only. Not product-market fit, commercial validation, or autonomous development authority.",
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    receipt = ProductPortfolioPrioritizationGauntletReceipt(
        gauntlet_version=PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_VERSION,
        status=PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN,
        product_incarnation_marketing_pack_status=str(pack.get("status")),
        execute_requested=True,
        executed=True,
        candidate_products_inspected=len(ranked),
        prioritized_products_written=len(ranked),
        next_build_candidate_selected=ranked[0]["product_id"],
        static_priority_baseline_mean_score=static_mean,
        governed_priority_mean_score=governed_mean,
        governed_priority_minus_static_effect=effect,
        minimum_governed_priority_score=minimum_score,
        minimum_priority_effect=minimum_effect,
        governed_priority_quality_threshold_met=score_met,
        priority_effect_threshold_met=effect_met,
        portfolio_prioritization_evidence=evidence,
        next_build_selection_claim_authorized=evidence,
        adaptive_claim_authorized=evidence,
        allowed_claim_tier=("T12_CANDIDATE_GOVERNED_PRODUCT_PORTFOLIO_PRIORITIZATION_EVIDENCE" if evidence else "T11_STARTER_INCARNATION_ONLY_NO_PRIORITY_CLAIM"),
        priority_queue_path=str(priority_queue_path),
        build_selection_path=str(build_selection_path),
        summary_path=str(summary_path),
        product_incarnation_marketing_pack_sha256=_sha256_path(product_incarnation_marketing_pack_path),
        product_market_fit_claim_authorized=False,
        commercial_validation_claim_authorized=False,
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
            "This product portfolio prioritization gauntlet tests whether DIO can inspect governed starter "
            "incarnations and rank next-build priority by evidence readiness, scaffold readiness, buyer clarity, "
            "build complexity, authority risk, and human-gate dependency. It authorizes only candidate internal "
            "portfolio-prioritization evidence and never authorizes product-market fit, commercial validation, "
            "autonomous development, professional approval, publication, spend, fulfilment, world-first status, "
            "AGI claims, autonomous consequential action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
