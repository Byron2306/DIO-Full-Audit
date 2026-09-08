#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD_SOURCE = ROOT / "deploy" / "systemd"
DESKTOP_SOURCE = ROOT / "deploy" / "desktop" / "dio-apps.desktop"
SYSTEMD_FILES = (
    "dio-launcher.service",
    "dio-control-deck.service",
    "dio-goldeneye.service",
    "dio-market-command.service",
    "dio-apps.target",
)


def install(destination_home: Path | None = None, invoke_systemd: bool = True) -> list[Path]:
    home = destination_home or Path.home()
    systemd_dir = home / ".config/systemd/user"
    desktop_dir = home / ".local/share/applications"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    desktop_dir.mkdir(parents=True, exist_ok=True)

    installed: list[Path] = []
    for name in SYSTEMD_FILES:
        destination = systemd_dir / name
        shutil.copy2(SYSTEMD_SOURCE / name, destination)
        installed.append(destination)

    desktop_destination = desktop_dir / "dio-apps.desktop"
    shutil.copy2(DESKTOP_SOURCE, desktop_destination)
    installed.append(desktop_destination)

    if invoke_systemd:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "dio-apps.target"], check=True)

    return installed


def main() -> int:
    parser = argparse.ArgumentParser(description="Install DIO user-level launcher assets")
    parser.add_argument("--home", type=Path, default=None, help="Alternate home root for validation")
    parser.add_argument("--no-systemd", action="store_true", help="Copy assets without invoking systemctl")
    args = parser.parse_args()
    paths = install(destination_home=args.home, invoke_systemd=not args.no_systemd)
    print("Installed DIO launcher assets:")
    for path in paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
