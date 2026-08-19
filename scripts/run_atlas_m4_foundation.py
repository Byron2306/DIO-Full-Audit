#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas import atlas_foundation_receipt, atlas_pivot_foundation_receipt


def main() -> int:
    foundation = atlas_foundation_receipt(REPO_ROOT)
    pivot = atlas_pivot_foundation_receipt(REPO_ROOT)
    passed = foundation.get("passed") is True and pivot.get("passed") is True
    receipt = {
        "schema": "dio.atlas.m4_foundation_programme_receipt.v1",
        "acceptance": "DIO_ATLAS_M4_FOUNDATION_AND_PIVOT_READY" if passed else "DIO_ATLAS_M4_FOUNDATION_AND_PIVOT_BLOCKED",
        "passed": passed,
        "atlas_foundation": foundation,
        "analogical_pivot_foundation": pivot,
        "m1_verified": foundation.get("m1_verified") is True,
        "m2_verified": foundation.get("m2_verified") is True,
        "m3_boundary_preserved": foundation.get("m3_boundary_preserved") is True,
        "knowledge_is_capability": False,
        "similarity_is_equivalence": False,
        "analogy_is_evidence": False,
        "domain_adjacency_is_market_demand": False,
        "task_match_is_execution_proof": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "direct_learning_to_execution": False,
        "new_runtime_engine_created": False,
        "m4_final_verified": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
