from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_V1"
)
AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY"
)
AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_REFUSED_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_REFUSED"
)


AUDIENCE_MORPHOLOGIES = (
    {
        "morphology_id": "MORPH-001",
        "name": "risk_sensitive_compliance_gatekeeper",
        "market_signal": "autonomy wording increases legal review friction",
        "proof_appetite": "receipt_first",
        "risk_sensitivity": "very_high",
        "jargon_tolerance": "medium",
        "cta_permission": "review_receipts_only",
        "static_language": "DIO is an autonomous AI platform that can automate complex business work.",
        "recomposed_language": (
            "DIO is receipt-first orchestration infrastructure for governed AI work. It keeps authority limits, "
            "human review, risk controls, and claim boundaries visible before consequential action."
        ),
        "required_terms": ["receipt-first", "authority limits", "human review", "risk controls"],
        "forbidden_terms": ["autonomous", "guarantee", "world-first", "agi", "automate complex"],
    },
    {
        "morphology_id": "MORPH-002",
        "name": "time_poor_executive_sponsor",
        "market_signal": "executives need strategic compression without technical fog",
        "proof_appetite": "executive_summary",
        "risk_sensitivity": "high",
        "jargon_tolerance": "low",
        "cta_permission": "request_a_briefing",
        "static_language": "DIO coordinates organs, manifests, semantic gates, receipts, and typed authority surfaces.",
        "recomposed_language": (
            "DIO gives leaders a governed command layer for AI-enabled work: faster assessment, clearer proof, "
            "safer handoffs, and human-gated decisions without technical fog."
        ),
        "required_terms": ["leaders", "governed command layer", "clearer proof", "human-gated decisions"],
        "forbidden_terms": ["guarantee", "world-first", "agi", "fully autonomous", "replaces teams"],
    },
    {
        "morphology_id": "MORPH-003",
        "name": "technical_evaluator",
        "market_signal": "technical evaluators distrust vision without reproducible traces",
        "proof_appetite": "hashes_tests_and_receipts",
        "risk_sensitivity": "high",
        "jargon_tolerance": "high",
        "cta_permission": "inspect_the_receipt_chain",
        "static_language": "DIO is a breakthrough intelligence organism for product and market execution.",
        "recomposed_language": (
            "DIO exposes test-bound claims, source-bound receipts, hash-linked artifacts, branch-scoped runners, "
            "and authority locks so evaluators can inspect the proof chain."
        ),
        "required_terms": ["test-bound", "source-bound receipts", "hash-linked", "authority locks"],
        "forbidden_terms": ["breakthrough", "guarantee", "production-proven", "world-first", "agi"],
    },
    {
        "morphology_id": "MORPH-004",
        "name": "academic_reviewer",
        "market_signal": "reviewers require bounded claims, method traceability, and limitations",
        "proof_appetite": "method_and_limitations",
        "risk_sensitivity": "very_high",
        "jargon_tolerance": "medium",
        "cta_permission": "read_method_note",
        "static_language": "DIO proves adaptive intelligence and can transform work across industries.",
        "recomposed_language": (
            "DIO reports bounded internal evidence with explicit method traceability, limitations, comparison arms, "
            "and non-authority claims for scholarly review."
        ),
        "required_terms": ["bounded internal evidence", "method traceability", "limitations", "comparison arms"],
        "forbidden_terms": ["proves adaptive intelligence", "guarantee", "world-first", "agi", "transform work"],
    },
    {
        "morphology_id": "MORPH-005",
        "name": "teacher_practitioner",
        "market_signal": "teachers need practical value without replacement anxiety",
        "proof_appetite": "examples_and_guardrails",
        "risk_sensitivity": "medium",
        "jargon_tolerance": "low",
        "cta_permission": "try_a_sample_pack",
        "static_language": "DIO can replace repetitive teaching preparation with AI-generated resources.",
        "recomposed_language": (
            "DIO helps teachers prepare evidence-bound learning assets, examples, rubrics, and support materials "
            "while preserving teacher judgement and classroom context."
        ),
        "required_terms": ["teachers", "evidence-bound", "rubrics", "teacher judgement"],
        "forbidden_terms": ["replace", "guarantee", "accredited", "autonomous", "fully automated"],
    },
    {
        "morphology_id": "MORPH-006",
        "name": "agency_operations_buyer",
        "market_signal": "agencies need scalable campaign variants with brand and claim control",
        "proof_appetite": "workflow_and_approval",
        "risk_sensitivity": "high",
        "jargon_tolerance": "medium",
        "cta_permission": "review_campaign_surface",
        "static_language": "DIO can generate viral ads, posts, videos, and campaign assets automatically.",
        "recomposed_language": (
            "DIO composes campaign variants from proof packs, audience constraints, brand controls, claim locks, "
            "and human-approved publication gates."
        ),
        "required_terms": ["campaign variants", "proof packs", "brand controls", "claim locks"],
        "forbidden_terms": ["viral", "automatically", "guarantee", "autonomous", "publish without review"],
    },
    {
        "morphology_id": "MORPH-007",
        "name": "risk_governed_market_analytics_evaluator",
        "market_signal": "profit language is unsafe without verified external performance",
        "proof_appetite": "risk_and_observation_boundary",
        "risk_sensitivity": "very_high",
        "jargon_tolerance": "medium",
        "cta_permission": "inspect_research_boundary",
        "static_language": "DIO improves trading decisions and finds profitable market opportunities.",
        "recomposed_language": (
            "DIO separates public observation, economic hypothesis, verified-cost analysis, and human-gated review, "
            "framing market outputs as bounded research evidence."
        ),
        "required_terms": ["public observation", "economic hypothesis", "verified-cost", "bounded research evidence"],
        "forbidden_terms": ["profit", "profitable", "trading decisions", "guarantee", "autonomous"],
    },
    {
        "morphology_id": "MORPH-008",
        "name": "founder_operator",
        "market_signal": "founders need opportunity language connected to execution constraints",
        "proof_appetite": "roadmap_and_gate",
        "risk_sensitivity": "medium",
        "jargon_tolerance": "medium",
        "cta_permission": "choose_a_reference_workflow",
        "static_language": "DIO can turn any idea into a launch-ready product and sell it.",
        "recomposed_language": (
            "DIO turns product ideas into governed reference workflows with scoped build steps, evidence receipts, "
            "market-signal checks, and launch claims held behind human gates."
        ),
        "required_terms": ["governed reference workflows", "scoped build steps", "evidence receipts", "human gates"],
        "forbidden_terms": ["any idea", "launch-ready", "sell it", "guarantee", "autonomous"],
    },
)


@dataclass(frozen=True)
class AudienceMorphologyRecompositionGauntletReceipt:
    gauntlet_version: str
    status: str
    adaptive_linguistic_marketing_pack_status: str
    execute_requested: bool
    executed: bool
    morphologies_bound: int
    recomposition_outputs_written: int
    static_variants_scored: int
    recomposed_variants_scored: int
    static_morphology_baseline_mean_score: float
    adaptive_morphology_recomposition_mean_score: float
    adaptive_morphology_minus_static_effect: float
    minimum_morphology_recomposition_effect: float
    minimum_adaptive_morphology_score: float
    morphology_recomposition_effect_threshold_met: bool
    adaptive_morphology_quality_threshold_met: bool
    audience_morphology_evidence: bool
    morphology_recomposition_claim_authorized: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    registry_path: str
    outputs_path: str
    summary_path: str
    adaptive_linguistic_marketing_pack_sha256: str
    commercial_validation_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    manipulation_claim_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_all(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return all(needle.lower() in lower for needle in needles)


def _contains_none(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return all(needle.lower() not in lower for needle in needles)


def _dimension_terms(morphology: dict) -> list[str]:
    return [
        str(morphology["proof_appetite"]).replace("_", " "),
        str(morphology["risk_sensitivity"]).replace("_", " "),
        str(morphology["jargon_tolerance"]).replace("_", " "),
        str(morphology["cta_permission"]).replace("_", " "),
    ]


def _score_variant(*, text: str, morphology: dict) -> float:
    lower = text.lower()
    required = list(morphology["required_terms"])
    forbidden = list(morphology["forbidden_terms"])
    required_hits = sum(1 for term in required if term.lower() in lower)
    forbidden_hits = sum(1 for term in forbidden if term.lower() in lower)
    signal_words = [
        word
        for word in str(morphology["market_signal"]).lower().replace("-", " ").split()
        if len(word) > 6
    ]
    signal_hits = sum(1 for word in signal_words if word in lower)
    dimension_hits = sum(1 for term in _dimension_terms(morphology) if term in lower)

    required_score = required_hits / len(required) if required else 0.0
    forbidden_score = max(0.0, 1.0 - (forbidden_hits / max(1, len(forbidden))))
    signal_score = min(1.0, signal_hits / 2.0)
    dimension_score = min(1.0, dimension_hits / 2.0)
    boundary_score = 1.0 if _contains_none(text, forbidden) else 0.0
    return round(
        max(
            0.0,
            min(
                1.0,
                required_score * 0.38
                + forbidden_score * 0.22
                + signal_score * 0.12
                + dimension_score * 0.08
                + boundary_score * 0.20,
            ),
        ),
        6,
    )


def _build_output(morphology: dict) -> dict:
    static_score = _score_variant(text=str(morphology["static_language"]), morphology=morphology)
    recomposed_score = _score_variant(text=str(morphology["recomposed_language"]), morphology=morphology)
    return {
        "morphology_id": morphology["morphology_id"],
        "name": morphology["name"],
        "market_signal": morphology["market_signal"],
        "proof_appetite": morphology["proof_appetite"],
        "risk_sensitivity": morphology["risk_sensitivity"],
        "jargon_tolerance": morphology["jargon_tolerance"],
        "cta_permission": morphology["cta_permission"],
        "static_language": morphology["static_language"],
        "recomposed_language": morphology["recomposed_language"],
        "required_terms": list(morphology["required_terms"]),
        "forbidden_terms": list(morphology["forbidden_terms"]),
        "static_morphology_score": static_score,
        "adaptive_morphology_score": recomposed_score,
        "adaptive_minus_static_effect": round(recomposed_score - static_score, 6),
        "morphology_dimensions_bound": all(
            key in morphology
            for key in ("proof_appetite", "risk_sensitivity", "jargon_tolerance", "cta_permission")
        ),
        "required_terms_present_in_recomposition": _contains_all(
            str(morphology["recomposed_language"]), list(morphology["required_terms"])
        ),
        "forbidden_terms_absent_from_recomposition": _contains_none(
            str(morphology["recomposed_language"]), list(morphology["forbidden_terms"])
        ),
        "status": "AUDIENCE_MORPHOLOGY_RECOMPOSITION_RECORDED",
        "adaptive_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "autonomous_action_claim_authorized": False,
        "manipulation_claim_authorized": False,
        "authority_expansion_authorized": False,
    }


def run_audience_morphology_recomposition_gauntlet(
    *,
    adaptive_linguistic_marketing_pack_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> AudienceMorphologyRecompositionGauntletReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    marketing_pack = _load_json(adaptive_linguistic_marketing_pack_path)
    registry_path = output_dir / "audience_morphology_registry.json"
    outputs_path = output_dir / "audience_morphology_recomposition_outputs.jsonl"
    summary_path = output_dir / "audience_morphology_recomposition_summary.json"
    receipt_path = output_dir / "audience_morphology_recomposition_gauntlet_receipt.json"

    pack_ready = (
        marketing_pack.get("status")
        == "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY"
        and marketing_pack.get("linguistic_marketing_language_authorized") is True
        and marketing_pack.get("adaptive_claim_authorized") is True
        and marketing_pack.get("commercial_validation_claim_authorized") is False
        and marketing_pack.get("world_first_claim_authorized") is False
        and marketing_pack.get("agi_claim_authorized") is False
        and marketing_pack.get("autonomous_action_claim_authorized") is False
        and marketing_pack.get("authority_expansion_authorized") is False
    )

    minimum_effect = 0.35
    minimum_score = 0.84

    if not pack_ready or not execute:
        receipt = AudienceMorphologyRecompositionGauntletReceipt(
            gauntlet_version=AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_VERSION,
            status=AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_REFUSED_TOKEN,
            adaptive_linguistic_marketing_pack_status=str(marketing_pack.get("status")),
            execute_requested=execute,
            executed=False,
            morphologies_bound=0,
            recomposition_outputs_written=0,
            static_variants_scored=0,
            recomposed_variants_scored=0,
            static_morphology_baseline_mean_score=0.0,
            adaptive_morphology_recomposition_mean_score=0.0,
            adaptive_morphology_minus_static_effect=0.0,
            minimum_morphology_recomposition_effect=minimum_effect,
            minimum_adaptive_morphology_score=minimum_score,
            morphology_recomposition_effect_threshold_met=False,
            adaptive_morphology_quality_threshold_met=False,
            audience_morphology_evidence=False,
            morphology_recomposition_claim_authorized=False,
            adaptive_claim_authorized=False,
            allowed_claim_tier="T0_NO_AUDIENCE_MORPHOLOGY_RECOMPOSITION_CLAIM",
            registry_path=str(registry_path),
            outputs_path=str(outputs_path),
            summary_path=str(summary_path),
            adaptive_linguistic_marketing_pack_sha256=_sha256_path(adaptive_linguistic_marketing_pack_path),
            commercial_validation_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            world_first_claim_authorized=False,
            agi_claim_authorized=False,
            autonomous_action_claim_authorized=False,
            manipulation_claim_authorized=False,
            authority_expansion_authorized=False,
            boundary=(
                "Audience morphology recomposition gauntlet refused unless the T8 adaptive linguistic marketing "
                "proof pack is ready and explicit execution is requested. No adaptive, commercial, professional, "
                "publication, spend, fulfilment, world-first, AGI, autonomous-action, manipulation, or "
                "authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    registry = {
        "registry_version": AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_VERSION,
        "audience_morphologies": [dict(item) for item in AUDIENCE_MORPHOLOGIES],
        "boundary": (
            "Audience morphologies bind proof appetite, risk sensitivity, jargon tolerance, CTA permission, "
            "required language, and forbidden language. They do not authorize manipulation, autonomous external "
            "action, commercial validation, world-first claims, or authority expansion."
        ),
    }
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    outputs = [_build_output(morphology) for morphology in AUDIENCE_MORPHOLOGIES]
    with outputs_path.open("w") as fh:
        for output in outputs:
            fh.write(json.dumps(output, sort_keys=True) + "\n")

    static_scores = [float(output["static_morphology_score"]) for output in outputs]
    adaptive_scores = [float(output["adaptive_morphology_score"]) for output in outputs]
    static_mean = round(mean(static_scores), 6)
    adaptive_mean = round(mean(adaptive_scores), 6)
    effect = round(adaptive_mean - static_mean, 6)
    effect_met = effect >= minimum_effect
    quality_met = adaptive_mean >= minimum_score
    evidence = effect_met and quality_met

    summary = {
        "morphologies_bound": len(AUDIENCE_MORPHOLOGIES),
        "static_morphology_baseline_mean_score": static_mean,
        "adaptive_morphology_recomposition_mean_score": adaptive_mean,
        "adaptive_morphology_minus_static_effect": effect,
        "minimum_morphology_recomposition_effect": minimum_effect,
        "minimum_adaptive_morphology_score": minimum_score,
        "morphology_recomposition_effect_threshold_met": effect_met,
        "adaptive_morphology_quality_threshold_met": quality_met,
        "audience_morphology_evidence": evidence,
        "claim_boundary": (
            "This is internal controlled audience-morphology recomposition evidence only. It does not prove "
            "external demand, conversion lift, product-market fit, manipulation capability, AGI, world-first "
            "status, autonomous action, or authority expansion."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    receipt = AudienceMorphologyRecompositionGauntletReceipt(
        gauntlet_version=AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_VERSION,
        status=AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY_TOKEN,
        adaptive_linguistic_marketing_pack_status=str(marketing_pack.get("status")),
        execute_requested=True,
        executed=True,
        morphologies_bound=len(AUDIENCE_MORPHOLOGIES),
        recomposition_outputs_written=len(outputs),
        static_variants_scored=len(outputs),
        recomposed_variants_scored=len(outputs),
        static_morphology_baseline_mean_score=static_mean,
        adaptive_morphology_recomposition_mean_score=adaptive_mean,
        adaptive_morphology_minus_static_effect=effect,
        minimum_morphology_recomposition_effect=minimum_effect,
        minimum_adaptive_morphology_score=minimum_score,
        morphology_recomposition_effect_threshold_met=effect_met,
        adaptive_morphology_quality_threshold_met=quality_met,
        audience_morphology_evidence=evidence,
        morphology_recomposition_claim_authorized=evidence,
        adaptive_claim_authorized=evidence,
        allowed_claim_tier=(
            "T9_CANDIDATE_AUDIENCE_MORPHOLOGY_SEMANTIC_RECOMPOSITION_EVIDENCE"
            if evidence
            else "T8_LINGUISTIC_PIVOT_ONLY_NO_AUDIENCE_MORPHOLOGY_CLAIM"
        ),
        registry_path=str(registry_path),
        outputs_path=str(outputs_path),
        summary_path=str(summary_path),
        adaptive_linguistic_marketing_pack_sha256=_sha256_path(adaptive_linguistic_marketing_pack_path),
        commercial_validation_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        manipulation_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This audience morphology recomposition gauntlet tests whether DIO can bind audience morphology "
            "dimensions and recompute proof-bound language for different buyer/evaluator types after market "
            "signal pressure. It authorizes only candidate audience-morphology semantic recomposition evidence "
            "when thresholds are met and never authorizes commercial validation, professional approval, "
            "publication, spend, fulfilment, world-first status, AGI claims, autonomous consequential action, "
            "manipulation claims, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
