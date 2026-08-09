#!/usr/bin/env python3
"""Collapse stale active measured generations behind the live line."""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.measured_identity import MeasuredProjectionGenerationStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact stale active measured generations")
    parser.add_argument("--database", default=os.environ.get("ARDA_MEASURED_GENERATION_DB", "/var/lib/arda/projection/arda_measured_generation.sqlite3"))
    parser.add_argument("--node-id")
    parser.add_argument("--cgroup-id")
    parser.add_argument("--keep-manifest-id")
    args = parser.parse_args()

    store = MeasuredProjectionGenerationStore(args.database)
    try:
        result = store.compact_active_records(
            node_id=args.node_id,
            cgroup_id=args.cgroup_id,
            keep_manifest_id=args.keep_manifest_id,
        )
    finally:
        store.close()

    print(json.dumps({"ok": True, "database": os.path.abspath(args.database), **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
