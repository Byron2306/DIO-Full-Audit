from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


T21_HUMAN_DECISION_APPLICATION_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_T21_HUMAN_DECISION_APPLICATION_GATE_V1"
)
T21_HUMAN_DECISION_APPLICATION_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T21_HUMAN_DECISION_APPLICATION_READY"
)
T21_HUMAN_DECISION_APPLICATION_REFUSED_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T21_HUMAN_DECISION_APPLICATION_REFUSED"
)

T20_DECISION_PACKET_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T20_HUMAN_APPROVAL_DECISION_PACKET_READY"
)
T20_CLAIM_TIER = "T20_INTERNAL_HUMAN_APPROVAL_DECISION_PACKET_READY"

APPROVE_LOCAL_RC = "APPROVE_LOCAL_RC"
REQUEST_CHANGES = "REQUEST_CHANGES"
REFUSE_RELEASE_CANDIDATE = "REFUSE_RELEASE_CANDIDATE"
DECISION_OPTIONS = [APPROVE_LOCAL_RC, REQUEST_CHANGES, REFUSE_RELEASE_CANDIDATE]

T21_APPROVED_LOCAL_RC_ONLY = "T21_HUMAN_APPROVED_LOCAL_RC_ONLY"
T21_CHANGES_REQUESTED = "T21_CHANGES_REQUESTED"
T21_RELEASE_CANDIDATE_REFUSED = "T21_RELEASE_CANDIDATE_REFUSED"
T21_REFUSED = "T21_REFUSED_INVALID_OR_UNBOUND_HUMAN_DECISION"


@dataclass(frozen=True)
class T21HumanDecisionApplicationReceipt:
    gate_version: str
    status: str
    allowed_claim_tier: str
    inherited_t20_claim_tier: str
    t20_status: str
    t20_receipt_sha256: str
    source_bound: bool
    selected_product: str
    human_decision_applied: str
    valid_human_decision: bool
    decision_options: list[str]
    decision_packet_authorized: bool
    human_approval_required: bool
    human_approval_state_before_decision: str
    human_approval_state_after_decision: str
    synthetic_dry_run_evidence: bool
    synthetic_inputs_processed: int
    draft_dossiers_written: int
    dry_run_receipts_written: int
    human_gate_checks_written: int
    human_gates_preserved: bool
    local_release_candidate_claim_authorized: bool
    release_candidate_packaging_authorized: bool
    local_rc_approved: bool
    release_approved: bool
    changes_requested: bool
    release_refused: bool
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


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return int(value or 0)


def _decision_tier(decision: str) -> str:
    if decision == APPROVE_LOCAL_RC:
        return T21_APPROVED_LOCAL_RC_ONLY
    if decision == REQUEST_CHANGES:
        return T21_CHANGES_REQUESTED
    if decision == REFUSE_RELEASE_CANDIDATE:
        return T21_RELEASE_CANDIDATE_REFUSED
    return T21_REFUSED


def apply_t21_human_decision(
    *,
    t20_receipt_path: Path,
    human_decision: str,
    output_path: Path,
) -> T21HumanDecisionApplicationReceipt:
    t20 = _load_json(t20_receipt_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    decision = str(human_decision).strip().upper()
    source_bound = t20_receipt_path.exists() and t20_receipt_path.is_file()
    t20_status = str(t20.get("status", ""))
    inherited_tier = str(t20.get("allowed_claim_tier", ""))
    selected_product = str(t20.get("selected_product", ""))
    before_state = str(t20.get("human_approval_state", ""))
    options = list(t20.get("decision_options", []))
    valid_decision = decision in DECISION_OPTIONS and decision in options

    ready = (
        source_bound
        and valid_decision
        and t20_status == T20_DECISION_PACKET_READY_TOKEN
        and inherited_tier == T20_CLAIM_TIER
        and selected_product == "DIO_TRUST_DOSSIER_STUDIO"
        and t20.get("decision_packet_authorized") is True
        and t20.get("human_approval_required") is True
        and before_state == "NEEDS_YOU"
        and t20.get("human_gates_preserved") is True
        and _as_int(t20.get("synthetic_inputs_processed")) >= 3
        and _as_int(t20.get("draft_dossiers_written")) >= 3
        and _as_int(t20.get("dry_run_receipts_written")) >= 3
        and _as_int(t20.get("human_gate_checks_written")) >= 3
        and t20.get("actual_product_execution_authorized") is False
        and t20.get("product_capability_execution_authorized") is False
        and t20.get("external_deployment_authorized") is False
        and t20.get("external_use_authorized") is False
        and t20.get("commercial_validation_claim_authorized") is False
        and t20.get("authority_expansion_authorized") is False
    )

    local_rc_approved = ready and decision == APPROVE_LOCAL_RC
    changes_requested = ready and decision == REQUEST_CHANGES
    release_refused = ready and decision == REFUSE_RELEASE_CANDIDATE
    after_state = (
        "APPROVED_LOCAL_RC_ONLY"
        if local_rc_approved
        else "CHANGES_REQUESTED"
        if changes_requested
        else "RELEASE_CANDIDATE_REFUSED"
        if release_refused
        else "NO_RELEASE_WITHOUT_VALID_HUMAN_DECISION"
    )

    receipt = T21HumanDecisionApplicationReceipt(
        gate_version=T21_HUMAN_DECISION_APPLICATION_VERSION,
        status=(
            T21_HUMAN_DECISION_APPLICATION_READY_TOKEN
            if ready
            else T21_HUMAN_DECISION_APPLICATION_REFUSED_TOKEN
        ),
        allowed_claim_tier=_decision_tier(decision) if ready else T21_REFUSED,
        inherited_t20_claim_tier=inherited_tier,
        t20_status=t20_status,
        t20_receipt_sha256=_sha256_path(t20_receipt_path),
        source_bound=source_bound,
        selected_product=selected_product,
        human_decision_applied=decision,
        valid_human_decision=valid_decision,
        decision_options=DECISION_OPTIONS,
        decision_packet_authorized=t20.get("decision_packet_authorized") is True,
        human_approval_required=True,
        human_approval_state_before_decision=before_state,
        human_approval_state_after_decision=after_state,
        synthetic_dry_run_evidence=t20.get("synthetic_dry_run_evidence") is True,
        synthetic_inputs_processed=_as_int(t20.get("synthetic_inputs_processed")),
        draft_dossiers_written=_as_int(t20.get("draft_dossiers_written")),
        dry_run_receipts_written=_as_int(t20.get("dry_run_receipts_written")),
        human_gate_checks_written=_as_int(t20.get("human_gate_checks_written")),
        human_gates_preserved=t20.get("human_gates_preserved") is True,
        local_release_candidate_claim_authorized=ready,
        release_candidate_packaging_authorized=ready,
        local_rc_approved=local_rc_approved,
        release_approved=local_rc_approved,
        changes_requested=changes_requested,
        release_refused=release_refused,
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
            "This T21 gate applies one explicit human decision to the source-bound T20 decision "
            "packet. APPROVE_LOCAL_RC authorizes only internal local release-candidate status for "
            "DIO_TRUST_DOSSIER_STUDIO; REQUEST_CHANGES keeps the release candidate unapproved; "
            "REFUSE_RELEASE_CANDIDATE refuses it. No decision authorizes actual product execution, "
            "product capability execution, external use, deployment, autonomous development, commercial "
            "validation, product-market fit, professional approval, publication, spend, fulfilment, AGI, "
            "world-first status, autonomous consequential action, or authority expansion."
            if ready
            else "T21 human decision application refused because the decision was invalid or the T20 packet "
            "was not source-bound in a NEEDS_YOU state. No release, execution, deployment, commercial, "
            "professional, publication, spend, fulfilment, AGI, world-first, autonomous-action, or "
            "authority-expansion claims are authorized."
        ),
    )

    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
