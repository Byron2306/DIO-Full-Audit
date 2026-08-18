from pathlib import Path

from metamorphic.integration_inventory import (
    CANONICAL_INTEGRATION_ANCHORS,
    CONSTITUTIONAL_INVARIANTS,
    PHASE0_EXIT_TOKEN,
    validate_integration_inventory,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_phase0_canonical_anchors_are_present():
    receipt = validate_integration_inventory(REPO_ROOT)
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == PHASE0_EXIT_TOKEN
    assert receipt["missing"] == []
    assert receipt["duplicate_paths"] == []
    assert receipt["anchor_count"] == len(CANONICAL_INTEGRATION_ANCHORS)


def test_phase0_freezes_no_authority_from_learning():
    assert "anything_can_become_anything_except_authority" in CONSTITUTIONAL_INVARIANTS
    assert "learning_never_mints_or_widens_authority" in CONSTITUTIONAL_INVARIANTS
    assert "no_outcome_crystal_before_world_settlement" in CONSTITUTIONAL_INVARIANTS


def test_phase0_declares_m2_as_required_destination():
    receipt = validate_integration_inventory(REPO_ROOT)
    assert receipt["m2_destination_declared"] is True
    assert "m2_commercial_metabolism_is_required_destination" in CONSTITUTIONAL_INVARIANTS


def test_phase0_inventory_contains_no_runtime_engine_claim():
    receipt = validate_integration_inventory(REPO_ROOT)
    assert receipt["new_runtime_engines_created"] is False
    assert receipt["authority_widened"] is False


def test_phase0_missing_anchor_fails_closed(tmp_path):
    receipt = validate_integration_inventory(tmp_path)
    assert receipt["passed"] is False
    assert receipt["acceptance"] == "DIO_METAMORPHIC_M1_CONSTITUTION_BLOCKED"
    assert receipt["missing"]


def test_phase0_canon_document_freezes_primary_law_and_m2_goal():
    canon = (REPO_ROOT / "docs" / "DIO_METAMORPHIC_SPINE_M1.md").read_text(encoding="utf-8")
    assert "Anything can become anything else except authority." in canon
    assert "M2 — Commercial Metabolism" in canon
    assert "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED" in canon
