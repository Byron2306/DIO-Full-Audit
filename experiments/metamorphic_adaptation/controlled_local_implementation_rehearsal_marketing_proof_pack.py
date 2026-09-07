from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_MARKETING_PROOF_PACK_READY"
REQUIRED_REHEARSAL_STATUS = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_READY"
PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_MARKETING_PROOF_PACK_V1"
MARKETING_CLAIM_TIER = "T14_MARKETING_SAFE_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL"


@dataclass(frozen=True)
class ControlledImplementationRehearsalMarketingProofPackReceipt:
    status: str
    pack_version: str
    marketing_claim_tier: str
    controlled_local_implementation_rehearsal_status: str
    controlled_local_implementation_rehearsal_sha256: str
    selected_product: str
    modules_rehearsed: int
    test_skeletons_rehearsed: int
    receipt_schemas_rehearsed: int
    acceptance_gate_bindings_rehearsed: int
    controlled_rehearsal_mean_score: float
    static_implementation_baseline_mean_score: float
    controlled_rehearsal_minus_static_effect: float
    implementation_rehearsal_evidence: bool
    implementation_rehearsal_marketing_language_authorized: bool
    local_implementation_rehearsal_claim_authorized: bool
    starter_code_claim_authorized: bool
    starter_code_written: bool
    adaptive_claim_authorized: bool
    autonomous_action_claim_authorized: bool
    autonomous_development_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    professional_approval_claim_authorized: bool
    agi_claim_authorized: bool
    world_first_claim_authorized: bool
    authority_expansion_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    allowed_public_claims_count: int
    forbidden_public_claims_count: int
    boundary: str
    implementation_rehearsal_claims_path: str
    implementation_rehearsal_copy_path: str


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _approved_claims(rehearsal: dict[str, Any]) -> list[str]:
    selected_product = str(rehearsal.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    effect = float(rehearsal.get("controlled_rehearsal_minus_static_effect", 0.0))
    baseline = float(rehearsal.get("static_implementation_baseline_mean_score", 0.0))
    score = float(rehearsal.get("controlled_rehearsal_mean_score", 0.0))
    modules = int(rehearsal.get("modules_rehearsed", 0))
    tests = int(rehearsal.get("test_skeletons_rehearsed", 0))
    receipts = int(rehearsal.get("receipt_schemas_rehearsed", 0))
    gates = int(rehearsal.get("acceptance_gate_bindings_rehearsed", 0))
    return [
        "DIO produced T14 candidate evidence of controlled local implementation rehearsal in an internal controlled gauntlet.",
        f"DIO converted the selected sprint plan for {selected_product} into a local implementation rehearsal packet under the tested harness.",
        f"The T14 gauntlet measured a controlled-rehearsal minus static-implementation effect of {effect:.4f}.",
        f"The static implementation baseline scored {baseline:.4f}; the controlled rehearsal route scored {score:.4f}.",
        f"DIO rehearsed {modules} module skeleton plans, {tests} test skeleton plans, {receipts} receipt schemas, and {gates} acceptance gate bindings.",
        "The T14 evidence supports bounded language about controlled implementation rehearsal, not starter code completion, autonomous development, product-market fit, or commercial validation.",
        "The implementation-rehearsal signal preserved human gates and blocked AGI, world-first, starter-code, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _forbidden_claims() -> list[str]:
    return [
        "DIO has completed starter code for this product",
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees viable products, sales, revenue, or buyer outcomes",
        "DIO can autonomously build, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO is enterprise-proven",
        "DIO has world-first status",
        "DIO may expand its own authority from implementation-rehearsal evidence",
        "DIO can skip human review because an implementation rehearsal scored well",
    ]


def _copy(rehearsal: dict[str, Any], approved: list[str], forbidden: list[str]) -> str:
    selected_product = str(rehearsal.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    modules = int(rehearsal.get("modules_rehearsed", 0))
    tests = int(rehearsal.get("test_skeletons_rehearsed", 0))
    receipts = int(rehearsal.get("receipt_schemas_rehearsed", 0))
    gates = int(rehearsal.get("acceptance_gate_bindings_rehearsed", 0))
    baseline = float(rehearsal.get("static_implementation_baseline_mean_score", 0.0))
    score = float(rehearsal.get("controlled_rehearsal_mean_score", 0.0))
    effect = float(rehearsal.get("controlled_rehearsal_minus_static_effect", 0.0))
    approved_md = "\n".join(f"- {claim}" for claim in approved)
    forbidden_md = "\n".join(f"- {claim}" for claim in forbidden)
    return f"""# DIO Controlled Local Implementation Rehearsal Marketing Proof Pack

## Marketing-safe claim

DIO has internal controlled T14 candidate evidence of controlled local implementation rehearsal: it converted the selected sprint plan for {selected_product} into a local rehearsal packet with module skeleton plans, test skeleton plans, receipt schemas, acceptance gate bindings, and a human approval checkpoint while preserving claim locks.

## Approved language

{approved_md}

## Positioning line

DIO does not merely plan a selected product sprint. It can rehearse the local implementation path for {selected_product} with module plans, test plans, receipt schemas, acceptance gates, and permission boundaries.

## Proof numbers

- Static implementation baseline: {baseline:.4f}
- Controlled rehearsal score: {score:.4f}
- Controlled rehearsal minus static effect: {effect:.4f}
- Module skeleton plans rehearsed: {modules}
- Test skeleton plans rehearsed: {tests}
- Receipt schemas rehearsed: {receipts}
- Acceptance gate bindings rehearsed: {gates}

## Required disclaimers

- Internal controlled gauntlet evidence only.
- Candidate implementation-rehearsal evidence, not starter code completion.
- Not product-market fit.
- Not commercial validation.
- No autonomous development.
- Not AGI.
- Not professional approval.
- Not world-first status.
- No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.

## Forbidden claims

{forbidden_md}
"""


def build_controlled_implementation_rehearsal_marketing_proof_pack(
    controlled_local_implementation_rehearsal: Path,
    output_dir: Path,
) -> ControlledImplementationRehearsalMarketingProofPackReceipt:
    rehearsal = _load_json(controlled_local_implementation_rehearsal)
    if rehearsal.get("status") != REQUIRED_REHEARSAL_STATUS:
        raise ValueError(
            "expected controlled local implementation rehearsal receipt status "
            f"{REQUIRED_REHEARSAL_STATUS}, got {rehearsal.get('status')!r}"
        )

    approved = _approved_claims(rehearsal)
    forbidden = _forbidden_claims()
    claims_path = output_dir / "controlled_local_implementation_rehearsal_marketing_proof_claims.json"
    copy_path = output_dir / "controlled_local_implementation_rehearsal_marketing_safe_copy.md"
    receipt_path = output_dir / "controlled_local_implementation_rehearsal_marketing_proof_pack_receipt.json"

    claims_payload = {
        "marketing_claim_tier": MARKETING_CLAIM_TIER,
        "approved_public_claims": approved,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "Candidate implementation-rehearsal evidence, not starter code completion.",
            "Not product-market fit.",
            "Not commercial validation.",
            "No autonomous development.",
            "Not AGI.",
            "Not professional approval.",
            "Not world-first status.",
            "No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
        ],
    }
    _write_json(claims_path, claims_payload)
    _write_markdown(copy_path, _copy(rehearsal, approved, forbidden))

    receipt = ControlledImplementationRehearsalMarketingProofPackReceipt(
        status=READY_TOKEN,
        pack_version=PACK_VERSION,
        marketing_claim_tier=MARKETING_CLAIM_TIER,
        controlled_local_implementation_rehearsal_status=str(rehearsal.get("status")),
        controlled_local_implementation_rehearsal_sha256=_sha256_path(controlled_local_implementation_rehearsal),
        selected_product=str(rehearsal.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO")),
        modules_rehearsed=int(rehearsal.get("modules_rehearsed", 0)),
        test_skeletons_rehearsed=int(rehearsal.get("test_skeletons_rehearsed", 0)),
        receipt_schemas_rehearsed=int(rehearsal.get("receipt_schemas_rehearsed", 0)),
        acceptance_gate_bindings_rehearsed=int(rehearsal.get("acceptance_gate_bindings_rehearsed", 0)),
        controlled_rehearsal_mean_score=float(rehearsal.get("controlled_rehearsal_mean_score", 0.0)),
        static_implementation_baseline_mean_score=float(rehearsal.get("static_implementation_baseline_mean_score", 0.0)),
        controlled_rehearsal_minus_static_effect=float(rehearsal.get("controlled_rehearsal_minus_static_effect", 0.0)),
        implementation_rehearsal_evidence=bool(rehearsal.get("implementation_rehearsal_evidence", False)),
        implementation_rehearsal_marketing_language_authorized=True,
        local_implementation_rehearsal_claim_authorized=bool(rehearsal.get("local_implementation_rehearsal_claim_authorized", False)),
        starter_code_claim_authorized=False,
        starter_code_written=False,
        adaptive_claim_authorized=True,
        autonomous_action_claim_authorized=False,
        autonomous_development_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        professional_approval_claim_authorized=False,
        agi_claim_authorized=False,
        world_first_claim_authorized=False,
        authority_expansion_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        allowed_public_claims_count=len(approved),
        forbidden_public_claims_count=len(forbidden),
        boundary="This controlled local implementation rehearsal marketing proof pack converts T14 candidate implementation-rehearsal evidence into bounded, marketing-safe language. It authorizes only proof-bound public wording about internal controlled local implementation rehearsal and never authorizes starter code completion, autonomous development, product-market fit, commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claims, autonomous consequential action, or authority expansion.",
        implementation_rehearsal_claims_path=str(claims_path),
        implementation_rehearsal_copy_path=str(copy_path),
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
