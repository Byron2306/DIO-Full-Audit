from pathlib import Path

from products.commercial_pricing_registry import build_commercial_pricing_registry


ROOT = Path(__file__).resolve().parents[1]


def _by_name(registry):
    return {row["name"]: row for row in registry["products"]}


def test_pricing_census_covers_exact_verified_68_product_portfolio():
    registry = build_commercial_pricing_registry(ROOT)
    assert registry["schema"] == "dio.commercial_pricing_registry.v1"
    assert registry["product_count"] == 68
    assert registry["historical_53_count"] == 53
    assert registry["canon_extension_count"] == 15
    assert len({row["product_id"] for row in registry["products"]}) == 68
    assert len({row["name"] for row in registry["products"]}) == 68
    assert registry["authority_created"] is False
    assert registry["external_effects"] is False


def test_every_product_has_explicit_commercial_shape_not_generic_fallback():
    registry = build_commercial_pricing_registry(ROOT)
    for row in registry["products"]:
        assert row["profile_source"] == "explicit_68_product_census"
        assert row["buyer_classes"]
        assert row["primary_scope_unit"]
        assert row["pricing_model"]
        assert row["reference_band_zar"]["min"] > 0
        assert row["reference_band_zar"]["max"] >= row["reference_band_zar"]["min"]
        assert row["pricing_state"] == "HYPOTHESIS"
        assert row["commercial_validation"] == "UNPROVED"
        assert row["customers_will_pay"] == "UNPROVED"
        assert row["quote_authority"]["mode"] in {"bounded_estimate", "operator_review"}
        assert row["authority_created"] is False


def test_census_distinguishes_everyday_professional_and_industrial_value_shapes():
    rows = _by_name(build_commercial_pricing_registry(ROOT))
    evidex = rows["Evidex EvidenceOps"]
    assert evidex["buyer_classes"] == ["C0", "C1", "C2", "C3", "C4", "C5"]
    assert evidex["primary_scope_unit"] == "evidence_item"
    assert evidex["pricing_model"] == "setup_plus_volume"
    assert evidex["industrial_scale_supported"] is True

    sophia = rows["Sophia Integrity"]
    assert "C0" in sophia["buyer_classes"] and "C5" in sophia["buyer_classes"]
    assert sophia["primary_scope_unit"] == "manuscript_page"
    assert "reference" in sophia["secondary_scope_units"]

    vamp = rows["VAMP Performance"]
    assert vamp["primary_scope_unit"] == "performance_evidence_item"
    assert "employee" in vamp["secondary_scope_units"]
    assert "C4" in vamp["buyer_classes"]

    edit = rows["Document Studio Edit"]
    assert edit["buyer_classes"][0] == "C0"
    assert edit["reference_band_zar"]["min"] < 500

    ai = rows["DIO AI Assurance"]
    assert ai["buyer_classes"][0] == "C2"
    assert ai["reference_band_zar"]["min"] >= 5000

    dora = rows["DORA Vendor Assurance"]
    assert dora["buyer_classes"] == ["C3", "C4", "C5"]
    assert dora["reference_band_zar"]["max"] >= 50000

    correspondence = rows["Professional Correspondence"]
    assert correspondence["buyer_classes"] == ["C0", "C1", "C2"]
    assert correspondence["reference_band_zar"]["max"] <= 1500


def test_enterprise_scale_is_not_naive_per_unit_multiplication():
    rows = _by_name(build_commercial_pricing_registry(ROOT))
    for name in (
        "Evidex EvidenceOps",
        "Sophia Integrity",
        "VAMP Performance",
        "DIO AI Assurance",
        "CriticalAI Assurance",
        "DORA Vendor Assurance",
        "POPIA Readiness",
    ):
        row = rows[name]
        assert row["enterprise_pricing"]["mode"] in {
            "setup_plus_volume", "setup_plus_usage", "programme", "retainer_plus_volume", "license_plus_usage"
        }
        assert row["enterprise_pricing"]["naive_unit_multiplication"] is False


def test_registry_refuses_silent_portfolio_drift(tmp_path: Path):
    fake = tmp_path / "config" / "atlas"
    fake.mkdir(parents=True)
    source = ROOT / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
    lines = source.read_text(encoding="utf-8").splitlines()
    (fake / "dio_meta_incarnation_crosswalk.csv").write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    try:
        build_commercial_pricing_registry(tmp_path)
    except ValueError as exc:
        assert "historical portfolio count" in str(exc).lower()
    else:
        raise AssertionError("pricing census silently accepted non-53 historical portfolio")
