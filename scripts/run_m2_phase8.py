#!/usr/bin/env python3
"""Run DIO M2 Phase 8 projection adaptation and negative-learning proof."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from commercial_metabolism.learning import phase8_projection_adaptation_receipt


def main() -> int:
    receipt = phase8_projection_adaptation_receipt(REPO_ROOT)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
