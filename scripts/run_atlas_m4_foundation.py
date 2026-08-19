#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas import (
    atlas_foundation_receipt,
    atlas_pivot_foundation_receipt,
    candidate_surface_receipt,
    negative_learning_surface_pivot_receipt,
    validate_atlas_constitution,
    validate_meta_profile_crosswalk,
)


def main() -> int:
    constitution = validate_atlas_constitution(REPO_ROOT)
    meta = validate_meta_profile_crosswalk(REPO_ROOT)
    foundation = atlas_foundation_receipt(REPO_ROOT)
    pivot = atlas_pivot_foundation_receipt(REPO_ROOT)
    surface = candidate_surface_receipt(REPO_ROOT)
    vast_pivot = negative_learning_surface_pivot_receipt(REPO_ROOT)
    passed = (
        constitution.get("passed") is True
        and meta.get("passed") is True
        and foundation.get("passed") is True
        and pivot.get("passed") is True
        and surface.get("passed") is True
        and vast_pivot.get("passed") is True
    )
    receipt = {
        "schema": "dio.atlas.m4_foundation_programme_receipt.v2",
        "acceptance": "DIO_ATLAS_M4_FOUNDATION_AND_PIVOT_READY" if passed else "DIO_ATLAS_M4_FOUNDATION_AND_PIVOT_BLOCKED",
        "passed": passed,
        "atlas_constitution": constitution,
        "dio_meta_crosswalk": meta,
        "atlas_foundation": foundation,
        "analogical_pivot_foundation": pivot,
        "derived_portfolio_surface": surface,
        "vast_negative_learning_pivot": vast_pivot,
        "legacy_portfolio_incarnation_count": surface.get("legacy_portfolio_incarnation_count"),
        "legacy_portfolio_is_generated_candidate_universe": False,
        "derived_candidate_incarnation_count": surface.get("derived_candidate_incarnation_count"),
        "novel_candidate_incarnation_count": surface.get("novel_candidate_incarnation_count"),
        "candidate_to_legacy_ratio": surface.get("candidate_to_legacy_ratio"),
        "derived_domain_coverage_ratio": surface.get("domain_coverage_ratio"),
        "selected_negative_learning_pivot_count": vast_pivot.get("selected_candidate_count"),
        "selected_negative_learning_domain_family_count": vast_pivot.get("selected_domain_family_count"),
        "profile_row_count": meta.get("profile_row_count"),
        "capability_cost_first_class": meta.get("capability_cost_first_class") is True,
        "m1_verified": foundation.get("m1_verified") is True,
        "m2_verified": foundation.get("m2_verified") is True,
        "m3_boundary_preserved": foundation.get("m3_boundary_preserved") is True,
        "knowledge_is_capability": False,
        "similarity_is_equivalence": False,
        "analogy_is_evidence": False,
        "domain_adjacency_is_market_demand": False,
        "task_match_is_execution_proof": False,
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "direct_learning_to_execution": False,
        "new_runtime_engine_created": False,
        "m4_final_verified": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
