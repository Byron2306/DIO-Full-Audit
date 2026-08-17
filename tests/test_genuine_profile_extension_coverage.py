from __future__ import annotations

from pathlib import Path

from scripts.audit_genuine_profile_extension_coverage import audit


ROOT = Path(__file__).resolve().parents[1]


def test_all_genuine_profile_extensions_have_typed_unpromoted_profiles() -> None:
    result = audit(ROOT)

    assert result["state"] == "reconciled"
    assert result["genuine_profile_extensions"] == 28
    assert result["typed_profiles"] == 28
    assert result["missing_profiles"] == 0
    assert result["auto_promotable_profiles"] == 0
    assert result["canonical_collisions"] == 0
    assert result["orphan_unpromoted_profiles"] == []
    assert result["errors"] == []


def test_genuine_profile_extension_audit_preserves_identity_and_authority_boundaries() -> None:
    result = audit(ROOT)

    assert len(result["profiles"]) == 28
    for row in result["profiles"]:
        assert row["state"] == "typed_unpromoted_profile"
        assert row["identity_state"] == "genuine_profile_extension_unpromoted"
        assert row["canonical_portfolio_registration"] is False
        assert row["product_id"].startswith("dio_")

    assert "not product execution proof" in result["truth_boundary"]
    assert "public launch authority" in result["truth_boundary"]
    assert "external release authority" in result["truth_boundary"]
