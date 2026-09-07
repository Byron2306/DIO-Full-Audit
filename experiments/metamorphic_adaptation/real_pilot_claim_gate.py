from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_PILOT_CLAIM_GATE_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_CLAIM_GATE_V1"
REAL_PILOT_CLAIM_GATE_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_CLAIM_GATE_VERDICT_READY"
REAL_PILOT_CLAIM_GATE_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_CLAIM_GATE_REFUSED"


@dataclass(frozen=True)
class RealPilotClaimGateReceipt:
    gate_version: str
    status: str
    compatibility_status: str
    blind_evaluation_status: str
    real_pilot_native_compatibility_proven: bool
    real_blind_evaluation_exercised: bool
    evaluated_blind_outputs: int
    mechanics_proven: bool
    real_adaptive_evidence: bool
    allowed_claim_tier: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    compatibility_verdict_sha256: str
    blind_evaluation_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_real_pilot_claim_gate(
    *,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
) -> RealPilotClaimGateReceipt:
    compatibility = _load(compatibility_verdict_path)
    blind = _load(blind_evaluation_receipt_path)

    compatibility_ready = (
        compatibility.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_READY"
        and compatibility.get("real_pilot_native_compatibility_proven") is True
        and compatibility.get("ready_for_real_blind_evaluation") is True
        and compatibility.get("adaptive_claim_authorized") is False
    )

    blind_ready = (
        blind.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_BLIND_EVALUATION_READY"
        and blind.get("real_pilot_native_compatibility_proven") is True
        and blind.get("evaluated_blind_outputs") == 5
        and blind.get("real_native_mode") is True
        and blind.get("real_adaptive_evidence") is False
        and blind.get("adaptive_claim_authorized") is False
    )

    mechanics_proven = compatibility_ready and blind_ready

    return RealPilotClaimGateReceipt(
        gate_version=REAL_PILOT_CLAIM_GATE_VERSION,
        status=REAL_PILOT_CLAIM_GATE_READY_TOKEN if mechanics_proven else REAL_PILOT_CLAIM_GATE_REFUSED_TOKEN,
        compatibility_status=str(compatibility.get("status")),
        blind_evaluation_status=str(blind.get("status")),
        real_pilot_native_compatibility_proven=bool(
            compatibility.get("real_pilot_native_compatibility_proven")
        ),
        real_blind_evaluation_exercised=blind_ready,
        evaluated_blind_outputs=int(blind.get("evaluated_blind_outputs", 0)),
        mechanics_proven=mechanics_proven,
        real_adaptive_evidence=False,
        allowed_claim_tier=(
            "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
            if mechanics_proven
            else "T0_NO_CLAIM"
        ),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        compatibility_verdict_sha256=_sha256_path(compatibility_verdict_path),
        blind_evaluation_sha256=_sha256_path(blind_evaluation_receipt_path),
        boundary=(
            "This real pilot claim gate authorizes only the statement that a limited real native "
            "pilot compatibility run and blind evaluation pipeline were exercised. It does not "
            "authorize an adaptive-composition claim, retained-learning claim, real performance "
            "improvement claim, commercial validation claim, professional approval claim, "
            "publication, spend, fulfilment, world-first claim, or authority expansion."
        ),
    )


def write_real_pilot_claim_gate(
    *,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
    output_path: Path,
) -> RealPilotClaimGateReceipt:
    receipt = evaluate_real_pilot_claim_gate(
        compatibility_verdict_path=compatibility_verdict_path,
        blind_evaluation_receipt_path=blind_evaluation_receipt_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
