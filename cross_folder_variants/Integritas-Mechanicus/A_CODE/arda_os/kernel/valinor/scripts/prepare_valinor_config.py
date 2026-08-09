#!/usr/bin/env python3
"""Prepare a Linux source tree .config for the Valinor kernel flavor."""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VALINOR_DIR = SCRIPT_DIR.parent
DEFAULT_BASE = VALINOR_DIR / "config.base"
DEFAULT_FRAGMENT = VALINOR_DIR / "config.fragment"
CHECKER = SCRIPT_DIR / "check_valinor_config.py"


def _read_required(path: Path) -> dict[str, str]:
    required: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# ") and stripped.endswith(" is not set"):
            key = stripped[2 : -len(" is not set")]
            required[key] = "n"
            continue
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        required[key] = value
    return required


def _upsert_config_value(lines: list[str], key: str, value: str) -> list[str]:
    replacement = f"{key}={value}"
    disabled = f"# {key} is not set"
    updated = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped == disabled:
            if not replaced:
                updated.append(replacement)
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        updated.append(replacement)
    return updated


def _run(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Valinor .config in a Linux source tree")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--base-config", default=str(DEFAULT_BASE))
    parser.add_argument("--fragment", default=str(DEFAULT_FRAGMENT))
    parser.add_argument("--skip-olddefconfig", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    base_config = Path(args.base_config).resolve()
    fragment = Path(args.fragment).resolve()
    config_path = source_dir / ".config"

    failures = []
    if not source_dir.is_dir():
        failures.append(f"source_dir_missing:{source_dir}")
    if not (source_dir / "Makefile").is_file():
        failures.append(f"linux_makefile_missing:{source_dir}")
    if not base_config.is_file():
        failures.append(f"base_config_missing:{base_config}")
    if not fragment.is_file():
        failures.append(f"fragment_missing:{fragment}")
    if failures:
        report = {"ok": False, "failures": failures}
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else "\n".join(failures))
        return 1

    shutil.copyfile(base_config, config_path)
    lines = config_path.read_text(encoding="utf-8").splitlines()
    for key, value in _read_required(fragment).items():
        lines = _upsert_config_value(lines, key, value)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    olddefconfig = None
    if not args.skip_olddefconfig:
        rc, output = _run(["make", "olddefconfig"], source_dir)
        olddefconfig = {"returncode": rc, "output": output}
        if rc != 0:
            report = {
                "ok": False,
                "failures": ["olddefconfig_failed"],
                "olddefconfig": olddefconfig,
            }
            print(json.dumps(report, indent=2, sort_keys=True) if args.json else output)
            return 1

    rc, check_output = _run(
        [
            sys.executable,
            str(CHECKER),
            "--config",
            str(config_path),
            "--fragment",
            str(fragment),
            "--json",
        ],
        VALINOR_DIR,
    )
    check_report = json.loads(check_output)
    report = {
        "ok": rc == 0,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_dir),
        "config": str(config_path),
        "base_config": str(base_config),
        "fragment": str(fragment),
        "olddefconfig": olddefconfig,
        "check": check_report,
    }
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else check_output)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
