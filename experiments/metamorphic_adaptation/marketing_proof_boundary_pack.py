from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


MARKETING_PROOF_BOUNDARY_PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_V1"
MARKETING_PROOF_BOUNDARY_PACK_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_READY"
MARKETING_PROOF_BOUNDARY_PACK_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_MARKETING_PROOF_BOUNDARY_PACK_REFUSED"


@dataclass(frozen=True)
class MarketingProofBoundaryPackReceipt:
    pack_version: str
    status: str
    ecosystem_adaptation_digest_status: str
    sequential_retained_gauntlet_status: str
    marketing_claim_tier: str
    bounded_marketing_language_authorized: bool
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
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    marketing_claims_path: str
    marketing_copy_path: str
    ecosystem_adaptation_digest_sha256: str
    sequential_retained_gauntlet_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base_forbidden_claims() -> list[str]:
    return [
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO is commercially validated",
        "DIO is enterprise-proven",
        "DIO is professionally approved",
        "DIO is legally or medically authorized",
        "DIO can autonomously execute consequential external actions",
        "DIO guarantees buyer outcomes",
        "DIO guarantees profit or revenue",
        "DIO has world-first status",
        "DIO may publish, spend, fulfil, or contact externally without a human gate",
        "DIO can expand its own authority from adaptive evidence",
    ]


def _allowed_claims(ecosystem: dict, retained: dict) -> list[str]:
    return [
        "DIO demonstrated bounded ecosystem adaptive evidence in an internal controlled gauntlet.",
        "Full ecosystem orchestration outperformed DIO core-only on organ-dependent tasks in the tested harness.",
        (
            "The T5 ecosystem gauntlet measured a full-minus-baseline effect of "
            f"{float(ecosystem.get('full_minus_baseline_effect', 0.0)):.3f}."
        ),
        (
            "DIO produced T6 candidate retained ecosystem adaptation evidence across three sequential "
            "encounters under controlled harness conditions."
        ),
        (
            "The T6 candidate gauntlet improved from encounter 1 mean "
            f"{float(retained.get('encounter_1_mean_score', 0.0)):.2f} to encounter 3 mean "
            f"{float(retained.get('encounter_3_mean_score', 0.0)):.2f}."
        ),
        "The retained-adaptation signal was produced without code-change authorization between encounters.",
        "All marketing language remains bounded to internal controlled evidence and does not imply commercial validation.",
    ]


def _write_marketing_copy(path: Path, allowed_claims: list[str], forbidden_claims: list[str]) -> None:
    lines = [
        "# DIO Marketing Proof Boundary Pack",
        "",
        "## Marketing-safe claim",
        "",
        (
            "DIO has internal controlled evidence of bounded ecosystem adaptation, plus T6 candidate "
            "evidence of retained ecosystem adaptation across sequential encounters."
        ),
        "",
        "## Approved language",
        "",
    ]
    lines.extend(f"- {claim}" for claim in allowed_claims)
    lines.extend([
        "",
        "## Required disclaimers",
        "",
        "- Internal controlled gauntlet evidence only.",
        "- Not AGI.",
        "- Not commercial validation.",
        "- Not professional approval.",
        "- Not world-first status.",
        "- No autonomous external action, spend, publication, fulfilment, or authority expansion.",
        "",
        "## Forbidden claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in forbidden_claims)
    path.write_text("\n".join(lines) + "\n")


def build_marketing_proof_boundary_pack(
    *,
    ecosystem_adaptation_digest_path: Path,
    sequential_retained_gauntlet_path: Path,
    output_dir: Path,
) -> MarketingProofBoundaryPackReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    ecosystem = _load_json(ecosystem_adaptation_digest_path)
    retained = _load_json(sequential_retained_gauntlet_path)

    claims_path = output_dir / "marketing_proof_boundary_claims.json"
    copy_path = output_dir / "marketing_safe_copy.md"
    receipt_path = output_dir / "marketing_proof_boundary_pack_receipt.json"

    ecosystem_ready = (
        ecosystem.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY"
        and ecosystem.get("real_ecosystem_adaptive_evidence") is True
        and ecosystem.get("adaptive_claim_authorized") is True
        and ecosystem.get("commercial_or_world_first_claim_authorized") is False
        and ecosystem.get("professional_approval_claim_authorized") is False
        and ecosystem.get("authority_expansion_authorized") is False
    )
    retained_ready = (
        retained.get("status") == "DIO_METAMORPHIC_ADAPTATION_SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY"
        and retained.get("real_retained_adaptive_evidence") is True
        and retained.get("adaptive_claim_authorized") is True
        and retained.get("same_executor_across_encounters") is True
        and retained.get("code_change_between_encounters_authorized") is False
        and retained.get("commercial_or_world_first_claim_authorized") is False
        and retained.get("professional_approval_claim_authorized") is False
        and retained.get("authority_expansion_authorized") is False
    )
    ready = ecosystem_ready and retained_ready

    forbidden_claims = _base_forbidden_claims()
    allowed_claims = _allowed_claims(ecosystem, retained) if ready else []

    if ready:
        claims = {
            "pack_version": MARKETING_PROOF_BOUNDARY_PACK_VERSION,
            "marketing_claim_tier": "T6_MARKETING_SAFE_CANDIDATE_RETAINED_ECOSYSTEM_ADAPTATION",
            "allowed_public_claims": allowed_claims,
            "forbidden_public_claims": forbidden_claims,
            "required_disclaimers": [
                "Internal controlled gauntlet evidence only.",
                "T6 is candidate retained-adaptation evidence, not external validation.",
                "No commercial validation, professional approval, world-first status, or authority expansion is authorized.",
            ],
            "proof_numbers": {
                "t5_baseline_arm_mean": float(ecosystem.get("baseline_arm_mean", 0.0)),
                "t5_full_arm_mean": float(ecosystem.get("full_arm_mean", 0.0)),
                "t5_full_minus_baseline_effect": float(ecosystem.get("full_minus_baseline_effect", 0.0)),
                "t6_encounter_1_mean_score": float(retained.get("encounter_1_mean_score", 0.0)),
                "t6_encounter_2_mean_score": float(retained.get("encounter_2_mean_score", 0.0)),
                "t6_encounter_3_mean_score": float(retained.get("encounter_3_mean_score", 0.0)),
                "t6_encounter_3_minus_encounter_1_effect": float(retained.get("encounter_3_minus_encounter_1_effect", 0.0)),
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
        _write_marketing_copy(copy_path, allowed_claims, forbidden_claims)
        status = MARKETING_PROOF_BOUNDARY_PACK_READY_TOKEN
        tier = "T6_MARKETING_SAFE_CANDIDATE_RETAINED_ECOSYSTEM_ADAPTATION"
        bounded_marketing_language_authorized = True
        adaptive_claim_authorized = True
    else:
        claims_path.write_text(json.dumps({
            "pack_version": MARKETING_PROOF_BOUNDARY_PACK_VERSION,
            "marketing_claim_tier": "T0_NO_MARKETING_PROOF_CLAIM",
            "allowed_public_claims": [],
            "forbidden_public_claims": forbidden_claims,
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
        }, indent=2, sort_keys=True) + "\n")
        copy_path.write_text(
            "# DIO Marketing Proof Boundary Pack\n\n"
            "Marketing proof language refused because the required T5/T6 evidence receipts were not ready.\n"
        )
        status = MARKETING_PROOF_BOUNDARY_PACK_REFUSED_TOKEN
        tier = "T0_NO_MARKETING_PROOF_CLAIM"
        bounded_marketing_language_authorized = False
        adaptive_claim_authorized = False

    receipt = MarketingProofBoundaryPackReceipt(
        pack_version=MARKETING_PROOF_BOUNDARY_PACK_VERSION,
        status=status,
        ecosystem_adaptation_digest_status=str(ecosystem.get("status")),
        sequential_retained_gauntlet_status=str(retained.get("status")),
        marketing_claim_tier=tier,
        bounded_marketing_language_authorized=bounded_marketing_language_authorized,
        adaptive_claim_authorized=adaptive_claim_authorized,
        commercial_validation_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        autonomous_action_claim_authorized=False,
        authority_expansion_authorized=False,
        allowed_public_claims_count=len(allowed_claims),
        forbidden_public_claims_count=len(forbidden_claims),
        marketing_claims_path=str(claims_path),
        marketing_copy_path=str(copy_path),
        ecosystem_adaptation_digest_sha256=_sha256_path(ecosystem_adaptation_digest_path),
        sequential_retained_gauntlet_sha256=_sha256_path(sequential_retained_gauntlet_path),
        boundary=(
            "This marketing proof boundary pack converts T5/T6 internal controlled evidence into bounded, "
            "marketing-safe language. It authorizes only proof-bound public wording and never authorizes "
            "commercial validation, professional approval, publication, spend, fulfilment, world-first status, "
            "AGI claims, autonomous consequential action, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
