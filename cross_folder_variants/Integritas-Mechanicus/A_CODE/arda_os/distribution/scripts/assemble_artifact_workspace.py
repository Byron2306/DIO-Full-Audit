#!/usr/bin/env python3
"""Assemble an ARDA artifact-emission workspace from image plans and rootfs workspace state."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import textwrap
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
REPO_ROOT = DISTRIBUTION_DIR.parents[1]
DEFAULT_IMAGE_PLAN = DISTRIBUTION_DIR / "releases" / "image-artifact-plan.json"
DEFAULT_WORKSPACE_SUMMARY = DISTRIBUTION_DIR / "build" / "workspace" / "plans" / "workspace-summary.json"
DEFAULT_OUTPUT_ROOT = DISTRIBUTION_DIR / "build" / "artifact-workspace"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_tree(src: Path, dest: Path) -> int:
    count = 0
    for root, dirnames, filenames in os.walk(src, topdown=True, followlinks=False):
        root_path = Path(root)
        relative_root = root_path.relative_to(src)
        target_root = dest / relative_root
        target_root.mkdir(parents=True, exist_ok=True)
        source_root_stat = root_path.lstat()
        os.chown(target_root, source_root_stat.st_uid, source_root_stat.st_gid)
        shutil.copystat(root_path, target_root, follow_symlinks=False)

        next_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            source_dir = root_path / dirname
            target_dir = target_root / dirname
            if source_dir.is_symlink():
                if target_dir.exists() or target_dir.is_symlink():
                    if target_dir.is_dir() and not target_dir.is_symlink():
                        shutil.rmtree(target_dir)
                    else:
                        target_dir.unlink()
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                target_dir.symlink_to(source_dir.readlink())
                source_stat = source_dir.lstat()
                os.lchown(target_dir, source_stat.st_uid, source_stat.st_gid)
                count += 1
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            source_stat = source_dir.lstat()
            os.chown(target_dir, source_stat.st_uid, source_stat.st_gid)
            shutil.copystat(source_dir, target_dir, follow_symlinks=False)
            next_dirnames.append(dirname)
        dirnames[:] = next_dirnames

        for filename in sorted(filenames):
            source_path = root_path / filename
            target_path = target_root / filename
            if source_path.is_symlink():
                if target_path.exists() or target_path.is_symlink():
                    target_path.unlink()
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.symlink_to(source_path.readlink())
                source_stat = source_path.lstat()
                os.lchown(target_path, source_stat.st_uid, source_stat.st_gid)
                count += 1
                continue
            mode = source_path.lstat().st_mode
            if not stat.S_ISREG(mode):
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            source_stat = source_path.lstat()
            os.chown(target_path, source_stat.st_uid, source_stat.st_gid)
            shutil.copystat(source_path, target_path, follow_symlinks=False)
            count += 1
    return count


def _find_first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_efi_iso_command(*, output: str, esp_image: Path, boot_staging_dir: Path) -> list[str]:
    iso_esp_image = boot_staging_dir / esp_image.name
    return [
        "bash",
        "-lc",
        "set -euo pipefail\n"
        f"cp {esp_image.as_posix()!s} {iso_esp_image.as_posix()!s}\n"
        "trap 'rm -f "
        f"{iso_esp_image.as_posix()!s}"
        "' EXIT\n"
        "xorriso -as mkisofs "
        "-iso-level 3 "
        "-full-iso9660-filenames "
        "-volid ARDA_VALINOR "
        "-eltorito-alt-boot "
        f"-e {esp_image.name} "
        "-no-emul-boot "
        "-isohybrid-gpt-basdat "
        "-append_partition 2 0xef "
        f"{esp_image.as_posix()!s} "
        f"-o {output} "
        f"{boot_staging_dir.as_posix()!s}\n",
    ]


def _fat_format_bits(esp_size_mb: int) -> int:
    return 16 if esp_size_mb <= 32 else 32


def _sign_pe_image(*, source: Path, output: Path, key: Path, cert: Path) -> None:
    sbsign = shutil.which("sbsign")
    if not sbsign:
        raise FileNotFoundError("sbsign is required for ARDA_VM_SNAKEOIL_SECURE_BOOT=1")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sbsign,
            "--key",
            str(key),
            "--cert",
            str(cert),
            "--output",
            str(output),
            str(source),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "sbsign failed for "
            f"{source}: {completed.stdout.strip()} {completed.stderr.strip()}".strip()
        )


def _decrypt_private_key(*, source: Path, output: Path, passphrase: str) -> None:
    completed = subprocess.run(
        [
            "openssl",
            "pkey",
            "-in",
            str(source),
            "-passin",
            f"pass:{passphrase}",
            "-out",
            str(output),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "openssl failed to decrypt VM Secure Boot key: "
            f"{completed.stdout.strip()} {completed.stderr.strip()}".strip()
        )
    output.chmod(0o600)


def _apply_vm_snakeoil_secureboot_lane(
    *,
    boot_staging_dir: Path,
    esp_dir: Path,
    kernel_dest: Path,
    initrd_dest: Path,
    bootappend_live: str,
    staged_files: list[str],
) -> dict:
    """Create a QEMU-only Secure Boot path trusted by Debian OVMF snakeoil VARS."""

    snakeoil_key = Path("/usr/share/ovmf/PkKek-1-snakeoil.key")
    snakeoil_cert = Path("/usr/share/ovmf/PkKek-1-snakeoil.pem")
    direct_grub = Path("/usr/lib/grub/x86_64-efi/monolithic/grubx64.efi")
    if not snakeoil_key.is_file() or not snakeoil_cert.is_file() or not direct_grub.is_file():
        return {
            "enabled": False,
            "reason": "missing_ovmf_snakeoil_key_or_unsigned_grub",
        }

    signing_dir = boot_staging_dir / ".secureboot-signing"
    signing_dir.mkdir(parents=True, exist_ok=True)
    signing_key = signing_dir / "PkKek-1-snakeoil.unencrypted.key"
    _decrypt_private_key(source=snakeoil_key, output=signing_key, passphrase="snakeoil")

    signed_kernel = kernel_dest.with_suffix(kernel_dest.suffix + ".snakeoil")
    _sign_pe_image(source=kernel_dest, output=signed_kernel, key=signing_key, cert=snakeoil_cert)
    shutil.move(signed_kernel, kernel_dest)
    staged_files.append(str(kernel_dest))

    signed_grub = boot_staging_dir / "EFI" / "BOOT" / "BOOTX64.EFI"
    ukify = shutil.which("ukify")
    stub = _find_first_existing(
        [
            Path("/usr/lib/systemd/boot/efi/linuxx64.efi.stub"),
            Path("/usr/lib/systemd/boot/efi/linuxx64.efi.stub.signed"),
            Path("/usr/lib/systemd/boot/efi/linuxx64.efi.stub.unsigned"),
        ]
    )
    uki_mode = False
    if ukify and stub is not None:
        completed = subprocess.run(
            [
                ukify,
                "build",
                "--linux",
                str(kernel_dest),
                "--initrd",
                str(initrd_dest),
                "--cmdline",
                bootappend_live,
                "--stub",
                str(stub),
                "--secureboot-private-key",
                str(signing_key),
                "--secureboot-certificate",
                str(snakeoil_cert),
                "--output",
                str(signed_grub),
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "ukify failed for VM Secure Boot lane: "
                f"{completed.stdout.strip()} {completed.stderr.strip()}".strip()
            )
        uki_mode = True
    else:
        _sign_pe_image(source=direct_grub, output=signed_grub, key=signing_key, cert=snakeoil_cert)

    for dest in (
        boot_staging_dir / "EFI" / "BOOT" / "grubx64.efi",
        boot_staging_dir / "EFI" / "debian" / "grubx64.efi",
        boot_staging_dir / "EFI" / "debian" / "shimx64.efi",
        esp_dir / "EFI" / "BOOT" / "BOOTX64.EFI",
        esp_dir / "EFI" / "BOOT" / "grubx64.efi",
        esp_dir / "EFI" / "debian" / "grubx64.efi",
        esp_dir / "EFI" / "debian" / "shimx64.efi",
    ):
        shutil.copy2(signed_grub, dest)
        staged_files.append(str(dest))

    return {
        "enabled": True,
        "key": str(snakeoil_key),
        "cert": str(snakeoil_cert),
        "transient_unencrypted_key": str(signing_key),
        "loader": "uki_signed_by_ovmf_snakeoil" if uki_mode else "direct_grub_signed_by_ovmf_snakeoil",
        "uki": uki_mode,
    }


def _stage_boot_assets(
    *,
    source_rootfs_dir: Path,
    boot_staging_dir: Path,
    esp_dir: Path,
    bootappend_live: str,
) -> dict:
    host_boot = Path("/boot")
    kernel = _find_first_existing(
        [
            host_boot / "vmlinuz-6.12.96-valinor",
            source_rootfs_dir / "boot" / "vmlinuz-6.12.96-valinor",
        ]
    )
    initrd = _find_first_existing(
        [
            source_rootfs_dir / "boot" / "initrd.img-6.12.96-valinor",
            host_boot / "initrd.img-6.12.96-valinor",
        ]
    )
    shim = _find_first_existing(
        [
            Path("/usr/lib/shim/shimx64.efi.signed"),
            Path("/usr/lib/shim/shimx64.efi"),
        ]
    )
    mm = _find_first_existing(
        [
            Path("/usr/lib/shim/mmx64.efi.signed"),
            Path("/usr/lib/shim/mmx64.efi"),
        ]
    )
    grub = _find_first_existing(
        [
            Path("/usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed"),
            Path("/usr/lib/grub/x86_64-efi/monolithic/grubx64.efi"),
        ]
    )

    missing = []
    for label, path in (
        ("kernel", kernel),
        ("initrd", initrd),
        ("shimx64.efi", shim),
        ("mmx64.efi", mm),
        ("grubx64.efi", grub),
    ):
        if path is None:
            missing.append(label)

    staged_files: list[str] = []
    if missing:
        return {"ok": False, "missing": missing, "staged_files": staged_files}

    boot_dir = boot_staging_dir / "boot"
    live_dir = boot_staging_dir / "live"
    grub_dir = boot_dir / "grub"
    efi_boot_dir = boot_staging_dir / "EFI" / "BOOT"
    efi_debian_dir = boot_staging_dir / "EFI" / "debian"
    esp_boot_dir = esp_dir / "EFI" / "BOOT"
    esp_debian_dir = esp_dir / "EFI" / "debian"
    for directory in (
        boot_dir,
        live_dir,
        grub_dir,
        efi_boot_dir,
        efi_debian_dir,
        esp_boot_dir,
        esp_debian_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    kernel_name = kernel.name
    initrd_name = initrd.name
    copy_pairs = (
        (kernel, boot_dir / kernel_name),
        (initrd, boot_dir / initrd_name),
        (shim, efi_boot_dir / "BOOTX64.EFI"),
        (grub, efi_boot_dir / "grubx64.efi"),
        (mm, efi_boot_dir / "mmx64.efi"),
        (shim, efi_debian_dir / "shimx64.efi"),
        (grub, efi_debian_dir / "grubx64.efi"),
        (mm, efi_debian_dir / "mmx64.efi"),
        (shim, esp_boot_dir / "BOOTX64.EFI"),
        (grub, esp_boot_dir / "grubx64.efi"),
        (mm, esp_boot_dir / "mmx64.efi"),
        (shim, esp_debian_dir / "shimx64.efi"),
        (grub, esp_debian_dir / "grubx64.efi"),
        (mm, esp_debian_dir / "mmx64.efi"),
    )
    for src, dest in copy_pairs:
        shutil.copy2(src, dest)
        staged_files.append(str(dest))

    vm_snakeoil_secureboot = {"enabled": False}
    if os.environ.get("ARDA_VM_SNAKEOIL_SECURE_BOOT") == "1":
        vm_snakeoil_secureboot = _apply_vm_snakeoil_secureboot_lane(
            boot_staging_dir=boot_staging_dir,
            esp_dir=esp_dir,
            kernel_dest=boot_dir / kernel_name,
            initrd_dest=boot_dir / initrd_name,
            bootappend_live=bootappend_live,
            staged_files=staged_files,
        )

    grub_background = _find_first_existing(
        [
            source_rootfs_dir / "usr" / "share" / "arda" / "identity" / "arda-wallpaper.png",
            REPO_ROOT / "arda_os" / "deploy" / "boot" / "themes" / "arda-grub" / "background.png",
            REPO_ROOT / "arda_os" / "deploy" / "boot" / "assets" / "arda-wallpaper.png",
        ]
    )
    if grub_background is not None:
        for dest in (
            grub_dir / "arda-background.png",
            efi_boot_dir / "arda-background.png",
            efi_debian_dir / "arda-background.png",
            esp_boot_dir / "arda-background.png",
            esp_debian_dir / "arda-background.png",
        ):
            shutil.copy2(grub_background, dest)
            staged_files.append(str(dest))

    grub_visual_prelude = ""
    if grub_background is not None:
        grub_visual_prelude = textwrap.dedent(
            """
            insmod gfxterm
            insmod png
            terminal_output gfxterm
            if background_image /boot/grub/arda-background.png; then
              set color_normal=white/black
              set color_highlight=cyan/black
            fi

            """
        )

    grub_cfg = textwrap.dedent(
        f"""
        {grub_visual_prelude.rstrip()}
        set timeout=5
        set default=0

        menuentry 'ARDA Valinor Live' {{
          linux /boot/{kernel_name} {bootappend_live}
          initrd /boot/{initrd_name}
        }}
        """
    ).strip() + "\n"
    for cfg_path in (
        grub_dir / "grub.cfg",
        efi_boot_dir / "grub.cfg",
        efi_debian_dir / "grub.cfg",
        esp_boot_dir / "grub.cfg",
        esp_debian_dir / "grub.cfg",
    ):
        _write_text(cfg_path, grub_cfg)
        staged_files.append(str(cfg_path))

    readme = textwrap.dedent(
        """
        ARDA boot staging

        This directory contains the staged UEFI boot payload for artifact emission.
        It is sufficient for boot-media population and validation work, but the ISO
        emission lane still needs explicit El Torito/EFI boot-image wiring before it
        can be claimed as a confirmed bootable installer image.
        """
    ).strip() + "\n"
    _write_text(boot_staging_dir / "README.boot-staging.txt", readme)
    staged_files.append(str(boot_staging_dir / "README.boot-staging.txt"))

    return {
        "ok": True,
        "kernel": str(kernel),
        "initrd": str(initrd),
        "shim": str(shim),
        "mm": str(mm),
        "grub": str(grub),
        "vm_snakeoil_secureboot": vm_snakeoil_secureboot,
        "staged_files": staged_files,
        "live_dir": str(live_dir),
    }


def assemble_artifact_workspace(
    *,
    image_plan_path: Path,
    workspace_summary_path: Path,
    output_root: Path,
) -> dict:
    if os.geteuid() != 0:
        raise PermissionError(
            "artifact_workspace_requires_root: preserving Debian rootfs ownership "
            "requires running assemble_artifact_workspace.py with sudo"
        )

    image_plan = _read_json(image_plan_path)
    workspace_summary = _read_json(workspace_summary_path)

    source_workspace_root = Path(workspace_summary["workspace_root"])
    source_rootfs_dir = Path(workspace_summary["rootfs_dir"])
    source_overlay_dir = Path(workspace_summary["overlay_workspace_copy"])
    live_build_reference = image_plan.get("live_build_reference") or {}
    bootappend_live = (
        live_build_reference.get("bootappend_live")
        or "boot=live components live-media-path=/live"
    )

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    output_root = output_root.resolve()

    rootfs_snapshot = output_root / "rootfs-snapshot"
    overlay_snapshot = output_root / "overlay-snapshot"
    esp_dir = output_root / "esp"
    boot_staging_dir = output_root / "boot-staging"
    release_dir = output_root / "release"
    plans_dir = output_root / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    esp_dir.mkdir(parents=True, exist_ok=True)
    boot_staging_dir.mkdir(parents=True, exist_ok=True)
    release_dir.mkdir(parents=True, exist_ok=True)

    copied_rootfs_files = _copy_tree(source_rootfs_dir, rootfs_snapshot) if source_rootfs_dir.exists() else 0
    copied_overlay_files = _copy_tree(source_overlay_dir, overlay_snapshot) if source_overlay_dir.exists() else 0
    boot_assets = _stage_boot_assets(
        source_rootfs_dir=source_rootfs_dir,
        boot_staging_dir=boot_staging_dir,
        esp_dir=esp_dir,
        bootappend_live=bootappend_live,
    )

    rootfs_tarball = output_root / "rootfs.tar"
    esp_image = output_root / "esp.img"
    live_filesystem = boot_staging_dir / "live" / "filesystem.squashfs"

    artifact_outputs: dict[str, str] = {}
    for artifact in image_plan.get("artifact_formats") or []:
        artifact_outputs[artifact["id"]] = str(release_dir / artifact["filename"])

    esp_size_mb = int(image_plan["image_layout"]["esp_size_mb"])
    fat_bits = _fat_format_bits(esp_size_mb)
    vm_secureboot = boot_assets.get("vm_snakeoil_secureboot") or {}
    if vm_secureboot.get("uki") is True:
        esp_population_script = (
            f"/usr/bin/mmd -i {esp_image.as_posix()!s} ::/EFI ::/EFI/BOOT\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o "
            f"{boot_staging_dir.as_posix()!s}/EFI/BOOT/BOOTX64.EFI ::/EFI/BOOT/BOOTX64.EFI\n"
        )
    else:
        esp_population_script = (
            f"/usr/bin/mmd -i {esp_image.as_posix()!s} ::/EFI ::/EFI/BOOT ::/EFI/debian\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/BOOT/BOOTX64.EFI ::/EFI/BOOT/BOOTX64.EFI\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/BOOT/grubx64.efi ::/EFI/BOOT/grubx64.efi\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/BOOT/mmx64.efi ::/EFI/BOOT/mmx64.efi\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/debian/shimx64.efi ::/EFI/debian/shimx64.efi\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/debian/grubx64.efi ::/EFI/debian/grubx64.efi\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/debian/mmx64.efi ::/EFI/debian/mmx64.efi\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/BOOT/grub.cfg ::/EFI/BOOT/grub.cfg\n"
            f"/usr/bin/mcopy -i {esp_image.as_posix()!s} -o {boot_staging_dir.as_posix()!s}/EFI/debian/grub.cfg ::/EFI/debian/grub.cfg\n"
        )
    build_commands = {
        "pack_rootfs": [
            "tar",
            "-C",
            rootfs_snapshot.as_posix(),
            "-cf",
            rootfs_tarball.as_posix(),
            ".",
        ],
        "make_live_rootfs": [
            "/usr/bin/mksquashfs",
            rootfs_snapshot.as_posix(),
            live_filesystem.as_posix(),
            "-noappend",
            "-processors",
            "1",
            "-comp",
            "zstd",
            "-Xcompression-level",
            "10",
            "-e",
            "boot",
        ],
        "make_esp_image": [
            "bash",
            "-lc",
            "set -euo pipefail\n"
            f"truncate -s {esp_size_mb}M {esp_image.as_posix()!s}\n"
            f"/usr/sbin/mkfs.vfat -F {fat_bits} {esp_image.as_posix()!s}\n"
            f"{esp_population_script}",
        ],
        "emit_raw_disk": [
            "qemu-img",
            "create",
            "-f",
            "raw",
            artifact_outputs["raw_disk"],
            f"{image_plan['image_layout']['rootfs_min_size_gb']}G",
        ],
        "emit_live_iso": _make_efi_iso_command(
            output=artifact_outputs["live_iso"],
            esp_image=esp_image,
            boot_staging_dir=boot_staging_dir,
        ),
        "emit_installer_iso": _make_efi_iso_command(
            output=artifact_outputs["installer_iso"],
            esp_image=esp_image,
            boot_staging_dir=boot_staging_dir,
        ),
    }

    summary = {
        "schema_version": "arda.distribution.artifact_workspace.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": image_plan["distribution_id"],
        "source_workspace_root": str(source_workspace_root),
        "artifact_workspace_root": str(output_root),
        "rootfs_snapshot": str(rootfs_snapshot),
        "overlay_snapshot": str(overlay_snapshot),
        "esp_dir": str(esp_dir),
        "boot_staging_dir": str(boot_staging_dir),
        "release_dir": str(release_dir),
        "artifact_outputs": artifact_outputs,
        "live_filesystem": str(live_filesystem),
        "copied_rootfs_files": copied_rootfs_files,
        "copied_overlay_files": copied_overlay_files,
        "boot_assets": boot_assets,
        "bootappend_live": bootappend_live,
        "rootfs_ready": copied_rootfs_files > 0,
        "build_commands": build_commands,
        "host_tools": image_plan.get("host_tools") or [],
        "blockers": (
            ([] if copied_rootfs_files > 0 else ["rootfs_snapshot_empty"])
            + ([] if boot_assets.get("ok") else ["boot_assets_missing"])
        ),
    }
    (plans_dir / "artifact-workspace-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (plans_dir / "image-artifact-plan.json").write_text(
        json.dumps(image_plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (plans_dir / "workspace-summary.json").write_text(
        json.dumps(workspace_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "artifact_workspace_root": str(output_root),
        "summary": str(plans_dir / "artifact-workspace-summary.json"),
        "artifact_count": len(artifact_outputs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the ARDA artifact-emission workspace")
    parser.add_argument("--image-plan", default=str(DEFAULT_IMAGE_PLAN))
    parser.add_argument("--workspace-summary", default=str(DEFAULT_WORKSPACE_SUMMARY))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    payload = assemble_artifact_workspace(
        image_plan_path=Path(args.image_plan),
        workspace_summary_path=Path(args.workspace_summary),
        output_root=Path(args.output_root),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
