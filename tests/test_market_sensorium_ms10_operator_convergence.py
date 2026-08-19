from __future__ import annotations

from market_sensorium.operator_convergence import MS10_VERIFIED, apply_ms10_gate


def _good() -> dict:
    return {
        "ms9_acceptance": "DIO_MARKET_SENSORIUM_AUTONOMIC_MULTI_CYCLE_SOAK_VERIFIED",
        "surface_count": 3,
        "all_surfaces_canonical_truth_bound": True,
        "all_surfaces_current_repo_bound": True,
        "all_surface_servers_current_and_local": True,
        "all_sensorium_features_visible": True,
        "existing_operator_capabilities_preserved": True,
        "independent_sensorium_truth_engines_created": 0,
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "authority_created": False,
        "external_effects": False,
    }


def test_ms10_accepts_three_current_surfaces_on_one_canonical_truth_plane() -> None:
    assert apply_ms10_gate(_good()) == MS10_VERIFIED


def test_ms10_refuses_stale_repo_surface() -> None:
    value = _good()
    value["all_surfaces_current_repo_bound"] = False
    assert apply_ms10_gate(value) == "REFUSE_STALE_OPERATOR_SURFACE_REPOSITORY"


def test_ms10_refuses_divergent_truth_engine() -> None:
    value = _good()
    value["all_surfaces_canonical_truth_bound"] = False
    assert apply_ms10_gate(value) == "REFUSE_DIVERGENT_OPERATOR_TRUTH_SOURCES"


def test_ms10_refuses_operator_capability_regression() -> None:
    value = _good()
    value["existing_operator_capabilities_preserved"] = False
    assert apply_ms10_gate(value) == "REFUSE_OPERATOR_CAPABILITY_REGRESSION"


def test_ms10_refuses_truth_or_authority_inflation() -> None:
    value = _good()
    value["market_demand_claimed"] = True
    assert apply_ms10_gate(value) == "REFUSE_OPERATOR_SURFACE_TRUTH_OR_AUTHORITY_INFLATION"
