from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.studio_harvest import ACCEPTANCE_TOKEN
from products.studio_harvest_gauntlet import run_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("state/studio_harvest/controlled"))
    result = run_gauntlet(output_dir=parser.parse_args().output)
    print(json.dumps(result, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
