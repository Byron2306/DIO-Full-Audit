from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_MARKETING_PROOF_PACK_READY"
REQUIRED_STARTER_CODE_STATUS = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_GENERATION_READY"
PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_MARKETING_PROOF_PACK_V1"
MARKETING_CLAIM_TIER = "T16_MARKETING_SAFE_CONTROLLED_LOCAL_STARTER_CODE_GENERATION"


@dataclass(frozen=True)
class ControlledStarterCodeMarketingProofPackReceipt:
    status: str
    pack_version: str
    marketing_claim_tier: str
    controlled_starter_code_generation_status: str
    controlled_starter_code_generation_sha256: str
    selected_product: str
    source_files_written: int
    test_files_written: int
    receipt_schema_files_written: int
    readmes_written: int
    static_code_baseline_mean_score: float
    controlled_starter_code_mean_score: float
    controlled_starter_code_minus_static_effect: float
    controlled_starter_code_generation_evidence: bool
    starter_code_marketing_language_authorized: bool
    local_starter_code_generation_claim_authorized: bool
    starter_code_claim_authorized: bool
    starter_code_written: bool
    product_capability_execution_authorized: bool
    actual_execution_authorized: bool
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
    starter_code_claims_path: str
    starter_code_copy_path: str


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


def _approved_claims(starter: dict[str, Any]) -> list[str]:
    selected_product = str(starter.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    source_count = int(starter.get("source_files_written", 0))
    test_count = int(starter.get("test_files_written", 0))
    receipt_count = int(starter.get("receipt_schema_files_written", 0))
    readme_count = int(starter.get("readmes_written", 0))
    score = float(starter.get("controlled_starter_code_mean_score", 0.0))
    baseline = float(starter.get("static_code_baseline_mean_score", 0.0))
    effect = float(starter.get("controlled_starter_code_minus_static_effect", 0.0))
    return [
        "DIO produced T16 candidate evidence of controlled local starter-code generation in an internal controlled gauntlet.",
        f"DIO generated local starter-code files for {selected_product} under the tested harness.",
        f"The T16 gauntlet measured a controlled-starter-code minus static-code effect of {effect:.4f}.",
        f"The static code baseline scored {baseline:.4f}; the controlled starter-code route scored {score:.4f}.",
        f"DIO wrote {source_count} source files, {test_count} test file, {receipt_count} receipt schema file, and {readme_count} README for {selected_product}.",
        "The T16 evidence supports bounded language about controlled local starter-code generation, not product capability execution, autonomous development, product-market fit, or commercial validation.",
        "The starter-code signal preserved human gates and blocked actual-execution, product-capability-execution, AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _forbidden_claims() -> list[str]:
    return [
        "DIO executed selected-product capabilities",
        "DIO completed a production implementation",
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees viable products, sales, revenue, or buyer outcomes",
        "DIO can autonomously build, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO has world-first status",
        "DIO may expand its own authority from starter-code evidence",
        "DIO can skip human review because starter code was generated",
    ]


def _copy(starter: dict[str, Any], approved: list[str], forbidden: list[str]) -> str:
    selected_product = str(starter.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    source_count = int(starter.get("source_files_written", 0))
    test_count = int(starter.get("test_files_written", 0))
    receipt_count = int(starter.get("receipt_schema_files_written", 0))
    readme_count = int(starter.get("readmes_written", 0))
    baseline = float(starter.get("static_code_baseline_mean_score", 0.0))
    score = float(starter.get("controlled_starter_code_mean_score", 0.0))
    effect = float(starter.get("controlled_starter_code_minus_static_effect", 0.0))
    approved_md = "\n".join(f"- {claim}" for claim in approved)
    forbidden_md = "\n".join(f"- {claim}" for claim in forbidden)
    return f"""# DIO Controlled Local Starter-Code Marketing Proof Pack

## Marketing-safe claim

DIO has internal controlled T16 candidate evidence of controlled local starter-code generation: it generated local starter-code files for {selected_product} while preserving the boundary that starter code is not product capability execution, autonomous development, product-market fit, commercial validation, or external deployment.

## Approved language

{approved_md}

## Positioning line

DIO does not merely rehearse implementation. It can generate a local, receipt-bound starter-code scaffold while keeping product capability execution and external action unauthorized.

## Proof numbers

- Static code baseline: {baseline:.4f}
- Controlled starter-code score: {score:.4f}
- Controlled starter-code minus static effect: {effect:.4f}
- Source files written: {source_count}
- Test files written: {test_count}
- Receipt schema files written: {receipt_count}
- READMEs written: {readme_count}

## Required disclaimers

- Internal controlled gauntlet evidence only.
- Candidate starter-code generation evidence, not product capability execution.
- No actual execution.
- Not product capability execution.
- Not autonomous development.
- Not production implementation.
- Not product-market fit.
- Not commercial validation.
- Not AGI.
- Not professional approval.
- Not world-first status.
- No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.

## Forbidden claims

{forbidden_md}
"""


def build_controlled_starter_code_marketing_proof_pack(
    controlled_starter_code_generation: Path,
    output_dir: Path,
) -> ControlledStarterCodeMarketingProofPackReceipt:
    starter = _load_json(controlled_starter_code_generation)
    if starter.get("status") != REQUIRED_STARTER_CODE_STATUS:
        raise ValueError(
            "expected controlled starter code generation receipt status "
            f"{REQUIRED_STARTER_CODE_STATUS}, got {starter.get('status')!r}"
        )
    if bool(starter.get("actual_execution_authorized", True)):
        raise ValueError("starter code generation receipt must keep actual execution unauthorized")
    if bool(starter.get("product_capability_execution_authorized", True)):
        raise ValueError("starter code generation receipt must keep product capability execution unauthorized")

    approved = _approved_claims(starter)
    forbidden = _forbidden_claims()
    claims_path = output_dir / "controlled_starter_code_marketing_proof_claims.json"
    copy_path = output_dir / "controlled_starter_code_marketing_safe_copy.md"
    receipt_path = output_dir / "controlled_starter_code_marketing_proof_pack_receipt.json"

    claims_payload = {
        "marketing_claim_tier": MARKETING_CLAIM_TIER,
        "approved_public_claims": approved,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "Candidate starter-code generation evidence, not product capability execution.",
            "No actual execution.",
            "Not product capability execution.",
            "Not autonomous development.",
            "Not production implementation.",
            "Not product-market fit.",
            "Not commercial validation.",
            "Not AGI.",
            "Not professional approval.",
            "Not world-first status.",
            "No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
        ],
    }
    _write_json(claims_path, claims_payload)
    _write_markdown(copy_path, _copy(starter, approved, forbidden))

    receipt = ControlledStarterCodeMarketingProofPackReceipt(
        status=READY_TOKEN,
        pack_version=PACK_VERSION,
        marketing_claim_tier=MARKETING_CLAIM_TIER,
        controlled_starter_code_generation_status=str(starter.get("status")),
        controlled_starter_code_generation_sha256=_sha256_path(controlled_starter_code_generation),
        selected_product=str(starter.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO")),
        source_files_written=int(starter.get("source_files_written", 0)),
        test_files_written=int(starter.get("test_files_written", 0)),
        receipt_schema_files_written=int(starter.get("receipt_schema_files_written", 0)),
        readmes_written=int(starter.get("readmes_written", 0)),
        static_code_baseline_mean_score=float(starter.get("static_code_baseline_mean_score", 0.0)),
        controlled_starter_code_mean_score=float(starter.get("controlled_starter_code_mean_score", 0.0)),
        controlled_starter_code_minus_static_effect=float(starter.get("controlled_starter_code_minus_static_effect", 0.0)),
        controlled_starter_code_generation_evidence=bool(starter.get("controlled_starter_code_generation_evidence", False)),
        starter_code_marketing_language_authorized=True,
        local_starter_code_generation_claim_authorized=bool(starter.get("local_starter_code_generation_claim_authorized", False)),
        starter_code_claim_authorized=bool(starter.get("starter_code_claim_authorized", False)),
        starter_code_written=bool(starter.get("starter_code_written", False)),
        product_capability_execution_authorized=False,
        actual_execution_authorized=False,
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
        boundary="This controlled starter-code marketing proof pack converts T16 candidate starter-code generation evidence into bounded, marketing-safe language. It authorizes only proof-bound public wording about internal controlled local starter-code generation and never authorizes product capability execution, actual execution, autonomous development, production implementation, product-market fit, commercial validation, publication, spend, fulfilment, world-first status, AGI claims, or authority expansion.",
        starter_code_claims_path=str(claims_path),
        starter_code_copy_path=str(copy_path),
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
