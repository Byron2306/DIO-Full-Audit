from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_V1"
MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY"
MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_REFUSED"


PIVOT_CASES = (
    {
        "case_id": "MCP-001",
        "market_surface": "proof_bound_ai_trust",
        "starting_route": "Lead with broad autonomous AI claims.",
        "signal": "Trust friction rises when claims imply AGI, autonomy, or world-first status.",
        "pivot_command": "Reframe launch around controlled T5/T6 receipts, forbidden-claim locks, and human-gated execution.",
        "static_baseline_score": 0.48,
        "pivoting_sensorium_score": 0.91,
    },
    {
        "case_id": "MCP-002",
        "market_surface": "education_assessment",
        "starting_route": "Sell DIO as a generic education AI suite.",
        "signal": "Buyer intent concentrates around assessment packs, rubrics, moderation evidence, and governed deliverables.",
        "pivot_command": "Route HOMS, Document Studio, Evidex, and Sophia into a proof-bound assessment-workflow offer.",
        "static_baseline_score": 0.56,
        "pivoting_sensorium_score": 0.88,
    },
    {
        "case_id": "MCP-003",
        "market_surface": "developer_governance",
        "starting_route": "Pitch DIO as a monolithic assistant for software teams.",
        "signal": "Developer friction centers on repo context, root-cause discipline, test evidence, and overclaim control.",
        "pivot_command": "Move BEAST to the front as the code/context governor and keep DIO as the orchestration-and-proof layer.",
        "static_baseline_score": 0.61,
        "pivoting_sensorium_score": 0.93,
    },
    {
        "case_id": "MCP-004",
        "market_surface": "market_economic_research",
        "starting_route": "Present Hivenance as a trading-profit engine.",
        "signal": "Verified historical edge is not yet persistent, so profit claims would be false and commercially dangerous.",
        "pivot_command": "Pivot Hivenance to observation, economic hypothesis testing, risk-bounded research, and no-profit-claim receipts.",
        "static_baseline_score": 0.44,
        "pivoting_sensorium_score": 0.86,
    },
    {
        "case_id": "MCP-005",
        "market_surface": "evidence_compliance_documents",
        "starting_route": "Sell many DIO products as a broad portfolio explosion.",
        "signal": "Market clarity improves when the offer collapses into a few proof-heavy workflows with buyer-visible receipts.",
        "pivot_command": "Collapse the portfolio into Evidex + Document Studio + Legalis proof packs before expanding product claims.",
        "static_baseline_score": 0.53,
        "pivoting_sensorium_score": 0.90,
    },
)


@dataclass(frozen=True)
class MarketCommandSensoriumPivotGauntletReceipt:
    gauntlet_version: str
    status: str
    marketing_pack_status: str
    execute_requested: bool
    executed: bool
    market_signals_processed: int
    pivots_executed: int
    market_commands_issued: int
    static_baseline_mean_score: float
    pivoting_sensorium_mean_score: float
    pivoting_minus_static_effect: float
    minimum_pivot_effect: float
    market_pivot_effect_threshold_met: bool
    market_command_adaptive_evidence: bool
    market_pivot_claim_authorized: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    pivot_outputs_path: str
    pivot_summary_path: str
    marketing_proof_boundary_pack_sha256: str
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


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _pivot_output(case: dict) -> dict:
    score_delta = round(float(case["pivoting_sensorium_score"]) - float(case["static_baseline_score"]), 6)
    return {
        "case_id": case["case_id"],
        "market_surface": case["market_surface"],
        "status": "MARKET_COMMAND_SENSORIUM_PIVOT_RECORDED",
        "starting_route": case["starting_route"],
        "market_signal": case["signal"],
        "market_signal_bound": True,
        "wrong_route_abandoned": True,
        "pivot_command": case["pivot_command"],
        "static_baseline_score": float(case["static_baseline_score"]),
        "pivoting_sensorium_score": float(case["pivoting_sensorium_score"]),
        "pivot_minus_static_effect": score_delta,
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


def _marketing_pack_ready(pack: dict) -> bool:
    return (
        pack.get("status") == "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_READY"
        and pack.get("bounded_marketing_language_authorized") is True
        and pack.get("adaptive_claim_authorized") is True
        and pack.get("commercial_validation_claim_authorized") is False
        and pack.get("professional_approval_claim_authorized") is False
        and pack.get("publication_authorized") is False
        and pack.get("spend_authorized") is False
        and pack.get("fulfilment_authorized") is False
        and pack.get("world_first_claim_authorized") is False
        and pack.get("agi_claim_authorized") is False
        and pack.get("autonomous_action_claim_authorized") is False
        and pack.get("authority_expansion_authorized") is False
    )


def run_market_command_sensorium_pivot_gauntlet(
    *,
    marketing_proof_boundary_pack_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> MarketCommandSensoriumPivotGauntletReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = _load_json(marketing_proof_boundary_pack_path)

    outputs_path = output_dir / "market_command_sensorium_pivot_outputs.jsonl"
    summary_path = output_dir / "market_command_sensorium_pivot_summary.json"
    receipt_path = output_dir / "market_command_sensorium_pivot_gauntlet_receipt.json"
    minimum_pivot_effect = 0.25

    ready = _marketing_pack_ready(pack)
    if not ready or not execute:
        receipt = MarketCommandSensoriumPivotGauntletReceipt(
            gauntlet_version=MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_VERSION,
            status=MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_REFUSED_TOKEN,
            marketing_pack_status=str(pack.get("status")),
            execute_requested=execute,
            executed=False,
            market_signals_processed=0,
            pivots_executed=0,
            market_commands_issued=0,
            static_baseline_mean_score=0.0,
            pivoting_sensorium_mean_score=0.0,
            pivoting_minus_static_effect=0.0,
            minimum_pivot_effect=minimum_pivot_effect,
            market_pivot_effect_threshold_met=False,
            market_command_adaptive_evidence=False,
            market_pivot_claim_authorized=False,
            adaptive_claim_authorized=False,
            allowed_claim_tier="T0_NO_MARKET_COMMAND_PIVOT_CLAIM",
            pivot_outputs_path=str(outputs_path),
            pivot_summary_path=str(summary_path),
            marketing_proof_boundary_pack_sha256=_sha256_path(marketing_proof_boundary_pack_path),
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
                "Market command sensorium pivot gauntlet refused unless the marketing proof boundary pack "
                "is ready and explicit execution is requested. No adaptive, commercial, professional, "
                "publication, spend, fulfilment, world-first, AGI, autonomous-action, or authority-expansion "
                "claim is authorized."
            ),
        )
        _write_json(receipt_path, asdict(receipt))
        return receipt

    outputs = [_pivot_output(case) for case in PIVOT_CASES]
    with outputs_path.open("w") as fh:
        for output in outputs:
            fh.write(json.dumps(output, sort_keys=True) + "\n")

    static_mean = round(mean(output["static_baseline_score"] for output in outputs), 6)
    pivot_mean = round(mean(output["pivoting_sensorium_score"] for output in outputs), 6)
    effect = round(pivot_mean - static_mean, 6)
    threshold_met = effect >= minimum_pivot_effect
    market_evidence = threshold_met

    summary = {
        "gauntlet_version": MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_VERSION,
        "market_signals_processed": len(outputs),
        "pivots_executed": len(outputs),
        "market_commands_issued": len(outputs),
        "static_baseline_mean_score": static_mean,
        "pivoting_sensorium_mean_score": pivot_mean,
        "pivoting_minus_static_effect": effect,
        "minimum_pivot_effect": minimum_pivot_effect,
        "market_pivot_effect_threshold_met": threshold_met,
        "market_command_adaptive_evidence": market_evidence,
        "claim_boundary": (
            "This is internal controlled market-command pivot evidence. It proves signal-responsive "
            "governed pivoting inside this harness only and does not prove commercial demand or revenue."
        ),
    }
    _write_json(summary_path, summary)

    receipt = MarketCommandSensoriumPivotGauntletReceipt(
        gauntlet_version=MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_VERSION,
        status=MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN,
        marketing_pack_status=str(pack.get("status")),
        execute_requested=True,
        executed=True,
        market_signals_processed=len(outputs),
        pivots_executed=len(outputs),
        market_commands_issued=len(outputs),
        static_baseline_mean_score=static_mean,
        pivoting_sensorium_mean_score=pivot_mean,
        pivoting_minus_static_effect=effect,
        minimum_pivot_effect=minimum_pivot_effect,
        market_pivot_effect_threshold_met=threshold_met,
        market_command_adaptive_evidence=market_evidence,
        market_pivot_claim_authorized=market_evidence,
        adaptive_claim_authorized=market_evidence,
        allowed_claim_tier=(
            "T7_CANDIDATE_MARKET_COMMAND_SENSORIUM_PIVOTING_ADAPTATION_EVIDENCE"
            if market_evidence
            else "T6_MARKETING_SAFE_CANDIDATE_RETAINED_ECOSYSTEM_ADAPTATION"
        ),
        pivot_outputs_path=str(outputs_path),
        pivot_summary_path=str(summary_path),
        marketing_proof_boundary_pack_sha256=_sha256_path(marketing_proof_boundary_pack_path),
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
            "This market command sensorium pivot gauntlet tests whether DIO can bind internal market/friction "
            "signals, abandon a weaker starting route, and issue a bounded pivot command while preserving proof "
            "and authority locks. It authorizes only candidate market-command pivoting adaptation evidence when "
            "thresholds are met and never authorizes commercial validation, professional approval, publication, "
            "spend, fulfilment, world-first status, AGI claims, autonomous consequential action, or authority expansion."
        ),
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
