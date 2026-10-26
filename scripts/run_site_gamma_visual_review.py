from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.site_gamma_visual_review import run_site_gamma_visual_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or generate the optional Gamma visual-review layer for an already-passed full-grade Site Studio run."
    )
    parser.add_argument(
        "--site-root",
        type=Path,
        default=Path("/tmp/dio-site-full-grade/site_studio"),
        help="Path to the Site Studio full-grade output root.",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Explicitly call Gamma and build GAMMA_REVIEW_SITE. Without this flag only the bound request is written.",
    )
    args = parser.parse_args()

    result = run_site_gamma_visual_review(
        site_root=args.site_root,
        generate=args.generate,
        root=ROOT,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("state") in {"REQUEST_READY_NOT_GENERATED", "READY_NEEDS_YOU"}:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
