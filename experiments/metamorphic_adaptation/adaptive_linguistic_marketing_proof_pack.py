from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_V1"
ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY"
ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_REFUSED"


@dataclass(frozen=True)
class AdaptiveLinguisticMarketingProofPackReceipt:
    pack_version: str
    status: str
    market_command_marketing_pack_status: str
    adaptive_linguistic_gauntlet_status: str
    marketing_claim_tier: str
    linguistic_marketing_language_authorized: bool
    adaptive_claim_authorized: bool
    audience_shifts_processed: int
    linguistic_pivots_executed: int
    static_linguistic_baseline_mean_score: float
    adaptive_linguistic_pivot_mean_score: float
    adaptive_linguistic_minus_static_effect: float
    minimum_linguistic_pivot_effect: float
    minimum_adaptive_linguistic_score: float
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    linguistic_claims_path: str
    linguistic_copy_path: str
    market_command_marketing_pack_sha256: str
    adaptive_linguistic_gauntlet_sha256: str
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


def _forbidden_claims() -> list[str]:
    return [
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees conversion lift, sales, revenue, or buyer outcomes",
        "DIO can autonomously publish, spend, contact, or fulfil campaigns",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO is enterprise-proven",
        "DIO has world-first status",
        "DIO may expand its own authority from linguistic or market signals",
        "DIO's adaptive linguistic evidence equals external demand proof",
        "DIO can manipulate audiences or bypass human review",
    ]


def _allowed_claims(linguistic: dict) -> list[str]:
    effect = float(linguistic.get("adaptive_linguistic_minus_static_effect", 0.0))
    static = float(linguistic.get("static_linguistic_baseline_mean_score", 0.0))
    adaptive = float(linguistic.get("adaptive_linguistic_pivot_mean_score", 0.0))
    return [
        "DIO produced T8 candidate evidence of adaptive linguistic market recomposition in an internal controlled gauntlet.",
        "After market and friction shifts, DIO retargeted audience language while preserving proof, claim locks, and authority boundaries.",
        f"The T8 linguistic gauntlet measured an adaptive-minus-static effect of {effect:.4f}.",
        f"The static linguistic baseline scored {static:.4f}; the adaptive linguistic route scored {adaptive:.4f}.",
        "DIO recomposed audience fit, proof emphasis, risk posture, and permitted vocabulary after market signal pressure.",
        "The T8 signal supports bounded marketing language about adaptive linguistic orchestration, not conversion lift or external demand proof.",
        "The linguistic pivot preserved human gates and blocked AGI, world-first, commercial-validation, and authority-expansion claims.",
    ]


def _write_markdown(path: Path, allowed: list[str], forbidden: list[str]) -> None:
    lines = [
        "# DIO Adaptive Linguistic Marketing Proof Pack",
        "",
        "## Marketing-safe claim",
        "",
        (
            "DIO has internal controlled T8 candidate evidence of adaptive linguistic market recomposition: "
            "after market and friction shifts, it retargeted audience language, proof emphasis, risk posture, "
            "and permitted vocabulary while preserving human gates, claim locks, and authority boundaries."
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
            "DIO does not merely generate copy. It recomposes market language under signal pressure, "
            "binding audience fit to evidence, risk, and permission boundaries."
        ),
        "",
        "## Required disclaimers",
        "",
        "- Internal controlled gauntlet evidence only.",
        "- Candidate adaptive-linguistic evidence, not external demand proof.",
        "- Not AGI.",
        "- Not commercial validation.",
        "- Not professional approval.",
        "- Not world-first status.",
        "- No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
        "",
        "## Forbidden claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in forbidden)
    path.write_text("\n".join(lines) + "\n")


def build_adaptive_linguistic_marketing_proof_pack(
    *,
    market_command_marketing_pack_path: Path,
    adaptive_linguistic_gauntlet_path: Path,
    output_dir: Path,
) -> AdaptiveLinguisticMarketingProofPackReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    market_pack = _load_json(market_command_marketing_pack_path)
    linguistic = _load_json(adaptive_linguistic_gauntlet_path)

    claims_path = output_dir / "adaptive_linguistic_marketing_proof_claims.json"
    copy_path = output_dir / "adaptive_linguistic_marketing_safe_copy.md"
    receipt_path = output_dir / "adaptive_linguistic_marketing_proof_pack_receipt.json"

    market_ready = (
        market_pack.get("status") == "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_READY"
        and market_pack.get("market_pivot_marketing_language_authorized") is True
        and market_pack.get("adaptive_claim_authorized") is True
        and market_pack.get("commercial_validation_claim_authorized") is False
        and market_pack.get("world_first_claim_authorized") is False
        and market_pack.get("agi_claim_authorized") is False
        and market_pack.get("authority_expansion_authorized") is False
    )
    linguistic_ready = (
        linguistic.get("status") == "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_PIVOT_GAUNTLET_READY"
        and linguistic.get("adaptive_linguistic_evidence") is True
        and linguistic.get("linguistic_pivot_claim_authorized") is True
        and linguistic.get("adaptive_claim_authorized") is True
        and float(linguistic.get("adaptive_linguistic_minus_static_effect", 0.0)) >= float(linguistic.get("minimum_linguistic_pivot_effect", 1.0))
        and float(linguistic.get("adaptive_linguistic_pivot_mean_score", 0.0)) >= float(linguistic.get("minimum_adaptive_linguistic_score", 1.0))
        and linguistic.get("commercial_validation_claim_authorized") is False
        and linguistic.get("world_first_claim_authorized") is False
        and linguistic.get("agi_claim_authorized") is False
        and linguistic.get("authority_expansion_authorized") is False
    )
    ready = market_ready and linguistic_ready

    forbidden = _forbidden_claims()
    allowed = _allowed_claims(linguistic) if ready else []
    tier = "T8_MARKETING_SAFE_ADAPTIVE_LINGUISTIC_MARKET_RECOMPOSITION" if ready else "T0_NO_ADAPTIVE_LINGUISTIC_MARKETING_CLAIM"

    claims = {
        "pack_version": ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_VERSION,
        "marketing_claim_tier": tier,
        "allowed_public_claims": allowed,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "T8 is candidate adaptive-linguistic market recomposition evidence, not external demand proof.",
            "No commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claim, autonomous action, or authority expansion is authorized.",
        ],
        "proof_numbers": {
            "audience_shifts_processed": int(linguistic.get("audience_shifts_processed", 0)),
            "linguistic_pivots_executed": int(linguistic.get("linguistic_pivots_executed", 0)),
            "static_linguistic_baseline_mean_score": float(linguistic.get("static_linguistic_baseline_mean_score", 0.0)),
            "adaptive_linguistic_pivot_mean_score": float(linguistic.get("adaptive_linguistic_pivot_mean_score", 0.0)),
            "adaptive_linguistic_minus_static_effect": float(linguistic.get("adaptive_linguistic_minus_static_effect", 0.0)),
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
        _write_markdown(copy_path, allowed, forbidden)
    else:
        copy_path.write_text(
            "# DIO Adaptive Linguistic Marketing Proof Pack\n\n"
            "Adaptive linguistic marketing language refused because the required T7/T8 evidence receipts were not ready.\n"
        )

    receipt = AdaptiveLinguisticMarketingProofPackReceipt(
        pack_version=ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_VERSION,
        status=ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY_TOKEN if ready else ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_REFUSED_TOKEN,
        market_command_marketing_pack_status=str(market_pack.get("status")),
        adaptive_linguistic_gauntlet_status=str(linguistic.get("status")),
        marketing_claim_tier=tier,
        linguistic_marketing_language_authorized=ready,
        adaptive_claim_authorized=ready,
        audience_shifts_processed=int(linguistic.get("audience_shifts_processed", 0)) if ready else 0,
        linguistic_pivots_executed=int(linguistic.get("linguistic_pivots_executed", 0)) if ready else 0,
        static_linguistic_baseline_mean_score=float(linguistic.get("static_linguistic_baseline_mean_score", 0.0)) if ready else 0.0,
        adaptive_linguistic_pivot_mean_score=float(linguistic.get("adaptive_linguistic_pivot_mean_score", 0.0)) if ready else 0.0,
        adaptive_linguistic_minus_static_effect=float(linguistic.get("adaptive_linguistic_minus_static_effect", 0.0)) if ready else 0.0,
        minimum_linguistic_pivot_effect=float(linguistic.get("minimum_linguistic_pivot_effect", 0.0)) if ready else 0.0,
        minimum_adaptive_linguistic_score=float(linguistic.get("minimum_adaptive_linguistic_score", 0.0)) if ready else 0.0,
        allowed_public_claims_count=len(allowed),
        forbidden_public_claims_count=len(forbidden),
        linguistic_claims_path=str(claims_path),
        linguistic_copy_path=str(copy_path),
        market_command_marketing_pack_sha256=_sha256_path(market_command_marketing_pack_path),
        adaptive_linguistic_gauntlet_sha256=_sha256_path(adaptive_linguistic_gauntlet_path),
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
            "This adaptive linguistic marketing proof pack converts T8 candidate linguistic pivot evidence into bounded, "
            "marketing-safe language. It authorizes only proof-bound public wording about internal controlled adaptive "
            "linguistic market recomposition and never authorizes commercial validation, professional approval, publication, "
            "spend, fulfilment, world-first status, AGI claims, autonomous consequential action, manipulation claims, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
