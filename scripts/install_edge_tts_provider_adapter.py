#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NICHEFOUNDRY_ROOT = Path("/home/byron/Downloads/NicheFoundry_Phase11")
DEFAULT_USER_EDGE_TTS = Path.home() / ".local" / "bin" / "edge-tts"


def _resolve_real_edge_tts(explicit: str = "") -> Path:
    candidates = [
        Path(explicit).expanduser() if explicit else None,
        DEFAULT_USER_EDGE_TTS,
    ]
    found = shutil.which("edge-tts")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if resolved.is_file() and os.access(resolved, os.X_OK):
            return resolved
    raise RuntimeError("Could not locate the existing Edge TTS executable. Expected ~/.local/bin/edge-tts or --real-bin.")


def install_adapter(nichefoundry_root: Path, real_bin: Path) -> Path:
    target = nichefoundry_root / ".venv-voicebox" / "bin" / "edge-tts"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            "#!/bin/sh",
            "# DIO/NicheFoundry provider boundary: the Edge TTS package is installed",
            "# in the operator user site, while DIO intentionally runs with",
            "# PYTHONNOUSERSITE=1. Remove that flag for this explicitly selected",
            "# provider only, then delegate all arguments unchanged.",
            "unset PYTHONNOUSERSITE",
            f'exec "{real_bin}" "$@"',
            "",
        ]
    )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(temporary, target)
    return target.resolve()


def probe_adapter(adapter: Path) -> dict[str, object]:
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        [str(adapter), "--version"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    return {
        "command": [str(adapter), "--version"],
        "returncode": completed.returncode,
        "output": output[-1200:],
        "python_no_user_site_was_set_for_probe": True,
        "passed": completed.returncode == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a provider-boundary adapter for user-site Edge TTS.")
    parser.add_argument("--nichefoundry-root", type=Path, default=DEFAULT_NICHEFOUNDRY_ROOT)
    parser.add_argument("--real-bin", default="")
    args = parser.parse_args()

    nichefoundry_root = args.nichefoundry_root.expanduser().resolve()
    if not nichefoundry_root.is_dir():
        raise SystemExit(f"NicheFoundry root does not exist: {nichefoundry_root}")
    real_bin = _resolve_real_edge_tts(args.real_bin)
    adapter = install_adapter(nichefoundry_root, real_bin)
    probe = probe_adapter(adapter)
    result = {
        "schema": "dio.edge_tts.provider_adapter_install.v1",
        "state": "READY" if probe["passed"] else "FAILED",
        "real_edge_tts": str(real_bin),
        "adapter": str(adapter),
        "provider_boundary": "PYTHONNOUSERSITE removed only for Edge TTS child process",
        "probe": probe,
    }
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if probe["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
