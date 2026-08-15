from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.meta_runtime_gauntlet import ACCEPTANCE_TOKEN, run_meta_runtime_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DIO Phase 8 consolidated META runtime gauntlet.")
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "meta_runtime_phase8")
    args = parser.parse_args()
    receipt = run_meta_runtime_gauntlet(output_dir=args.output)
    print(json.dumps({"incarnation_count": receipt["incarnation_count"], "meta_primitive_count": receipt["meta_primitive_count"], "deterministic_invocation": receipt["deterministic_invocation"], "input_immutability": receipt["input_immutability"], "external_release_gate": receipt["external_release_gate"]}, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
