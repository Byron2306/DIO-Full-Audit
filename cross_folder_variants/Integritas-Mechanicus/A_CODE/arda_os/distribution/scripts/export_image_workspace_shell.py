#!/usr/bin/env python3
"""Export the ARDA image workspace build sequence as a shell script."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_SUMMARY = DISTRIBUTION_DIR / "build" / "workspace" / "plans" / "workspace-summary.json"
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "build" / "workspace" / "plans" / "run-workspace.sh"

RUN_ORDER = [
    "debootstrap",
    "apply_overlay",
    "install_packages",
    "install_kernel",
    "generate_initramfs",
    "enable_units",
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _render(summary: dict) -> str:
    commands = summary.get("build_commands") or {}
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"ROOTFS_DIR={shlex.quote(summary['rootfs_dir'])}",
        f"WORKSPACE_ROOT={shlex.quote(summary['workspace_root'])}",
        'mkdir -p "$ROOTFS_DIR"',
        'rm -rf "$ROOTFS_DIR/workspace-artifacts"',
        'cp -a "$WORKSPACE_ROOT/artifacts" "$ROOTFS_DIR/workspace-artifacts"',
        "",
    ]
    for step in RUN_ORDER:
        command = list(commands.get(step) or [])
        if not command:
            continue
        lines.append(f"# {step}")
        lines.append(" ".join(shlex.quote(part) for part in command))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the ARDA image workspace shell runner")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    summary = _read_json(Path(args.summary))
    script = _render(summary)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(script, encoding="utf-8")
    output.chmod(0o755)
    print(json.dumps({"ok": True, "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
