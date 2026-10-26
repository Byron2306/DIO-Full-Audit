#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.baselines import compile_baselines, write_baselines  # noqa: E402


def main() -> int:
    source = ROOT / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
    organisations = ROOT / "config" / "market_sensorium" / "seeds"
    output = ROOT / "state" / "market_sensorium" / "domain_baseline_candidates.csv"
    rows, receipt = compile_baselines(source, organisations, per_domain=5)
    write_baselines(output, rows)
    payload = {
        "acceptance": "DIO_MARKET_SENSORIUM_BASELINE_CANDIDATES_READY",
        **receipt,
        "output_path": str(output.relative_to(ROOT)),
        "output_exists": output.is_file(),
        "authority_created": False,
        "market_demand_claimed": False,
        "best_target_claimed": False,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
