#!/usr/bin/env python3
"""Render the concrete ARDA disk-image and ISO artifact plan."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_PROFILE = DISTRIBUTION_DIR / "distribution_profile.json"
DEFAULT_ROOTFS_PLAN = DISTRIBUTION_DIR / "build" / "rootfs-plan.json"
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "releases" / "image-artifact-plan.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the ARDA image artifact plan")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--rootfs-plan", default=str(DEFAULT_ROOTFS_PLAN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    profile = _read_json(Path(args.profile))
    rootfs_plan = _read_json(Path(args.rootfs_plan))
    distribution_id = profile["distribution_id"]
    series = profile["base_distribution"]["series"]
    arch = profile["base_distribution"]["architecture"]
    workspace_root = "arda_os/distribution/build/workspace"
    release_root = "arda_os/distribution/releases/artifacts"

    payload = {
        "schema_version": "arda.distribution.image_artifact_plan.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": distribution_id,
        "base_distribution": profile["base_distribution"],
        "rootfs_plan": str(Path(args.rootfs_plan)),
        "workspace_root": workspace_root,
        "release_root": release_root,
        "artifact_formats": [
            {
                "id": "raw_disk",
                "filename": f"{distribution_id}-{series}-{arch}.img",
                "filesystem": "ext4",
                "partition_table": "gpt",
                "boot_mode": "uefi",
            },
            {
                "id": "live_iso",
                "filename": f"{distribution_id}-live-{series}-{arch}.iso",
                "builder": "xorriso",
                "image_type": "iso-hybrid",
                "boot_mode": "uefi",
            },
            {
                "id": "installer_iso",
                "filename": f"{distribution_id}-installer-{series}-{arch}.iso",
                "builder": "debian-installer + xorriso",
                "image_type": "iso-hybrid",
                "boot_mode": "uefi",
            },
        ],
        "image_layout": {
            "esp_size_mb": 128,
            "rootfs_min_size_gb": 12,
            "verity_partition_reserved": False,
            "workspace_artifacts_mount": "/workspace-artifacts",
        },
        "build_stages": [
            {
                "name": "rootfs_assembly",
                "inputs": [
                    str(Path(args.rootfs_plan)),
                    "arda_os/distribution/build/overlay/rootfs",
                    "arda_os/distribution/build/workspace/artifacts",
                ],
                "outputs": [
                    f"{workspace_root}/rootfs",
                ],
            },
            {
                "name": "boot_asset_staging",
                "inputs": [
                    f"{workspace_root}/rootfs",
                    f"{workspace_root}/overlay-rootfs",
                ],
                "outputs": [
                    f"{workspace_root}/esp",
                    f"{workspace_root}/boot-staging",
                ],
            },
            {
                "name": "artifact_emission",
                "inputs": [
                    f"{workspace_root}/rootfs",
                    f"{workspace_root}/esp",
                ],
                "outputs": [
                    f"{release_root}/{distribution_id}-{series}-{arch}.img",
                    f"{release_root}/{distribution_id}-live-{series}-{arch}.iso",
                    f"{release_root}/{distribution_id}-installer-{series}-{arch}.iso",
                ],
            },
        ],
        "host_tools": [
            "debootstrap",
            "xorriso",
            "mtools",
            "grub-mkstandalone",
            "mkfs.vfat",
            "sgdisk",
            "qemu-img",
        ],
        "live_build_reference": rootfs_plan.get("live_build") or {},
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
