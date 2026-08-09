#!/usr/bin/env python3
"""Render a machine-readable ARDA distribution manifest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
REPO_ROOT = DISTRIBUTION_DIR.parents[1]
DEFAULT_PROFILE = DISTRIBUTION_DIR / "distribution_profile.json"
HARMONY_ADDENDUM = REPO_ROOT / "arda_os" / "backend" / "services" / "arda_harmony_addendum.json"

if str(REPO_ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "arda_os"))

from backend.services.voice_registry import get_voice_registry
from render_remote_verifier_profile import render_profile as render_remote_verifier_profile


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _voice_manifest() -> list[dict]:
    registry = get_voice_registry()
    profiles: list[dict] = []
    for profile in registry.list_voice_profiles():
        if hasattr(profile, "model_dump"):
            profiles.append(profile.model_dump())
        elif hasattr(profile, "dict"):
            profiles.append(profile.dict())
        else:
            profiles.append(dict(profile.__dict__))
    return profiles


def _harmony_discovery() -> dict:
    payload = _read_json(HARMONY_ADDENDUM)
    categories = payload.get("categories") or {}
    return {
        "protocol": payload.get("protocol"),
        "category_count": len(categories),
        "categories": sorted(categories.keys()),
        "discovery_commands": payload.get("discovery_commands") or {},
    }


def render_manifest(profile_path: Path, output_path: Path) -> dict:
    profile = _read_json(profile_path)
    latest_release = _read_json(REPO_ROOT / "arda_os" / "kernel" / "valinor" / "releases" / "latest.json")
    install_plan = _read_json(REPO_ROOT / "arda_os" / "kernel" / "valinor" / "releases" / "install-plan.latest.json")

    payload = {
        "schema_version": "arda.distribution.manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": profile["distribution_id"],
        "distribution_name": profile["distribution_name"],
        "base_distribution": profile["base_distribution"],
        "required_packages": profile["required_packages"],
        "systemd_units": profile["systemd_units"],
        "valinor_release": latest_release,
        "valinor_install_plan": install_plan,
        "overlay_root": profile["artifacts"]["overlay_root"],
        "installer_profile": str(DISTRIBUTION_DIR / "releases" / "installer-profile.json"),
        "remote_verifier_profile": str(
            DISTRIBUTION_DIR / "releases" / "remote-verifier-profile.json"
        ),
        "harmony_discovery": _harmony_discovery(),
        "voice_profiles": _voice_manifest(),
        "trust_topology": {
            "verifier_mode": "off-box-required",
            "attested_host_must_not_hold_verifier_private_key": True,
            "attested_host_verifies_signed_verdicts_with_public_key_only": True,
        },
        "runtime_constitution_layers": [
            "measured_identity",
            "attestation_service",
            "boot_measurement",
            "harmonic_engine",
            "voice_registry",
            "polyphonic_governance",
            "earendil_flow",
            "gates_of_night",
            "arda_fabric_middleware",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output": str(output_path),
        "distribution_id": profile["distribution_id"],
    }


def render_installer_profile(profile_path: Path, output_path: Path) -> dict:
    profile = _read_json(profile_path)
    payload = {
        "schema_version": "arda.distribution.installer_profile.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": profile["distribution_id"],
        "installation_modes": [
            "live_iso",
            "installer_iso",
            "raw_disk_image",
        ],
        "partitioning": {
            "efi": {"filesystem": "vfat", "size_mb": 512},
            "root": {"filesystem": "ext4", "mount": "/", "verity_ready": True},
            "state": {"filesystem": "ext4", "mount": "/var/lib/arda", "persistent": True},
        },
        "post_install_actions": [
            "install_valinor_kernel",
            "install_arda_overlay",
            "enable_phase4_remote_verifier",
            "enable_valinor_postboot",
            "install_policy_bundle",
            "configure_identity_assets",
        ],
        "secure_boot": {
            "required": True,
            "shim_signed_required": True,
            "kernel_signing_required": True,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output": str(output_path),
        "distribution_id": profile["distribution_id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render ARDA distribution manifest artifacts")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument(
        "--manifest-output",
        default=str(DISTRIBUTION_DIR / "releases" / "distribution-manifest.json"),
    )
    parser.add_argument(
        "--installer-profile-output",
        default=str(DISTRIBUTION_DIR / "releases" / "installer-profile.json"),
    )
    parser.add_argument(
        "--remote-verifier-profile-output",
        default=str(DISTRIBUTION_DIR / "releases" / "remote-verifier-profile.json"),
    )
    args = parser.parse_args()

    manifest = render_manifest(Path(args.profile), Path(args.manifest_output))
    installer = render_installer_profile(Path(args.profile), Path(args.installer_profile_output))
    remote_verifier = render_remote_verifier_profile(
        Path(args.profile),
        Path(args.remote_verifier_profile_output),
    )
    print(
        json.dumps(
            {"ok": True, "manifest": manifest, "installer_profile": installer, "remote_verifier_profile": remote_verifier},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
