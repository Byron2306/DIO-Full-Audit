from __future__ import annotations

from pathlib import Path

from products.commercial_pricing_registry import build_commercial_pricing_registry
from presence_core.intake_scope_quote import build_intake_requirement
from presence_core.product_binding_registry import (
    ARCHETYPE_PRODUCTS,
    PHASE7_ACCEPTANCE,
    ROUTE_PRODUCTS,
    build_phase8_binding_registry,
    build_phase8_execution_profile,
    compile_product_journey_binding,
)


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ARCHETYPE_COUNTS = {
    "A": 6,
    "B": 4,
    "C": 8,
    "D": 32,
    "E": 11,
    "F": 4,
    "G": 2,
    "H": 1,
}


def test_phase8_registry_reconciles_exact_53_plus_15_portfolio() -> None:
    commercial = build_commercial_pricing_registry(ROOT)
    registry = build_phase8_binding_registry(ROOT)

    assert registry["schema"] == "dio.customer_journey.phase8_binding_registry.v1"
    assert registry["product_count"] == 68
    assert registry["historical_53_count"] == 53
    assert registry["canon_extension_count"] == 15
    assert registry["archetype_count"] == 8
    assert registry["route_count"] == 10
    assert registry["archetype_counts"] == EXPECTED_ARCHETYPE_COUNTS
    assert registry["unknown_archetypes"] == []
    assert registry["unknown_fulfilment_routes"] == []
    assert registry["bespoke_commerce_pipelines"] == []
    assert registry["authority_leaks"] == []
    assert len(registry["registry_sha256"]) == 64

    commercial_names = {row["name"] for row in commercial["products"]}
    bound_names = {row["product_name"] for row in registry["bindings"]}
    assert commercial_names == bound_names
    assert len(bound_names) == 68


def test_phase8_frozen_archetype_and_route_assignments_are_unique() -> None:
    archetype_names = [
        name
        for names in ARCHETYPE_PRODUCTS.values()
        for name in names
    ]
    route_names = [
        name
        for names in ROUTE_PRODUCTS.values()
        for name in names
    ]
    assert len(archetype_names) == len(set(archetype_names)) == 68
    assert len(route_names) == len(set(route_names)) == 68
    assert set(archetype_names) == set(route_names)


def test_every_binding_reuses_shared_lifecycle_and_preserves_authority_boundary() -> None:
    registry = build_phase8_binding_registry(ROOT)

    for binding in registry["bindings"]:
        lifecycle = binding["journey_lifecycle"]
        assert lifecycle["owner"] == "presence_core.journey_core"
        assert lifecycle["product_specific_lifecycle_code"] is False
        assert lifecycle["surface_neutral"] is True
        assert lifecycle["presence_authority"] is False

        assert binding["authority_created"] is False
        assert binding["external_send_authority"] is False
        assert binding["external_effects"] is False

        release = binding["release_profile"]
        assert release["exact_manifest_human_approval"] is True
        assert release["one_use_release_authority"] is True
        assert release["fulfilment_success_is_not_release_authority"] is True

        settlement = binding["settlement_profile"]
        assert settlement["controlled_test_revenue_recognised"] is False
        assert settlement["controlled_test_market_validation_eligible"] is False
        assert settlement["settlement_never_creates_release_authority"] is True

        assert binding["delivery_profile"]["delivery_receipt_required"] is True
        assert binding["delivery_profile"]["close_requires_delivery_receipt"] is True


def test_every_binding_reuses_phase2_intake_scope_pricing_and_quote_truth() -> None:
    registry = build_phase8_binding_registry(ROOT)
    commercial = {
        row["name"]: row
        for row in build_commercial_pricing_registry(ROOT)["products"]
    }

    for binding in registry["bindings"]:
        product_name = binding["product_name"]
        requirement = build_intake_requirement(ROOT, product_name)
        product = commercial[product_name]

        assert binding["intake_profile"]["required_inputs"] == requirement["required_inputs"]
        assert binding["intake_profile"]["optional_inputs"] == requirement["optional_inputs"]
        assert binding["scope_profile"] == requirement["scope"]
        assert binding["pricing_profile"]["pricing_model"] == product["pricing_model"]
        assert binding["pricing_profile"]["reference_band_zar"] == product["reference_band_zar"]
        assert binding["quote_authority"] == product["quote_authority"]


def test_all_ten_routes_are_resolved_to_pinned_or_native_sources() -> None:
    registry = build_phase8_binding_registry(ROOT)
    routes = {row["route_id"]: row for row in registry["routes"]}

    assert set(routes) == set(ROUTE_PRODUCTS)
    for route_id, route in routes.items():
        assert len(route["route_fingerprint"]) == 64
        assert route["authority_created"] is False
        assert route["external_send_authority"] is False
        if route["execution_class"] == "native":
            assert (ROOT / route["source_path"]).is_file()
            assert len(route["source_sha256"]) == 64
        else:
            assert route["repository"]
            assert len(route["repository_commit"]) == 40
            assert route["source_sha256"] is None

    for route_id in (
        "homs_assessment",
        "homs_learning",
        "sophia_review",
        "vamp_snapshot",
        "evidex_evidence",
        "obligation_assurance",
        "document_studio",
        "nichefoundry_campaign",
    ):
        assert routes[route_id]["proof_state"] == "PHASE7_VERIFIED"
        assert routes[route_id]["proof_ref"]["token"] == PHASE7_ACCEPTANCE["token"]


def test_market_intelligence_and_vesper_routes_are_not_campaign_aliases() -> None:
    registry = build_phase8_binding_registry(ROOT)
    routes = {row["route_id"]: row for row in registry["routes"]}

    market = routes["market_intelligence"]
    assert market["archetypes"] == ["F"]
    assert market["source_path"] == "market_command/intelligence.py"
    assert market["adapter_id"] == "dio.organ.market_intelligence"
    assert market["proof_state"] == "PHASE8_FRESH_PROOF_REQUIRED"

    vesper = routes["vesper_case_service"]
    assert vesper["archetypes"] == ["H"]
    assert vesper["source_path"] == "presence_core/vesper_journey_runtime.py"
    assert vesper["adapter_id"] == "dio.organ.vesper_case_service"
    assert vesper["proof_state"] == "PHASE8_FRESH_PROOF_REQUIRED"


def test_all_68_execution_profiles_are_deterministic_and_non_authoritative() -> None:
    registry = build_phase8_binding_registry(ROOT)
    for binding in registry["bindings"]:
        product_name = binding["product_name"]
        first = build_phase8_execution_profile(ROOT, product_name)
        second = build_phase8_execution_profile(ROOT, product_name)

        assert first == second
        assert first["schema"] == "dio.fulfilment_execution_profile.v1"
        assert first["journey_product_id"] == product_name
        assert first["compiled_product_id"] == binding["product_id"]
        assert first["phase8_binding_sha256"] == binding["binding_sha256"]
        assert first["execution_gate"]["state"] == "NEEDS_YOU"
        assert len(first["execution_profile_sha256"]) == 64
        assert first["authority_created"] is False
        assert first["release_authority_created"] is False
        assert first["external_send_authority"] is False
        assert len(first["executor_capabilities"]) == 1
        assert first["executor_capabilities"][0]["resolution_state"] == "RESOLVED"


def test_missing_product_compiler_manifests_are_reported_not_invented() -> None:
    registry = build_phase8_binding_registry(ROOT)
    states = {
        row["product_compiler_manifest"]["state"]
        for row in registry["bindings"]
    }
    assert states.issubset(
        {"CANONICAL_MANIFEST_PRESENT", "NO_CANONICAL_PRODUCT_MANIFEST"}
    )
    assert "NO_CANONICAL_PRODUCT_MANIFEST" in states
    for binding in registry["bindings"]:
        if binding["product_compiler_manifest"]["state"] == "NO_CANONICAL_PRODUCT_MANIFEST":
            assert binding["product_compiler_manifest"]["path"] is None
            assert "does not manufacture" in binding["truth_boundary"]


def test_single_product_compilation_refuses_non_canonical_name() -> None:
    try:
        compile_product_journey_binding(ROOT, "Definitely Not A DIO Product")
        assert False, "unknown product must be refused"
    except ValueError as exc:
        assert "canonical 68-product" in str(exc)
