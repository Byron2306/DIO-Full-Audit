from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MARKETING_PROOF_PACK_READY"
REQUIRED_READINESS_STATUS = "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MAP_READY"
PACK_VERSION = "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MARKETING_PROOF_PACK_V1"
MARKETING_CLAIM_TIER = "T15_MARKETING_SAFE_CAPABILITY_EXECUTION_READINESS_MAP"


@dataclass(frozen=True)
class CapabilityExecutionReadinessMarketingProofPackReceipt:
    status: str
    pack_version: str
    marketing_claim_tier: str
    capability_execution_readiness_status: str
    capability_execution_readiness_sha256: str
    selected_product: str
    capabilities_mapped: int
    can_execute_now_count: int
    could_execute_with_local_dependency_count: int
    could_execute_with_config_count: int
    human_gate_required_count: int
    authority_refused_count: int
    not_implemented_yet_count: int
    could_execute_total_count: int
    capability_execution_readiness_evidence: bool
    capability_execution_readiness_marketing_language_authorized: bool
    could_execute_claim_authorized: bool
    actual_execution_authorized: bool
    starter_code_claim_authorized: bool
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
    capability_readiness_claims_path: str
    capability_readiness_copy_path: str


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


def _approved_claims(readiness: dict[str, Any]) -> list[str]:
    selected_product = str(readiness.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    mapped = int(readiness.get("capabilities_mapped", 0))
    now = int(readiness.get("can_execute_now_count", 0))
    local = int(readiness.get("could_execute_with_local_dependency_count", 0))
    config = int(readiness.get("could_execute_with_config_count", 0))
    human = int(readiness.get("human_gate_required_count", 0))
    refused = int(readiness.get("authority_refused_count", 0))
    total = int(readiness.get("could_execute_total_count", now + local + config + human))
    return [
        "DIO produced T15 candidate evidence of capability execution readiness mapping in an internal controlled gauntlet.",
        f"DIO mapped {mapped} selected-product capabilities for {selected_product} by execution-readiness state under the tested harness.",
        f"DIO classified {now} capabilities as can execute now, {local} as could execute with local dependencies, and {config} as could execute with configuration.",
        f"DIO classified {human} capabilities as human-gate required and {refused} as authority-refused.",
        f"DIO identified {total} capabilities as could-execute in a bounded readiness sense while keeping actual execution unauthorized.",
        "The T15 evidence supports bounded language about capability readiness, not actual execution, starter code completion, autonomous development, product-market fit, or commercial validation.",
        "The readiness signal preserved human gates and blocked actual-execution, starter-code, AGI, world-first, autonomous-development, commercial-validation, and authority-expansion claims.",
    ]


def _forbidden_claims() -> list[str]:
    return [
        "DIO executed the selected-product capabilities",
        "DIO completed starter code from the readiness map",
        "DIO has proven product-market fit",
        "DIO is commercially validated",
        "DIO guarantees viable products, sales, revenue, or buyer outcomes",
        "DIO can autonomously build, publish, sell, spend, contact, or fulfil products",
        "DIO can make legal, medical, financial, or professional decisions",
        "DIO is AGI",
        "DIO is conscious or sentient",
        "DIO has world-first status",
        "DIO may expand its own authority from could-execute readiness evidence",
        "DIO can skip human review because a capability could execute",
    ]


def _required_disclaimers() -> list[str]:
    return [
        "Internal controlled gauntlet evidence only.",
        "Candidate capability-readiness evidence, not actual execution.",
        "Could-execute does not mean authorized-to-execute.",
        "No actual execution.",
        "Not starter code completion.",
        "Not product-market fit.",
        "Not commercial validation.",
        "Not autonomous development.",
        "Not AGI.",
        "Not professional approval.",
        "Not world-first status.",
        "No autonomous external action, spending, publication, fulfilment, contact, or authority expansion.",
    ]


def _copy(readiness: dict[str, Any], approved: list[str], forbidden: list[str]) -> str:
    selected_product = str(readiness.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    mapped = int(readiness.get("capabilities_mapped", 0))
    now = int(readiness.get("can_execute_now_count", 0))
    local = int(readiness.get("could_execute_with_local_dependency_count", 0))
    config = int(readiness.get("could_execute_with_config_count", 0))
    human = int(readiness.get("human_gate_required_count", 0))
    refused = int(readiness.get("authority_refused_count", 0))
    total = int(readiness.get("could_execute_total_count", now + local + config + human))
    approved_md = "\n".join(f"- {claim}" for claim in approved)
    forbidden_md = "\n".join(f"- {claim}" for claim in forbidden)
    disclaimers_md = "\n".join(f"- {line}" for line in _required_disclaimers())
    return f"""# DIO Capability Execution Readiness Marketing Proof Pack

## Marketing-safe claim

DIO has internal controlled T15 candidate evidence of capability execution readiness mapping: it classified which {selected_product} capabilities can execute now, could execute with local dependencies or configuration, require human gates, or are authority-refused while preserving the boundary that could execute is not actual execution.

## Approved language

{approved_md}

## Positioning line

DIO does not merely rehearse an implementation path. It can map which capabilities could execute under local, configuration, human-gate, or authority-refused conditions before any execution is authorized.

## Proof numbers

- Capabilities mapped: {mapped}
- Can execute now: {now}
- Could execute with local dependency: {local}
- Could execute with configuration: {config}
- Human gate required: {human}
- Authority refused: {refused}
- Could-execute total: {total}

## Required disclaimers

{disclaimers_md}

## Forbidden claims

{forbidden_md}
"""


def build_capability_execution_readiness_marketing_proof_pack(
    capability_execution_readiness_map: Path,
    output_dir: Path,
) -> CapabilityExecutionReadinessMarketingProofPackReceipt:
    readiness = _load_json(capability_execution_readiness_map)
    if readiness.get("status") != REQUIRED_READINESS_STATUS:
        raise ValueError(
            "expected capability execution readiness map receipt status "
            f"{REQUIRED_READINESS_STATUS}, got {readiness.get('status')!r}"
        )

    approved = _approved_claims(readiness)
    forbidden = _forbidden_claims()
    claims_path = output_dir / "capability_execution_readiness_marketing_proof_claims.json"
    copy_path = output_dir / "capability_execution_readiness_marketing_safe_copy.md"
    receipt_path = output_dir / "capability_execution_readiness_marketing_proof_pack_receipt.json"

    claims_payload = {
        "marketing_claim_tier": MARKETING_CLAIM_TIER,
        "approved_public_claims": approved,
        "forbidden_public_claims": forbidden,
        "required_disclaimers": _required_disclaimers(),
    }
    _write_json(claims_path, claims_payload)
    _write_markdown(copy_path, _copy(readiness, approved, forbidden))

    receipt = CapabilityExecutionReadinessMarketingProofPackReceipt(
        status=READY_TOKEN,
        pack_version=PACK_VERSION,
        marketing_claim_tier=MARKETING_CLAIM_TIER,
        capability_execution_readiness_status=str(readiness.get("status")),
        capability_execution_readiness_sha256=_sha256_path(capability_execution_readiness_map),
        selected_product=str(readiness.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO")),
        capabilities_mapped=int(readiness.get("capabilities_mapped", 0)),
        can_execute_now_count=int(readiness.get("can_execute_now_count", 0)),
        could_execute_with_local_dependency_count=int(readiness.get("could_execute_with_local_dependency_count", 0)),
        could_execute_with_config_count=int(readiness.get("could_execute_with_config_count", 0)),
        human_gate_required_count=int(readiness.get("human_gate_required_count", 0)),
        authority_refused_count=int(readiness.get("authority_refused_count", 0)),
        not_implemented_yet_count=int(readiness.get("not_implemented_yet_count", 0)),
        could_execute_total_count=int(readiness.get("could_execute_total_count", 0)),
        capability_execution_readiness_evidence=bool(readiness.get("capability_execution_readiness_evidence", False)),
        capability_execution_readiness_marketing_language_authorized=True,
        could_execute_claim_authorized=bool(readiness.get("could_execute_claim_authorized", False)),
        actual_execution_authorized=False,
        starter_code_claim_authorized=False,
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
        boundary="This capability execution readiness marketing proof pack converts T15 candidate could-execute readiness evidence into bounded, marketing-safe language. It authorizes only proof-bound public wording about internal controlled capability execution readiness and never authorizes actual execution, starter code completion, autonomous development, product-market fit, commercial validation, professional approval, publication, spend, fulfilment, world-first status, AGI claims, autonomous consequential action, or authority expansion.",
        capability_readiness_claims_path=str(claims_path),
        capability_readiness_copy_path=str(copy_path),
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
