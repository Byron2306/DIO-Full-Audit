from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


T20_HUMAN_APPROVAL_DECISION_PACKET_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_T20_HUMAN_APPROVAL_DECISION_PACKET_GATE_V1"
)
T20_HUMAN_APPROVAL_DECISION_PACKET_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T20_HUMAN_APPROVAL_DECISION_PACKET_READY"
)
T20_HUMAN_APPROVAL_DECISION_PACKET_REFUSED_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T20_HUMAN_APPROVAL_DECISION_PACKET_REFUSED"
)

T19_LOCAL_RELEASE_CANDIDATE_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T19_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_READY"
)
T19_CLAIM_TIER = "T19_INTERNAL_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_PACKAGING"
T20_CLAIM_TIER = "T20_INTERNAL_HUMAN_APPROVAL_DECISION_PACKET_READY"

DECISION_OPTIONS = [
    "APPROVE_LOCAL_RC",
    "REQUEST_CHANGES",
    "REFUSE_RELEASE_CANDIDATE",
]


@dataclass(frozen=True)
class T20HumanApprovalDecisionPacketReceipt:
    gate_version: str
    status: str
    allowed_claim_tier: str
    inherited_t19_claim_tier: str
    t19_status: str
    t19_receipt_sha256: str
    source_bound: bool
    selected_product: str
    synthetic_dry_run_evidence: bool
    synthetic_inputs_processed: int
    draft_dossiers_written: int
    dry_run_receipts_written: int
    human_gate_checks_written: int
    human_gates_preserved: bool
    human_approval_required: bool
    human_approval_state: str
    decision_options: list[str]
    default_decision: str
    decision_packet_authorized: bool
    local_release_candidate_claim_authorized: bool
    release_candidate_packaging_authorized: bool
    release_approved: bool
    release_refused: bool
    changes_requested: bool
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


def build_t20_human_approval_decision_packet(
    *,
    t19_receipt_path: Path,
    output_path: Path,
) -> T20HumanApprovalDecisionPacketReceipt:
    t19 = _load_json(t19_receipt_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_bound = t19_receipt_path.exists() and t19_receipt_path.is_file()
    t19_status = str(t19.get("status", ""))
    inherited_tier = str(t19.get("allowed_claim_tier", ""))
    selected_product = str(t19.get("selected_product", ""))
    human_state = str(t19.get("human_approval_state", ""))

    ready = (
        source_bound
        and t19_status == T19_LOCAL_RELEASE_CANDIDATE_READY_TOKEN
        and inherited_tier == T19_CLAIM_TIER
        and selected_product == "DIO_TRUST_DOSSIER_STUDIO"
        and t19.get("release_candidate_packaging_authorized") is True
        and t19.get("local_release_candidate_claim_authorized") is True
        and t19.get("human_approval_required") is True
        and human_state == "NEEDS_YOU"
        and t19.get("human_gates_preserved") is True
        and _as_int(t19.get("synthetic_inputs_processed")) >= 3
        and _as_int(t19.get("draft_dossiers_written")) >= 3
        and _as_int(t19.get("dry_run_receipts_written")) >= 3
        and _as_int(t19.get("human_gate_checks_written")) >= 3
        and t19.get("actual_product_execution_authorized") is False
        and t19.get("product_capability_execution_authorized") is False
        and t19.get("external_deployment_authorized") is False
        and t19.get("external_use_authorized") is False
        and t19.get("commercial_validation_claim_authorized") is False
        and t19.get("authority_expansion_authorized") is False
    )

    receipt = T20HumanApprovalDecisionPacketReceipt(
        gate_version=T20_HUMAN_APPROVAL_DECISION_PACKET_VERSION,
        status=(
            T20_HUMAN_APPROVAL_DECISION_PACKET_READY_TOKEN
            if ready
            else T20_HUMAN_APPROVAL_DECISION_PACKET_REFUSED_TOKEN
        ),
        allowed_claim_tier=T20_CLAIM_TIER if ready else "T20_REFUSED_NO_DECISION_PACKET",
        inherited_t19_claim_tier=inherited_tier,
        t19_status=t19_status,
        t19_receipt_sha256=_sha256_path(t19_receipt_path),
        source_bound=source_bound,
        selected_product=selected_product,
        synthetic_dry_run_evidence=t19.get("synthetic_dry_run_evidence") is True,
        synthetic_inputs_processed=_as_int(t19.get("synthetic_inputs_processed")),
        draft_dossiers_written=_as_int(t19.get("draft_dossiers_written")),
        dry_run_receipts_written=_as_int(t19.get("dry_run_receipts_written")),
        human_gate_checks_written=_as_int(t19.get("human_gate_checks_written")),
        human_gates_preserved=t19.get("human_gates_preserved") is True,
        human_approval_required=t19.get("human_approval_required") is True,
        human_approval_state=human_state,
        decision_options=DECISION_OPTIONS,
        default_decision="NO_RELEASE_WITHOUT_HUMAN_APPROVAL",
        decision_packet_authorized=ready,
        local_release_candidate_claim_authorized=ready,
        release_candidate_packaging_authorized=ready,
        release_approved=False,
        release_refused=False,
        changes_requested=False,
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
            "This T20 gate converts the source-bound T19 human-gated local release-candidate "
            "receipt into a human approval decision packet. It exposes only three possible human "
            "decisions: APPROVE_LOCAL_RC, REQUEST_CHANGES, or REFUSE_RELEASE_CANDIDATE. The default "
            "state remains NO_RELEASE_WITHOUT_HUMAN_APPROVAL. This packet does not itself approve "
            "release, execute the product, deploy externally, validate product-market fit, validate "
            "commercially, authorize spend, publication, fulfilment, professional approval, AGI, "
            "world-first status, autonomous action, or authority expansion."
            if ready
            else "T20 human approval decision packet refused because the T19 receipt did not preserve "
            "a source-bound NEEDS_YOU human-gated local release-candidate state. No release, execution, "
            "deployment, commercial, professional, publication, spend, fulfilment, world-first, AGI, "
            "autonomous-action, or authority-expansion claims are authorized."
        ),
    )

    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
