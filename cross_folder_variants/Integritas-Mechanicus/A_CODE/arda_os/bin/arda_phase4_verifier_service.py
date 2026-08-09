#!/usr/bin/env python3
"""Run the ARDA Phase 4 remote verifier API service."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.arda_phase4_verifier_service import app  # noqa: E402


def main() -> int:
    import uvicorn

    host = os.environ.get("ARDA_VERIFIER_HOST", "0.0.0.0")
    port = int(os.environ.get("ARDA_VERIFIER_PORT", "8094"))
    uvicorn.run(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

