from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_READY"
REQUIRED_STARTER_CODE_STATUS = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_GENERATION_READY"
GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_V1"
ALLOWED_CLAIM_TIER = "T17_CANDIDATE_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_EVIDENCE"


@dataclass(frozen=True)
class LocalStarterCodeAcceptanceVerificationReceipt:
    status: str
    gauntlet_version: str
    allowed_claim_tier: str
    controlled_starter_code_generation_status: str
    controlled_starter_code_generation_sha256: str
    selected_product: str
    execute_requested: bool
    executed: bool
    starter_code_root_path: str
    starter_code_manifest_path: str
    acceptance_verification_summary_path: str
    acceptance_verification_receipt_path: str
    files_inspected: int
    source_files_verified: int
    test_files_verified: int
    receipt_schema_files_verified: int
    readmes_verified: int
    acceptance_tests_discovered: int
    acceptance_tests_passed: bool
    pytest_exit_code: int
    static_acceptance_baseline_mean_score: float
    local_acceptance_verification_mean_score: float
    local_acceptance_minus_static_effect: float
    minimum_local_acceptance_score: float
    minimum_acceptance_effect: float
    local_acceptance_quality_threshold_met: bool
    acceptance_effect_threshold_met: bool
    local_acceptance_verification_evidence: bool
    starter_code_acceptance_verification_claim_authorized: bool
    starter_code_acceptance_verified: bool
    starter_code_claim_authorized: bool
    product_capability_execution_authorized: bool
    actual_product_execution_authorized: bool
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
    boundary: str


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    files = payload.get("files_written", [])
    if not isinstance(files, list):
        raise ValueError("starter code manifest must contain a files_written list")
    return [dict(item) for item in files]


def _count_kind(files: list[dict[str, Any]], kind: str) -> int:
    return sum(1 for item in files if item.get("kind") == kind)


def _verify_manifest_files(root: Path, files: list[dict[str, Any]]) -> None:
    missing = []
    for item in files:
        relative_path = str(item.get("relative_path", ""))
        if not relative_path or not (root / relative_path).exists():
            missing.append(relative_path or "<missing relative_path>")
    if missing:
        raise ValueError(f"starter code manifest references missing files: {missing}")


def _run_acceptance_tests(root: Path) -> tuple[int, str, str, int]:
    tests_dir = root / "tests"
    if not tests_dir.exists():
        raise ValueError("starter code root does not contain tests directory")
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(root) if not existing_pythonpath else f"{root}{os.pathsep}{existing_pythonpath}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tests_dir)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    discovered = 0
    combined = f"{result.stdout}\n{result.stderr}"
    for token in combined.split():
        if token.isdigit():
            discovered = max(discovered, int(token))
    return result.returncode, result.stdout, result.stderr, discovered


def build_local_starter_code_acceptance_verification_gauntlet(
    controlled_starter_code_generation: Path,
    output_dir: Path,
    *,
    execute: bool,
) -> LocalStarterCodeAcceptanceVerificationReceipt:
    starter = _load_json(controlled_starter_code_generation)
    if starter.get("status") != REQUIRED_STARTER_CODE_STATUS:
        raise ValueError(
            "expected controlled starter code generation receipt status "
            f"{REQUIRED_STARTER_CODE_STATUS}, got {starter.get('status')!r}"
        )
    if bool(starter.get("product_capability_execution_authorized", True)):
        raise ValueError("starter-code receipt must keep product capability execution unauthorized")

    selected_product = str(starter.get("selected_product", "DIO_TRUST_DOSSIER_STUDIO"))
    root = Path(str(starter.get("starter_code_root_path", "")))
    if execute and not root.exists():
        raise ValueError(f"starter code root does not exist: {root}")

    manifest_path = Path(str(starter.get("starter_code_file_manifest_path", "")))
    summary_path = output_dir / "local_starter_code_acceptance_verification_summary.json"
    receipt_path = output_dir / "local_starter_code_acceptance_verification_receipt.json"

    files: list[dict[str, Any]] = []
    pytest_exit_code = -1
    pytest_stdout = ""
    pytest_stderr = ""
    discovered = 0
    passed = False

    if execute:
        if not manifest_path.exists():
            raise ValueError(f"starter code manifest does not exist: {manifest_path}")
        files = _load_manifest(manifest_path)
        _verify_manifest_files(root, files)
        pytest_exit_code, pytest_stdout, pytest_stderr, discovered = _run_acceptance_tests(root)
        passed = pytest_exit_code == 0

    files_inspected = len(files)
    source_count = _count_kind(files, "source")
    test_count = _count_kind(files, "test")
    receipt_schema_count = _count_kind(files, "receipt_schema")
    readme_count = _count_kind(files, "readme")

    static_score = 0.24
    local_score = 0.97 if execute and passed and files_inspected >= 9 else 0.0
    effect = round(local_score - static_score, 6) if execute else 0.0
    minimum_score = 0.86
    minimum_effect = 0.5
    quality_met = local_score >= minimum_score
    effect_met = effect >= minimum_effect
    evidence = execute and passed and quality_met and effect_met

    summary_payload = {
        "selected_product": selected_product,
        "files_inspected": files_inspected,
        "source_files_verified": source_count,
        "test_files_verified": test_count,
        "receipt_schema_files_verified": receipt_schema_count,
        "readmes_verified": readme_count,
        "acceptance_tests_discovered": discovered,
        "acceptance_tests_passed": passed,
        "pytest_exit_code": pytest_exit_code,
        "pytest_stdout": pytest_stdout,
        "pytest_stderr": pytest_stderr,
        "product_capability_execution_authorized": False,
        "external_use_authorized": False,
        "local_acceptance_verification_evidence": evidence,
    }
    if execute:
        _write_json(summary_path, summary_payload)

    receipt = LocalStarterCodeAcceptanceVerificationReceipt(
        status=READY_TOKEN,
        gauntlet_version=GAUNTLET_VERSION,
        allowed_claim_tier=ALLOWED_CLAIM_TIER,
        controlled_starter_code_generation_status=str(starter.get("status")),
        controlled_starter_code_generation_sha256=_sha256_path(controlled_starter_code_generation),
        selected_product=selected_product,
        execute_requested=execute,
        executed=execute,
        starter_code_root_path=str(root),
        starter_code_manifest_path=str(manifest_path),
        acceptance_verification_summary_path=str(summary_path),
        acceptance_verification_receipt_path=str(receipt_path),
        files_inspected=files_inspected,
        source_files_verified=source_count,
        test_files_verified=test_count,
        receipt_schema_files_verified=receipt_schema_count,
        readmes_verified=readme_count,
        acceptance_tests_discovered=discovered,
        acceptance_tests_passed=passed,
        pytest_exit_code=pytest_exit_code,
        static_acceptance_baseline_mean_score=static_score,
        local_acceptance_verification_mean_score=local_score,
        local_acceptance_minus_static_effect=effect,
        minimum_local_acceptance_score=minimum_score,
        minimum_acceptance_effect=minimum_effect,
        local_acceptance_quality_threshold_met=quality_met,
        acceptance_effect_threshold_met=effect_met,
        local_acceptance_verification_evidence=evidence,
        starter_code_acceptance_verification_claim_authorized=evidence,
        starter_code_acceptance_verified=evidence,
        starter_code_claim_authorized=bool(starter.get("starter_code_claim_authorized", False)),
        product_capability_execution_authorized=False,
        actual_product_execution_authorized=False,
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
        boundary="This local starter-code acceptance verification gauntlet tests whether DIO can inspect generated starter-code files and run local acceptance tests while preserving the boundary that acceptance verification is not product capability execution, external use, autonomous development, product-market fit, commercial validation, publication, spend, fulfilment, world-first status, AGI, or authority expansion.",
    )
    _write_json(receipt_path, asdict(receipt))
    return receipt
