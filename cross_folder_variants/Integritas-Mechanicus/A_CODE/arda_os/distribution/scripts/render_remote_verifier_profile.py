#!/usr/bin/env python3
"""Render off-box remote verifier deployment profiles for ARDA distribution releases."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
REPO_ROOT = DISTRIBUTION_DIR.parents[1]
DEFAULT_PROFILE = DISTRIBUTION_DIR / "distribution_profile.json"
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "releases" / "remote-verifier-profile.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render_profile(profile_path: Path, output_path: Path) -> dict:
    profile = _read_json(profile_path)
    payload = {
        "schema_version": "arda.distribution.remote_verifier_profile.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": profile["distribution_id"],
        "verifier_host_profile": {
            "service_name": "arda-phase4-remote-verifier.service",
            "listen_host_env": "ARDA_VERIFIER_HOST",
            "listen_port_env": "ARDA_VERIFIER_PORT",
            "default_listen_host": "0.0.0.0",
            "default_listen_port": 8094,
            "required_packages": [
                "python3",
                "python3-cryptography",
                "python3-fastapi",
                "python3-uvicorn",
            ],
            "required_files": [
                "/etc/arda/arda-verifier.env",
                "/etc/arda/verifier/verifier-key.pem",
                "/etc/arda/verifier/verifier-key.pub.pem",
            ],
            "systemd_unit_source": str(REPO_ROOT / "arda_os" / "deploy" / "systemd" / "arda-phase4-remote-verifier.service"),
            "environment_template_source": str(REPO_ROOT / "arda_os" / "deploy" / "etc" / "arda-verifier.env.example"),
            "network_contract": {
                "health_endpoint": "/api/health",
                "verify_endpoint": "/verify/phase4",
                "tls_recommended": True,
                "private_key_must_remain_off_attested_host": True,
            },
        },
        "attested_host_profile": {
            "required_files": [
                "/etc/arda/attested-host.env",
                "/etc/arda/verifier/verifier-key.pub.pem",
                "/var/lib/arda/attestation/baselines/approved-pcr-baseline.json",
            ],
            "environment_template_source": str(REPO_ROOT / "arda_os" / "deploy" / "etc" / "arda-attested-host.env.example"),
            "required_env": {
                "ARDA_VERIFIER_URL": "http://verifier.example.internal:8094/verify/phase4",
                "ARDA_VERIFIER_ID": "arda-phase4-remote-verifier",
                "ARDA_VERIFIER_KEY_ID": "arda-phase4-verifier",
                "ARDA_VERIFIER_PUBLIC_KEY": "/etc/arda/verifier/verifier-key.pub.pem",
                "ARDA_PCR_BASELINE_PATH": "/var/lib/arda/attestation/baselines/approved-pcr-baseline.json",
                "ARDA_POSTBOOT_REQUIRE_VERIFIER": "1",
                "ARDA_POSTBOOT_ALLOW_LOCAL_FALLBACK": "0",
            },
            "boot_contract": [
                "post-boot gate submits fresh evidence to the remote verifier",
                "os-grade requires a fresh signed positive verdict",
                "local fallback remains disabled in the off-box trust model",
            ],
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
    parser = argparse.ArgumentParser(description="Render ARDA remote verifier deployment profiles")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    payload = render_profile(Path(args.profile), Path(args.output))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
