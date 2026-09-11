from __future__ import annotations

from typing import Any

from .atlas_search import compile_discovery_plan
from .sources import CapitalSource


def build_discovery_plan(
    signatures: list[dict[str, Any]],
    sources: dict[str, CapitalSource],
    cycle_budget: int,
    source_health: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one bounded Atlas plan, then annotate health without inventing capacity."""
    plan = compile_discovery_plan(signatures, sources, cycle_budget)
    health = source_health or {}
    allocations = []
    for row in plan.get("source_allocations") or []:
        item = dict(row)
        state = str((health.get(item["source_id"]) or {}).get("state") or "UNKNOWN")
        item["source_health_state"] = state
        item["adaptive_factors"] = {
            "atlas_preference": True,
            "source_health": state,
            "freshness_gap": "UNMEASURED",
            "deadline_urgency": "UNMEASURED",
            "coverage_gap": "UNMEASURED",
        }
        allocations.append(item)
    return {
        **plan,
        "schema": "dio.atlas.capital_discovery_plan.v2",
        "source_allocations": allocations,
        "planning_mode": "BOUNDED_ADAPTIVE",
        "synthetic_fallback_allowed": False,
        "authority_created": False,
        "external_effects": False,
    }
