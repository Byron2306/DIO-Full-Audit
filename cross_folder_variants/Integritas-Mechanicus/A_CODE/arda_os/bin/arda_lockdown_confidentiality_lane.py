#!/usr/bin/env python3
"""Build a verifier-aware confidentiality-lockdown promotion lane."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.phase4_rollout_control import RolloutControlError, TrustedVerifierVerdict  # noqa: E402


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a confidentiality-lockdown promotion lane")
    parser.add_argument("--signed-verdict", required=True)
    parser.add_argument("--verifier-public-key", default=os.environ.get("ARDA_VERIFIER_PUBLIC_KEY"))
    parser.add_argument("--verifier-key-id", default=os.environ.get("ARDA_VERIFIER_KEY_ID", "arda-phase4-verifier"))
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.verifier_public_key:
        print("ARDA_CONFIDENTIALITY_LANE: verifier public key is required", file=sys.stderr)
        return 1

    try:
        verdict_payload = _load_json(args.signed_verdict)
        verdict = TrustedVerifierVerdict(args.verifier_public_key, key_id=args.verifier_key_id).verify(verdict_payload)
    except (OSError, ValueError, RolloutControlError) as error:
        print(f"ARDA_CONFIDENTIALITY_LANE: {error}", file=sys.stderr)
        return 1

    authorized_states = sorted({str(item).strip().lower() for item in (verdict.get("authorized_states") or []) if str(item).strip()})
    lockdown = _safe_text("/sys/kernel/security/lockdown")
    active_mode = "integrity" if "[integrity]" in lockdown else ("confidentiality" if "[confidentiality]" in lockdown else None)

    payload = {
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verdict_id": verdict.get("verdict_id"),
        "authorized_states": authorized_states,
        "active_lockdown_mode": active_mode,
        "current_lockdown_raw": lockdown,
        "promotion_lane": {
            "name": "confidentiality_promotion_test",
            "requires_fresh_verifier_authorization": True,
            "requires_lockdown_state_authorization": "lockdown" in authorized_states,
            "prechecks": [
                "arda confidentiality-probe --json",
                "arda bootstrap --json",
                "arda os-grade --json --signed-verdict <fresh verdict>",
            ],
            "promotion_steps": [
                "capture a fresh verifier-signed verdict immediately before the test window",
                "ensure graphics, sudo, systemd-logind, and measured-policy tooling have a rollback path",
                "promote boot policy/kernel configuration to confidentiality lockdown in a dedicated reboot lane",
                "reboot and re-run bootstrap, os-grade, and attestation verification",
            ],
            "success_criteria": [
                "lockdown interface reports confidentiality active after reboot",
                "remote verifier signed quote remains green",
                "measured generation and fsverity_strict remain active",
                "interactive login, sudo, and systemd-logind continue functioning",
            ],
            "rollback_steps": [
                "obtain a fresh verifier-authorized rescue/lockdown transition if the platform is no longer production-ready",
                "boot fallback integrity profile or fallback kernel entry",
                "re-run os-grade and bootstrap after rollback",
            ],
        },
    }

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
