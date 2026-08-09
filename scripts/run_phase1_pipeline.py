#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, cmd: list[str]) -> None:
    print(f"\n== {name} ==")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT), text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 1 AutoRelease intake pipeline.")
    parser.add_argument("--input", required=True, help="JSON or CSV intake file.")
    parser.add_argument("--run", default=str(ROOT / "runs" / "latest"), help="Run output folder.")
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "latest"), help="Deliverable output folder.")
    parser.add_argument("--skip-evidex", action="store_true", help="Prepare review pack but do not call Evidex engine.")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip static dashboard generation.")
    args = parser.parse_args()

    python = sys.executable
    run_step("Route intake", [python, "scripts/route_intake.py", "--input", args.input, "--out", args.run])
    run_step("Build review packs", [python, "scripts/build_review_packs.py", "--run", args.run, "--out", args.out])
    if not args.skip_evidex:
        run_step("Run Evidex jobs", [python, "scripts/run_evidex_jobs.py", "--run", args.run, "--out", args.out])
        run_step("Build Evidex Phase 2 service layer", [python, "scripts/build_evidex_service_layer.py", "--run", args.run, "--out", args.out])
    run_step("Prepare NicheFoundry requests", [python, "scripts/run_nichefoundry_jobs.py", "--run", args.run, "--out", args.out])
    run_step("Prepare HOMS requests", [python, "scripts/run_homs_jobs.py", "--run", args.run, "--out", args.out])
    if not args.no_dashboard:
        run_step("Build operator dashboard", [python, "scripts/build_operator_dashboard.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
