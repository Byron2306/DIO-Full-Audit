from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_MARKETING_PROOF_PACK_READY"
PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_MARKETING_PROOF_PACK_V1"
EXPECTED_SPRINT_STATUS = "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_PLANNING_GAUNTLET_READY"
MARKETING_CLAIM_TIER = "T13_MARKETING_SAFE_SELECTED_PRODUCT_SPRINT_PLANNING"


@dataclass(frozen=True)
class SelectedProductSprintMarketingProofPackReceipt:
    status: str
    pack_version: str
    marketing_claim_tier: str
    selected_product_sprint_planning_status: str
    selected_product_sprint_planning_sha256: str
    selected_product: str
    work_packages_planned: int
    acceptance_gates_planned: int
    evidence_receipts_planned: int
    static_sprint_baseline_mean_score: float
    governed_sprint_plan_mean_score: float
    governed_sprint_minus_static_effect: float
    selected_product_sprint_planning_evidence: bool
    sprint_planning_claim_authorized: bool
    selected_product_sprint_marketing_language_authorized: bool
    adaptive_claim_authorized: bool
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    boundary: str
    sprint_marketing_claims_path: str
    sprint_marketing_copy_path: str
    autonomous_development_authorized: bool
    autonomous_action_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    professional_approval_claim_authorized: bool
    world_first_claim_authorized: bool
    agi_claim_authorized: bool
    authority_expansion_authorized: bool


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_bool(receipt: dict[str, Any], key: str, expected: bool) -> None:
    actual = receipt.get(key)
    if actual is not expected:
        raise ValueError(f"expected {key} to be {expected}, got {actual!r}")


def _validate_sprint_receipt(receipt: dict[str, Any]) -> None:
    status = receipt.get("status")
    if status != EXPECTED_SPRINT_STATUS:
        raise ValueError(f"unexpected sprint planning status: {status!r}")

    _required_bool(receipt, "selected_product_sprint_planning_evidence", True)
    _required_bool(receipt, "sprint_planning_claim_authorized", True)
    _required_bool(receipt, "adaptive_claim_authorized", True)

    for lock in (
        "autonomous_development_authorized",
        "autonomous_action_claim_authorized",
        "commercial_validation_claim_authorized",
        "product_market_fit_claim_authorized",
        "publication_authorized",
        "spend_authorized",
        "fulfilment_authorized",
        "professional_approval_claim_authorized",
        "world_first_claim_authorized",
        "agi_claim_authorized",
        "authority_expansion_authorized",
    ):
        _required_bool(receipt, lock, False)


def _claims(receipt: dict[str, Any]) -> dict[str, Any]:
    selected_product = receipt["selected_product"]
    approved_claims = [
        "DIO produced T13 candidate evidence of selected-product sprint planning in an internal controlled gauntlet.",
        f"DIO selected {selected_product} and converted it into a governed local sprint plan under the tested harness.",
        f"The T13 gauntlet measured a governed-sprint minus static-sprint effect of {receipt['governed_sprint_minus_static_effect']:.4f}.",
        f"The static sprint baseline scored {receipt['static_sprint_baseline_mean_score']:.4f}; the governed sprint route scored {receipt['governed_sprint_plan_mean_score']:.4f}.",
        f"DIO planned {receipt['work_packages_planned']} work packages, {receipt['acceptance_gates_planned']} acceptance gates, and {receipt['evidence_receipts_planned']} evidence receipts for {selected_product}.",
        "The T13 evidence supports bounded language about governed sprint planning, not autonomous development, product-market fit, or commercial validation.",
        "The sprint-planning signal preserved human gates and blocked AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]
    forbidden_claims = [
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees viable products, sales, revenue, or buyer outcomes",
        "DIO can autonomously build, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO is enterprise-proven",
        "DIO has world-first status",
        "DIO may expand its own authority from sprint-planning evidence",
        "DIO's internal sprint-planning evidence equals external demand proof",
        "DIO can skip human review because a sprint plan scored well",
    ]
    return {
        "marketing_safe_claim": (
            "DIO has internal controlled T13 candidate evidence of selected-product sprint planning: "
            f"it converted {selected_product}, the governed next-build candidate, into a local sprint plan "
            "with work packages, acceptance gates, evidence receipts, and human gates while preserving claim locks."
        ),
        "approved_claims": approved_claims,
        "forbidden_claims": forbidden_claims,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "Candidate sprint-planning evidence, not external demand proof.",
            "Not product-market fit.",
            "Not commercial validation.",
            "Not autonomous development.",
            "Not AGI.",
            "Not professional approval.",
            "Not world-first status.",
            "No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
        ],
        "positioning_line": (
            "DIO does not merely rank product candidates. It can convert the selected candidate into "
            "a governed sprint plan with work packages, acceptance gates, evidence receipts, and permission boundaries."
        ),
        "proof_numbers": {
            "static_sprint_baseline": receipt["static_sprint_baseline_mean_score"],
            "governed_sprint_score": receipt["governed_sprint_plan_mean_score"],
            "governed_sprint_minus_static_effect": receipt["governed_sprint_minus_static_effect"],
            "work_packages_planned": receipt["work_packages_planned"],
            "acceptance_gates_planned": receipt["acceptance_gates_planned"],
            "evidence_receipts_planned": receipt["evidence_receipts_planned"],
        },
    }


def _write_markdown(path: Path, claims: dict[str, Any]) -> None:
    proof = claims["proof_numbers"]
    lines = [
        "# DIO Selected Product Sprint Marketing Proof Pack",
        "",
        "## Marketing-safe claim",
        "",
        claims["marketing_safe_claim"],
        "",
        "## Approved language",
        "",
    ]
    lines.extend(f"- {claim}" for claim in claims["approved_claims"])
    lines.extend([
        "",
        "## Positioning line",
        "",
        claims["positioning_line"],
        "",
        "## Proof numbers",
        "",
        f"- Static sprint baseline: {proof['static_sprint_baseline']:.4f}",
        f"- Governed sprint score: {proof['governed_sprint_score']:.4f}",
        f"- Governed sprint minus static effect: {proof['governed_sprint_minus_static_effect']:.4f}",
        f"- Work packages planned: {proof['work_packages_planned']}",
        f"- Acceptance gates planned: {proof['acceptance_gates_planned']}",
        f"- Evidence receipts planned: {proof['evidence_receipts_planned']}",
        "",
        "## Required disclaimers",
        "",
    ])
    lines.extend(f"- {claim}" for claim in claims["required_disclaimers"])
    lines.extend(["", "## Forbidden claims", ""])
    lines.extend(f"- {claim}" for claim in claims["forbidden_claims"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_selected_product_sprint_marketing_proof_pack(
    selected_product_sprint_planning: str | Path,
    output_dir: str | Path,
) -> SelectedProductSprintMarketingProofPackReceipt:
    sprint_path = Path(selected_product_sprint_planning)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    sprint_receipt = _load_json(sprint_path)
    _validate_sprint_receipt(sprint_receipt)

    claims = _claims(sprint_receipt)
    claims_path = out / "selected_product_sprint_marketing_proof_claims.json"
    copy_path = out / "selected_product_sprint_marketing_safe_copy.md"
    receipt_path = out / "selected_product_sprint_marketing_proof_pack_receipt.json"

    _write_json(claims_path, claims)
    _write_markdown(copy_path, claims)

    receipt = SelectedProductSprintMarketingProofPackReceipt(
        status=READY_TOKEN,
        pack_version=PACK_VERSION,
        marketing_claim_tier=MARKETING_CLAIM_TIER,
        selected_product_sprint_planning_status=sprint_receipt["status"],
        selected_product_sprint_planning_sha256=_sha256_path(sprint_path),
        selected_product=sprint_receipt["selected_product"],
        work_packages_planned=int(sprint_receipt["work_packages_planned"]),
        acceptance_gates_planned=int(sprint_receipt["acceptance_gates_planned"]),
        evidence_receipts_planned=int(sprint_receipt["evidence_receipts_planned"]),
        static_sprint_baseline_mean_score=float(sprint_receipt["static_sprint_baseline_mean_score"]),
        governed_sprint_plan_mean_score=float(sprint_receipt["governed_sprint_plan_mean_score"]),
        governed_sprint_minus_static_effect=float(sprint_receipt["governed_sprint_minus_static_effect"]),
        selected_product_sprint_planning_evidence=True,
        sprint_planning_claim_authorized=True,
        selected_product_sprint_marketing_language_authorized=True,
        adaptive_claim_authorized=True,
        allowed_public_claims_count=len(claims["approved_claims"]),
        forbidden_public_claims_count=len(claims["forbidden_claims"]),
        boundary=(
            "This selected product sprint marketing proof pack converts T13 candidate sprint-planning evidence "
            "into bounded, marketing-safe language. It authorizes only proof-bound public wording about internal "
            "controlled selected-product sprint planning and never authorizes autonomous development, product-market "
            "fit, commercial validation, professional approval, publication, spend, fulfilment, world-first status, "
            "AGI claims, autonomous consequential action, or authority expansion."
        ),
        sprint_marketing_claims_path=str(claims_path),
        sprint_marketing_copy_path=str(copy_path),
        autonomous_development_authorized=False,
        autonomous_action_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        professional_approval_claim_authorized=False,
        world_first_claim_authorized=False,
        agi_claim_authorized=False,
        authority_expansion_authorized=False,
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
