#!/usr/bin/env python3
"""Fail closed if a checkout/mount change separates the unified runtime stores."""
import os
from pathlib import Path
import subprocess

EXPECTED_UUID = "9364e8bd-80e9-4bcd-aabc-661055ed487c"

def verify(
    repo: Path,
    state: Path,
    mount_uuid: str,
    state_uuid: str,
    telemetry_uuid: str,
) -> None:
    if mount_uuid != EXPECTED_UUID:
        raise RuntimeError("Expected DIO data volume is not mounted")
    if state_uuid != EXPECTED_UUID:
        raise RuntimeError("DIO state directory is not on the expected data volume")
    if telemetry_uuid != EXPECTED_UUID:
        raise RuntimeError("DIO telemetry directory is not on the expected data volume")
    if not state.is_dir() or (repo / "state").resolve() != state.resolve():
        raise RuntimeError("DIO state binding changed; refusing split runtime startup")
    if not (state / "telemetry").is_dir():
        raise RuntimeError("DIO telemetry directory is missing; refusing split runtime startup")
    if (repo / "telemetry").resolve() != (state / "telemetry").resolve():
        raise RuntimeError("DIO event binding changed; refusing split runtime startup")


def _filesystem_uuid(path: Path) -> str:
    return subprocess.check_output(
        ["findmnt", "-nro", "UUID", "--target", str(path.resolve())],
        text=True,
    ).strip()


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[1]
    configured = os.environ.get("DIO_STATE_ROOT", "")
    if not configured:
        raise SystemExit("DIO_STATE_ROOT is required")
    state = Path(configured).expanduser().resolve()
    telemetry = state / "telemetry"
    mounted = subprocess.check_output(
        ["findmnt", "-nro", "UUID", "--mountpoint", "/data"], text=True
    ).strip()
    if not state.is_dir() or not telemetry.is_dir():
        raise SystemExit("DIO state/telemetry directory is missing")
    verify(
        repo,
        state,
        mounted,
        _filesystem_uuid(state),
        _filesystem_uuid(telemetry),
    )
