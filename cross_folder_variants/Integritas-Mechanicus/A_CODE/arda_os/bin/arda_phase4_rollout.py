#!/usr/bin/env python3
"""Apply verifier-driven ARDA rollout state transitions."""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402
from backend.services.phase4_rollout_control import (  # noqa: E402
    Phase4RolloutController,
    TrustedVerifierVerdict,
    VerifiedVerdictReplayStore,
    RolloutControlError,
)


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply verifier-driven ARDA rollout state")
    parser.add_argument("--signed-verdict", required=True)
    parser.add_argument("--state", required=True, choices=["observe", "enforce", "lockdown", "rescue"])
    parser.add_argument("--projection-plan", default="/etc/arda/policy/active_projection_plan.json")
    parser.add_argument("--verifier-public-key", default=os.environ.get("ARDA_VERIFIER_PUBLIC_KEY"))
    parser.add_argument("--verifier-key-id", default=os.environ.get("ARDA_VERIFIER_KEY_ID", "arda-phase4-verifier"))
    parser.add_argument("--replay-db", default="/var/lib/arda/verifier/verdict-replay.sqlite3")
    parser.add_argument("--recovery-reason")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.verifier_public_key:
        print("ARDA_PHASE4_ROLLOUT: verifier public key is required", file=sys.stderr)
        return 1

    try:
        controller = Phase4RolloutController(
            TrustedVerifierVerdict(args.verifier_public_key, key_id=args.verifier_key_id),
            VerifiedVerdictReplayStore(args.replay_db),
        )
    except RolloutControlError as error:
        print(f"ARDA_PHASE4_ROLLOUT: {error}", file=sys.stderr)
        return 1
    signed_verdict = _read_json(args.signed_verdict)
    try:
        decision = controller.evaluate(signed_verdict, args.state)
    except RolloutControlError as error:
        print(f"ARDA_PHASE4_ROLLOUT: {error}", file=sys.stderr)
        return 1
    if args.state in {"lockdown", "rescue"} and not (args.recovery_reason or "").strip():
        print("ARDA_PHASE4_ROLLOUT: --recovery-reason is required for lockdown/rescue", file=sys.stderr)
        return 1

    service = OsEnforcementService(arm=False)
    try:
        projection = None
        lockdown_ok = True
        if decision.requested_state in {"observe", "rescue", "enforce"}:
            plan = _read_json(args.projection_plan)
            plan.setdefault("targets", {})
            plan["targets"]["enforcement_mode"] = decision.target_enforcement_mode
            projection = service.project_pinned_policy(
                harmonic_paths=plan.get("targets", {}).get("harmony_allow_paths", []),
                enforcement_mode=decision.target_enforcement_mode,
                constitutional_state=plan.get("targets", {}).get("constitutional_state"),
            )
        if decision.requested_state == "lockdown":
            lockdown_ok = service.set_emergency_lockdown(True)
        elif decision.requested_state in {"observe", "rescue", "enforce"}:
            lockdown_ok = service.set_emergency_lockdown(False)
        payload = {
            "ok": bool(decision.allowed and lockdown_ok),
            "requested_state": decision.requested_state,
            "target_enforcement_mode": decision.target_enforcement_mode,
            "enable_lockdown": decision.enable_lockdown,
            "reasons": list(decision.reasons),
            "recovery_reason": (args.recovery_reason or "").strip() or None,
            "projection": projection,
            "lockdown_ok": lockdown_ok,
            "status": service.get_status(),
        }
    finally:
        service.shutdown()

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
