from __future__ import annotations

import copy
from pathlib import Path

from jsonschema import Draft202012Validator

from products.compiler import compile_manifest, load_capability_catalog, load_json
from products.work_pattern_runtime import FOCUS_PATTERNS, load_runtime_registry, plan_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "products" / "manifests" / "contractproof.json"


def _by_pattern(plan: dict) -> dict[str, dict]:
    return {row["work_pattern_id"]: row for row in plan["patterns"]}


def _by_operation(pattern: dict) -> dict[str, dict]:
    return {row["operation_id"]: row for row in pattern["operations"]}


def _expected_state(catalog: dict, capability_id: str) -> str:
    return "RESOLVED" if catalog[capability_id]["status"] == "available" else "PLANNED"


def test_registry_declares_exactly_twelve_patterns_and_five_v1_focus_contracts() -> None:
    contracts, payload, _ = load_runtime_registry(ROOT)
    assert set(contracts) == {f"WP{index:02d}" for index in range(1, 13)}
    assert set(payload["focus_patterns"]) == FOCUS_PATTERNS
    for pattern_id, contract in contracts.items():
        if pattern_id in FOCUS_PATTERNS:
            assert contract["runtime_stage"] == "v1_focus"
            assert contract["operations"]
        else:
            assert contract["runtime_stage"] == "declared"
            assert contract["operations"] == []


def test_contracts_are_capability_only_and_non_executing() -> None:
    contracts, _, _ = load_runtime_registry(ROOT)
    for contract in contracts.values():
        for operation in contract["operations"]:
            assert operation["execution_required"] is False
            assert not operation["capability_id"].startswith("product.executor.")
            assert "provider" not in operation
            assert "ref" not in operation
            assert "organ" not in operation


def test_schema_rejects_direct_provider_wiring() -> None:
    payload = load_json(ROOT / "config" / "portfolio" / "work_pattern_runtime.json")
    schema = load_json(ROOT / "schemas" / "dio_work_pattern_runtime.schema.json")
    tampered = copy.deepcopy(payload)
    tampered["contracts"][0]["operations"][0]["provider"] = "Evidex"
    errors = list(Draft202012Validator(schema).iter_errors(tampered))
    assert errors
    assert any("Additional properties are not allowed" in error.message for error in errors)


def test_contractproof_evidence_pattern_tracks_earned_frontier_without_creating_authority() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    evidence = _by_pattern(plan)["WP01"]
    operations = _by_operation(evidence)
    catalog, _ = load_capability_catalog(ROOT)
    assert operations["materialize_case"]["resolution_state"] == "RESOLVED"
    assert operations["capture_provenance"]["resolution_state"] == "RESOLVED"
    assert operations["map_evidence"]["resolution_state"] == "RESOLVED"
    assert operations["assess_sufficiency"]["resolution_state"] == _expected_state(catalog, "evidence.sufficiency")
    assert operations["emit_gaps"]["resolution_state"] == _expected_state(catalog, "evidence.gaps")
    expected_runtime = "READY" if all(row["resolution_state"] == "RESOLVED" for row in operations.values()) else "PARTIAL"
    assert evidence["runtime_state"] == expected_runtime
    assert evidence["human_gate"]["state"] == "NEEDS_YOU"


def test_contractproof_obligation_pattern_tracks_current_capability_frontier() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    obligation = _by_pattern(plan)["WP05"]
    operations = _by_operation(obligation)
    catalog, _ = load_capability_catalog(ROOT)
    obligation_capabilities = {
        "extract_obligations": "obligation.extract",
        "normalize_obligations": "obligation.normalize",
        "identify_deadlines": "obligation.deadlines",
        "assess_status": "obligation.evaluate",
    }
    expected_states = []
    for operation_id, capability_id in obligation_capabilities.items():
        expected = _expected_state(catalog, capability_id)
        assert operations[operation_id]["resolution_state"] == expected
        expected_states.append(expected)
    assert operations["bind_evidence"]["resolution_state"] == "RESOLVED"
    assert obligation["runtime_state"] == ("READY" if all(state == "RESOLVED" for state in expected_states) else "PARTIAL")


def test_contractproof_proof_pattern_keeps_capitalroom_scope_truthful_as_product_adapter_is_earned() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    proof = _by_pattern(plan)["WP11"]
    operations = _by_operation(proof)
    catalog, _ = load_capability_catalog(ROOT)
    capitalroom = next(row for row in catalog["proof.room.compile"]["providers"] if row["provider_id"] == "capitalroom_proof_room")
    assert "dio_contractproof" not in capitalroom["product_scope"]
    expected_room = "RESOLVED" if any("dio_contractproof" in row["product_scope"] for row in catalog["proof.room.compile"]["providers"]) else "UNAVAILABLE"
    assert operations["compile_portable_room"]["resolution_state"] == expected_room
    if expected_room == "RESOLVED":
        assert operations["compile_portable_room"]["provider"]["provider_id"] != "capitalroom_proof_room"
    assert operations["verify_integrity"]["resolution_state"] == _expected_state(catalog, "proof.integrity.verify")
    assert operations["prepare_disclosure"]["resolution_state"] == _expected_state(catalog, "proof.disclosure.prepare")
    expected_runtime = "READY" if all(row["resolution_state"] == "RESOLVED" for row in operations.values()) else "BLOCKED"
    assert proof["runtime_state"] == expected_runtime


def test_phase3_runtime_never_executes_or_relaxes_human_authority_even_when_product_executor_is_earned() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    compiled = compile_manifest(ROOT, MANIFEST)
    assert plan["planning_gate"]["state"] in {"ALLOW", "NEEDS_IMPLEMENTATION"}
    assert plan["execution_gate"]["state"] == "REFUSE"
    assert plan["compiler_execution_gate"]["state"] in {"REFUSE", "NEEDS_YOU"}
    assert plan["compiler_execution_gate"]["state"] != "ALLOW"
    assert plan["authority_created"] is False
    assert plan["executor_created"] is False
    assert compiled["gates"]["execution"]["state"] in {"REFUSE", "NEEDS_YOU"}
    assert compiled["gates"]["external_release"]["state"] == "REFUSE"
    for pattern in plan["patterns"]:
        assert pattern["human_gate"]["state"] == "NEEDS_YOU"


def test_unrelated_phase3_frontier_remains_planned_until_earned() -> None:
    catalog, _ = load_capability_catalog(ROOT)
    planned = {
        "intake.normalize",
        "intake.classify",
        "intake.missing_information",
        "document.project",
        "document.qa",
        "document.release.prepare",
    }
    for capability_id in planned:
        assert catalog[capability_id]["status"] == "planned"
        assert catalog[capability_id]["providers"] == []
