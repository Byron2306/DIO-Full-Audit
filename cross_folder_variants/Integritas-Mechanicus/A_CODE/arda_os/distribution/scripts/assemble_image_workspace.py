#!/usr/bin/env python3
"""Assemble a concrete ARDA image build workspace from plans and release metadata."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
REPO_ROOT = DISTRIBUTION_DIR.parents[1]

DEFAULT_ROOTFS_PLAN = DISTRIBUTION_DIR / "build" / "rootfs-plan.json"
DEFAULT_OVERLAY_ROOT = DISTRIBUTION_DIR / "build" / "overlay" / "rootfs"
DEFAULT_MANIFEST = DISTRIBUTION_DIR / "releases" / "distribution-manifest.json"
DEFAULT_WORKSPACE = DISTRIBUTION_DIR / "build" / "workspace"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_file(src: Path, dest: Path, records: list[dict]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    records.append(
        {
            "source": str(src),
            "destination": str(dest),
            "size": src.stat().st_size,
        }
    )


def _copy_tree(src: Path, dest: Path, records: list[dict]) -> None:
    for path in sorted(src.rglob("*")):
        relative = path.relative_to(src)
        target = dest / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        _copy_file(path, target, records)


def assemble_workspace(
    *,
    rootfs_plan_path: Path,
    overlay_root: Path,
    distribution_manifest_path: Path,
    workspace_root: Path,
) -> dict:
    rootfs_plan_path = rootfs_plan_path.resolve()
    overlay_root = overlay_root.resolve()
    distribution_manifest_path = distribution_manifest_path.resolve()
    workspace_root = workspace_root.resolve()
    rootfs_plan = _read_json(rootfs_plan_path)
    distribution_manifest = _read_json(distribution_manifest_path)

    if workspace_root.exists():
        try:
            shutil.rmtree(workspace_root)
        except PermissionError as exc:
            raise PermissionError(
                f"workspace_root_not_removable: {workspace_root} "
                f"(try: sudo rm -rf {workspace_root})"
            ) from exc
    workspace_root.mkdir(parents=True, exist_ok=True)

    rootfs_dir = workspace_root / "rootfs"
    artifacts_dir = workspace_root / "artifacts"
    plans_dir = workspace_root / "plans"
    overlay_dest = workspace_root / "overlay-rootfs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    plans_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[dict] = []
    _copy_tree(overlay_root, overlay_dest, copied_files)

    kernel_artifacts = []
    skipped_kernel_artifacts = []
    valinor_release = distribution_manifest.get("valinor_release") or {}
    for artifact in valinor_release.get("artifacts") or []:
        name = str(artifact.get("name") or "")
        src = Path(str(artifact.get("path") or ""))
        if not src.is_file():
            continue
        if name.endswith(".deb") and ("linux-image" in name or "linux-headers" in name or "linux-libc-dev" in name):
            if "dbg" in name:
                skipped_kernel_artifacts.append(
                    {
                        "name": name,
                        "source": str(src),
                        "reason": "debug_artifact_excluded_by_default",
                    }
                )
                continue
            dest = artifacts_dir / name
            _copy_file(src, dest, copied_files)
            kernel_artifacts.append(
                {
                    "name": name,
                    "source": str(src),
                    "workspace_path": str(dest),
                }
            )

    apt_packages = list((rootfs_plan.get("package_installation") or {}).get("required_packages") or [])
    debstrap = list((rootfs_plan.get("debootstrap") or {}).get("command") or [])
    if debstrap:
        debstrap = [rootfs_dir.as_posix() if token == "<rootfs-dir>" else token for token in debstrap]

    kernel_debs = [item["workspace_path"] for item in kernel_artifacts if "dbg" not in item["name"]]
    install_kernel_cmd = []
    if kernel_debs:
        install_kernel_cmd = [
            "chroot",
            rootfs_dir.as_posix(),
            "env",
            "DEBIAN_FRONTEND=noninteractive",
            "dpkg",
            "-i",
        ] + [f"/workspace-artifacts/{Path(item).name}" for item in kernel_debs]
    install_packages_cmd = [
        "chroot",
        rootfs_dir.as_posix(),
        "bash",
        "-lc",
        (
            "set -euo pipefail; "
            "export DEBIAN_FRONTEND=noninteractive; "
            "export NEEDRESTART_MODE=a; "
            "printf '#!/bin/sh\\nexit 101\\n' > /usr/sbin/policy-rc.d; "
            "chmod 0755 /usr/sbin/policy-rc.d; "
            "mkdir -p /etc/initramfs-tools; "
            "printf 'update_initramfs=no\\n' > /etc/initramfs-tools/update-initramfs.conf; "
            "diversion=$(dpkg-divert --list /usr/sbin/update-initramfs 2>/dev/null || true); "
            "if [ -z \"$diversion\" ]; then "
            "dpkg-divert --local --rename --add /usr/sbin/update-initramfs >/dev/null; "
            "fi; "
            "printf '#!/bin/sh\\necho \"ARDA_IMAGE_BUILD: deferred update-initramfs $@\" >&2\\nexit 0\\n' "
            "> /usr/sbin/update-initramfs; "
            "chmod 0755 /usr/sbin/update-initramfs; "
            "apt-get update; "
            "apt-get install -y --no-install-recommends "
            "-o Dpkg::Options::=--force-confdef "
            "-o Dpkg::Options::=--force-confold "
            + " ".join(apt_packages)
        ),
    ]
    generate_initramfs_cmd = [
        "chroot",
        rootfs_dir.as_posix(),
        "bash",
        "-lc",
        (
            "set -euo pipefail; "
            "kernel_release=$(basename \"$(ls -d /lib/modules/*valinor* | sort | tail -n1)\"); "
            "mkdir -p /etc/initramfs-tools; "
            "printf 'update_initramfs=yes\\n' > /etc/initramfs-tools/update-initramfs.conf; "
            "diversion=$(dpkg-divert --list /usr/sbin/update-initramfs 2>/dev/null || true); "
            "if [ -n \"$diversion\" ]; then "
            "rm -f /usr/sbin/update-initramfs; "
            "dpkg-divert --rename --remove /usr/sbin/update-initramfs >/dev/null; "
            "fi; "
            "if ! command -v update-initramfs >/dev/null 2>&1; then "
            "DEBIAN_FRONTEND=noninteractive apt-get install -y --reinstall initramfs-tools; "
            "fi; "
            "if command -v plymouth-set-default-theme >/dev/null 2>&1; then "
            "plymouth-set-default-theme details || true; "
            "fi; "
            "update-initramfs -c -k \"$kernel_release\""
        ),
    ]

    build_commands = {
        "debootstrap": debstrap,
        "install_packages": install_packages_cmd,
        "apply_overlay": [
            "python3",
            str(REPO_ROOT / "arda_os" / "distribution" / "scripts" / "apply_overlay.py"),
            "--overlay-root",
            overlay_dest.as_posix(),
            "--rootfs-dir",
            rootfs_dir.as_posix(),
        ],
        "install_kernel": install_kernel_cmd,
        "generate_initramfs": generate_initramfs_cmd,
        "enable_units": [
            "chroot",
            rootfs_dir.as_posix(),
            "bash",
            "-lc",
            (
                "set -euo pipefail; "
                "systemctl enable arda-valinor-boot-audit.service || true; "
                "systemctl enable arda-phase4-remote-verifier.service || true; "
                "systemctl enable arda-valinor-postboot.service || true; "
                "systemctl enable serial-getty@ttyS0.service; "
                "if ! id arda >/dev/null 2>&1; then useradd --create-home --shell /bin/bash arda; fi; "
                "printf 'root:live\\narda:live\\n' | chpasswd; "
                "passwd -u root || true; "
                "passwd -u arda || true; "
                "usermod -aG sudo arda || true; "
                "chown -R arda:arda /home/arda || true; "
                "chmod 0755 /usr/local/bin/arda-live-desktop-awakening || true; "
                "chmod 0755 /home/arda/.xsession || true; "
                "chown root:root /usr/local/bin/arda-live-desktop-awakening || true; "
                "mkdir -p /etc/systemd/system/debug-shell.service.d; "
                "printf '[Service]\\nExecStart=\\nExecStart=/bin/bash -l\\n' "
                "> /etc/systemd/system/debug-shell.service.d/override.conf; "
                "systemctl enable debug-shell.service || true; "
                "systemctl set-default graphical.target || true; "
                "systemctl enable lightdm.service || true; "
                "if command -v firefox-esr >/dev/null 2>&1; then "
                "update-alternatives --set x-www-browser /usr/bin/firefox-esr || true; "
                "update-alternatives --set www-browser /usr/bin/firefox-esr || true; "
                "fi; "
                "rm -f /etc/systemd/system/default.target; "
                "ln -s /usr/lib/systemd/system/graphical.target /etc/systemd/system/default.target"
            ),
        ],
    }

    summary = {
        "schema_version": "arda.distribution.workspace.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": distribution_manifest.get("distribution_id"),
        "workspace_root": str(workspace_root),
        "rootfs_dir": str(rootfs_dir),
        "overlay_source": str(overlay_root),
        "overlay_workspace_copy": str(overlay_dest),
        "plans": {
            "rootfs_plan": str(rootfs_plan_path),
            "distribution_manifest": str(distribution_manifest_path),
        },
        "kernel_artifacts": kernel_artifacts,
        "skipped_kernel_artifacts": skipped_kernel_artifacts,
        "build_commands": build_commands,
        "host_prerequisites": {
            "image_workspace": [
                "debootstrap",
                "chroot",
                "apt-get",
                "dpkg",
                "systemctl",
            ],
            "artifact_emission": [
                "tar",
                "truncate",
                "qemu-img",
                "xorriso",
            ],
        },
        "copied_file_count": len(copied_files),
    }

    (plans_dir / "workspace-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (plans_dir / "distribution-manifest.json").write_text(
        json.dumps(distribution_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (plans_dir / "rootfs-plan.json").write_text(
        json.dumps(rootfs_plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "ok": True,
        "workspace_root": str(workspace_root),
        "summary": str(plans_dir / "workspace-summary.json"),
        "kernel_artifact_count": len(kernel_artifacts),
        "copied_file_count": len(copied_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble an ARDA image build workspace")
    parser.add_argument("--rootfs-plan", default=str(DEFAULT_ROOTFS_PLAN))
    parser.add_argument("--overlay-root", default=str(DEFAULT_OVERLAY_ROOT))
    parser.add_argument("--distribution-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE))
    args = parser.parse_args()

    payload = assemble_workspace(
        rootfs_plan_path=Path(args.rootfs_plan),
        overlay_root=Path(args.overlay_root),
        distribution_manifest_path=Path(args.distribution_manifest),
        workspace_root=Path(args.workspace_root),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
