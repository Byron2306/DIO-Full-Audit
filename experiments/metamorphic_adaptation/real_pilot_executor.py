from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_PILOT_EXECUTOR_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_EXECUTOR_V1"
REAL_PILOT_EXECUTOR_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_EXECUTION_READY"
REAL_PILOT_EXECUTOR_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_EXECUTION_REFUSED"


ARM_COMMANDS: dict[str, tuple[str, ...]] = {
    "A_STATELESS_RESET": (
        "python",
        "scripts/run_product_grade.py",
        "--output",
        "{arm_output}/product_grade",
    ),
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING": (
        "python",
        "scripts/run_professional_task_gauntlet.py",
        "--output",
        "{arm_output}/professional_task",
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
        "{arm_output}/product_incarnation",
    ),
}


@dataclass(frozen=True)
class RealPilotExecutionReceipt:
    executor_version: str
    status: str
    scaffold_status: str
    execute_requested: bool
    executed: bool
    real_native_mode: bool
    pilot_encounters_loaded: int
    pilot_encounters_executed: int
    pilot_encounters_passed: int
    pilot_encounters_timed_out: int
    pilot_encounters_failed: int
    real_pilot_execution_receipts_path: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _render_command(command: tuple[str, ...], *, arm_output: Path) -> list[str]:
    rendered = []
    for part in command:
        rendered.append(part.replace("{arm_output}", str(arm_output)))
    if rendered and rendered[0] == "python":
        rendered[0] = sys.executable
    return rendered


def execute_real_pilot(
    *,
    scaffold_receipt_path: Path,
    pilot_encounters_path: Path,
    output_dir: Path,
    execute: bool = False,
    timeout_seconds: int = 30,
) -> RealPilotExecutionReceipt:
    scaffold = _load_json(scaffold_receipt_path)
    encounters = _load_jsonl(pilot_encounters_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    receipts_path = output_dir / "real_pilot_execution_receipts.jsonl"
    receipt_path = output_dir / "real_pilot_execution_receipt.json"

    scaffold_ready = (
        scaffold.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_READY"
        and scaffold.get("real_pilot_authorized") is True
        and scaffold.get("adaptive_claim_authorized") is False
        and scaffold.get("commercial_or_world_first_claim_authorized") is False
    )

    if not scaffold_ready or not execute:
        receipt = RealPilotExecutionReceipt(
            executor_version=REAL_PILOT_EXECUTOR_VERSION,
            status=REAL_PILOT_EXECUTOR_REFUSED_TOKEN,
            scaffold_status=str(scaffold.get("status")),
            execute_requested=execute,
            executed=False,
            real_native_mode=True,
            pilot_encounters_loaded=len(encounters),
            pilot_encounters_executed=0,
            pilot_encounters_passed=0,
            pilot_encounters_timed_out=0,
            pilot_encounters_failed=0,
            real_pilot_execution_receipts_path=str(receipts_path),
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            boundary=(
                "Real pilot native execution refused unless the scaffold is ready and explicit execution "
                "is requested. No adaptive, commercial, professional, publication, spend, fulfilment, "
                "world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    env = dict(os.environ)
    repo_root = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"

    passed = 0
    timed_out = 0
    failed = 0

    with receipts_path.open("w") as fh:
        for encounter in encounters:
            arm = encounter["arm"]
            blind_id = encounter["blind_id"]
            command_template = ARM_COMMANDS[arm]
            arm_output = output_dir / arm
            arm_output.mkdir(parents=True, exist_ok=True)

            command = _render_command(command_template, arm_output=arm_output)

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
                status = "REAL_PILOT_NATIVE_PASSED" if exit_code == 0 else "REAL_PILOT_NATIVE_FAILED"
            except subprocess.TimeoutExpired as exc:
                exit_code = 124
                stdout = exc.stdout or ""
                stderr = (exc.stderr or "") + f"\nNATIVE_COMMAND_TIMEOUT: command exceeded {timeout_seconds} seconds."
                status = "REAL_PILOT_NATIVE_TIMED_OUT"

            if status == "REAL_PILOT_NATIVE_PASSED":
                passed += 1
            elif status == "REAL_PILOT_NATIVE_TIMED_OUT":
                timed_out += 1
            else:
                failed += 1

            stdout_bytes = stdout.encode("utf-8") if isinstance(stdout, str) else stdout
            stderr_bytes = stderr.encode("utf-8") if isinstance(stderr, str) else stderr

            (arm_output / f"{blind_id}.stdout.log").write_bytes(stdout_bytes or b"")
            (arm_output / f"{blind_id}.stderr.log").write_bytes(stderr_bytes or b"")

            fh.write(json.dumps({
                "blind_id": blind_id,
                "arm": arm,
                "encounter_index": encounter["encounter_index"],
                "status": status,
                "executed": True,
                "real_native_mode": True,
                "command": command,
                "exit_code": exit_code,
                "stdout_sha256": _sha256_bytes(stdout_bytes or b""),
                "stderr_sha256": _sha256_bytes(stderr_bytes or b""),
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            }, sort_keys=True) + "\n")

    receipt = RealPilotExecutionReceipt(
        executor_version=REAL_PILOT_EXECUTOR_VERSION,
        status=REAL_PILOT_EXECUTOR_READY_TOKEN,
        scaffold_status=str(scaffold.get("status")),
        execute_requested=True,
        executed=True,
        real_native_mode=True,
        pilot_encounters_loaded=len(encounters),
        pilot_encounters_executed=len(encounters),
        pilot_encounters_passed=passed,
        pilot_encounters_timed_out=timed_out,
        pilot_encounters_failed=failed,
        real_pilot_execution_receipts_path=str(receipts_path),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This real pilot executor runs a limited native smoke encounter per arm. It records "
            "execution compatibility only, does not constitute adaptive performance evidence, does not "
            "claim improvement, and does not authorize commercial, professional, publication, spend, "
            "fulfilment, world-first, or authority-expansion claims."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
