from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from products.studio_harvest import verify_studio_proof
from products.studio_harvest_gauntlet import CASES, run_gauntlet as run_composition_gauntlet
from products.studio_native_activation import (
    ACCEPTANCE_TOKEN,
    StudioNativeActivationError,
    activate_studio_case,
    verify_native_execution_proof,
)


def _identity(result: dict[str, Any]) -> tuple[Any, ...]:
    return (
        result["receipt"]["native_execution_fingerprint"],
        result["proof_manifest"]["proof_fingerprint"],
        tuple((row["path"], row["sha256"]) for row in result["proof_manifest"]["artifacts"]),
    )


def _tamper_probe(result: dict[str, Any], root: Path) -> bool:
    source = Path(result["output_dir"])
    probe = root / f"tamper-native-{result['manifest']['studio_id']}"
    if probe.exists():
        shutil.rmtree(probe)
    shutil.copytree(source, probe)
    first = result["proof_manifest"]["artifacts"][0]["path"]
    target = probe / first
    target.write_bytes(target.read_bytes() + b"\nTAMPER")
    try:
        verify_native_execution_proof(probe, result["proof_manifest"])
    except StudioNativeActivationError:
        return True
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    return False


def _by_engine(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["engine_id"]: row for row in result["ledger"]["organs"]}


def _assert_truthful_capabilities(result: dict[str, Any]) -> None:
    for row in result["ledger"]["organs"]:
        executed = set(row.get("executed_capabilities") or [])
        required = set(row.get("required_capabilities") or [])
        if not executed.issubset(required):
            raise AssertionError(f"{row['engine_id']} claimed undeclared native capability")
        missing = required - executed
        if row["execution_state"] == "NATIVE_EXECUTED" and missing:
            raise AssertionError(f"{row['engine_id']} was promoted despite missing capabilities")
        if row["execution_state"] == "PARTIAL_NATIVE_EXECUTION" and not (executed and missing):
            raise AssertionError(f"{row['engine_id']} partial state is not truthful")
        if row["execution_state"] == "SOURCE_BOUND_ONLY" and executed:
            raise AssertionError(f"{row['engine_id']} source-bound state contains execution claims")


def _expected_states(studio_id: str) -> dict[str, str]:
    if studio_id == "site_studio":
        return {
            "market_command": "NATIVE_EXECUTED",
            "nichefoundry": "PARTIAL_NATIVE_EXECUTION",
            "document_studio": "PARTIAL_NATIVE_EXECUTION",
            "evidex": "PARTIAL_NATIVE_EXECUTION",
            "commercial_truth": "PARTIAL_NATIVE_EXECUTION",
        }
    if studio_id == "professional_correspondence_studio":
        return {
            "outlook_mail_core": "NATIVE_EXECUTED",
            "document_studio": "NATIVE_EXECUTED",
            "commercial_truth": "NATIVE_EXECUTED",
            "evidex": "SOURCE_BOUND_ONLY",
        }
    if studio_id == "finance_readiness_studio":
        return {
            "nichefoundry": "NATIVE_EXECUTED",
            "sophia": "NATIVE_EXECUTED",
            "vamp": "NATIVE_EXECUTED",
            "document_studio": "PARTIAL_NATIVE_EXECUTION",
            "evidex": "PARTIAL_NATIVE_EXECUTION",
            "commercial_truth": "PARTIAL_NATIVE_EXECUTION",
        }
    if studio_id == "article_publication_studio":
        return {
            "nichefoundry": "NATIVE_EXECUTED",
            "sophia": "NATIVE_EXECUTED",
            "document_studio": "PARTIAL_NATIVE_EXECUTION",
            "evidex": "PARTIAL_NATIVE_EXECUTION",
            "commercial_truth": "PARTIAL_NATIVE_EXECUTION",
        }
    raise AssertionError(f"missing native activation expectation for {studio_id}")


def run_gauntlet(*, output_dir: Path | None = None) -> dict[str, Any]:
    owned = tempfile.TemporaryDirectory(prefix="dio-studio-native-") if output_dir is None else None
    out = Path(owned.name) if owned else Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    composition_regression = run_composition_gauntlet(output_dir=out / "composition-regression")
    if composition_regression.get("acceptance_token") != "DIO_STUDIO_HARVEST_READY":
        raise AssertionError("Studio Harvest composition regression failed")

    studios: dict[str, Any] = {}
    for studio_id, manifest_path in CASES.items():
        first = activate_studio_case(manifest_path=manifest_path, output_dir=out / studio_id / "run-a")
        second = activate_studio_case(manifest_path=manifest_path, output_dir=out / studio_id / "run-b")
        if _identity(first) != _identity(second):
            raise AssertionError(f"{studio_id} native execution is non-deterministic")
        verify_studio_proof(Path(first["composition"]["output_dir"]), first["composition"]["proof_manifest"])
        verify_native_execution_proof(Path(first["output_dir"]), first["proof_manifest"])
        verify_native_execution_proof(Path(second["output_dir"]), second["proof_manifest"])
        if not _tamper_probe(first, out):
            raise AssertionError(f"{studio_id} native execution tamper detection failed")
        _assert_truthful_capabilities(first)

        receipt = first["receipt"]
        if receipt["native_multi_organ_execution"] != "PASS":
            raise AssertionError(f"{studio_id} did not reach native multi-organ execution")
        if receipt["organ_execution_truth"] != "NATIVE_MULTI_ORGAN_EXECUTION_PROVED_WITH_AUXILIARY_GAPS":
            raise AssertionError(f"{studio_id} execution truth was unexpectedly promoted or degraded")
        if any(receipt[key] != "REFUSE" for key in ("external_publication", "external_send", "media_spend", "payment")):
            raise AssertionError(f"{studio_id} external authority drift")
        if receipt["authority_created"] or receipt["external_effects"] or receipt["new_engine_created"]:
            raise AssertionError(f"{studio_id} native execution created forbidden effects or a new engine")

        engines = _by_engine(first)
        if engines["lingua"]["execution_state"] != "NATIVE_EXECUTED":
            raise AssertionError(f"{studio_id} did not execute LINGUA natively")
        if engines["vesper"]["execution_state"] != "PARTIAL_NATIVE_EXECUTION":
            raise AssertionError(f"{studio_id} Vesper route truth changed unexpectedly")

        for engine_id, state in _expected_states(studio_id).items():
            if engines[engine_id]["execution_state"] != state:
                raise AssertionError(f"{studio_id} {engine_id} expected {state}, got {engines[engine_id]['execution_state']}")

        studios[studio_id] = {
            "native_multi_organ_execution": "PASS",
            "deterministic_native_execution": "PASS",
            "native_tamper_detection": "PASS",
            "truthful_capability_accounting": "PASS",
            "authority_boundary": "PASS",
            "organ_execution_truth": receipt["organ_execution_truth"],
            "native_organ_count": receipt["native_organ_count"],
            "partial_organ_count": receipt["partial_organ_count"],
            "source_bound_only_count": receipt["source_bound_only_count"],
            "external_publication": "REFUSE",
            "external_send": "REFUSE",
            "media_spend": "REFUSE",
            "payment": "REFUSE",
            "human_gate": "NEEDS_YOU",
            "native_execution_fingerprint": receipt["native_execution_fingerprint"],
        }

    result = {
        "schema": "dio.studio_native_execution_gauntlet_receipt.v1",
        "composition_regression": "PASS",
        "studio_count": len(studios),
        "studios": studios,
        "new_engine_created": False,
        "external_effects": False,
        "acceptance_token": ACCEPTANCE_TOKEN,
    }
    (out / "STUDIO_NATIVE_EXECUTION_GAUNTLET_RECEIPT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owned is not None:
        owned.cleanup()
    return result
