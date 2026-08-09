#!/usr/bin/env python3
"""
Export a compact Phase 6 evidence bundle from operational logs and attestation artifacts.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STATUS_SNAPSHOT = "/var/log/arda/status_snapshot.json"
DEFAULT_EGRESS_LEDGER = "/var/log/arda/accountability_ledger.jsonl"
DEFAULT_ATTESTATION_DIR = "/var/lib/arda/attestation/latest"
DEFAULT_EXPORT_ROOT = "/var/log/arda/exports"


def _copy_if_exists(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Arda operational evidence")
    parser.add_argument("--status-snapshot", default=DEFAULT_STATUS_SNAPSHOT)
    parser.add_argument("--egress-ledger", default=DEFAULT_EGRESS_LEDGER)
    parser.add_argument("--attestation-dir", default=DEFAULT_ATTESTATION_DIR)
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir or os.path.join(DEFAULT_EXPORT_ROOT, timestamp))
    output_dir.mkdir(parents=True, exist_ok=True)

    copied = {
        "status_snapshot": _copy_if_exists(Path(args.status_snapshot), output_dir / "status_snapshot.json"),
        "egress_ledger": _copy_if_exists(Path(args.egress_ledger), output_dir / "accountability_ledger.jsonl"),
        "attestation_dir": _copy_if_exists(Path(args.attestation_dir), output_dir / "attestation"),
    }

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "cwd": os.getcwd(),
        "output_dir": str(output_dir),
        "copied": copied,
    }
    with open(output_dir / "export_manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

