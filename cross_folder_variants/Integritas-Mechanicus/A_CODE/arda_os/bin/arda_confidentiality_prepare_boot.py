#!/usr/bin/env python3
"""Prepare a confidentiality-lockdown boot lane artifact without editing boot config."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


GRUB_DEFAULTS = Path("/etc/default/grub")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_var(contents: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=(.*)$", contents, re.MULTILINE)
    if not match:
        return ""
    raw = match.group(1).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw[1:-1]
    return raw


def _normalize_cmdline(cmdline: str) -> str:
    parts = [part for part in cmdline.split() if part]
    filtered = [part for part in parts if not part.startswith("lockdown=")]
    filtered.append("lockdown=confidentiality")
    return " ".join(filtered)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a confidentiality-lockdown boot lane artifact")
    parser.add_argument("--grub-defaults", default=str(GRUB_DEFAULTS))
    parser.add_argument("--output", default="/var/lib/arda/confidentiality/boot-lane.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    grub_defaults = Path(args.grub_defaults)
    if not grub_defaults.is_file():
        print(f"ARDA_CONFIDENTIALITY_PREPARE_BOOT: grub defaults missing: {grub_defaults}", file=sys.stderr)
        return 1

    contents = _read_text(grub_defaults)
    current_default = _extract_var(contents, "GRUB_CMDLINE_LINUX_DEFAULT")
    current_linux = _extract_var(contents, "GRUB_CMDLINE_LINUX")
    confidentiality_linux = _normalize_cmdline(current_linux)

    payload = {
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "grub_defaults": str(grub_defaults),
        "current": {
            "GRUB_CMDLINE_LINUX_DEFAULT": current_default,
            "GRUB_CMDLINE_LINUX": current_linux,
        },
        "confidentiality_lane": {
            "GRUB_CMDLINE_LINUX_DEFAULT": current_default,
            "GRUB_CMDLINE_LINUX": confidentiality_linux,
        },
        "rollback_lane": {
            "GRUB_CMDLINE_LINUX_DEFAULT": current_default,
            "GRUB_CMDLINE_LINUX": current_linux,
        },
        "next_actions": [
            f"backup {grub_defaults} before edits",
            f"set GRUB_CMDLINE_LINUX=\"{confidentiality_linux}\" for the confidentiality lane",
            "run update-grub",
            "reboot into the confidentiality lane and run bootstrap, os-grade, and remote verifier attestation",
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
