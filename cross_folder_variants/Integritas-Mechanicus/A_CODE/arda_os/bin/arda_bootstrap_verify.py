#!/usr/bin/env python3
"""Verify that an ARDA host has the minimum boot/policy substrate to claim protection."""

import argparse
import json
import os
import platform
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _current_active_records(status: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    records = (
        status.get("phase3_measured_identity", {})
        .get("required_maps", {})
        .get("active_records", [])
    )
    current = []
    for record in records:
        payload = record.get("payload") or {}
        expires_at = payload.get("expires_at")
        if not expires_at:
            current.append(record)
            continue
        try:
            parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            current.append(record)
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed.astimezone(timezone.utc) > now:
            current.append(record)
            continue
        if record.get("state") == "active" and record.get("enforcement_mode") == "fsverity_strict":
            current.append(record)
    return current


def _latest_active_record(status: dict) -> dict | None:
    active_records = _current_active_records(status)
    if not active_records:
        return None
    return max(active_records, key=lambda record: int(record.get("generation") or 0))


def _find_manifest_file(manifest_id: str, projection_dir: Path) -> Path | None:
    direct = projection_dir / f"{manifest_id}.json"
    candidates = [direct]
    try:
        candidates.extend(sorted(projection_dir.glob("*.json")))
    except OSError:
        pass
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        payload = _read_json(candidate)
        if payload and payload.get("manifest_id") == manifest_id:
            return candidate
    return None


def _effective_manifest_path(requested: Path, status: dict) -> Path:
    if requested.is_file():
        return requested
    latest_record = _latest_active_record(status)
    if latest_record is None:
        return requested
    manifest_id = str(latest_record.get("manifest_id") or "").strip()
    if not manifest_id:
        return requested
    projection_dir = requested.parent if str(requested.parent) else Path("/var/lib/arda/projection")
    resolved = _find_manifest_file(manifest_id, projection_dir)
    return resolved or requested


def _effective_policy_state(status: dict, projection: dict | None) -> dict:
    policy_state = dict(status.get("policy_projection_state") or {})
    if policy_state.get("generation_hash_prefix"):
        return policy_state
    projection_targets = (projection or {}).get("targets", {})
    policy_generation = str(
        (projection_targets.get("constitutional_state") or {}).get("policy_generation") or ""
    )
    redline_rule_count = int(
        (projection_targets.get("constitutional_state") or {}).get("redline_rule_count") or 0
    )
    if not policy_generation:
        return policy_state
    return {
        "generation_hash_prefix": int.from_bytes(
            hashlib.sha256(policy_generation.encode("utf-8")).digest()[:8],
            "little",
        ),
        "redline_rule_count": redline_rule_count,
        "projection_flags": 1 if redline_rule_count > 0 else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ARDA bootstrap state on the current host")
    parser.add_argument("--bundle", default="/etc/arda/policy/active_bundle.json")
    parser.add_argument("--projection-plan", default="/etc/arda/policy/active_projection_plan.json")
    parser.add_argument("--manifest", default="/var/lib/arda/projection/measured-root.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    projection_path = Path(args.projection_plan)
    requested_manifest_path = Path(args.manifest)

    service = OsEnforcementService(arm=False)
    try:
        status = service.get_status()
    finally:
        service.shutdown()

    manifest_path = _effective_manifest_path(requested_manifest_path, status)
    bundle = _read_json(bundle_path)
    projection = _read_json(projection_path)
    manifest = _read_json(manifest_path)
    policy_state = _effective_policy_state(status, projection)
    active_records = _current_active_records(status)
    latest_active_record = _latest_active_record(status)

    checks = {
        "valinor_kernel": "valinor" in platform.release(),
        "policy_bundle_present": bundle_path.is_file() and bundle is not None,
        "projection_plan_present": projection_path.is_file() and projection is not None,
        "projection_targets_non_empty": bool(
            (projection or {}).get("targets", {}).get("harmony_allow_paths")
        ),
        "projection_mode_declared": (
            (projection or {}).get("targets", {}).get("enforcement_mode")
            in {"audit", "legacy_inode", "fsverity_strict"}
        ),
        "authoritative_maps_present": bool(
            status.get("required_maps", {}).get("all_required_present")
        ),
        "policy_state_present": bool(policy_state.get("generation_hash_prefix")),
        "measured_manifest_present": manifest_path.is_file() and manifest is not None,
        "measured_records_present": bool(active_records),
        "bpf_authoritative": bool(
            status.get("is_authoritative") and not status.get("is_simulation")
        ),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    report = {
        "ok": not blockers,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kernel": platform.release(),
        "checks": checks,
        "blockers": blockers,
        "bundle": str(bundle_path),
        "projection_plan": str(projection_path),
        "manifest": str(manifest_path),
        "status_summary": {
            "arm_mode": status.get("arm_mode"),
            "enforcement_mode": status.get("enforcement_mode"),
            "policy_projection_state": policy_state,
            "active_generation": latest_active_record.get("generation") if latest_active_record else None,
            "active_manifest_id": latest_active_record.get("manifest_id") if latest_active_record else None,
        },
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("ARDA BOOTSTRAP VERIFY")
        print(f"ok: {report['ok']}")
        print(f"kernel: {report['kernel']}")
        print("blockers:")
        for blocker in blockers or ["none"]:
            print(f"- {blocker}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
