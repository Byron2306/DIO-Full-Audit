from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


FULL_TRANSFER_EXECUTOR_VERSION = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_EXECUTOR_V1"
FULL_TRANSFER_EXECUTOR_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_EXECUTION_READY"
FULL_TRANSFER_EXECUTOR_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_EXECUTION_REFUSED"


ARM_COMMANDS: dict[str, tuple[str, ...]] = {
    "A_STATELESS_RESET": (
        "python",
        "scripts/run_product_grade.py",
        "--output",
        "{encounter_output}/product_grade",
    ),
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING": (
        "python",
        "scripts/run_professional_task_gauntlet.py",
        "--output",
        "{encounter_output}/professional_task",
    ),
    "C_SEMANTIC_RETAINED": (
        "python",
        "scripts/lingua_marketing_learning.py",
        "status",
    ),
    "D_MARKET_RETAINED": (
        "python",
        "scripts/run_market_sensorium_cycle.py",
    ),
    "E_FULL_SEMANTIC_MARKET_BEAST": (
        "python",
        "scripts/run_product_incarnation_studio_phase16.py",
        "--output",
        "{encounter_output}/product_incarnation",
    ),
}


@dataclass(frozen=True)
class FullControlledTransferExecutionReceipt:
    executor_version: str
    status: str
    scaffold_status: str
    execute_requested: bool
    executed: bool
    real_native_mode: bool
    full_run_encounters_loaded: int
    full_run_encounters_executed: int
    full_run_encounters_passed: int
    full_run_encounters_failed: int
    full_run_encounters_timed_out: int
    execution_receipts_path: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    scaffold_receipt_sha256: str
    scaffold_encounters_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _render_command(command: tuple[str, ...], *, encounter_output: Path) -> list[str]:
    rendered = []
    for part in command:
        rendered.append(part.replace("{encounter_output}", str(encounter_output)))
    if rendered and rendered[0] == "python":
        rendered[0] = sys.executable
    return rendered


def execute_full_controlled_transfer(
    *,
    scaffold_receipt_path: Path,
    scaffold_encounters_path: Path,
    output_dir: Path,
    execute: bool = False,
    timeout_seconds: int = 30,
) -> FullControlledTransferExecutionReceipt:
    scaffold = _load_json(scaffold_receipt_path)
    encounters = _load_jsonl(scaffold_encounters_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    execution_receipts_path = output_dir / "full_controlled_transfer_execution_receipts.jsonl"
    receipt_path = output_dir / "full_controlled_transfer_execution_receipt.json"

    scaffold_ready = (
        scaffold.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_READY"
        and scaffold.get("full_run_planning_authorized") is True
        and scaffold.get("execute_by_default") is False
        and scaffold.get("full_run_encounters_staged") == 25
        and scaffold.get("adaptive_claim_authorized") is False
        and scaffold.get("commercial_or_world_first_claim_authorized") is False
        and len(encounters) == 25
        and all(item.get("executed") is False for item in encounters)
        and all(item.get("native_execution_allowed_only_with_explicit_flag") is True for item in encounters)
    )

    if not scaffold_ready or not execute:
        receipt = FullControlledTransferExecutionReceipt(
            executor_version=FULL_TRANSFER_EXECUTOR_VERSION,
            status=FULL_TRANSFER_EXECUTOR_REFUSED_TOKEN,
            scaffold_status=str(scaffold.get("status")),
            execute_requested=execute,
            executed=False,
            real_native_mode=True,
            full_run_encounters_loaded=len(encounters),
            full_run_encounters_executed=0,
            full_run_encounters_passed=0,
            full_run_encounters_failed=0,
            full_run_encounters_timed_out=0,
            execution_receipts_path=str(execution_receipts_path),
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            scaffold_receipt_sha256=_sha256_path(scaffold_receipt_path),
            scaffold_encounters_sha256=_sha256_path(scaffold_encounters_path),
            boundary=(
                "Full controlled transfer native execution refused unless the scaffold is ready "
                "and explicit execution is requested. No adaptive, commercial, professional, "
                "publication, spend, fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"

    passed = 0
    timed_out = 0
    failed = 0

    with execution_receipts_path.open("w") as fh:
        for item in encounters:
            blind_id = item["blind_id"]
            arm = item["arm"]
            encounter_index = int(item["encounter_index"])
            encounter_output = output_dir / arm / f"encounter_{encounter_index:02d}"
            encounter_output.mkdir(parents=True, exist_ok=True)

            command = _render_command(ARM_COMMANDS[arm], encounter_output=encounter_output)

            try:
                completed = subprocess.run(
                    command,
                    cwd=repo_root,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                exit_code = completed.returncode
                stdout = completed.stdout
                stderr = completed.stderr
                status = "FULL_CONTROLLED_TRANSFER_NATIVE_PASSED" if exit_code == 0 else "FULL_CONTROLLED_TRANSFER_NATIVE_FAILED"
            except subprocess.TimeoutExpired as exc:
                exit_code = 124
                stdout = exc.stdout or ""
                stderr = (exc.stderr or "") + f"\nNATIVE_COMMAND_TIMEOUT: command exceeded {timeout_seconds} seconds."
                status = "FULL_CONTROLLED_TRANSFER_NATIVE_TIMED_OUT"

            if status == "FULL_CONTROLLED_TRANSFER_NATIVE_PASSED":
                passed += 1
            elif status == "FULL_CONTROLLED_TRANSFER_NATIVE_TIMED_OUT":
                timed_out += 1
            else:
                failed += 1

            stdout_bytes = stdout.encode("utf-8") if isinstance(stdout, str) else stdout
            stderr_bytes = stderr.encode("utf-8") if isinstance(stderr, str) else stderr

            stdout_path = encounter_output / f"{blind_id}.stdout.log"
            stderr_path = encounter_output / f"{blind_id}.stderr.log"
            stdout_path.write_bytes(stdout_bytes or b"")
            stderr_path.write_bytes(stderr_bytes or b"")

            fh.write(json.dumps({
                "blind_id": blind_id,
                "arm": arm,
                "encounter_index": encounter_index,
                "status": status,
                "executed": True,
                "real_native_mode": True,
                "command": command,
                "exit_code": exit_code,
                "stdout_sha256": _sha256_bytes(stdout_bytes or b""),
                "stderr_sha256": _sha256_bytes(stderr_bytes or b""),
                "stdout_log_path": str(stdout_path),
                "stderr_log_path": str(stderr_path),
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            }, sort_keys=True) + "\n")

    receipt = FullControlledTransferExecutionReceipt(
        executor_version=FULL_TRANSFER_EXECUTOR_VERSION,
        status=FULL_TRANSFER_EXECUTOR_READY_TOKEN,
        scaffold_status=str(scaffold.get("status")),
        execute_requested=True,
        executed=True,
        real_native_mode=True,
        full_run_encounters_loaded=len(encounters),
        full_run_encounters_executed=len(encounters),
        full_run_encounters_passed=passed,
        full_run_encounters_failed=failed,
        full_run_encounters_timed_out=timed_out,
        execution_receipts_path=str(execution_receipts_path),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        scaffold_receipt_sha256=_sha256_path(scaffold_receipt_path),
        scaffold_encounters_sha256=_sha256_path(scaffold_encounters_path),
        boundary=(
            "This executor runs the full 25-encounter real controlled transfer native smoke run. "
            "It records execution compatibility only, does not constitute adaptive performance "
            "evidence, does not claim improvement, and does not authorize commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
