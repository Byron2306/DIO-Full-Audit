from __future__ import annotations

from pathlib import Path

from scripts.audit_genuine_profile_extension_coverage import audit


ROOT = Path(__file__).resolve().parents[1]


def test_all_genuine_profile_extensions_have_typed_profiles_without_auto_promotion() -> None:
    result = audit(ROOT)

    assert result["state"] == "reconciled"
    assert result["genuine_profile_extensions"] == 28
    assert result["typed_profiles"] == 28
    assert result["typed_unpromoted_profiles"] == 27
    assert result["typed_canonical_registered_profiles"] == 1
    assert result["missing_profiles"] == 0
    assert result["auto_promotable_profiles"] == 0
    assert result["orphan_typed_profiles"] == []
    assert result["errors"] == []
    assert result["warnings"] == []


def test_genuine_profile_extension_audit_separates_portfolio_registration_from_execution_identity() -> None:
    result = audit(ROOT)

    assert len(result["profiles"]) == 28
    canonical_rows = []
    for row in result["profiles"]:
        assert row["product_id"].startswith("dio_")
        if row["state"] == "typed_canonical_registered_profile_extension":
            canonical_rows.append(row)
            assert row["identity_state"] == "canonical_portfolio_registered_profile_extension"
            assert row["canonical_portfolio_registration"] is True
            assert row["canonical_identity_present"] is True
            assert row["meta_composition_present"] is True
        else:
            assert row["state"] == "typed_unpromoted_profile"
            assert row["identity_state"] == "genuine_profile_extension_unpromoted"
            assert row["canonical_portfolio_registration"] is False
            assert row["canonical_identity_present"] is False
            assert row["meta_composition_present"] is False

    assert [(row["profile_id"], row["product_id"]) for row in canonical_rows] == [
        ("vendorproof", "dio_vendorproof")
    ]
    assert "canonical portfolio registration remains distinct" in result["truth_boundary"]
    assert "not product execution proof" in result["truth_boundary"]
    assert "public launch authority" in result["truth_boundary"]
    assert "external release authority" in result["truth_boundary"]
