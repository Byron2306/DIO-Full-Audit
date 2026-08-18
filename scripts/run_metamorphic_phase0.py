#!/usr/bin/env python3
"""Run the DIO Metamorphic Spine Phase 0 constitution/inventory gate."""
from __future__ import annotations

import json
from pathlib import Path

from metamorphic.integration_inventory import validate_integration_inventory


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    receipt = validate_integration_inventory(repo_root)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
