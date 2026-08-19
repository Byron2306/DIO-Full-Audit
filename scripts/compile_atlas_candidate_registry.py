#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas import candidate_surface_receipt, materialize_candidate_registry_csv


DEFAULT_OUTPUT = Path("state/atlas/dio_atlas_candidate_incarnations.csv")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile the derived DIO ATLAS candidate-incarnation registry to CSV."
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUTPUT),
        help=f"Output CSV path, relative to repo root by default ({DEFAULT_OUTPUT}).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    surface = candidate_surface_receipt(REPO_ROOT)
    materialized = materialize_candidate_registry_csv(REPO_ROOT, args.out)
    passed = (
        surface.get("passed") is True
        and materialized.get("output_exists") is True
        and materialized.get("candidate_count") == surface.get("derived_candidate_incarnation_count")
    )
    receipt = {
        "schema": "dio.atlas.candidate_registry_compiler_receipt.v1",
        "acceptance": "DIO_ATLAS_CANDIDATE_REGISTRY_CSV_READY" if passed else "DIO_ATLAS_CANDIDATE_REGISTRY_CSV_BLOCKED",
        "passed": passed,
        "legacy_portfolio_incarnation_count": surface.get("legacy_portfolio_incarnation_count"),
        "derived_candidate_incarnation_count": surface.get("derived_candidate_incarnation_count"),
        "novel_candidate_incarnation_count": surface.get("novel_candidate_incarnation_count"),
        "candidate_to_legacy_ratio": surface.get("candidate_to_legacy_ratio"),
        "domain_coverage_ratio": surface.get("domain_coverage_ratio"),
        "candidate_state_counts": surface.get("candidate_state_counts"),
        "capability_cost_counts": surface.get("capability_cost_counts"),
        "candidate_registry_digest": surface.get("candidate_registry_digest"),
        "output_path": materialized.get("output_path"),
        "output_exists": materialized.get("output_exists") is True,
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "m4_final_verified": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
