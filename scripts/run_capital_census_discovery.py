#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_capital.adapters.cordis import CordisAdapter
from market_capital.adapters.crossref_funders import CrossrefFundersAdapter
from market_capital.adapters.giving360 import Giving360Adapter
from market_capital.adapters.grants_gov import GrantsGovAdapter
from market_capital.adapters.propublica_nonprofits import ProPublicaNonprofitsAdapter
from market_capital.adapters.usaspending import USASpendingAdapter
from market_capital.atlas_search import build_search_signature
from market_capital.census import CapitalCensus
from market_capital.discovery_planner import build_discovery_plan
from market_capital.discovery_runner import run_discovery_cycle
from market_capital.sources import load_capital_sources


def _machine_adapters():
    return {
        "SRC-GRANTS-GOV": GrantsGovAdapter(),
        "SRC-CORDIS": CordisAdapter(),
        "SRC-360GIVING": Giving360Adapter(),
        "SRC-CROSSREF-FUNDERS": CrossrefFundersAdapter(),
        "SRC-USASPENDING": USASpendingAdapter(),
        "SRC-PROPUBLICA-NONPROFITS": ProPublicaNonprofitsAdapter(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded Atlas-steered Capital & Support census discovery cycle")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--product", action="append", dest="products", default=[], help="Canonical product slug; repeat for multiple wedges")
    parser.add_argument("--cycle-budget", type=int, default=100)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    products = args.products or ["homs_assess", "agent_authority", "evidex_evidenceops", "accessible_publish"]
    signatures = [build_search_signature(root, [product]) for product in products]
    sources = load_capital_sources(root)
    plan = build_discovery_plan(signatures, sources, args.cycle_budget)

    if args.plan_only:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    census_path = root / "state" / "market_capital" / "census" / "capital_support.sqlite"
    census = CapitalCensus(census_path)
    census.initialize()
    receipt = run_discovery_cycle(root=root, census=census, plan=plan, adapters=_machine_adapters())
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
