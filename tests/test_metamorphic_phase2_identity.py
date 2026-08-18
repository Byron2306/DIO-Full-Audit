import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from metamorphic.contracts import MetamorphicRole
from metamorphic.registry import (
    DEFAULT_CONFIG,
    PHASE2_EXIT_TOKEN,
    MetamorphicRegistryError,
    _validate_manifest_authority,
    _validate_required_organs,
    build_reference_registry,
    phase2_identity_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase2_receipt_proves_exact_three_reference_units():
    receipt = phase2_identity_receipt(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE2_EXIT_TOKEN
    assert receipt["unit_count"] == 3
    assert receipt["same_unit_product_and_capability"] is True
    assert receipt["professional_proof_bound"] is True
    assert receipt["site_studio_reference_excluded"] is True
    assert receipt["new_engine_created"] is False
    assert receipt["authority_widened"] is False
    assert receipt["resolver_policy_implemented"] is False
    assert receipt["semantic_law_promoted"] is False


def test_phase2_product_and_capability_views_are_same_object():
    registry = build_reference_registry(REPO_ROOT)
    for unit in registry.units():
        product = registry.as_role(unit.unit_id, MetamorphicRole.PRODUCT)
        capability = registry.as_role(unit.unit_id, MetamorphicRole.CAPABILITY)
        assert product is unit
        assert capability is unit
        assert product is capability
        assert product.unit_digest == capability.unit_digest


def test_phase2_role_views_preserve_executor_evidence_quality_and_authority():
    registry = build_reference_registry(REPO_ROOT)
    unit = registry.get("professional_correspondence_studio")
    product = registry.as_role(unit.unit_id, "product")
    capability = registry.as_role(unit.unit_id, "capability")
    assert product.executor_id == capability.executor_id
    assert product.executor_digest == capability.executor_digest
    assert product.evidence_contract == capability.evidence_contract
    assert product.quality_contract == capability.quality_contract
    assert product.authority_ceiling == capability.authority_ceiling == "controlled_artifact_only"


def test_phase2_capability_indexes_point_to_stored_unit_objects():
    registry = build_reference_registry(REPO_ROOT)
    expectations = {
        "professional_correspondence": "professional_correspondence_studio",
        "finance_readiness": "finance_readiness_studio",
        "article_publication": "article_publication_studio",
    }
    for capability, unit_id in expectations.items():
        providers = registry.providers_for(capability)
        assert len(providers) == 1
        assert providers[0] is registry.get(unit_id)


def test_phase2_source_executor_and_professional_proof_digests_bind_real_repo_bytes():
    config = json.loads((REPO_ROOT / DEFAULT_CONFIG).read_text(encoding="utf-8"))
    executor_path = REPO_ROOT / config["executor"]["executor_path"]
    professional_proof_path = REPO_ROOT / config["professional_proof"]["path"]
    registry = build_reference_registry(REPO_ROOT)
    by_id = {row["unit_id"]: row for row in config["units"]}
    for unit in registry.units():
        assert unit.source_digest == _sha(REPO_ROOT / by_id[unit.unit_id]["manifest_path"])
        assert unit.executor_digest == _sha(executor_path)
        assert unit.evidence_contract["native_executor_path"] == config["executor"]["executor_path"]
        assert unit.evidence_contract["professional_proof_digest"] == _sha(professional_proof_path)
        assert unit.evidence_contract["professional_acceptance_token"] == "DIO_PROFESSIONAL_TASK_GAUNTLET_VERIFIED"
        assert unit.evidence_contract["verified_case_count"] == 3
        assert unit.maturity_state == "professional_task_verified"


def test_phase2_professional_cases_are_native_and_authority_bound():
    registry = build_reference_registry(REPO_ROOT)
    for unit in registry.units():
        cases = unit.evidence_contract["verified_cases"]
        assert len(cases) == 3
        assert {row["tier"] for row in cases} == {"normal", "messy", "adversarial"}
        assert all(str(row["receipt_fingerprint"]).startswith("sha256:") for row in cases)
        assert min(int(row["score"]) for row in cases) >= 98


def test_phase2_site_studio_is_not_a_reference_unit():
    registry = build_reference_registry(REPO_ROOT)
    ids = {unit.unit_id for unit in registry.units()}
    assert "site_studio" not in ids
    assert ids == {
        "professional_correspondence_studio",
        "finance_readiness_studio",
        "article_publication_studio",
    }


def test_phase2_duplicate_identity_with_changed_contract_is_refused():
    registry = build_reference_registry(REPO_ROOT)
    unit = registry.get("professional_correspondence_studio")
    changed = replace(unit, authority_ceiling="observation_only")
    with pytest.raises(MetamorphicRegistryError):
        registry.register(changed)
    assert registry.get(unit.unit_id) is unit


def test_phase2_idempotent_same_contract_registration_returns_existing_object():
    registry = build_reference_registry(REPO_ROOT)
    unit = registry.get("finance_readiness_studio")
    duplicate_value = replace(unit)
    assert duplicate_value is not unit
    returned = registry.register(duplicate_value)
    assert returned is unit
    assert registry.get(unit.unit_id) is unit


def test_phase2_undeclared_role_is_refused_without_cloning():
    registry = build_reference_registry(REPO_ROOT)
    unit = registry.get("article_publication_studio")
    with pytest.raises(MetamorphicRegistryError):
        registry.as_role(unit.unit_id, MetamorphicRole.COMPOSITE_NODE)
    assert registry.get(unit.unit_id) is unit


def test_phase2_unsafe_authority_manifest_is_refused():
    manifest = json.loads(
        (REPO_ROOT / "config/studio_harvest/professional_correspondence_studio.json").read_text(encoding="utf-8")
    )
    required = json.loads((REPO_ROOT / DEFAULT_CONFIG).read_text(encoding="utf-8"))["required_manifest_authority"]
    unsafe = copy.deepcopy(manifest)
    unsafe["authority"]["external_send"] = "ALLOW"
    with pytest.raises(MetamorphicRegistryError):
        _validate_manifest_authority(unsafe, required)


def test_phase2_missing_required_organ_source_fails_closed(tmp_path):
    manifest = {
        "required_organs": [
            {
                "engine_id": "ghost",
                "source_ref": "missing/ghost.py",
                "capabilities": ["ghost.capability"],
            }
        ]
    }
    with pytest.raises(MetamorphicRegistryError):
        _validate_required_organs(tmp_path, manifest)


def test_phase2_registry_fingerprint_is_deterministic():
    first = build_reference_registry(REPO_ROOT)
    second = build_reference_registry(REPO_ROOT)
    assert first.registry_fingerprint == second.registry_fingerprint
    assert [unit.unit_digest for unit in first.units()] == [unit.unit_digest for unit in second.units()]
