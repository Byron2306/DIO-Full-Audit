#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.registry import bootstrap_generic_job, product_profiles  # noqa: E402


def candidate_jobs(runs_root: Path) -> Iterable[Path]:
    registered = set(product_profiles())
    if not runs_root.exists():
        return []
    candidates: list[Path] = []
    for run_dir in sorted(runs_root.glob("mailbox-auto-*")):
        if not run_dir.is_dir():
            continue
        for product_id in registered:
            product_dir = run_dir / product_id
            if not product_dir.is_dir():
                continue
            for path in sorted(product_dir.glob("*.json")):
                if path.name == "run_summary.json":
                    continue
                candidates.append(path)
    return candidates


def reconcile_once(runs_root: Path, state_root: Path) -> dict[str, Any]:
    seen = 0
    created = 0
    unchanged = 0
    failed: list[dict[str, str]] = []

    for source_path in candidate_jobs(runs_root):
        seen += 1
        try:
            source = json.loads(source_path.read_text(encoding="utf-8"))
            job_id = str(source.get("job_id") or "")
            target = state_root / job_id / "JOB.json"
            existed = target.is_file()
            bootstrap_generic_job(source_path, state_root, runs_root)
            if existed:
                unchanged += 1
            else:
                created += 1
        except Exception as exc:  # reconciliation must isolate malformed individual jobs
            failed.append({"path": str(source_path), "error": f"{type(exc).__name__}: {exc}"})

    return {
        "seen": seen,
        "created": created,
        "unchanged": unchanged,
        "failed": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile staged routed jobs for registered DIO product profiles into canonical governed workflows.")
    parser.add_argument("--runs-root", default=str(ROOT / "runs"))
    parser.add_argument("--state-root", default=str(ROOT / "state" / "product_jobs"))
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    runs_root = Path(args.runs_root).expanduser().resolve()
    state_root = Path(args.state_root).expanduser().resolve()

    while True:
        result = reconcile_once(runs_root, state_root)
        print(json.dumps(result, sort_keys=True), flush=True)
        if not args.watch:
            return 1 if result["failed"] else 0
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
