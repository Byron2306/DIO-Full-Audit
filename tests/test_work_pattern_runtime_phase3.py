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


def test_contractproof_evidence_pattern_is_partial_not_magically_ready() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    evidence = _by_pattern(plan)["WP01"]
    operations = _by_operation(evidence)
    assert evidence["runtime_state"] == "PARTIAL"
    assert operations["materialize_case"]["resolution_state"] == "RESOLVED"
    assert operations["capture_provenance"]["resolution_state"] == "RESOLVED"
    assert operations["map_evidence"]["resolution_state"] == "RESOLVED"
    assert operations["assess_sufficiency"]["resolution_state"] == "PLANNED"
    assert operations["emit_gaps"]["resolution_state"] == "PLANNED"


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
        expected = "RESOLVED" if catalog[capability_id]["status"] == "available" else "PLANNED"
        assert operations[operation_id]["resolution_state"] == expected
        expected_states.append(expected)
    assert operations["bind_evidence"]["resolution_state"] == "RESOLVED"
    assert obligation["runtime_state"] == ("READY" if all(state == "RESOLVED" for state in expected_states) else "PARTIAL")


def test_contractproof_proof_pattern_respects_provider_product_scope() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    proof = _by_pattern(plan)["WP11"]
    operations = _by_operation(proof)
    assert proof["runtime_state"] == "BLOCKED"
    assert operations["compile_portable_room"]["resolution_state"] == "UNAVAILABLE"
    assert "no earned provider declares applicability" in operations["compile_portable_room"]["reason"]
    assert operations["verify_integrity"]["resolution_state"] == "PLANNED"
    assert operations["prepare_disclosure"]["resolution_state"] == "PLANNED"


def test_phase3_runtime_never_relaxes_execution_or_human_authority() -> None:
    plan = plan_manifest(ROOT, MANIFEST)
    compiled = compile_manifest(ROOT, MANIFEST)
    assert plan["planning_gate"]["state"] == "NEEDS_IMPLEMENTATION"
    assert plan["execution_gate"]["state"] == "REFUSE"
    assert plan["compiler_execution_gate"]["state"] == "REFUSE"
    assert plan["authority_created"] is False
    assert plan["executor_created"] is False
    assert compiled["gates"]["execution"]["state"] == "REFUSE"
    for pattern in plan["patterns"]:
        assert pattern["human_gate"]["state"] == "NEEDS_YOU"


def test_phase3_new_capabilities_are_declared_planned_not_earned() -> None:
    catalog, _ = load_capability_catalog(ROOT)
    planned = {
        "evidence.sufficiency",
        "evidence.gaps",
        "intake.normalize",
        "intake.classify",
        "intake.missing_information",
        "document.project",
        "document.qa",
        "document.release.prepare",
        "proof.integrity.verify",
        "proof.disclosure.prepare",
    }
    for capability_id in planned:
        assert catalog[capability_id]["status"] == "planned"
        assert catalog[capability_id]["providers"] == []
