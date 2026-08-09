#!/usr/bin/env python3
"""
Arda Phase 1 Status CLI

Operational wrapper around the hardened OsEnforcementService status and self-test
surface. This gives Phase 1 a human-usable diagnostic path instead of relying on
unit tests or ad hoc imports.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


def _format_status(status):
    loader = status.get("loader_status", {})
    readiness = status.get("readiness", {})
    required_maps = status.get("required_maps", {})
    lines = [
        "ARDA SOVEREIGN GUARD STATUS",
        f"sovereign_mode: {status['sovereign_mode']}",
        f"is_authoritative: {status['is_authoritative']}",
        f"is_simulation: {status['is_simulation']}",
        f"attach_verified: {status['attach_verified']}",
        f"arm_mode: {status['arm_mode']}",
        f"bpf_source: {status['bpf_source'] or '(missing)'}",
        f"pin_path: {status['pin_path'] or '(unpinned)'}",
        f"armed_at: {status['armed_at'] or '(not armed)'}",
        f"last_error: {status['last_error'] or '(none)'}",
        f"preferred_loader_mode: {loader.get('preferred_loader_mode', '(unknown)')}",
        f"canonical_loader_source_exists: {loader.get('canonical_loader_source_exists')}",
        f"canonical_loader_binary_exists: {loader.get('canonical_loader_binary_exists')}",
        f"canonical_bpf_object_exists: {loader.get('canonical_bpf_object_exists')}",
        f"required_map_contract_ready: {required_maps.get('all_required_present')}",
        f"ready_for_authoritative_attempt: {readiness.get('ready_for_authoritative_attempt')}",
        f"deny_count: {status.get('deny_count')}",
    ]
    last_deny_event = status.get("last_deny_event")
    if last_deny_event:
        lines.append(
            "last_deny_event: "
            f"reason={last_deny_event.get('deny_reason')} "
            f"mode={last_deny_event.get('enforcement_mode')} "
            f"cgroup_id={last_deny_event.get('cgroup_id')} "
            f"generation={last_deny_event.get('active_generation')} "
            f"inode={last_deny_event.get('inode')} "
            f"dev={last_deny_event.get('dev')}"
        )

    blockers = readiness.get("blockers") or []
    recommendations = readiness.get("recommendations") or []
    if blockers:
        lines.append(f"blockers: {', '.join(blockers)}")
    if recommendations:
        lines.append(f"next_actions: {' | '.join(recommendations)}")

    maps = required_maps.get("maps") or {}
    if maps:
        for map_name, map_info in maps.items():
            lines.append(
                f"map[{map_name}]: present={map_info.get('present')} "
                f"pin={map_info.get('pin_exists')} handle={map_info.get('in_process_handle')}"
            )

    self_test = status.get("last_self_test")
    if self_test:
        lines.append(f"last_self_test_ok: {self_test.get('ok')}")
        lines.append(f"last_self_test_timestamp: {self_test.get('timestamp')}")
        failure = self_test.get("details", {}).get("failure")
        lines.append(f"last_self_test_failure: {failure or '(none)'}")
    else:
        lines.append("last_self_test_ok: (not run)")

    return "\n".join(lines)


def _markdown_status(payload):
    status = payload["status"]
    readiness = status.get("readiness", {})
    loader = status.get("loader_status", {})
    required_maps = status.get("required_maps", {})
    lines = [
        "# Arda Phase 1 Status Snapshot",
        "",
        f"- Timestamp: {payload.get('timestamp', '(unknown)')}",
        f"- CWD: `{payload['cwd']}`",
        "",
        "## Guard State",
        "",
        f"- `sovereign_mode`: `{status['sovereign_mode']}`",
        f"- `is_authoritative`: `{status['is_authoritative']}`",
        f"- `is_simulation`: `{status['is_simulation']}`",
        f"- `arm_mode`: `{status['arm_mode']}`",
        f"- `attach_verified`: `{status['attach_verified']}`",
        f"- `last_error`: `{status['last_error'] or '(none)'}`",
        f"- `fallback_last_error`: `{status.get('fallback_last_error') or '(none)'}`",
        "",
        "## Loader State",
        "",
        f"- `preferred_loader_mode`: `{loader.get('preferred_loader_mode')}`",
        f"- `canonical_loader_source_exists`: `{loader.get('canonical_loader_source_exists')}`",
        f"- `canonical_loader_binary_exists`: `{loader.get('canonical_loader_binary_exists')}`",
        f"- `canonical_bpf_source_exists`: `{loader.get('canonical_bpf_source_exists')}`",
        f"- `canonical_bpf_object_exists`: `{loader.get('canonical_bpf_object_exists')}`",
        f"- `loader_attempted`: `{status.get('loader_attempted')}`",
        f"- `loader_last_error`: `{status.get('loader_last_error') or '(none)'}`",
        "",
        "## Readiness",
        "",
        f"- `ready_for_authoritative_attempt`: `{readiness.get('ready_for_authoritative_attempt')}`",
        f"- `required_map_contract_ready`: `{required_maps.get('all_required_present')}`",
        f"- `deny_count`: `{status.get('deny_count')}`",
    ]
    last_deny_event = status.get("last_deny_event")
    if last_deny_event:
        lines.extend(
            [
                f"- `last_deny_reason`: `{last_deny_event.get('deny_reason')}`",
                f"- `last_deny_mode`: `{last_deny_event.get('enforcement_mode')}`",
                f"- `last_deny_cgroup_id`: `{last_deny_event.get('cgroup_id')}`",
                f"- `last_deny_generation`: `{last_deny_event.get('active_generation')}`",
                f"- `last_deny_inode`: `{last_deny_event.get('inode')}`",
                f"- `last_deny_dev`: `{last_deny_event.get('dev')}`",
            ]
        )

    blockers = readiness.get("blockers") or []
    if blockers:
        lines.append("")
        lines.append("### Blockers")
        lines.append("")
        for blocker in blockers:
            lines.append(f"- `{blocker}`")

    recommendations = readiness.get("recommendations") or []
    if recommendations:
        lines.append("")
        lines.append("### Recommendations")
        lines.append("")
        for recommendation in recommendations:
            lines.append(f"- {recommendation}")

    maps = required_maps.get("maps") or {}
    if maps:
        lines.extend(
            [
                "",
                "## Required Maps",
                "",
            ]
        )
        for map_name, map_info in maps.items():
            lines.append(
                f"- `{map_name}`: `present={map_info.get('present')}` `pin={map_info.get('pin_exists')}` `handle={map_info.get('in_process_handle')}` `pin_path={map_info.get('pin_path')}`"
            )

    native = payload.get("native_denial_test")
    if native:
        lines.extend(
            [
                "",
                "## Native Denial Test",
                "",
                f"- `ok`: `{native.get('ok')}`",
                f"- `failure`: `{native.get('details', {}).get('failure', '(none)')}`",
            ]
        )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Phase 1 status and self-test for Arda's sovereign guard")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the focused Phase 1 guard self-test before reporting status",
    )
    parser.add_argument(
        "--test-executable",
        help="Executable path to use for the Phase 1 self-test map synchronization step",
    )
    parser.add_argument(
        "--native-denial-test",
        action="store_true",
        help="Attempt the stronger native kernel denial self-test for an unharmonic executable",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Emit a markdown snapshot instead of plain text or JSON",
    )
    args = parser.parse_args()

    service = OsEnforcementService()

    result = None
    native_result = None
    if args.self_test:
        result = service.run_self_test(args.test_executable)
    if args.native_denial_test:
        native_result = service.run_native_denial_self_test()

    status = service.get_status()
    payload = {
        "status": status,
        "self_test": result,
        "native_denial_test": native_result,
        "cwd": os.getcwd(),
        "timestamp": status.get("armed_at") or datetime.now(timezone.utc).isoformat(),
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.markdown:
        print(_markdown_status(payload), end="")
    else:
        print(_format_status(status))
        if result:
            print("")
            print("SELF-TEST RESULT")
            print(f"ok: {result['ok']}")
            for check_name, check_value in result["checks"].items():
                print(f"{check_name}: {check_value}")
            failure = result.get("details", {}).get("failure")
            if failure:
                print(f"failure: {failure}")
        if native_result:
            print("")
            print("NATIVE DENIAL TEST RESULT")
            print(f"ok: {native_result['ok']}")
            for check_name, check_value in native_result["checks"].items():
                print(f"{check_name}: {check_value}")
            failure = native_result.get("details", {}).get("failure")
            if failure:
                print(f"failure: {failure}")

    if args.self_test and result and not result["ok"]:
        return 1
    if args.native_denial_test and native_result and not native_result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
