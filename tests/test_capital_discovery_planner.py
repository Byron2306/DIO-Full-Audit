from pathlib import Path

from market_capital.atlas_search import build_search_signature
from market_capital.discovery_planner import build_discovery_plan
from market_capital.sources import load_capital_sources


def test_plan_reserves_exploration_and_never_exceeds_cycle_budget():
    signatures = [build_search_signature(Path("."), ["homs_assess"])]
    sources = load_capital_sources(Path("."))
    plan = build_discovery_plan(signatures, sources, cycle_budget=100)
    assert sum(x["budget"] for x in plan["source_allocations"]) <= 100
    assert plan["novelty_budget"] >= 10
    assert plan["reverification_budget"] > 0
    assert plan["authority_created"] is False


def test_plan_never_allocates_beyond_source_rate_cap():
    signatures = [build_search_signature(Path("."), ["homs_assess"])]
    sources = load_capital_sources(Path("."))
    plan = build_discovery_plan(signatures, sources, cycle_budget=500)
    for row in plan["source_allocations"]:
        cap = sources[row["source_id"]].rate_budget
        if cap > 0:
            assert row["budget"] <= cap
