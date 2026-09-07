from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_PILOT_COMPATIBILITY_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_V1"
REAL_PILOT_COMPATIBILITY_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_READY"
REAL_PILOT_COMPATIBILITY_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_REFUSED"


@dataclass(frozen=True)
class RealPilotCompatibilityVerdict:
    verdict_version: str
    status: str
    execution_status: str
    real_native_mode: bool
    pilot_encounters_loaded: int
    pilot_encounters_executed: int
    pilot_encounters_passed: int
    pilot_encounters_failed: int
    pilot_encounters_timed_out: int
    real_pilot_native_compatibility_proven: bool
    ready_for_real_blind_evaluation: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    execution_receipt_sha256: str
    execution_receipts_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_real_pilot_compatibility(
    *,
    execution_receipt_path: Path,
    execution_receipts_path: Path,
) -> RealPilotCompatibilityVerdict:
    receipt = _load(execution_receipt_path)
    encounters = _load_jsonl(execution_receipts_path)

    execution_status = str(receipt.get("status"))
    passed = int(receipt.get("pilot_encounters_passed", 0))
    failed = int(receipt.get("pilot_encounters_failed", 0))
    timed_out = int(receipt.get("pilot_encounters_timed_out", 0))
    loaded = int(receipt.get("pilot_encounters_loaded", 0))
    executed = int(receipt.get("pilot_encounters_executed", 0))

    encounter_statuses_match = (
        len(encounters) == executed
        and all(item.get("executed") is True for item in encounters)
        and all(item.get("real_native_mode") is True for item in encounters)
        and all(item.get("adaptive_claim_authorized") is False for item in encounters)
        and all(item.get("commercial_or_world_first_claim_authorized") is False for item in encounters)
    )

    compatibility_proven = (
        execution_status == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_EXECUTION_READY"
        and receipt.get("real_native_mode") is True
        and receipt.get("executed") is True
        and loaded == 5
        and executed == 5
        and passed == 5
        and failed == 0
        and timed_out == 0
        and receipt.get("adaptive_claim_authorized") is False
        and receipt.get("commercial_or_world_first_claim_authorized") is False
        and encounter_statuses_match
    )

    return RealPilotCompatibilityVerdict(
        verdict_version=REAL_PILOT_COMPATIBILITY_VERSION,
        status=(
            REAL_PILOT_COMPATIBILITY_READY_TOKEN
            if compatibility_proven
            else REAL_PILOT_COMPATIBILITY_REFUSED_TOKEN
        ),
        execution_status=execution_status,
        real_native_mode=bool(receipt.get("real_native_mode")),
        pilot_encounters_loaded=loaded,
        pilot_encounters_executed=executed,
        pilot_encounters_passed=passed,
        pilot_encounters_failed=failed,
        pilot_encounters_timed_out=timed_out,
        real_pilot_native_compatibility_proven=compatibility_proven,
        ready_for_real_blind_evaluation=compatibility_proven,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        execution_receipts_sha256=_sha256_path(execution_receipts_path),
        boundary=(
            "This verdict authorizes only the statement that the limited real native pilot "
            "executed compatibly. It does not constitute adaptive performance evidence, does "
            "not claim improvement, and does not authorize commercial validation, professional "
            "approval, publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )


def write_real_pilot_compatibility_verdict(
    *,
    execution_receipt_path: Path,
    execution_receipts_path: Path,
    output_path: Path,
) -> RealPilotCompatibilityVerdict:
    verdict = evaluate_real_pilot_compatibility(
        execution_receipt_path=execution_receipt_path,
        execution_receipts_path=execution_receipts_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(verdict), indent=2, sort_keys=True) + "\n")
    return verdict
