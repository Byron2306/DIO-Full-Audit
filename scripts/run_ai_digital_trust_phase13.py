from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from products.ai_trust_gauntlet import ACCEPTANCE_TOKEN, run_gauntlet

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--output", type=Path, default=Path("state/ai_trust/phase13"))
    r = run_gauntlet(output_dir=p.parse_args().output)
    print(json.dumps({k:r[k] for k in ("incarnation_count","deterministic_execution","prompt_injection_boundary","model_drift_detection","stale_evaluation_detection","external_release")}, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN); return 0
if __name__ == "__main__": raise SystemExit(main())
