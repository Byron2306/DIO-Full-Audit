#!/usr/bin/env python3
"""Run DIO Metamorphic Spine Phase 8 boundary-closure proof."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from metamorphic.boundary_closure import phase8_boundary_closure_receipt


def main() -> int:
    receipt = phase8_boundary_closure_receipt(REPO_ROOT)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
