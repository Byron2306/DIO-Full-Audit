#!/usr/bin/env python3
"""Build a verifier-gated confidentiality promotion artifact and rollback plan."""

import argparse
import json
import os
import subprocess
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


def _run_json_command(command: list[str]) -> tuple[int, dict | None, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = None
    text = (result.stdout or "") + (result.stderr or "")
    try:
        payload = json.loads(result.stdout)
    except Exception:
        payload = None
    return result.returncode, payload, text.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a verifier-gated confidentiality promotion transition")
    parser.add_argument("--signed-verdict", required=True)
    parser.add_argument("--verifier-public-key", default=os.environ.get("ARDA_VERIFIER_PUBLIC_KEY"))
    parser.add_argument("--verifier-key-id", default=os.environ.get("ARDA_VERIFIER_KEY_ID", "arda-phase4-verifier"))
    parser.add_argument("--promotion-record", default="/var/lib/arda/confidentiality/promotion-record.json")
    parser.add_argument("--rollback-record", default="/var/lib/arda/confidentiality/rollback-record.json")
    parser.add_argument("--os-grade-signed-verdict", default="/var/lib/arda/verifier/latest-verdict.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.verifier_public_key:
        print("ARDA_CONFIDENTIALITY_PROMOTE: verifier public key is required", file=sys.stderr)
        return 1

    try:
        verdict_payload = _load_json(args.signed_verdict)
        verdict = TrustedVerifierVerdict(args.verifier_public_key, key_id=args.verifier_key_id).verify(verdict_payload)
    except (OSError, ValueError, RolloutControlError) as error:
        print(f"ARDA_CONFIDENTIALITY_PROMOTE: {error}", file=sys.stderr)
        return 1

    authorized_states = sorted({str(item).strip().lower() for item in (verdict.get("authorized_states") or []) if str(item).strip()})
    if "lockdown" not in authorized_states:
        print("ARDA_CONFIDENTIALITY_PROMOTE: verifier verdict does not authorize lockdown", file=sys.stderr)
        return 1

    probe_rc, probe_payload, probe_text = _run_json_command(
        [sys.executable, str(REPO_ROOT / "bin" / "arda_lockdown_confidentiality_probe.py"), "--json"]
    )
    bootstrap_rc, bootstrap_payload, bootstrap_text = _run_json_command(
        [sys.executable, str(REPO_ROOT / "bin" / "arda_bootstrap_verify.py"), "--json"]
    )
    os_grade_cmd = [
        sys.executable,
        str(REPO_ROOT / "bin" / "arda_os_grade_gate.py"),
        "--json",
        "--signed-verdict",
        args.os_grade_signed_verdict,
        "--verifier-public-key",
        args.verifier_public_key,
        "--verifier-key-id",
        args.verifier_key_id,
    ]
    os_grade_rc, os_grade_payload, os_grade_text = _run_json_command(os_grade_cmd)

    blockers = []
    if probe_rc != 0 or not probe_payload or not probe_payload.get("ok"):
        blockers.append("confidentiality_probe")
    if bootstrap_rc != 0 or not bootstrap_payload or not bootstrap_payload.get("ok"):
        blockers.append("bootstrap")
    if os_grade_rc != 0 or not os_grade_payload or not os_grade_payload.get("ok"):
        blockers.append("os_grade")

    current_lockdown_raw = _safe_text("/sys/kernel/security/lockdown")
    active_lockdown_mode = "integrity" if "[integrity]" in current_lockdown_raw else ("confidentiality" if "[confidentiality]" in current_lockdown_raw else None)

    promotion_payload = {
        "ok": not blockers,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verdict_id": verdict.get("verdict_id"),
        "authorized_states": authorized_states,
        "active_lockdown_mode": active_lockdown_mode,
        "current_lockdown_raw": current_lockdown_raw,
        "blockers": blockers,
        "prechecks": {
            "confidentiality_probe": {
                "ok": bool(probe_payload and probe_payload.get("ok")),
                "returncode": probe_rc,
                "payload": probe_payload,
                "raw": probe_text,
            },
            "bootstrap": {
                "ok": bool(bootstrap_payload and bootstrap_payload.get("ok")),
                "returncode": bootstrap_rc,
                "payload": bootstrap_payload,
                "raw": bootstrap_text,
            },
            "os_grade": {
                "ok": bool(os_grade_payload and os_grade_payload.get("ok")),
                "returncode": os_grade_rc,
                "payload": os_grade_payload,
                "raw": os_grade_text,
            },
        },
        "promotion": {
            "mode": "planned_reboot_lane",
            "requires_reboot": True,
            "verifier_authorized_lockdown": True,
            "next_actions": [
                "preserve a known-good integrity boot entry as rollback",
                "apply a confidentiality lockdown boot configuration in a separate reboot lane",
                "reboot into the confidentiality lane",
                "re-run bootstrap, os-grade, and verifier attestation immediately after boot",
            ],
        },
    }

    rollback_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verdict_id": verdict.get("verdict_id"),
        "rollback_strategy": {
            "fallback_boot_entry_required": True,
            "rescue_requires_fresh_verifier_authorization": True,
            "steps": [
                "boot fallback integrity profile or fallback kernel entry",
                "mint a fresh verifier verdict if rescue or lockdown transition is required",
                "run arda rescue with a fresh signed verdict and explicit recovery reason",
                "verify bootstrap and os-grade after rollback",
            ],
        },
    }

    for path, payload in (
        (Path(args.promotion_record), promotion_payload),
        (Path(args.rollback_record), rollback_payload),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(promotion_payload, indent=2, sort_keys=True))
    return 0 if promotion_payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
