from __future__ import annotations

import json
from pathlib import Path

from commercial_metabolism.episode import phase4_market_episode_receipt


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    receipt = phase4_market_episode_receipt(repo_root)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    raise SystemExit(0 if receipt.get("passed") is True else 1)
