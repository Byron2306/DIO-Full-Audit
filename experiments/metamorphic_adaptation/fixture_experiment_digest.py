from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


FIXTURE_DIGEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_FIXTURE_EXPERIMENT_DIGEST_V1"
FIXTURE_DIGEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FIXTURE_EXPERIMENT_DIGEST_READY"
FIXTURE_DIGEST_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FIXTURE_EXPERIMENT_DIGEST_REFUSED"


@dataclass(frozen=True)
class FixtureExperimentDigest:
    digest_version: str
    status: str
    manifest_status: str
    run_scaffold_status: str
    execution_status: str
    blind_evaluation_status: str
    factorial_analysis_status: str
    transfer_claim_gate_status: str
    end_to_end_fixture_mechanics_proven: bool
    allowed_claim_tier: str
    ready_for_real_controlled_transfer_execution: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    controlled_transfer_manifest_sha256: str
    controlled_transfer_run_receipt_sha256: str
    controlled_transfer_execution_receipt_sha256: str
    blind_evaluation_receipt_sha256: str
    factorial_analysis_receipt_sha256: str
    transfer_claim_gate_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_fixture_experiment_digest(
    *,
    controlled_transfer_manifest_path: Path,
    controlled_transfer_run_receipt_path: Path,
    controlled_transfer_execution_receipt_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
    transfer_claim_gate_path: Path,
) -> FixtureExperimentDigest:
    manifest = _load(controlled_transfer_manifest_path)
    run = _load(controlled_transfer_run_receipt_path)
    execution = _load(controlled_transfer_execution_receipt_path)
    blind = _load(blind_evaluation_receipt_path)
    factorial = _load(factorial_analysis_receipt_path)
    claim_gate = _load(transfer_claim_gate_path)

    mechanics_proven = (
        manifest.get("status") == "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_MANIFEST_READY"
        and manifest.get("transfer_run_authorized") is True
        and run.get("status") == "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUN_SCAFFOLD_READY"
        and execution.get("status") == "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_EXECUTION_FIXTURE_READY"
        and blind.get("status") == "DIO_METAMORPHIC_ADAPTATION_BLIND_EVALUATION_FIXTURE_READY"
        and factorial.get("status") == "DIO_METAMORPHIC_ADAPTATION_FACTORIAL_ANALYSIS_FIXTURE_READY"
        and claim_gate.get("status") == "DIO_METAMORPHIC_ADAPTATION_TRANSFER_CLAIM_GATE_FIXTURE_VERDICT_READY"
        and claim_gate.get("mechanics_proven") is True
        and claim_gate.get("allowed_claim_tier") == "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM"
        and claim_gate.get("adaptive_claim_authorized") is False
    )

    return FixtureExperimentDigest(
        digest_version=FIXTURE_DIGEST_VERSION,
        status=FIXTURE_DIGEST_READY_TOKEN if mechanics_proven else FIXTURE_DIGEST_REFUSED_TOKEN,
        manifest_status=str(manifest.get("status")),
        run_scaffold_status=str(run.get("status")),
        execution_status=str(execution.get("status")),
        blind_evaluation_status=str(blind.get("status")),
        factorial_analysis_status=str(factorial.get("status")),
        transfer_claim_gate_status=str(claim_gate.get("status")),
        end_to_end_fixture_mechanics_proven=mechanics_proven,
        allowed_claim_tier=(
            "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM"
            if mechanics_proven
            else "T0_NO_CLAIM"
        ),
        ready_for_real_controlled_transfer_execution=mechanics_proven,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        controlled_transfer_manifest_sha256=_sha256_path(controlled_transfer_manifest_path),
        controlled_transfer_run_receipt_sha256=_sha256_path(controlled_transfer_run_receipt_path),
        controlled_transfer_execution_receipt_sha256=_sha256_path(controlled_transfer_execution_receipt_path),
        blind_evaluation_receipt_sha256=_sha256_path(blind_evaluation_receipt_path),
        factorial_analysis_receipt_sha256=_sha256_path(factorial_analysis_receipt_path),
        transfer_claim_gate_sha256=_sha256_path(transfer_claim_gate_path),
        boundary=(
            "This digest authorizes only the statement that the fixture-mode end-to-end "
            "controlled transfer experiment mechanics were exercised and judged. It permits "
            "preparation for real controlled transfer execution. It does not authorize an "
            "adaptive-composition claim, real performance claim, commercial validation claim, "
            "professional approval claim, publication, spend, fulfilment, world-first claim, "
            "or authority expansion."
        ),
    )


def write_fixture_experiment_digest(
    *,
    controlled_transfer_manifest_path: Path,
    controlled_transfer_run_receipt_path: Path,
    controlled_transfer_execution_receipt_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
    transfer_claim_gate_path: Path,
    output_path: Path,
) -> FixtureExperimentDigest:
    digest = build_fixture_experiment_digest(
        controlled_transfer_manifest_path=controlled_transfer_manifest_path,
        controlled_transfer_run_receipt_path=controlled_transfer_run_receipt_path,
        controlled_transfer_execution_receipt_path=controlled_transfer_execution_receipt_path,
        blind_evaluation_receipt_path=blind_evaluation_receipt_path,
        factorial_analysis_receipt_path=factorial_analysis_receipt_path,
        transfer_claim_gate_path=transfer_claim_gate_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(digest), indent=2, sort_keys=True) + "\n")
    return digest
