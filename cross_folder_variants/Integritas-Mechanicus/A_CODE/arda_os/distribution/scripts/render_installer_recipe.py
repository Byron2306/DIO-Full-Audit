#!/usr/bin/env python3
"""Render the ARDA installer recipe from current distribution inputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_PROFILE = DISTRIBUTION_DIR / "distribution_profile.json"
DEFAULT_MANIFEST = DISTRIBUTION_DIR / "releases" / "distribution-manifest.json"
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "releases" / "installer-recipe.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the ARDA installer recipe")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--distribution-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    profile = _read_json(Path(args.profile))
    manifest = _read_json(Path(args.distribution_manifest))
    distribution_id = manifest["distribution_id"]

    payload = {
        "schema_version": "arda.distribution.installer_recipe.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": distribution_id,
        "installer_mode": "debian-preseeded-arda",
        "base_distribution": profile["base_distribution"],
        "partition_recipe": {
            "esp": {
                "filesystem": "fat32",
                "mountpoint": "/boot/efi",
                "size_mb": 512,
            },
            "root": {
                "filesystem": "ext4",
                "mountpoint": "/",
                "min_size_gb": 12,
            },
        },
        "post_install_steps": [
            "install Valinor kernel artifacts",
            "install ARDA overlay",
            "configure attested-host remote verifier environment",
            "enable postboot systemd service",
            "stage active policy bundle and projection plan",
            "rebuild initramfs and grub configuration",
            "capture first-boot attestation",
        ],
        "required_packages": profile["required_packages"],
        "required_units": profile["systemd_units"],
        "first_boot_contract": {
            "secure_boot_expected": True,
            "tpm_expected": True,
            "remote_verifier_required": True,
            "remote_verifier_must_be_off_box": True,
            "os_grade_prefers_signed_verdict": True,
        },
        "identity_assets": [
            "usr/share/arda/identity/arda-wallpaper.png",
            "usr/share/arda/identity/arda-emblem.png",
            "boot/grub/themes/arda-sovereign",
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
