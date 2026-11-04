#!/usr/bin/env python3
"""Refresh observed local Pocket TTS process evidence after a service restart."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "state/presence/voice_verification/vera_runtime_inventory.json"
EXPECTED_COMMAND = [
    "/home/byron/.local/share/dio-pocket-tts/venv/bin/python",
    "/home/byron/.local/share/dio-pocket-tts/venv/bin/pocket-tts",
    "serve", "--host", "127.0.0.1", "--port", "8000", "--language", "english",
    "--default-voice", "vera",
]


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    args = parser.parse_args()
    inventory_path = args.inventory.expanduser().resolve()
    if not inventory_path.is_file():
        raise SystemExit(f"Runtime inventory is missing: {inventory_path}")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if inventory.get("schema") != "dio.vesper.local_verified_runtime_inventory.v1":
        raise SystemExit("Unsupported Vera runtime inventory schema.")
    service = inventory.get("service") or {}
    if service.get("endpoint") != "http://127.0.0.1:8000/tts":
        raise SystemExit("Runtime inventory endpoint is not the expected loopback Pocket TTS endpoint.")

    result = subprocess.run(
        ["systemctl", "--user", "show", "--property=MainPID", "--value", "dio-vera-tts.service"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    pid = int(result.stdout.strip())
    if pid <= 1:
        raise SystemExit("dio-vera-tts.service has no running main process.")
    proc = Path(f"/proc/{pid}")
    command = proc.joinpath("cmdline").read_bytes().decode().rstrip("\0").split("\0")
    if command != EXPECTED_COMMAND or command != service.get("command"):
        raise SystemExit("Running Pocket TTS command differs from the previously observed local engine.")
    stat_tail = proc.joinpath("stat").read_text(encoding="ascii").split(")", 1)[1].split()
    start_ticks = stat_tail[19]

    with urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
        health = json.loads(response.read())
        if response.status != 200 or not isinstance(health, dict):
            raise SystemExit("Pocket TTS loopback health check did not return a valid object.")

    for row in inventory.get("files") or []:
        path = Path(str(row.get("path") or ""))
        if not path.is_file() or path.stat().st_size != int(row.get("bytes") or -1):
            raise SystemExit(f"Recorded Vera runtime file is missing or changed: {path}")
        if sha256_file(path) != row.get("sha256"):
            raise SystemExit(f"Recorded Vera runtime file hash mismatch: {path}")

    previous_pid = service.get("pid")
    inventory["observed_at"] = datetime.now(timezone.utc).isoformat()
    service.update({"pid": pid, "command": command, "process_start_ticks": start_ticks,
                    "package_version": service.get("package_version", "3.3.0")})
    inventory["service"] = service
    inventory["refresh_observation"] = {
        "method": "systemd_user_main_pid_proc_cmdline_proc_start_ticks_and_loopback_health",
        "previous_pid": previous_pid,
        "current_pid": pid,
        "health_response": health,
        "model_and_source_files_rehashed": True,
        "remote_attestation": False,
    }

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=inventory_path.parent,
                                         prefix=".vera-runtime-", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(inventory, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, inventory_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    print(json.dumps({"inventory": str(inventory_path), "previous_pid": previous_pid,
                      "current_pid": pid, "process_start_ticks": start_ticks,
                      "health": "READY", "runtime_files_verified": len(inventory.get("files") or [])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
