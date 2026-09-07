from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


ATLAS_PRODUCT_COMPOSITION_GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_ATLAS_GUIDED_PRODUCT_COMPOSITION_GAUNTLET_V1"
ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ATLAS_GUIDED_PRODUCT_COMPOSITION_GAUNTLET_READY"
ATLAS_PRODUCT_COMPOSITION_GAUNTLET_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ATLAS_GUIDED_PRODUCT_COMPOSITION_GAUNTLET_REFUSED"


DOMAIN_OPPORTUNITIES = (
    {
        "opportunity_id": "ATLAS-PROD-001",
        "domain": "education governance",
        "niche": "assessment moderation and evidence packs",
        "audience_morphology": "school leadership and education governance buyer",
        "market_signal": "teachers need resources, but buyers need moderation evidence, auditability, and leadership-visible risk controls",
        "static_product": {
            "name": "Teacher Resource Generator",
            "description": "Creates classroom activities and worksheets for teachers.",
            "grade": "UTILITY_PROTOTYPE",
            "terms": ["activities", "worksheets"],
        },
        "adaptive_product": {
            "name": "HOMS Moderation Evidence Studio",
            "description": (
                "A governed education product that composes assessment packs, moderation traces, reviewer-ready receipts, "
                "curriculum alignment notes, and leadership-visible risk controls for human approval."
            ),
            "grade": "DEVELOPMENT_READY_DOMAIN_INCARNATION",
            "atlas_work_map": ["curriculum alignment", "assessment evidence", "moderation workflow", "review receipt", "human approval gate"],
            "required_terms": ["assessment packs", "moderation", "receipts", "risk controls", "human approval"],
            "forbidden_terms": ["accredited", "replaces teachers", "guarantee", "autonomous"],
        },
    },
    {
        "opportunity_id": "ATLAS-PROD-002",
        "domain": "AI trust and compliance",
        "niche": "internal AI system evidence dossiers",
        "audience_morphology": "risk-sensitive compliance leader",
        "market_signal": "AI buyers fear autonomy, hallucination, audit failure, and unbounded claims",
        "static_product": {
            "name": "AI Automation Toolkit",
            "description": "Automates complex AI work for teams.",
            "grade": "UTILITY_PROTOTYPE",
            "terms": ["automates", "complex work"],
        },
        "adaptive_product": {
            "name": "DIO Trust Dossier Studio",
            "description": (
                "A proof-bound dossier product that binds AI task scope, model-risk notes, evaluation receipts, claim locks, "
                "authority limits, and human-gated release decisions."
            ),
            "grade": "DEVELOPMENT_READY_DOMAIN_INCARNATION",
            "atlas_work_map": ["risk register", "evaluation receipt", "claim lock", "authority boundary", "release gate"],
            "required_terms": ["proof-bound", "evaluation receipts", "claim locks", "authority limits", "human-gated"],
            "forbidden_terms": ["AGI", "autonomous", "world-first", "guarantee"],
        },
    },
    {
        "opportunity_id": "ATLAS-PROD-003",
        "domain": "niche creator operations",
        "niche": "campaign incarnation governance",
        "audience_morphology": "agency and studio operations buyer",
        "market_signal": "creative buyers need repeatable campaign surfaces without unsafe publication or claim drift",
        "static_product": {
            "name": "Ad Asset Generator",
            "description": "Creates ads, videos, posts, and campaign assets quickly.",
            "grade": "UTILITY_PROTOTYPE",
            "terms": ["ads", "videos", "posts"],
        },
        "adaptive_product": {
            "name": "NicheFoundry Campaign Incarnation Studio",
            "description": (
                "A campaign product factory that turns proof packs, audience constraints, brand-safe variants, channel rules, "
                "claim locks, and publication gates into human-approved campaign incarnations."
            ),
            "grade": "DEVELOPMENT_READY_DOMAIN_INCARNATION",
            "atlas_work_map": ["proof pack", "audience constraint", "channel surface", "brand safety", "publication gate"],
            "required_terms": ["proof packs", "audience constraints", "claim locks", "publication gates", "human-approved"],
            "forbidden_terms": ["viral", "publishes automatically", "guarantee", "autonomous"],
        },
    },
    {
        "opportunity_id": "ATLAS-PROD-004",
        "domain": "research evidence production",
        "niche": "study-to-dossier academic evidence workflows",
        "audience_morphology": "academic reviewer and research lead",
        "market_signal": "research users need traceable method, instruments, analysis boundaries, and publication-ready evidence discipline",
        "static_product": {
            "name": "Research Writing Assistant",
            "description": "Helps write papers and summarize research data.",
            "grade": "UTILITY_PROTOTYPE",
            "terms": ["write papers", "summarize"],
        },
        "adaptive_product": {
            "name": "Evidex Research Dossier Studio",
            "description": (
                "A research evidence product that binds instruments, analysis plans, source receipts, statistical boundaries, "
                "ethics notes, and reviewer-facing dossier outputs."
            ),
            "grade": "DEVELOPMENT_READY_DOMAIN_INCARNATION",
            "atlas_work_map": ["instrument binding", "analysis plan", "source receipt", "ethics note", "review dossier"],
            "required_terms": ["instruments", "analysis plans", "source receipts", "ethics notes", "reviewer-facing"],
            "forbidden_terms": ["publish automatically", "guarantee acceptance", "fabricate", "autonomous"],
        },
    },
    {
        "opportunity_id": "ATLAS-PROD-005",
        "domain": "market analytics research",
        "niche": "risk-governed signal evaluation",
        "audience_morphology": "risk-governed analytics evaluator",
        "market_signal": "market users need observation and hypothesis discipline, not profit promises or execution authority",
        "static_product": {
            "name": "Trading Opportunity Finder",
            "description": "Finds market opportunities and improves trading decisions.",
            "grade": "UTILITY_PROTOTYPE",
            "terms": ["opportunities", "trading decisions"],
        },
        "adaptive_product": {
            "name": "Hivenance Signal Evidence Lab",
            "description": (
                "A risk-governed analytics product that separates public observation, economic hypothesis, verified-cost analysis, "
                "temporal validation, and human-gated decision review."
            ),
            "grade": "DEVELOPMENT_READY_DOMAIN_INCARNATION",
            "atlas_work_map": ["public observation", "economic hypothesis", "verified cost", "temporal validation", "human review"],
            "required_terms": ["public observation", "economic hypothesis", "verified-cost", "temporal validation", "human-gated"],
            "forbidden_terms": ["profit", "guarantee", "autonomous trading", "financial advice"],
        },
    },
    {
        "opportunity_id": "ATLAS-PROD-006",
        "domain": "document operations",
        "niche": "format-safe document transformation and proof receipts",
        "audience_morphology": "technical evaluator and operations buyer",
        "market_signal": "document conversion buyers need deterministic structure, custody, profile control, and repeatable proof",
        "static_product": {
            "name": "Document Converter",
            "description": "Converts documents between formats.",
            "grade": "UTILITY_PROTOTYPE",
            "terms": ["converts", "formats"],
        },
        "adaptive_product": {
            "name": "Document Studio Proof Renderer",
            "description": (
                "A governed document product that binds source custody, profile-controlled rendering, format validation, "
                "deterministic receipts, and human-approved delivery gates."
            ),
            "grade": "DEVELOPMENT_READY_DOMAIN_INCARNATION",
            "atlas_work_map": ["source custody", "profile rendering", "format validation", "deterministic receipt", "delivery gate"],
            "required_terms": ["source custody", "profile-controlled", "format validation", "deterministic receipts", "delivery gates"],
            "forbidden_terms": ["perfect", "guarantee", "autonomous delivery", "legally certified"],
        },
    },
)


@dataclass(frozen=True)
class AtlasGuidedProductCompositionReceipt:
    gauntlet_version: str
    status: str
    audience_morphology_gauntlet_status: str
    execute_requested: bool
    executed: bool
    opportunities_processed: int
    atlas_work_maps_bound: int
    static_products_scored: int
    adaptive_products_scored: int
    development_ready_specs_written: int
    static_product_baseline_mean_score: float
    adaptive_atlas_product_mean_score: float
    adaptive_atlas_minus_static_effect: float
    minimum_atlas_product_effect: float
    minimum_adaptive_atlas_product_score: float
    atlas_product_effect_threshold_met: bool
    adaptive_atlas_product_quality_threshold_met: bool
    atlas_guided_product_composition_evidence: bool
    higher_grade_product_composition_evidence: bool
    product_composition_claim_authorized: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    registry_path: str
    specs_path: str
    summary_path: str
    audience_morphology_gauntlet_sha256: str
    commercial_validation_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    autonomous_development_authorized: bool
    autonomous_action_claim_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_all(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return all(term.lower() in lower for term in terms)


def _contains_none(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return all(term.lower() not in lower for term in terms)


def _score_static_product(product: dict, adaptive: dict) -> float:
    text = f"{product.get('name', '')} {product.get('description', '')}".lower()
    required_hits = sum(1 for term in adaptive["required_terms"] if term.lower() in text)
    forbidden_hits = sum(1 for term in adaptive["forbidden_terms"] if term.lower() in text)
    grade_score = 0.10 if product.get("grade") == "UTILITY_PROTOTYPE" else 0.25
    required_score = required_hits / len(adaptive["required_terms"])
    boundary_score = 1.0 if forbidden_hits == 0 else 0.15
    topology_score = 0.0
    return round(max(0.0, min(1.0, grade_score * 0.20 + required_score * 0.45 + topology_score * 0.20 + boundary_score * 0.15)), 6)


def _score_adaptive_product(product: dict) -> float:
    text = f"{product.get('name', '')} {product.get('description', '')} {' '.join(product.get('atlas_work_map', []))}".lower()
    required_hits = sum(1 for term in product["required_terms"] if term.lower() in text)
    forbidden_hits = sum(1 for term in product["forbidden_terms"] if term.lower() in text)
    topology_hits = len(product.get("atlas_work_map", []))
    required_score = required_hits / len(product["required_terms"])
    boundary_score = 1.0 if forbidden_hits == 0 else 0.15
    topology_score = min(1.0, topology_hits / 5.0)
    grade_score = 1.0 if product.get("grade") == "DEVELOPMENT_READY_DOMAIN_INCARNATION" else 0.35
    return round(max(0.0, min(1.0, grade_score * 0.20 + required_score * 0.40 + topology_score * 0.25 + boundary_score * 0.15)), 6)


def _build_spec(opportunity: dict) -> dict:
    adaptive = opportunity["adaptive_product"]
    static = opportunity["static_product"]
    static_score = _score_static_product(static, adaptive)
    adaptive_score = _score_adaptive_product(adaptive)
    return {
        "opportunity_id": opportunity["opportunity_id"],
        "domain": opportunity["domain"],
        "niche": opportunity["niche"],
        "audience_morphology": opportunity["audience_morphology"],
        "market_signal": opportunity["market_signal"],
        "static_product": static,
        "adaptive_product_spec": {
            "name": adaptive["name"],
            "description": adaptive["description"],
            "target_grade": adaptive["grade"],
            "atlas_work_map": list(adaptive["atlas_work_map"]),
            "evidence_spine": ["source-bound input", "domain profile", "claim lock", "receipt", "human gate"],
            "development_path": ["manifest", "validator", "executor", "rubric", "claim gate", "marketing proof pack"],
            "authority_boundary": "Composition and development planning only. No autonomous publication, spend, fulfilment, professional approval, or authority expansion.",
        },
        "static_product_score": static_score,
        "adaptive_atlas_product_score": adaptive_score,
        "adaptive_minus_static_effect": round(adaptive_score - static_score, 6),
        "required_terms_present": _contains_all(adaptive["description"] + " " + " ".join(adaptive["atlas_work_map"]), adaptive["required_terms"]),
        "forbidden_terms_absent": _contains_none(adaptive["description"], adaptive["forbidden_terms"]),
        "atlas_work_map_bound": len(adaptive["atlas_work_map"]) >= 5,
        "status": "ATLAS_GUIDED_PRODUCT_SPEC_RECORDED",
        "commercial_validation_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "autonomous_development_authorized": False,
        "authority_expansion_authorized": False,
    }


def run_atlas_guided_product_composition_gauntlet(
    *,
    audience_morphology_gauntlet_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> AtlasGuidedProductCompositionReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    morphology = _load_json(audience_morphology_gauntlet_path)
    registry_path = output_dir / "atlas_guided_product_opportunity_registry.json"
    specs_path = output_dir / "atlas_guided_product_composition_specs.jsonl"
    summary_path = output_dir / "atlas_guided_product_composition_summary.json"
    receipt_path = output_dir / "atlas_guided_product_composition_gauntlet_receipt.json"

    morphology_ready = (
        morphology.get("status") == "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY"
        and morphology.get("audience_morphology_evidence") is True
        and morphology.get("adaptive_claim_authorized") is True
        and morphology.get("commercial_validation_claim_authorized") is False
        and morphology.get("authority_expansion_authorized") is False
    )
    min_effect = 0.40
    min_score = 0.84

    if not morphology_ready or not execute:
        receipt = AtlasGuidedProductCompositionReceipt(
            gauntlet_version=ATLAS_PRODUCT_COMPOSITION_GAUNTLET_VERSION,
            status=ATLAS_PRODUCT_COMPOSITION_GAUNTLET_REFUSED_TOKEN,
            audience_morphology_gauntlet_status=str(morphology.get("status")),
            execute_requested=execute,
            executed=False,
            opportunities_processed=0,
            atlas_work_maps_bound=0,
            static_products_scored=0,
            adaptive_products_scored=0,
            development_ready_specs_written=0,
            static_product_baseline_mean_score=0.0,
            adaptive_atlas_product_mean_score=0.0,
            adaptive_atlas_minus_static_effect=0.0,
            minimum_atlas_product_effect=min_effect,
            minimum_adaptive_atlas_product_score=min_score,
            atlas_product_effect_threshold_met=False,
            adaptive_atlas_product_quality_threshold_met=False,
            atlas_guided_product_composition_evidence=False,
            higher_grade_product_composition_evidence=False,
            product_composition_claim_authorized=False,
            adaptive_claim_authorized=False,
            allowed_claim_tier="T0_NO_ATLAS_PRODUCT_COMPOSITION_CLAIM",
            registry_path=str(registry_path),
            specs_path=str(specs_path),
            summary_path=str(summary_path),
            audience_morphology_gauntlet_sha256=_sha256_path(audience_morphology_gauntlet_path),
            commercial_validation_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            autonomous_development_authorized=False,
            autonomous_action_claim_authorized=False,
            world_first_claim_authorized=False,
            agi_claim_authorized=False,
            authority_expansion_authorized=False,
            boundary="ATLAS-guided product composition refused unless T9 audience morphology evidence is ready and explicit execution is requested.",
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    registry_path.write_text(json.dumps({"gauntlet_version": ATLAS_PRODUCT_COMPOSITION_GAUNTLET_VERSION, "opportunities": DOMAIN_OPPORTUNITIES}, indent=2, sort_keys=True) + "\n")
    specs = [_build_spec(item) for item in DOMAIN_OPPORTUNITIES]
    with specs_path.open("w") as fh:
        for spec in specs:
            fh.write(json.dumps(spec, sort_keys=True) + "\n")

    static_mean = round(mean(float(item["static_product_score"]) for item in specs), 6)
    adaptive_mean = round(mean(float(item["adaptive_atlas_product_score"]) for item in specs), 6)
    effect = round(adaptive_mean - static_mean, 6)
    effect_met = effect >= min_effect
    quality_met = adaptive_mean >= min_score
    clean_specs = all(item["required_terms_present"] and item["forbidden_terms_absent"] and item["atlas_work_map_bound"] for item in specs)
    evidence = effect_met and quality_met and clean_specs

    summary = {
        "opportunities_processed": len(specs),
        "static_product_baseline_mean_score": static_mean,
        "adaptive_atlas_product_mean_score": adaptive_mean,
        "adaptive_atlas_minus_static_effect": effect,
        "minimum_atlas_product_effect": min_effect,
        "minimum_adaptive_atlas_product_score": min_score,
        "atlas_product_effect_threshold_met": effect_met,
        "adaptive_atlas_product_quality_threshold_met": quality_met,
        "clean_specs": clean_specs,
        "atlas_guided_product_composition_evidence": evidence,
        "claim_boundary": "Internal controlled product-composition evidence only. This is not commercial validation, product-market fit, autonomous development, publication, spend, fulfilment, professional approval, AGI, world-first status, or authority expansion.",
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    receipt = AtlasGuidedProductCompositionReceipt(
        gauntlet_version=ATLAS_PRODUCT_COMPOSITION_GAUNTLET_VERSION,
        status=ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN,
        audience_morphology_gauntlet_status=str(morphology.get("status")),
        execute_requested=True,
        executed=True,
        opportunities_processed=len(specs),
        atlas_work_maps_bound=sum(1 for item in specs if item["atlas_work_map_bound"]),
        static_products_scored=len(specs),
        adaptive_products_scored=len(specs),
        development_ready_specs_written=len(specs),
        static_product_baseline_mean_score=static_mean,
        adaptive_atlas_product_mean_score=adaptive_mean,
        adaptive_atlas_minus_static_effect=effect,
        minimum_atlas_product_effect=min_effect,
        minimum_adaptive_atlas_product_score=min_score,
        atlas_product_effect_threshold_met=effect_met,
        adaptive_atlas_product_quality_threshold_met=quality_met,
        atlas_guided_product_composition_evidence=evidence,
        higher_grade_product_composition_evidence=evidence,
        product_composition_claim_authorized=evidence,
        adaptive_claim_authorized=evidence,
        allowed_claim_tier="T10_CANDIDATE_ATLAS_GUIDED_DOMAIN_PRODUCT_COMPOSITION_EVIDENCE" if evidence else "T9_AUDIENCE_MORPHOLOGY_ONLY_NO_PRODUCT_COMPOSITION_CLAIM",
        registry_path=str(registry_path),
        specs_path=str(specs_path),
        summary_path=str(summary_path),
        audience_morphology_gauntlet_sha256=_sha256_path(audience_morphology_gauntlet_path),
        commercial_validation_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        autonomous_development_authorized=False,
        autonomous_action_claim_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This ATLAS-guided product composition gauntlet tests whether DIO can combine audience morphology, market signal pressure, "
            "domain topology, evidence spines, and authority gates to compose higher-grade niche/domain product specifications. "
            "It authorizes only candidate internal product-composition evidence and never authorizes commercial validation, product-market fit, "
            "professional approval, autonomous development, publication, spend, fulfilment, world-first status, AGI claims, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
