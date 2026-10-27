from pathlib import Path

from market_capital.atlas_search import build_search_signature, compile_discovery_plan
from market_capital.sources import load_capital_sources


ROOT = Path(".")


def test_education_and_governed_ai_generate_different_search_spaces():
    education = build_search_signature(ROOT, ["homs_assess"])
    trust = build_search_signature(ROOT, ["agent_authority"])

    assert education["canonical_product_ids"] == ["homs_assess"]
    assert trust["canonical_product_ids"] == ["agent_authority"]
    assert education["domain_ids"] != trust["domain_ids"]
    assert education["query_families"] != trust["query_families"]
    assert education["source_class_preferences"] != trust["source_class_preferences"]
    assert education["truth_class"] == "STRATEGIC_SEARCH_MODEL_OUTPUT"
    assert trust["truth_class"] == "STRATEGIC_SEARCH_MODEL_OUTPUT"
    assert education["authority_created"] is False
    assert trust["authority_created"] is False


def test_signature_is_grounded_in_canonical_crosswalk_not_stale_product_aliases():
    signature = build_search_signature(ROOT, ["homs_assess"])
    assert "D902" in signature["domain_ids"]
    assert "D904" in signature["domain_ids"]
    assert "WP06" in signature["work_pattern_ids"]
    assert signature["product_records"][0]["incarnation"] == "HOMS Assess"


def test_discovery_plan_is_bounded_and_reserves_novelty():
    signatures = [
        build_search_signature(ROOT, ["homs_assess"]),
        build_search_signature(ROOT, ["agent_authority"]),
    ]
    plan = compile_discovery_plan(signatures, load_capital_sources(ROOT), cycle_budget=25)
    assert plan["schema"] == "dio.atlas.capital_discovery_plan.v1"
    assert sum(item["budget"] for item in plan["source_allocations"]) <= 25
    assert plan["novelty_budget"] > 0
    assert plan["reverification_budget"] > 0
    assert plan["truth_class"] == "STRATEGIC_SEARCH_MODEL_OUTPUT"
    assert plan["authority_created"] is False


def test_unknown_product_is_rejected_instead_of_synthesized():
    try:
        build_search_signature(ROOT, ["definitely_not_a_dio_product"])
    except KeyError as exc:
        assert "definitely_not_a_dio_product" in str(exc)
    else:
        raise AssertionError("unknown product must not produce a synthetic Atlas signature")
