#!/usr/bin/env python3
"""Run DIO M2 Phase 4 market episode compiler proof."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from commercial_metabolism.episode import phase4_market_episode_receipt


def main() -> int:
    receipt = phase4_market_episode_receipt(REPO_ROOT)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
