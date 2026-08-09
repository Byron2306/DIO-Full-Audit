#!/usr/bin/env python3
"""Render a concrete rootfs build plan for ARDA Valinor images."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_PROFILE = DISTRIBUTION_DIR / "distribution_profile.json"
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "build" / "rootfs-plan.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the ARDA rootfs build plan")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    series = profile["base_distribution"]["series"]
    arch = profile["base_distribution"]["architecture"]
    packages = profile["required_packages"]

    payload = {
        "schema_version": "arda.distribution.rootfs_plan.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": profile["distribution_id"],
        "debootstrap": {
            "series": series,
            "architecture": arch,
            "variant": "minbase",
            "command": [
                "debootstrap",
                f"--arch={arch}",
                "--variant=minbase",
                series,
                "<rootfs-dir>",
                "https://deb.debian.org/debian",
            ],
        },
        "live_build": {
            "distribution": series,
            "architecture": arch,
            "binary_images": [
                "iso-hybrid",
            ],
            "bootappend_live": (
                "boot=live components live-media-path=/live username=arda live-config.username=arda "
                "quiet splash nomodeset loglevel=3 udev.log_level=3 "
                "vt.global_cursor_default=0 plymouth.ignore-serial-consoles "
                "systemd.show_status=auto rd.systemd.show_status=auto "
                "systemd.unit=graphical.target"
            ),
        },
        "package_installation": {
            "required_packages": packages,
            "chroot_command": [
                "chroot",
                "<rootfs-dir>",
                "apt-get",
                "install",
                "-y",
                *packages,
            ],
        },
        "overlay_application": {
            "source": "arda_os/distribution/build/overlay/rootfs",
            "destination": "<rootfs-dir>",
        },
        "kernel_installation": {
            "required": True,
            "artifacts_source": "arda_os/kernel/valinor/releases/latest.json",
            "image_packages": "<install from distribution manifest valinor_release.artifacts>",
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
