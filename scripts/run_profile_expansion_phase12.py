from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from products.profile_expansion import ACCEPTANCE_TOKEN, run_profile_expansion

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("state/profile_expansion/phase12"))
    receipt = run_profile_expansion(output_dir=parser.parse_args().output)
    print(json.dumps({key: receipt[key] for key in ("incarnation_count", "new_incarnation", "profile_source_custody", "deterministic_execution", "external_release")}, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0
if __name__ == "__main__": raise SystemExit(main())
