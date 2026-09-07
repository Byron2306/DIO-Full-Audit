from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


MARKET_COMMAND_MARKETING_PROOF_PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_V1"
MARKET_COMMAND_MARKETING_PROOF_PACK_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_READY"
MARKET_COMMAND_MARKETING_PROOF_PACK_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_REFUSED"


@dataclass(frozen=True)
class MarketCommandMarketingProofPackReceipt:
    pack_version: str
    status: str
    prior_marketing_pack_status: str
    market_command_pivot_status: str
    marketing_claim_tier: str
    market_pivot_marketing_language_authorized: bool
    adaptive_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    authority_expansion_authorized: bool
    static_baseline_mean_score: float
    pivoting_sensorium_mean_score: float
    pivoting_minus_static_effect: float
    minimum_pivot_effect: float
    market_signals_processed: int
    pivots_executed: int
    market_commands_issued: int
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    market_command_claims_path: str
    market_command_copy_path: str
    prior_marketing_pack_sha256: str
    market_command_pivot_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbidden_claims() -> list[str]:
    return [
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees revenue, sales, or buyer outcomes",
        "DIO can autonomously spend money or publish campaigns",
        "DIO can contact prospects or customers without a human gate",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO is enterprise-proven",
        "DIO has world-first status",
        "DIO may expand its own authority from market signals",
        "DIO's internal market-command evidence equals external demand proof",
    ]


def _allowed_claims(pivot: dict) -> list[str]:
    effect = float(pivot.get("pivoting_minus_static_effect", 0.0))
    static = float(pivot.get("static_baseline_mean_score", 0.0))
    pivoting = float(pivot.get("pivoting_sensorium_mean_score", 0.0))
    return [
        "DIO produced T7 candidate evidence of market-command sensorium pivoting adaptation in an internal controlled gauntlet.",
        "The pivoting sensorium route outperformed the static market-command baseline under the tested harness.",
        f"The T7 pivot gauntlet measured a pivoting-minus-static effect of {effect:.3f}.",
        f"The static baseline scored {static:.3f}; the pivoting sensorium route scored {pivoting:.3f}.",
        "DIO demonstrated controlled route-change behavior under internal market and friction signal pressure.",
        "The T7 signal preserves proof locks, human gates, and authority boundaries.",
        "This evidence supports bounded marketing language about adaptive market-command orchestration, not commercial validation.",
    ]


def _write_copy(path: Path, allowed: list[str], forbidden: list[str]) -> None:
    lines = [
        "# DIO Market Command Marketing Proof Pack",
        "",
        "## Marketing-safe claim",
        "",
        (
            "DIO has internal controlled T7 candidate evidence of market-command sensorium pivoting adaptation: "
            "it detected market/friction signal pressure, abandoned weaker static routes, and issued bounded pivot commands "
            "while preserving proof and authority locks."
        ),
        "",
        "## Approved language",
        "",
    ]
    lines.extend(f"- {claim}" for claim in allowed)
    lines.extend(
        [
            "",
            "## Required disclaimers",
            "",
            "- Internal controlled gauntlet evidence only.",
            "- Candidate market-command pivoting evidence, not external demand proof.",
            "- Not AGI.",
            "- Not commercial validation.",
            "- Not professional approval.",
            "- Not world-first status.",
            "- No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
            "",
            "## Forbidden claims",
            "",
        ]
    )
    lines.extend(f"- {claim}" for claim in forbidden)
    path.write_text("\n".join(lines) + "\n")


def build_market_command_marketing_proof_pack(
    *,
    marketing_proof_boundary_pack_path: Path,
    market_command_pivot_gauntlet_path: Path,
    output_dir: Path,
) -> MarketCommandMarketingProofPackReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    prior = _load_json(marketing_proof_boundary_pack_path)
    pivot = _load_json(market_command_pivot_gauntlet_path)

    claims_path = output_dir / "market_command_marketing_proof_claims.json"
    copy_path = output_dir / "market_command_marketing_safe_copy.md"
    receipt_path = output_dir / "market_command_marketing_proof_pack_receipt.json"

    prior_ready = (
        prior.get("status") == "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_READY"
        and prior.get("bounded_marketing_language_authorized") is True
        and prior.get("adaptive_claim_authorized") is True
        and prior.get("commercial_validation_claim_authorized") is False
        and prior.get("world_first_claim_authorized") is False
        and prior.get("agi_claim_authorized") is False
        and prior.get("authority_expansion_authorized") is False
    )
    pivot_ready = (
        pivot.get("status") == "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY"
        and pivot.get("market_command_adaptive_evidence") is True
        and pivot.get("market_pivot_claim_authorized") is True
        and pivot.get("adaptive_claim_authorized") is True
        and pivot.get("market_pivot_effect_threshold_met") is True
        and float(pivot.get("pivoting_minus_static_effect", 0.0)) >= float(pivot.get("minimum_pivot_effect", 1.0))
        and pivot.get("commercial_validation_claim_authorized") is False
        and pivot.get("world_first_claim_authorized") is False
        and pivot.get("agi_claim_authorized") is False
        and pivot.get("autonomous_action_claim_authorized") is False
        and pivot.get("authority_expansion_authorized") is False
    )
    ready = prior_ready and pivot_ready

    forbidden = _forbidden_claims()
    allowed = _allowed_claims(pivot) if ready else []

    if ready:
        status = MARKET_COMMAND_MARKETING_PROOF_PACK_READY_TOKEN
        tier = "T7_MARKETING_SAFE_MARKET_COMMAND_SENSORIUM_PIVOTING_ADAPTATION"
        language_authorized = True
        adaptive_authorized = True
    else:
        status = MARKET_COMMAND_MARKETING_PROOF_PACK_REFUSED_TOKEN
        tier = "T0_NO_MARKET_COMMAND_MARKETING_CLAIM"
        language_authorized = False
        adaptive_authorized = False

    claims = {
        "pack_version": MARKET_COMMAND_MARKETING_PROOF_PACK_VERSION,
        "marketing_claim_tier": tier,
        "allowed_public_claims": allowed,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "Candidate market-command pivoting evidence, not external demand proof.",
            "No commercial validation, professional approval, world-first status, AGI claim, autonomous action, or authority expansion is authorized.",
        ],
        "proof_numbers": {
            "static_baseline_mean_score": float(pivot.get("static_baseline_mean_score", 0.0)),
            "pivoting_sensorium_mean_score": float(pivot.get("pivoting_sensorium_mean_score", 0.0)),
            "pivoting_minus_static_effect": float(pivot.get("pivoting_minus_static_effect", 0.0)),
            "minimum_pivot_effect": float(pivot.get("minimum_pivot_effect", 0.0)),
            "market_signals_processed": int(pivot.get("market_signals_processed", 0)),
            "pivots_executed": int(pivot.get("pivots_executed", 0)),
            "market_commands_issued": int(pivot.get("market_commands_issued", 0)),
        },
        "claim_locks": {
            "commercial_validation_claim_authorized": False,
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
        _write_copy(copy_path, allowed, forbidden)
    else:
        copy_path.write_text(
            "# DIO Market Command Marketing Proof Pack\n\n"
            "Market-command marketing proof language refused because prerequisite evidence was not ready.\n"
        )

    receipt = MarketCommandMarketingProofPackReceipt(
        pack_version=MARKET_COMMAND_MARKETING_PROOF_PACK_VERSION,
        status=status,
        prior_marketing_pack_status=str(prior.get("status")),
        market_command_pivot_status=str(pivot.get("status")),
        marketing_claim_tier=tier,
        market_pivot_marketing_language_authorized=language_authorized,
        adaptive_claim_authorized=adaptive_authorized,
        commercial_validation_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        authority_expansion_authorized=False,
        static_baseline_mean_score=float(pivot.get("static_baseline_mean_score", 0.0)),
        pivoting_sensorium_mean_score=float(pivot.get("pivoting_sensorium_mean_score", 0.0)),
        pivoting_minus_static_effect=float(pivot.get("pivoting_minus_static_effect", 0.0)),
        minimum_pivot_effect=float(pivot.get("minimum_pivot_effect", 0.0)),
        market_signals_processed=int(pivot.get("market_signals_processed", 0)),
        pivots_executed=int(pivot.get("pivots_executed", 0)),
        market_commands_issued=int(pivot.get("market_commands_issued", 0)),
        allowed_public_claims_count=len(allowed),
        forbidden_public_claims_count=len(forbidden),
        market_command_claims_path=str(claims_path),
        market_command_copy_path=str(copy_path),
        prior_marketing_pack_sha256=_sha256_path(marketing_proof_boundary_pack_path),
        market_command_pivot_sha256=_sha256_path(market_command_pivot_gauntlet_path),
        boundary=(
            "This market-command marketing proof pack converts T7 candidate pivoting evidence into bounded, "
            "marketing-safe language. It authorizes only proof-bound public wording about internal controlled "
            "market-command sensorium pivoting adaptation and never authorizes commercial validation, professional "
            "approval, publication, spend, fulfilment, world-first status, AGI claims, autonomous consequential "
            "action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
