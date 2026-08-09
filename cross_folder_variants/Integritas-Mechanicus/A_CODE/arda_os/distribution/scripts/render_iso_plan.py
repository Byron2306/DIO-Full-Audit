#!/usr/bin/env python3
"""Render the phased ISO/distribution build plan for ARDA Valinor."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "releases" / "iso-build-plan.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the ARDA ISO build plan")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    payload = {
        "schema_version": "arda.distribution.iso_plan.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": "arda-valinor",
        "phases": [
            {
                "phase": 1,
                "name": "overlay and manifest generation",
                "outputs": [
                    "arda_os/distribution/build/overlay",
                    "arda_os/distribution/releases/distribution-manifest.json",
                    "arda_os/distribution/releases/installer-profile.json",
                ],
            },
            {
                "phase": 2,
                "name": "base rootfs construction",
                "methods": [
                    "debootstrap trixie amd64 rootfs",
                    "debian live-build customization",
                ],
                "output": "arda_os/distribution/build/rootfs-plan.json",
            },
            {
                "phase": 3,
                "name": "arda integration",
                "steps": [
                    "install Valinor kernel .deb artifacts",
                    "copy ARDA overlay into rootfs",
                    "enable verifier and postboot systemd units",
                    "install policy bundle and projection plan",
                    "install wallpaper, boot theme, and identity assets",
                ],
            },
            {
                "phase": 4,
                "name": "bootability and trust chain",
                "steps": [
                    "sign kernel and boot artifacts",
                    "verify shim/grub path",
                    "generate initramfs and grub config",
                    "prepare installer and live boot entries",
                ],
            },
            {
                "phase": 5,
                "name": "artifact emission",
                "artifacts": [
                    "arda-valinor-live-amd64.iso",
                    "arda-valinor-installer-amd64.iso",
                    "arda-valinor-amd64.img",
                ],
            },
        ],
        "minimum_host_requirements": {
            "architecture": "amd64",
            "secure_boot": True,
            "tpm2": True,
            "uefi": True,
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
