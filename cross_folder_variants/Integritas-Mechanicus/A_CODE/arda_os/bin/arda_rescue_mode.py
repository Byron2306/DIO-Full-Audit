#!/usr/bin/env python3
"""Return a live ARDA host to a conservative audit posture."""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402
from backend.services.phase4_rollout_control import (  # noqa: E402
    Phase4RolloutController,
    RolloutControlError,
    TrustedVerifierVerdict,
    VerifiedVerdictReplayStore,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Return ARDA to audit posture with evidence preserved")
    parser.add_argument(
        "--projection-plan",
        default="/etc/arda/policy/active_projection_plan.json",
        help="Current projection plan to clone into an audit fallback",
    )
    parser.add_argument(
        "--output",
        default="/etc/arda/policy/rescue_projection_plan.json",
        help="Where to write the rescue audit projection plan",
    )
    parser.add_argument(
        "--record",
        default="/var/lib/arda/recovery/rescue-last.json",
        help="Where to write the rescue action record",
    )
    parser.add_argument("--signed-verdict", help="Fresh verifier service response or signed verdict for rescue authorization")
    parser.add_argument("--verifier-public-key", default=os.environ.get("ARDA_VERIFIER_PUBLIC_KEY"))
    parser.add_argument("--verifier-key-id", default=os.environ.get("ARDA_VERIFIER_KEY_ID", "arda-phase4-verifier"))
    parser.add_argument("--replay-db", default="/var/lib/arda/verifier/verdict-replay.sqlite3")
    parser.add_argument("--recovery-reason", required=True)
    parser.add_argument("--seed-running-processes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    projection_path = Path(args.projection_plan)
    output_path = Path(args.output)
    record_path = Path(args.record)

    if not projection_path.is_file():
        print(f"ARDA_RESCUE: projection plan missing: {projection_path}", file=sys.stderr)
        return 1
    if not args.signed_verdict or not args.verifier_public_key:
        print("ARDA_RESCUE: fresh verifier authorization is required for rescue", file=sys.stderr)
        return 1

    try:
        controller = Phase4RolloutController(
            TrustedVerifierVerdict(args.verifier_public_key, key_id=args.verifier_key_id),
            VerifiedVerdictReplayStore(args.replay_db),
        )
        signed_verdict = _load_json(Path(args.signed_verdict))
        controller.evaluate(signed_verdict, "rescue")
    except (OSError, ValueError, RolloutControlError) as error:
        print(f"ARDA_RESCUE: {error}", file=sys.stderr)
        return 1

    plan = _load_json(projection_path)
    rescue_plan = json.loads(json.dumps(plan))
    rescue_plan.setdefault("targets", {})
    rescue_plan["targets"]["enforcement_mode"] = "audit"

    previous_mode = (
        plan.get("targets", {}).get("enforcement_mode")
        or "unknown"
    )
    _write_json(output_path, rescue_plan)

    service = OsEnforcementService(arm=False)
    try:
        projection = service.project_pinned_policy(
            harmonic_paths=rescue_plan.get("targets", {}).get("harmony_allow_paths", []),
            enforcement_mode="audit",
            constitutional_state=rescue_plan.get("targets", {}).get("constitutional_state"),
            seed_running_processes=args.seed_running_processes,
        )
        lockdown_ok = service.set_emergency_lockdown(False)
        status = service.get_status()
    except Exception as error:
        print(f"ARDA_RESCUE: {error}", file=sys.stderr)
        return 1
    finally:
        service.shutdown()

    payload = {
        "ok": projection.get("ok") is True and lockdown_ok is True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "previous_mode": previous_mode,
        "rescue_mode": "audit",
        "projection_plan_source": str(projection_path),
        "projection_plan_output": str(output_path),
        "lockdown_disabled": lockdown_ok,
        "recovery_reason": args.recovery_reason,
        "seed_running_processes": args.seed_running_processes,
        "projection": projection,
        "status_summary": {
            "arm_mode": status.get("arm_mode"),
            "enforcement_mode": status.get("enforcement_mode"),
            "deny_count": status.get("deny_count"),
            "policy_projection_state": status.get("policy_projection_state"),
        },
    }
    _write_json(record_path, payload)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("ARDA RESCUE MODE")
        print(f"ok: {payload['ok']}")
        print(f"previous_mode: {payload['previous_mode']}")
        print(f"rescue_mode: {payload['rescue_mode']}")
        print(f"record: {record_path}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
