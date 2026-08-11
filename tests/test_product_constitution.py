from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts.check_product_constitution import EXPECTED_FLAGS, EXPECTED_MATURITY, EXPECTED_META, EXPECTED_PATTERNS, EXPECTED_PROFILE_CLASSES, EXPECTED_SUITES, validate_constitution

ROOT = Path(__file__).resolve().parents[1]

def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def synthetic_manifest() -> dict:
    flags = {flag: False for flag in EXPECTED_FLAGS}
    return {
        "schema":"dio.product_manifest.v1","manifest_version":"1.0.0","product_id":"constitution.synthetic","name":"Constitution Synthetic Product",
        "incarnation":{"id":"constitution.synthetic","surface":"internal","buyer_context":[]},"suite_ids":[],"work_patterns":["WP01"],"meta_capabilities":["meta_evidence","meta_room"],
        "profiles":{"domain":[{"profile_id":"phase1.synthetic_domain","binding":"UNBOUND"}],"framework":[{"profile_id":"phase1.synthetic_framework","binding":"UNBOUND"}],"authority":[{"profile_id":"phase1.synthetic_authority","binding":"UNBOUND"}],"connector_pack":[{"profile_id":"phase1.synthetic_connector","binding":"UNBOUND"}],"output":[{"profile_id":"phase1.synthetic_output","binding":"UNBOUND"}],"commercial":[{"profile_id":"phase1.synthetic_commercial","binding":"UNBOUND"}]},
        "capability_requirements":[{"capability_id":"evidence.normalize","required":True,"execution_required":False}],
        "executor_policy":{"resolution":"compiler","missing_required_executor":"REFUSE"},"maturity":{"state":"registered","operational_flags":flags}
    }

def test_constitution_gate_freezes_expected_cardinalities() -> None:
    result = validate_constitution()
    assert result["state"] == "DIO_PRODUCT_CONSTITUTION_FROZEN"
    assert (result["work_patterns"],result["meta_capabilities"],result["profile_classes"],result["maturity_states"],result["operational_flags"],result["suites"]) == (12,4,6,9,7,6)

def test_work_patterns_are_exact_wp01_to_wp12() -> None:
    assert {row["id"] for row in load("config/portfolio/work_patterns.json")["work_patterns"]} == EXPECTED_PATTERNS

def test_meta_registry_is_exactly_four_primitives() -> None:
    payload = load("config/portfolio/meta_capabilities.json")
    assert {row["id"] for row in payload["meta_capabilities"]} == EXPECTED_META
    assert payload["composition_authority"] == "config/products/manifests/"

def test_profile_classes_are_closed_in_constitution_v1() -> None:
    assert {row["id"] for row in load("config/portfolio/profile_classes.json")["profile_classes"]} == EXPECTED_PROFILE_CLASSES

def test_maturity_order_and_operational_flags_are_independent() -> None:
    payload = load("config/portfolio/maturity_vocabulary.json")
    assert [row["id"] for row in payload["states"]] == EXPECTED_MATURITY
    assert {row["id"] for row in payload["operational_flags"]} == EXPECTED_FLAGS
    assert payload["laws"]["no_automatic_legacy_status_mapping"] is True

def test_suites_are_packaging_only() -> None:
    payload = load("config/portfolio/suites.json")
    assert {row["id"] for row in payload["suites"]} == EXPECTED_SUITES
    assert payload["laws"] == {"suite_is_market_packaging_only":True,"suite_changes_runtime":False,"suite_creates_authority":False,"suite_changes_maturity":False}

def test_manifest_schema_accepts_capability_first_registered_product() -> None:
    schema = load("schemas/dio_product_manifest.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(synthetic_manifest())

def test_manifest_schema_rejects_missing_profile_class() -> None:
    schema = load("schemas/dio_product_manifest.schema.json"); payload = synthetic_manifest(); del payload["profiles"]["authority"]
    with pytest.raises(ValidationError): Draft202012Validator(schema).validate(payload)

def test_manifest_schema_hard_locks_missing_executor_to_refuse() -> None:
    schema = load("schemas/dio_product_manifest.schema.json"); payload = synthetic_manifest(); payload["executor_policy"]["missing_required_executor"] = "ALLOW"
    with pytest.raises(ValidationError): Draft202012Validator(schema).validate(payload)

def test_bound_profile_reference_requires_version_and_hash() -> None:
    schema = load("schemas/dio_product_manifest.schema.json"); payload = synthetic_manifest(); payload["profiles"]["domain"][0]["binding"] = "BOUND"
    with pytest.raises(ValidationError): Draft202012Validator(schema).validate(payload)

def test_manifest_has_no_direct_organ_or_executor_wiring_fields() -> None:
    schema = load("schemas/dio_product_manifest.schema.json"); payload = synthetic_manifest(); payload["organ_plan"] = [{"organ_id":"evidex"}]
    with pytest.raises(ValidationError): Draft202012Validator(schema).validate(payload)
