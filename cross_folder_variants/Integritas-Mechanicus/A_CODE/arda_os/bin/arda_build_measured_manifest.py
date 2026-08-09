#!/usr/bin/env python3
"""Build a fresh non-empty Arda measured-identity manifest."""

import argparse
import ctypes
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.measured_policy_profiles import (  # noqa: E402
    expand_measurement_profile,
    merge_discovered_manifest_paths,
)


AUDIENCE = "arda-measured-preflight"
SCHEMA_VERSION = "arda.measured_manifest.v1"
AT_FDCWD = -100


class _FileHandle(ctypes.Structure):
    _fields_ = [
        ("handle_bytes", ctypes.c_uint),
        ("handle_type", ctypes.c_int),
        ("f_handle", ctypes.c_ubyte * 128),
    ]


def _canonical_json_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _fsverity_digest(path: str) -> tuple[int, str, str]:
    fsverity = shutil.which("fsverity")
    if fsverity:
        result = subprocess.run(
            [fsverity, "digest", path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            text = result.stdout.strip().lower()
            for token in reversed(text.replace(":", " ").split()):
                if len(token) in (64, 128):
                    try:
                        bytes.fromhex(token)
                        return 1, token, "fsverity"
                    except ValueError:
                        pass
    return 1, _sha256_file(path), "sha256-fallback"


def _namespace_inode(path: str) -> int | None:
    try:
        target = os.readlink(path)
        if "[" in target and target.endswith("]"):
            return int(target.rsplit("[", 1)[1][:-1])
    except Exception:
        return None
    return None


def _read_cgroup_id() -> str:
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
    except Exception:
        return "self"
    return lines[-1].split(":", 2)[-1] if lines else "self"


def _read_cgroup_kernel_id() -> int | None:
    cgroup_path = _read_cgroup_id()
    mount_root = "/sys/fs/cgroup"
    relative = cgroup_path.lstrip("/")
    target = os.path.join(mount_root, relative) if relative else mount_root
    libc = ctypes.CDLL(None, use_errno=True)
    handle = _FileHandle()
    handle.handle_bytes = 128
    mount_id = ctypes.c_int()
    rc = libc.name_to_handle_at(
        ctypes.c_int(AT_FDCWD),
        ctypes.c_char_p(target.encode("utf-8")),
        ctypes.byref(handle),
        ctypes.byref(mount_id),
        ctypes.c_int(0),
    )
    if rc == 0 and handle.handle_bytes >= 8:
        return int.from_bytes(bytes(handle.f_handle[:8]), "little")
    try:
        return os.stat(target).st_ino
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an Arda measured-identity manifest")
    parser.add_argument("--path", action="append", default=[], help="Executable or file path to include")
    parser.add_argument("--profile", choices=["critical-host"], action="append", default=[])
    parser.add_argument("--discover-live-system", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--node-id", default=os.uname().nodename)
    parser.add_argument("--policy-generation", required=True)
    parser.add_argument("--generation", type=int, default=1)
    parser.add_argument("--ttl-seconds", type=int, default=240)
    parser.add_argument("--attestation-result-id")
    parser.add_argument("--attestation-evidence-digest")
    parser.add_argument("--signing-key", default=os.environ.get("ARDA_MEASURED_MANIFEST_KEY", "local-proof-key"))
    args = parser.parse_args()

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=args.ttl_seconds)
    requested_paths = list(args.path)
    for profile in args.profile:
        requested_paths.extend(expand_measurement_profile(profile, repo_root=str(REPO_ROOT)))
    discovery_manifest = None
    if args.discover_live_system:
        from backend.services.arda_discover import build_manifest, discover_all  # noqa: E402

        discovery_manifest = build_manifest(discover_all())
        requested_paths.extend(merge_discovered_manifest_paths(discovery_manifest))
    if not requested_paths:
        print("ARDA_BUILD_MEASURED_MANIFEST: no input paths", file=sys.stderr)
        return 1

    entries = []
    seen = set()
    digest_sources = {}

    for requested in requested_paths:
        path = os.path.abspath(requested)
        if path in seen or not os.path.exists(path) or not os.path.isfile(path):
            continue
        algorithm_id, fs_digest, digest_source = _fsverity_digest(path)
        workload_digest = _sha256_file(path)
        entries.append(
            {
                "path": path,
                "fs_verity_algorithm_id": algorithm_id,
                "fs_verity_digest": fs_digest,
                "workload_digest": f"sha256:{workload_digest}",
            }
        )
        digest_sources[path] = digest_source
        seen.add(path)

    if not entries:
        print("ARDA_BUILD_MEASURED_MANIFEST: no executable entries", file=sys.stderr)
        return 1

    manifest_id_seed = {
        "node_id": args.node_id,
        "policy_generation": args.policy_generation,
        "generation": args.generation,
        "entries": entries,
        "issued_at": issued_at.isoformat(),
    }
    manifest_id = "measured-" + hashlib.sha256(_canonical_json_bytes(manifest_id_seed)).hexdigest()[:16]
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "generation": args.generation,
        "node_id": args.node_id,
        "policy_generation": args.policy_generation,
        "audience": AUDIENCE,
        "attestation_result_id": args.attestation_result_id,
        "attestation_evidence_digest": args.attestation_evidence_digest,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "entries": entries,
    }
    signature = hmac.new(args.signing_key.encode("utf-8"), _canonical_json_bytes(unsigned), hashlib.sha256).hexdigest()
    manifest = {
        **unsigned,
        "cgroup_id": _read_cgroup_id(),
        "cgroup_kernel_id": _read_cgroup_kernel_id() or 1,
        "pid_namespace_inode": _namespace_inode("/proc/self/ns/pid"),
        "mount_namespace_inode": _namespace_inode("/proc/self/ns/mnt"),
        "signature": {
            "algorithm": "hmac-sha256-local-proof",
            "keyid": "ARDA_MEASURED_MANIFEST_KEY",
            "signature": signature,
        },
        "builder_audit": {
            "digest_sources": digest_sources,
            "fsverity_command": shutil.which("fsverity"),
            "live_discovery": {
                "enabled": bool(args.discover_live_system),
                "discovered_entry_count": len((discovery_manifest or {}).get("entries") or []),
                "discovery_protocol": (discovery_manifest or {}).get("protocol"),
            },
        },
    }

    output = os.path.abspath(args.output)
    _write_json(output, manifest)

    aliases = []
    manifest_id_path = os.path.join(os.path.dirname(output), f"{manifest_id}.json")
    if os.path.abspath(manifest_id_path) != output:
        _write_json(manifest_id_path, manifest)
        aliases.append(os.path.abspath(manifest_id_path))

    if "critical-host" in args.profile:
        stable_output = os.path.join(os.path.dirname(output), "measured-critical.json")
        if os.path.abspath(stable_output) != output:
            _write_json(stable_output, manifest)
            aliases.append(os.path.abspath(stable_output))

    print(
        json.dumps(
            {
                "ok": True,
                "output": output,
                "aliases": aliases,
                "manifest_id": manifest_id,
                "entry_count": len(entries),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
