#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.mail_readiness import audit_mail_observation_readiness  # noqa: E402


def main() -> int:
    result = audit_mail_observation_readiness(ROOT, python_executable=sys.executable)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
