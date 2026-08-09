#!/usr/bin/env python3
"""Validate a Linux kernel config against the Valinor feature contract."""

import argparse
import json
import sys
from pathlib import Path


def _read_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") and " is not set" not in stripped:
            continue
        if stripped.startswith("# ") and stripped.endswith(" is not set"):
            key = stripped[2 : -len(" is not set")]
            values[key] = "n"
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            values[key] = value
    return values


def _read_required(path: Path) -> dict[str, str]:
    required: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# ") and stripped.endswith(" is not set"):
            key = stripped[2 : -len(" is not set")]
            required[key] = "n"
            continue
        if stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        required[key] = value
    return required


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Valinor kernel config requirements")
    parser.add_argument("--config", required=True)
    parser.add_argument("--fragment", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    fragment_path = Path(args.fragment)
    config = _read_config(config_path)
    required = _read_required(fragment_path)

    checks = {}
    blockers = []
    for key, expected in required.items():
        actual = config.get(key)
        ok = actual == expected
        checks[key] = {"expected": expected, "actual": actual, "ok": ok}
        if not ok:
            blockers.append(key)

    report = {
        "ok": not blockers,
        "config": str(config_path),
        "fragment": str(fragment_path),
        "checked": len(checks),
        "blockers": blockers,
        "checks": checks,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("VALINOR CONFIG CHECK")
        print(f"ok: {report['ok']}")
        print("blockers:")
        for blocker in blockers or ["none"]:
            print(f"- {blocker}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
