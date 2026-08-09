#!/usr/bin/env python3
"""Create a non-mutating Valinor kernel install and rollback plan."""

import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return 127, "command not found"
    return result.returncode, (result.stdout + result.stderr).strip()


def _artifact_names(manifest: dict, prefix: str) -> list[str]:
    return [
        artifact["path"]
        for artifact in manifest.get("artifacts", [])
        if artifact.get("name", "").startswith(prefix)
        and "-dbg_" not in artifact.get("name", "")
        and "-dbgsym_" not in artifact.get("name", "")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan a rollback-safe Valinor kernel install")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    output = Path(args.output).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = _artifact_names(manifest, "linux-image")
    headers = _artifact_names(manifest, "linux-headers")
    current_kernel = platform.release()
    grub_code, grub_default = _run(["grub-editenv", "list"])

    blockers = []
    if not images:
        blockers.append("missing_linux_image_package")
    if not headers:
        blockers.append("missing_linux_headers_package")

    install_commands = []
    if images or headers:
        install_commands.append("sudo dpkg -i " + " ".join(headers + images))
        install_commands.append("sudo update-initramfs -c -k <valinor-kernel-version>")
        install_commands.append("sudo update-grub")

    rollback_commands = [
        f"Reboot and select the known-good kernel from GRUB: {current_kernel}",
        "If needed from current boot: sudo grub-reboot '<known-good menu entry>' && sudo reboot",
        "If Valinor packages must be removed: sudo apt remove 'linux-image-*-valinor' 'linux-headers-*-valinor'",
    ]

    plan = {
        "schema_version": "arda.valinor_install_plan.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": not blockers,
        "blockers": blockers,
        "manifest": str(manifest_path),
        "current_kernel": current_kernel,
        "grub_env": {
            "returncode": grub_code,
            "output": grub_default,
        },
        "artifacts": {
            "linux_image_packages": images,
            "linux_header_packages": headers,
        },
        "install_commands": install_commands,
        "rollback_commands": rollback_commands,
        "post_boot_gate": [
            "uname -r",
            "test \"$(uname -r | grep -c valinor)\" -gt 0",
            "sudo env ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --promote --seed-running-processes --capture-tpm --require-tpm-capture --attestation-dir /var/lib/arda/attestation/latest",
        ],
        "systemd_units": [
            "arda_os/kernel/valinor/systemd/arda-valinor-postboot.service",
            "arda_os/kernel/valinor/systemd/arda-bombadil-valinor.service",
        ],
        "systemd_plan": [
            "arda_os/kernel/valinor/scripts/render_systemd_units.py --output-dir arda_os/kernel/valinor/releases/systemd",
            "Review rendered units before installation.",
            "sudo cp arda_os/kernel/valinor/releases/systemd/*.service /etc/systemd/system/",
            "sudo systemctl daemon-reload",
            "sudo systemctl enable arda-valinor-postboot.service arda-bombadil-valinor.service",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": plan["ok"], "output": str(output), "blockers": blockers}, indent=2, sort_keys=True))
    return 0 if plan["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
