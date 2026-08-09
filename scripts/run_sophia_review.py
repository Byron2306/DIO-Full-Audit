#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.sophia.review_pipeline import run_review  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a controlled Sophia academic review product job.")
    parser.add_argument("request", type=Path, help="Sophia review request JSON.")
    parser.add_argument("--out", type=Path, default=ROOT / "deliverables" / "sophia_academic_reviews")
    parser.add_argument("--base-url", default="http://127.0.0.1:7070")
    parser.add_argument("--sophia-root", type=Path, default=Path("/home/byron/Integritas-Mechanicus"))
    args = parser.parse_args()
    request_path = args.request.expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    job_dir = run_review(
        request,
        request_path,
        args.out.expanduser().resolve(),
        args.base_url,
        args.sophia_root.expanduser().resolve(),
    )
    print(json.dumps({"status": "needs_human_review", "job_dir": str(job_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
