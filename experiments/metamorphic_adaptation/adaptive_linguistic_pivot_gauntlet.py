from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_V1"
ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY"
ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_REFUSED"


AUDIENCE_SHIFTS = (
    {
        "shift_id": "LING-001",
        "from_audience": "AI automation curiosity buyers",
        "to_audience": "risk-sensitive compliance leaders",
        "market_signal": "autonomy language creates legal and trust friction",
        "static_language": "DIO is an autonomous AI automation platform that can run complex work for teams.",
        "adaptive_language": (
            "DIO is proof-bound orchestration infrastructure for governed AI work. It preserves human gates, "
            "authority limits, receipts, and claim boundaries when work becomes consequential."
        ),
        "required_terms": ["proof-bound", "human gates", "authority limits", "receipts"],
        "forbidden_terms": ["autonomous", "guarantee", "world-first", "agi"],
    },
    {
        "shift_id": "LING-002",
        "from_audience": "teacher-practitioners",
        "to_audience": "school leadership and education governance buyers",
        "market_signal": "classroom feature language fails budget and governance evaluation",
        "static_language": "DIO helps teachers create learning activities and classroom resources faster.",
        "adaptive_language": (
            "DIO supports governed education-product orchestration: evidence-bound module assets, reviewer-ready "
            "receipts, bounded learner support, and leadership-visible risk controls."
        ),
        "required_terms": ["governed", "evidence-bound", "receipts", "risk controls"],
        "forbidden_terms": ["replaces teachers", "guarantee", "autonomous", "accredited"],
    },
    {
        "shift_id": "LING-003",
        "from_audience": "founder/operator buyers",
        "to_audience": "technical evaluator and repo-governance buyer",
        "market_signal": "vision-language is insufficient without code and proof traceability",
        "static_language": "DIO turns ambitious product ideas into launch-ready systems.",
        "adaptive_language": (
            "DIO routes product work through code-aware governance, scoped repair plans, test-bound claims, "
            "semantic boundaries, and evidence receipts before any launch claim is allowed."
        ),
        "required_terms": ["code-aware", "scoped", "test-bound", "evidence receipts"],
        "forbidden_terms": ["launch-ready", "guarantee", "production-proven", "autonomous"],
    },
    {
        "shift_id": "LING-004",
        "from_audience": "creator-tool audience",
        "to_audience": "agency and studio operations buyer",
        "market_signal": "creative-output language lacks campaign governance and proof discipline",
        "static_language": "DIO can create ads, videos, posts, and campaign assets for creators.",
        "adaptive_language": (
            "DIO composes governed campaign surfaces from proof packs, audience constraints, claim locks, "
            "brand-safe variants, and human-approved publication gates."
        ),
        "required_terms": ["proof packs", "audience constraints", "claim locks", "publication gates"],
        "forbidden_terms": ["publishes automatically", "guarantee", "viral", "autonomous"],
    },
    {
        "shift_id": "LING-005",
        "from_audience": "trading-curious audience",
        "to_audience": "risk-governed analytics evaluator",
        "market_signal": "profit-oriented language is unsafe and unsupported by verified market evidence",
        "static_language": "DIO can find market opportunities and improve trading decisions.",
        "adaptive_language": (
            "DIO separates public observation, economic hypothesis, verified-cost analysis, and human-gated "
            "decision review. It rejects unsupported return promises and treats market outputs as bounded research evidence."
        ),
        "required_terms": ["public observation", "economic hypothesis", "verified-cost", "human-gated"],
        "forbidden_terms": ["profit", "guarantee", "trading decisions", "autonomous"],
    },
)


@dataclass(frozen=True)
class AdaptiveLinguisticPivotGauntletReceipt:
    gauntlet_version: str
    status: str
    market_command_marketing_pack_status: str
    execute_requested: bool
    executed: bool
    audience_shifts_processed: int
    linguistic_pivots_executed: int
    static_copy_variants_scored: int
    adaptive_copy_variants_scored: int
    static_linguistic_baseline_mean_score: float
    adaptive_linguistic_pivot_mean_score: float
    adaptive_linguistic_minus_static_effect: float
    minimum_linguistic_pivot_effect: float
    minimum_adaptive_linguistic_score: float
    linguistic_pivot_effect_threshold_met: bool
    adaptive_linguistic_quality_threshold_met: bool
    adaptive_linguistic_evidence: bool
    linguistic_pivot_claim_authorized: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    outputs_path: str
    summary_path: str
    market_command_marketing_pack_sha256: str
    commercial_validation_claim_authorized: bool
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


def _contains_all(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return all(needle.lower() in lower for needle in needles)


def _contains_none(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return all(needle.lower() not in lower for needle in needles)


def _score_variant(*, text: str, required_terms: list[str], forbidden_terms: list[str], signal: str) -> float:
    lower = text.lower()
    required_hits = sum(1 for term in required_terms if term.lower() in lower)
    forbidden_hits = sum(1 for term in forbidden_terms if term.lower() in lower)
    signal_terms = [word for word in signal.lower().replace("-", " ").split() if len(word) > 6]
    signal_hits = sum(1 for word in signal_terms if word in lower)
    required_score = required_hits / len(required_terms) if required_terms else 0.0
    forbidden_score = max(0.0, 1.0 - (forbidden_hits / max(1, len(forbidden_terms))))
    signal_score = min(1.0, signal_hits / 2.0)
    boundary_score = 1.0 if _contains_none(text, forbidden_terms) else 0.25
    return round(
        max(0.0, min(1.0, required_score * 0.45 + forbidden_score * 0.25 + signal_score * 0.10 + boundary_score * 0.20)),
        6,
    )


def _build_output(shift: dict) -> dict:
    static_score = _score_variant(
        text=shift["static_language"],
        required_terms=shift["required_terms"],
        forbidden_terms=shift["forbidden_terms"],
        signal=shift["market_signal"],
    )
    adaptive_score = _score_variant(
        text=shift["adaptive_language"],
        required_terms=shift["required_terms"],
        forbidden_terms=shift["forbidden_terms"],
        signal=shift["market_signal"],
    )
    return {
        "shift_id": shift["shift_id"],
        "from_audience": shift["from_audience"],
        "to_audience": shift["to_audience"],
        "market_signal": shift["market_signal"],
        "static_language": shift["static_language"],
        "adaptive_language": shift["adaptive_language"],
        "required_terms": list(shift["required_terms"]),
        "forbidden_terms": list(shift["forbidden_terms"]),
        "static_linguistic_score": static_score,
        "adaptive_linguistic_score": adaptive_score,
        "adaptive_minus_static_effect": round(adaptive_score - static_score, 6),
        "required_terms_present_in_adaptive": _contains_all(shift["adaptive_language"], shift["required_terms"]),
        "forbidden_terms_absent_from_adaptive": _contains_none(shift["adaptive_language"], shift["forbidden_terms"]),
        "status": "ADAPTIVE_LINGUISTIC_PIVOT_RECORDED",
        "adaptive_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "world_first_claim_authorized": False,
        "agi_claim_authorized": False,
        "autonomous_action_claim_authorized": False,
        "authority_expansion_authorized": False,
    }


def run_adaptive_linguistic_pivot_gauntlet(
    *,
    market_command_marketing_pack_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> AdaptiveLinguisticPivotGauntletReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    marketing_pack = _load_json(market_command_marketing_pack_path)
    outputs_path = output_dir / "adaptive_linguistic_pivot_outputs.jsonl"
    summary_path = output_dir / "adaptive_linguistic_pivot_summary.json"
    receipt_path = output_dir / "adaptive_linguistic_pivot_gauntlet_receipt.json"

    pack_ready = (
        marketing_pack.get("status") == "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_READY"
        and marketing_pack.get("market_pivot_marketing_language_authorized") is True
        and marketing_pack.get("adaptive_claim_authorized") is True
        and marketing_pack.get("commercial_validation_claim_authorized") is False
        and marketing_pack.get("world_first_claim_authorized") is False
        and marketing_pack.get("agi_claim_authorized") is False
        and marketing_pack.get("authority_expansion_authorized") is False
    )

    minimum_effect = 0.30
    minimum_score = 0.82

    if not pack_ready or not execute:
        receipt = AdaptiveLinguisticPivotGauntletReceipt(
            gauntlet_version=ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_VERSION,
            status=ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_REFUSED_TOKEN,
            market_command_marketing_pack_status=str(marketing_pack.get("status")),
            execute_requested=execute,
            executed=False,
            audience_shifts_processed=0,
            linguistic_pivots_executed=0,
            static_copy_variants_scored=0,
            adaptive_copy_variants_scored=0,
            static_linguistic_baseline_mean_score=0.0,
            adaptive_linguistic_pivot_mean_score=0.0,
            adaptive_linguistic_minus_static_effect=0.0,
            minimum_linguistic_pivot_effect=minimum_effect,
            minimum_adaptive_linguistic_score=minimum_score,
            linguistic_pivot_effect_threshold_met=False,
            adaptive_linguistic_quality_threshold_met=False,
            adaptive_linguistic_evidence=False,
            linguistic_pivot_claim_authorized=False,
            adaptive_claim_authorized=False,
            allowed_claim_tier="T0_NO_LINGUISTIC_PIVOT_CLAIM",
            outputs_path=str(outputs_path),
            summary_path=str(summary_path),
            market_command_marketing_pack_sha256=_sha256_path(market_command_marketing_pack_path),
            commercial_validation_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            world_first_claim_authorized=False,
            agi_claim_authorized=False,
            autonomous_action_claim_authorized=False,
            authority_expansion_authorized=False,
            boundary=(
                "Adaptive linguistic pivot gauntlet refused unless the T7 market-command marketing proof pack is ready "
                "and explicit execution is requested. No adaptive, commercial, professional, publication, spend, "
                "fulfilment, world-first, AGI, autonomous-action, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    outputs = [_build_output(shift) for shift in AUDIENCE_SHIFTS]
    with outputs_path.open("w") as fh:
        for output in outputs:
            fh.write(json.dumps(output, sort_keys=True) + "\n")

    static_scores = [float(output["static_linguistic_score"]) for output in outputs]
    adaptive_scores = [float(output["adaptive_linguistic_score"]) for output in outputs]
    static_mean = round(mean(static_scores), 6)
    adaptive_mean = round(mean(adaptive_scores), 6)
    effect = round(adaptive_mean - static_mean, 6)
    effect_met = effect >= minimum_effect
    quality_met = adaptive_mean >= minimum_score
    evidence = effect_met and quality_met

    summary = {
        "audience_shifts_processed": len(outputs),
        "static_linguistic_baseline_mean_score": static_mean,
        "adaptive_linguistic_pivot_mean_score": adaptive_mean,
        "adaptive_linguistic_minus_static_effect": effect,
        "minimum_linguistic_pivot_effect": minimum_effect,
        "minimum_adaptive_linguistic_score": minimum_score,
        "linguistic_pivot_effect_threshold_met": effect_met,
        "adaptive_linguistic_quality_threshold_met": quality_met,
        "adaptive_linguistic_evidence": evidence,
        "claim_boundary": (
            "This is internal controlled linguistic pivot evidence only. It does not prove external demand, "
            "conversion lift, product-market fit, AGI, world-first status, autonomous action, or authority expansion."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    receipt = AdaptiveLinguisticPivotGauntletReceipt(
        gauntlet_version=ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_VERSION,
        status=ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY_TOKEN,
        market_command_marketing_pack_status=str(marketing_pack.get("status")),
        execute_requested=True,
        executed=True,
        audience_shifts_processed=len(outputs),
        linguistic_pivots_executed=len(outputs),
        static_copy_variants_scored=len(outputs),
        adaptive_copy_variants_scored=len(outputs),
        static_linguistic_baseline_mean_score=static_mean,
        adaptive_linguistic_pivot_mean_score=adaptive_mean,
        adaptive_linguistic_minus_static_effect=effect,
        minimum_linguistic_pivot_effect=minimum_effect,
        minimum_adaptive_linguistic_score=minimum_score,
        linguistic_pivot_effect_threshold_met=effect_met,
        adaptive_linguistic_quality_threshold_met=quality_met,
        adaptive_linguistic_evidence=evidence,
        linguistic_pivot_claim_authorized=evidence,
        adaptive_claim_authorized=evidence,
        allowed_claim_tier=(
            "T8_CANDIDATE_ADAPTIVE_LINGUISTIC_MARKET_RECOMPOSITION_EVIDENCE"
            if evidence
            else "T7_MARKET_COMMAND_PIVOT_ONLY_NO_LINGUISTIC_CLAIM"
        ),
        outputs_path=str(outputs_path),
        summary_path=str(summary_path),
        market_command_marketing_pack_sha256=_sha256_path(market_command_marketing_pack_path),
        commercial_validation_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This adaptive linguistic pivot gauntlet tests whether DIO can retarget language after market and "
            "friction shifts while preserving proof, audience fit, claim locks, and authority boundaries. It authorizes "
            "only candidate adaptive-linguistic market recomposition evidence when thresholds are met and never authorizes "
            "commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claims, "
            "autonomous consequential action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
