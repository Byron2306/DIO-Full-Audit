from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


T19_LOCAL_RELEASE_CANDIDATE_GATE_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_T19_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_GATE_V1"
)
T19_LOCAL_RELEASE_CANDIDATE_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T19_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_READY"
)
T19_LOCAL_RELEASE_CANDIDATE_REFUSED_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T19_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_REFUSED"
)

T18_MARKETING_PROOF_PACK_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_MARKETING_PROOF_PACK_READY"
)
T18_DRY_RUN_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_READY"
)
T18_MARKETING_CLAIM_TIER = "T18_MARKETING_SAFE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN"
T19_LOCAL_RELEASE_CANDIDATE_CLAIM_TIER = (
    "T19_INTERNAL_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_PACKAGING"
)
SELECTED_PRODUCT = "DIO_TRUST_DOSSIER_STUDIO"


@dataclass(frozen=True)
class T19HumanGatedLocalReleaseCandidateReceipt:
    gate_version: str
    status: str
    selected_product: str
    source_bound: bool
    t18_marketing_proof_pack_status: str
    t18_dry_run_status: str
    inherited_marketing_claim_tier: str
    allowed_claim_tier: str
    synthetic_dry_run_evidence: bool
    synthetic_inputs_processed: int
    draft_dossiers_written: int
    dry_run_receipts_written: int
    human_gate_checks_written: int
    boundary_checks_passed: int
    static_dry_run_baseline_mean_score: float
    controlled_dry_run_mean_score: float
    controlled_dry_run_minus_static_effect: float
    t18_marketing_proof_pack_sha256: str
    human_gates_preserved: bool
    human_approval_required: bool
    human_approval_state: str
    release_candidate_packaging_authorized: bool
    local_release_candidate_claim_authorized: bool
    product_capability_dry_run_claim_authorized: bool
    actual_product_execution_authorized: bool
    product_capability_execution_authorized: bool
    external_use_authorized: bool
    external_deployment_authorized: bool
    autonomous_development_authorized: bool
    autonomous_action_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    agi_claim_authorized: bool
    world_first_claim_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_int(payload: dict, key: str) -> int:
    return int(payload.get(key, 0))


def _as_float(payload: dict, key: str) -> float:
    return float(payload.get(key, 0.0))


def _prohibited_flags_are_locked(payload: dict) -> bool:
    prohibited_false_keys = [
        "actual_product_execution_authorized",
        "product_capability_execution_authorized",
        "external_use_authorized",
        "autonomous_development_authorized",
        "autonomous_action_claim_authorized",
        "commercial_validation_claim_authorized",
        "product_market_fit_claim_authorized",
        "professional_approval_claim_authorized",
        "publication_authorized",
        "spend_authorized",
        "fulfilment_authorized",
        "agi_claim_authorized",
        "world_first_claim_authorized",
        "authority_expansion_authorized",
    ]
    return all(payload.get(key) is False for key in prohibited_false_keys)


def _ready_payload(payload: dict, source_bound: bool) -> bool:
    human_gates_preserved = _as_int(payload, "human_gate_checks_written") >= 3
    dry_run_artifacts_present = (
        _as_int(payload, "synthetic_inputs_processed") >= 3
        and _as_int(payload, "draft_dossiers_written") >= 3
        and _as_int(payload, "dry_run_receipts_written") >= 3
        and _as_int(payload, "boundary_checks_passed") >= 3
    )
    dry_run_effect_present = _as_float(payload, "controlled_dry_run_minus_static_effect") > 0.0

    return (
        source_bound
        and payload.get("status") == T18_MARKETING_PROOF_PACK_READY_TOKEN
        and payload.get("human_gated_product_capability_dry_run_status") == T18_DRY_RUN_READY_TOKEN
        and payload.get("marketing_claim_tier") == T18_MARKETING_CLAIM_TIER
        and payload.get("selected_product") == SELECTED_PRODUCT
        and payload.get("synthetic_dry_run_evidence") is True
        and payload.get("product_capability_dry_run_claim_authorized") is True
        and payload.get("product_capability_dry_run_marketing_language_authorized") is True
        and dry_run_artifacts_present
        and dry_run_effect_present
        and human_gates_preserved
        and _prohibited_flags_are_locked(payload)
    )


def evaluate_t19_human_gated_local_release_candidate(
    *,
    t18_marketing_proof_pack_path: Path,
    output_path: Path,
) -> T19HumanGatedLocalReleaseCandidateReceipt:
    source_bound = t18_marketing_proof_pack_path.exists() and t18_marketing_proof_pack_path.is_file()
    payload = _load_json(t18_marketing_proof_pack_path) if source_bound else {}
    ready = _ready_payload(payload, source_bound)
    human_gates_preserved = _as_int(payload, "human_gate_checks_written") >= 3

    receipt = T19HumanGatedLocalReleaseCandidateReceipt(
        gate_version=T19_LOCAL_RELEASE_CANDIDATE_GATE_VERSION,
        status=(
            T19_LOCAL_RELEASE_CANDIDATE_READY_TOKEN
            if ready
            else T19_LOCAL_RELEASE_CANDIDATE_REFUSED_TOKEN
        ),
        selected_product=str(payload.get("selected_product", "")),
        source_bound=source_bound,
        t18_marketing_proof_pack_status=str(payload.get("status", "")),
        t18_dry_run_status=str(payload.get("human_gated_product_capability_dry_run_status", "")),
        inherited_marketing_claim_tier=str(payload.get("marketing_claim_tier", "")),
        allowed_claim_tier=(T19_LOCAL_RELEASE_CANDIDATE_CLAIM_TIER if ready else "REFUSED"),
        synthetic_dry_run_evidence=payload.get("synthetic_dry_run_evidence") is True,
        synthetic_inputs_processed=_as_int(payload, "synthetic_inputs_processed"),
        draft_dossiers_written=_as_int(payload, "draft_dossiers_written"),
        dry_run_receipts_written=_as_int(payload, "dry_run_receipts_written"),
        human_gate_checks_written=_as_int(payload, "human_gate_checks_written"),
        boundary_checks_passed=_as_int(payload, "boundary_checks_passed"),
        static_dry_run_baseline_mean_score=_as_float(
            payload, "static_dry_run_baseline_mean_score"
        ),
        controlled_dry_run_mean_score=_as_float(payload, "controlled_dry_run_mean_score"),
        controlled_dry_run_minus_static_effect=_as_float(
            payload, "controlled_dry_run_minus_static_effect"
        ),
        t18_marketing_proof_pack_sha256=(
            _sha256_path(t18_marketing_proof_pack_path) if source_bound else ""
        ),
        human_gates_preserved=human_gates_preserved,
        human_approval_required=True,
        human_approval_state="NEEDS_YOU",
        release_candidate_packaging_authorized=ready,
        local_release_candidate_claim_authorized=ready,
        product_capability_dry_run_claim_authorized=(
            payload.get("product_capability_dry_run_claim_authorized") is True and ready
        ),
        actual_product_execution_authorized=False,
        product_capability_execution_authorized=False,
        external_use_authorized=False,
        external_deployment_authorized=False,
        autonomous_development_authorized=False,
        autonomous_action_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        agi_claim_authorized=False,
        world_first_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This T19 gate promotes the source-bound T18 synthetic, human-gated dry-run proof pack "
            "only into internal local release-candidate packaging evidence for DIO_TRUST_DOSSIER_STUDIO. "
            "It keeps human approval required and records the approval state as NEEDS_YOU. It does not "
            "authorize actual product execution, product capability execution, external use, deployment, "
            "autonomous development, commercial validation, product-market fit, professional approval, "
            "publication, spend, fulfilment, AGI, world-first, autonomous consequential action, or authority expansion."
            if ready
            else "T19 local release-candidate packaging was refused because the source-bound T18 proof pack "
            "did not preserve the required dry-run evidence, human gates, positive controlled dry-run effect, "
            "or forbidden-claim locks. Human approval remains required and no external, commercial, professional, "
            "publication, spend, fulfilment, world-first, AGI, or authority-expansion claim is authorized."
        ),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
