#!/usr/bin/env python3
"""
Show the active Arda policy bundle and optional projection plan.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.policy_compiler import (  # noqa: E402
    POLICY_BUNDLE_PATH,
    load_and_verify_policy_bundle,
)
from backend.services.policy_engine import load_and_verify_policy  # noqa: E402
from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


DEFAULT_ACTIVE_BUNDLE_PATH = "/etc/arda/policy/active_bundle.json"
DEFAULT_PROJECTION_PATH = "/etc/arda/policy/active_projection_plan.json"


def _load_json_if_present(path: str):
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _default_bundle_path() -> str:
    if os.path.exists(DEFAULT_ACTIVE_BUNDLE_PATH):
        return DEFAULT_ACTIVE_BUNDLE_PATH
    return POLICY_BUNDLE_PATH


def _policy_digest(policy: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Show active Arda policy bundle state")
    parser.add_argument("--bundle", default=_default_bundle_path())
    parser.add_argument("--projection-plan", default=DEFAULT_PROJECTION_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        bundle = load_and_verify_policy_bundle(args.bundle)
        projection = _load_json_if_present(args.projection_plan)
        source_policy = load_and_verify_policy()
    except Exception as error:
        print(f"ARDA_POLICY_SHOW: {error}", file=sys.stderr)
        return 1

    service = OsEnforcementService(arm=False)
    try:
        live_status = service.get_status()
    finally:
        service.shutdown()

    targets = (projection or {}).get("targets", {})
    constitutional_state = targets.get("constitutional_state", {})
    source_policy_digest = _policy_digest(source_policy)
    bundle_source_digest = str(bundle.get("source_policy_digest") or "")
    live_enforcement_mode = live_status.get("enforcement_mode")
    declared_projection_mode = targets.get("enforcement_mode")

    payload = {
        "cwd": os.getcwd(),
        "bundle_path": os.path.abspath(args.bundle),
        "projection_plan_path": os.path.abspath(args.projection_plan),
        "bundle_source": (
            "deployed_active_bundle"
            if os.path.abspath(args.bundle) == os.path.abspath(DEFAULT_ACTIVE_BUNDLE_PATH)
            else "repository_default_bundle"
        ),
        "bundle": bundle,
        "source_policy": {
            "policy_id": source_policy.get("policy_id"),
            "policy_version": source_policy.get("version"),
            "source_policy_digest": source_policy_digest,
            "redline_rule_count": len(source_policy.get("redline_rules", [])),
        },
        "projection_plan": projection,
        "bundle_fresh_against_source_policy": bundle_source_digest == source_policy_digest,
        "mode_alignment": {
            "declared_projection_mode": declared_projection_mode,
            "live_enforcement_mode": live_enforcement_mode,
            "aligned": bool(
                declared_projection_mode
                and live_enforcement_mode
                and declared_projection_mode == live_enforcement_mode
            ),
        },
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    lines = [
        "ARDA POLICY SHOW",
        f"bundle_path: {payload['bundle_path']}",
        f"bundle_source: {payload['bundle_source']}",
        f"projection_plan_path: {payload['projection_plan_path']}",
        f"policy_id: {bundle.get('policy_id')}",
        f"policy_version: {bundle.get('policy_version')}",
        f"compiled_at: {bundle.get('compiled_at')}",
        f"source_policy_digest: {bundle.get('source_policy_digest')}",
        f"bundle_signature_present: {bool(bundle.get('signature'))}",
        f"bundle_fresh_against_source_policy: {payload['bundle_fresh_against_source_policy']}",
        f"projection_present: {projection is not None}",
        f"projection_enforcement_mode: {declared_projection_mode or '(missing)'}",
        f"live_enforcement_mode: {live_enforcement_mode or '(missing)'}",
        f"mode_alignment: {payload['mode_alignment']['aligned']}",
        f"projection_allow_path_count: {len(targets.get('harmony_allow_paths', []))}",
        f"projection_redline_rule_count: {len(targets.get('redline_rules', []))}",
        f"source_policy_redline_rule_count: {len(source_policy.get('redline_rules', []))}",
        f"policy_generation: {constitutional_state.get('policy_generation', '(missing)')}",
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
