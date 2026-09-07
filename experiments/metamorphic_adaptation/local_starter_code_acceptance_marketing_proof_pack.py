from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_MARKETING_PROOF_PACK_READY"
REQUIRED_ACCEPTANCE_STATUS = "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_READY"
PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_MARKETING_PROOF_PACK_V1"
MARKETING_CLAIM_TIER = "T17_MARKETING_SAFE_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION"


@dataclass(frozen=True)
class LocalStarterCodeAcceptanceMarketingProofPackReceipt:
    status: str
    pack_version: str
    marketing_claim_tier: str
    local_starter_code_acceptance_status: str
    local_starter_code_acceptance_sha256: str
    selected_product: str
    files_inspected: int
    source_files_verified: int
    test_files_verified: int
    receipt_schema_files_verified: int
    readmes_verified: int
    acceptance_tests_discovered: int
    acceptance_tests_passed: bool
    pytest_exit_code: int
    starter_code_acceptance_verified: bool
    local_acceptance_verification_mean_score: float
    static_acceptance_baseline_mean_score: float
    local_acceptance_minus_static_effect: float
    starter_code_acceptance_marketing_language_authorized: bool
    starter_code_acceptance_verification_claim_authorized: bool
    starter_code_claim_authorized: bool
    actual_product_execution_authorized: bool
    product_capability_execution_authorized: bool
    external_use_authorized: bool
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
    acceptance_marketing_claims_path: str
    acceptance_marketing_copy_path: str


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


def _approved_claims(acceptance: dict[str, Any]) -> list[str]:
    selected_product = str(acceptance.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    files = int(acceptance.get("files_inspected", 0))
    sources = int(acceptance.get("source_files_verified", 0))
    tests = int(acceptance.get("test_files_verified", 0))
    schemas = int(acceptance.get("receipt_schema_files_verified", 0))
    discovered = int(acceptance.get("acceptance_tests_discovered", 0))
    pytest_exit_code = int(acceptance.get("pytest_exit_code", -1))
    effect = float(acceptance.get("local_acceptance_minus_static_effect", 0.0))
    baseline = float(acceptance.get("static_acceptance_baseline_mean_score", 0.0))
    score = float(acceptance.get("local_acceptance_verification_mean_score", 0.0))
    return [
        "DIO produced T17 candidate evidence of local starter-code acceptance verification in an internal controlled gauntlet.",
        f"DIO inspected {files} starter-code scaffold files for {selected_product} under the tested harness.",
        f"DIO verified {sources} source files, {tests} test file, and {schemas} receipt schema file in the starter scaffold.",
        f"DIO discovered {discovered} local acceptance tests and recorded pytest exit code {pytest_exit_code}.",
        f"The T17 gauntlet measured a local-acceptance minus static-acceptance effect of {effect:.4f}; the static baseline scored {baseline:.4f} and the local acceptance route scored {score:.4f}.",
        "The T17 evidence supports bounded language about local starter-code acceptance verification, not actual product execution, external use, autonomous development, product-market fit, or commercial validation.",
        "The acceptance-verification signal preserved human gates and blocked actual-execution, product-capability-execution, external-use, AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _forbidden_claims() -> list[str]:
    return [
        "DIO executed selected-product capabilities",
        "DIO externally used or deployed the starter product",
        "DIO completed a production implementation",
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees viable products, sales, revenue, or buyer outcomes",
        "DIO can autonomously build, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO has world-first status",
        "DIO can skip human review because local acceptance tests passed",
    ]


def _copy(acceptance: dict[str, Any], approved: list[str], forbidden: list[str]) -> str:
    selected_product = str(acceptance.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    files = int(acceptance.get("files_inspected", 0))
    sources = int(acceptance.get("source_files_verified", 0))
    tests = int(acceptance.get("test_files_verified", 0))
    schemas = int(acceptance.get("receipt_schema_files_verified", 0))
    readmes = int(acceptance.get("readmes_verified", 0))
    discovered = int(acceptance.get("acceptance_tests_discovered", 0))
    pytest_exit_code = int(acceptance.get("pytest_exit_code", -1))
    baseline = float(acceptance.get("static_acceptance_baseline_mean_score", 0.0))
    score = float(acceptance.get("local_acceptance_verification_mean_score", 0.0))
    effect = float(acceptance.get("local_acceptance_minus_static_effect", 0.0))
    approved_md = "\n".join(f"- {claim}" for claim in approved)
    forbidden_md = "\n".join(f"- {claim}" for claim in forbidden)
    return f"""# DIO Local Starter-Code Acceptance Marketing Proof Pack

## Marketing-safe claim

DIO has internal controlled T17 candidate evidence of local starter-code acceptance verification: it inspected the generated starter-code scaffold for {selected_product}, verified the file manifest, ran local acceptance tests, and recorded pytest exit code {pytest_exit_code} while preserving the boundary that acceptance verification is not actual product execution, external use, product-market fit, commercial validation, or deployment.

## Approved language

{approved_md}

## Positioning line

DIO does not merely generate starter code. It can locally verify the generated scaffold against acceptance tests and receipt boundaries while keeping product capability execution and external use unauthorized.

## Proof numbers

- Static acceptance baseline: {baseline:.4f}
- Local acceptance verification score: {score:.4f}
- Local acceptance minus static effect: {effect:.4f}
- Files inspected: {files}
- Source files verified: {sources}
- Test files verified: {tests}
- Receipt schema files verified: {schemas}
- READMEs verified: {readmes}
- Acceptance tests discovered: {discovered}
- Pytest exit code: {pytest_exit_code}

## Required disclaimers

- Internal controlled gauntlet evidence only.
- Candidate local starter-code acceptance verification evidence, not product capability execution.
- No actual product execution.
- No external use.
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


def build_local_starter_code_acceptance_marketing_proof_pack(
    local_starter_code_acceptance_verification: Path,
    output_dir: Path,
) -> LocalStarterCodeAcceptanceMarketingProofPackReceipt:
    acceptance = _load_json(local_starter_code_acceptance_verification)
    if acceptance.get("status") != REQUIRED_ACCEPTANCE_STATUS:
        raise ValueError(
            "expected local starter code acceptance verification receipt status "
            f"{REQUIRED_ACCEPTANCE_STATUS}, got {acceptance.get('status')!r}"
        )

    approved = _approved_claims(acceptance)
    forbidden = _forbidden_claims()
    claims_path = output_dir / "local_starter_code_acceptance_marketing_proof_claims.json"
    copy_path = output_dir / "local_starter_code_acceptance_marketing_safe_copy.md"
    receipt_path = output_dir / "local_starter_code_acceptance_marketing_proof_pack_receipt.json"

    claims_payload = {
        "marketing_claim_tier": MARKETING_CLAIM_TIER,
        "approved_public_claims": approved,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": [
            "Internal controlled gauntlet evidence only.",
            "Candidate local starter-code acceptance verification evidence, not product capability execution.",
            "No actual product execution.",
            "No external use.",
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
    _write_markdown(copy_path, _copy(acceptance, approved, forbidden))

    receipt = LocalStarterCodeAcceptanceMarketingProofPackReceipt(
        status=READY_TOKEN,
        pack_version=PACK_VERSION,
        marketing_claim_tier=MARKETING_CLAIM_TIER,
        local_starter_code_acceptance_status=str(acceptance.get("status")),
        local_starter_code_acceptance_sha256=_sha256_path(local_starter_code_acceptance_verification),
        selected_product=str(acceptance.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO")),
        files_inspected=int(acceptance.get("files_inspected", 0)),
        source_files_verified=int(acceptance.get("source_files_verified", 0)),
        test_files_verified=int(acceptance.get("test_files_verified", 0)),
        receipt_schema_files_verified=int(acceptance.get("receipt_schema_files_verified", 0)),
        readmes_verified=int(acceptance.get("readmes_verified", 0)),
        acceptance_tests_discovered=int(acceptance.get("acceptance_tests_discovered", 0)),
        acceptance_tests_passed=bool(acceptance.get("acceptance_tests_passed", False)),
        pytest_exit_code=int(acceptance.get("pytest_exit_code", -1)),
        starter_code_acceptance_verified=bool(acceptance.get("starter_code_acceptance_verified", False)),
        local_acceptance_verification_mean_score=float(acceptance.get("local_acceptance_verification_mean_score", 0.0)),
        static_acceptance_baseline_mean_score=float(acceptance.get("static_acceptance_baseline_mean_score", 0.0)),
        local_acceptance_minus_static_effect=float(acceptance.get("local_acceptance_minus_static_effect", 0.0)),
        starter_code_acceptance_marketing_language_authorized=True,
        starter_code_acceptance_verification_claim_authorized=bool(acceptance.get("starter_code_acceptance_verification_claim_authorized", False)),
        starter_code_claim_authorized=bool(acceptance.get("starter_code_claim_authorized", False)),
        actual_product_execution_authorized=False,
        product_capability_execution_authorized=False,
        external_use_authorized=False,
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
        boundary="This local starter-code acceptance marketing proof pack converts T17 candidate acceptance-verification evidence into bounded, marketing-safe language. It authorizes only proof-bound public wording about local starter-code acceptance verification and never authorizes actual product execution, product capability execution, external use, autonomous development, product-market fit, commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claims, autonomous consequential action, or authority expansion.",
        acceptance_marketing_claims_path=str(claims_path),
        acceptance_marketing_copy_path=str(copy_path),
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
