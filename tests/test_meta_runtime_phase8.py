from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from products.meta_runtime import EXPECTED_META, MetaRuntimeError, build_runtime_plan, load_runtime_registry, validate_runtime_registry
from products.meta_runtime_gauntlet import ACCEPTANCE_TOKEN, run_meta_runtime_gauntlet
from products.reference_gauntlet import REGISTRY_PATH as INCARNATION_REGISTRY_PATH


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_registry_consolidates_exactly_four_meta_primitives() -> None:
    registry = load_runtime_registry(ROOT)
    assert {row["id"] for row in registry["meta_capabilities"]} == EXPECTED_META
    assert registry["runtime_entrypoint"] == "products/meta_runtime.py"
    assert registry["runtime_order"] == ["meta_evidence", "meta_assurance", "meta_authority", "meta_room"]
    assert registry["laws"]["single_runtime_entrypoint"] is True
    assert registry["laws"]["executes_external_effects"] is False


def test_runtime_rejects_unsafe_law_and_dependency_reordering() -> None:
    registry = copy.deepcopy(load_runtime_registry(ROOT))
    registry["laws"]["creates_authority"] = True
    with pytest.raises(MetaRuntimeError):
        validate_runtime_registry(registry, root=ROOT)
    registry = copy.deepcopy(load_runtime_registry(ROOT))
    registry["runtime_order"] = ["meta_assurance", "meta_evidence", "meta_authority", "meta_room"]
    with pytest.raises(MetaRuntimeError):
        validate_runtime_registry(registry, root=ROOT)


def test_each_reference_incarnation_resolves_one_complete_runtime_plan() -> None:
    references = json.loads(INCARNATION_REGISTRY_PATH.read_text(encoding="utf-8"))
    fingerprints = set()
    for entry in references["incarnations"]:
        plan = build_runtime_plan(ROOT, ROOT / entry["manifest"])
        assert [step["meta_id"] for step in plan["steps"]] == ["meta_evidence", "meta_assurance", "meta_authority", "meta_room"]
        assert all(step["authority"] is False and step["execution"] is False and step["external_effects"] is False for step in plan["steps"])
        assert plan["compiled_gates"]["execution"]["state"] == "NEEDS_YOU"
        assert plan["compiled_gates"]["external_release"]["state"] == "REFUSE"
        fingerprints.add(plan["plan_fingerprint"])
    assert len(fingerprints) == 4


def test_full_meta_runtime_gauntlet_is_deterministic_and_non_authorizing(tmp_path: Path) -> None:
    receipt = run_meta_runtime_gauntlet(output_dir=tmp_path / "phase8")
    assert receipt["acceptance_token"] == ACCEPTANCE_TOKEN
    assert receipt["incarnation_count"] == 4
    assert receipt["meta_primitive_count"] == 4
    assert receipt["legacy_registry_alignment"] == "PASS"
    assert receipt["deterministic_planning"] == "PASS"
    assert receipt["deterministic_invocation"] == "PASS"
    assert receipt["input_immutability"] == "PASS"
    assert receipt["authority_created"] is False
    assert receipt["executor_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release_authorized"] is False
    assert receipt["external_release_gate"] == "REFUSE"
    assert all(row["deterministic"] and row["input_immutable"] for row in receipt["products"])
    runtime_schema = json.loads((ROOT / "schemas" / "dio_meta_runtime_receipt.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(runtime_schema)
    for entry in json.loads(INCARNATION_REGISTRY_PATH.read_text(encoding="utf-8"))["incarnations"]:
        runtime_receipt = json.loads((tmp_path / "phase8" / entry["slug"] / "META_RUNTIME_RECEIPT.json").read_text(encoding="utf-8"))
        Draft202012Validator(runtime_schema).validate(runtime_receipt)


def test_meta_runtime_is_not_a_fifth_meta_product_or_vertical_executor() -> None:
    assert not (ROOT / "config" / "products" / "manifests" / "meta_runtime.json").exists()
    source = (ROOT / "products" / "meta_runtime.py").read_text(encoding="utf-8")
    assert "external_release_authorized" in source
    assert "capability_lease_created" in source
    assert "authorization_created" in source
