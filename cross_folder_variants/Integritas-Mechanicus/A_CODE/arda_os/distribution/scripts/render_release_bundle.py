#!/usr/bin/env python3
"""Render the ARDA distribution release bundle metadata."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_PROFILE = DISTRIBUTION_DIR / "distribution_profile.json"
DEFAULT_MANIFEST = DISTRIBUTION_DIR / "releases" / "distribution-manifest.json"
DEFAULT_IMAGE_PLAN = DISTRIBUTION_DIR / "releases" / "image-artifact-plan.json"
DEFAULT_INSTALLER_RECIPE = DISTRIBUTION_DIR / "releases" / "installer-recipe.json"
DEFAULT_REMOTE_VERIFIER_PROFILE = DISTRIBUTION_DIR / "releases" / "remote-verifier-profile.json"
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "releases" / "release-bundle.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the ARDA release bundle manifest")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--distribution-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--image-plan", default=str(DEFAULT_IMAGE_PLAN))
    parser.add_argument("--installer-recipe", default=str(DEFAULT_INSTALLER_RECIPE))
    parser.add_argument("--remote-verifier-profile", default=str(DEFAULT_REMOTE_VERIFIER_PROFILE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    profile = _read_json(Path(args.profile))
    distribution_manifest = _read_json(Path(args.distribution_manifest))
    image_plan = _read_json(Path(args.image_plan))
    installer_recipe = _read_json(Path(args.installer_recipe))
    remote_verifier_profile = _read_json(Path(args.remote_verifier_profile))

    payload = {
        "schema_version": "arda.distribution.release_bundle.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": distribution_manifest["distribution_id"],
        "distribution_name": profile["distribution_name"],
        "release_channels": [
            "raw-image",
            "live-iso",
            "installer-iso",
        ],
        "plans": {
            "distribution_manifest": str(Path(args.distribution_manifest)),
            "image_artifact_plan": str(Path(args.image_plan)),
            "installer_recipe": str(Path(args.installer_recipe)),
            "remote_verifier_profile": str(Path(args.remote_verifier_profile)),
        },
        "artifacts": image_plan["artifact_formats"],
        "boot_contract": installer_recipe["first_boot_contract"],
        "trust_topology": remote_verifier_profile,
        "shipping_guarantees": [
            "valinor kernel required",
            "secure boot aware boot path",
            "off-box verifier topology defined",
            "measured identity and policy assets staged",
            "verifier-led rollout lanes available",
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
