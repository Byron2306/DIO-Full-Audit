#!/usr/bin/env python3
"""Report whether the live host is safe to treat as a Valinor OS base."""

import argparse
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RELEASE = "6.12.96-valinor"
BROKEN_RELEASES = ("6.12.96-valinor-valinor",)


def _run(command: list[str]) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "command not found", "text": "command not found"}
    text = (result.stdout + result.stderr).strip()
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "text": text,
    }


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _exists(path: str) -> bool:
    return Path(path).exists()


def _package_installed(package: str) -> bool:
    result = _run(["dpkg-query", "-W", "-f=${Status}", package])
    return result["returncode"] == 0 and result["stdout"] == "install ok installed"


def _disk(path: str) -> dict:
    usage = shutil.disk_usage(path)
    return {
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_gib": round(usage.free / (1024**3), 2),
        "used_percent": round((usage.used / usage.total) * 100, 2),
    }


def _lsmod_names() -> set[str]:
    text = _read_text(Path("/proc/modules")) or ""
    return {line.split()[0] for line in text.splitlines() if line.strip()}


def _theme_path() -> str | None:
    defaults = Path("/etc/default/grub")
    text = _read_text(defaults)
    if not text:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("GRUB_THEME="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _grub_theme_status() -> dict:
    theme = _theme_path()
    status = {"configured": theme, "present": False, "assets": {}, "warnings": []}
    if not theme:
        return status

    theme_path = Path(theme)
    status["present"] = theme_path.is_file()
    theme_dir = theme_path.parent
    for asset in ("background.png", "seal.png", "crown-bar.png"):
        status["assets"][asset] = (theme_dir / asset).is_file()

    text = _read_text(theme_path)
    if text:
        suspicious = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "pixmap" in line.lower() and "%" in line and "*" not in line:
                suspicious.append({"line": line_no, "text": line.strip()})
        if suspicious:
            status["warnings"].append(
                {
                    "kind": "possible_box_pixmap_pattern_error",
                    "matches": suspicious[:10],
                }
            )
    return status


def _post_boot_gate() -> dict:
    script = REPO_ROOT / "arda_os/kernel/valinor/scripts/post_boot_valinor_gate.py"
    result = _run([str(script), "--json"])
    payload = None
    if result["stdout"]:
        try:
            payload = json.loads(result["stdout"])
        except json.JSONDecodeError:
            payload = None
    return {"ok": result["returncode"] == 0, "result": payload, "raw": result["text"]}


def _hardware_rooted_os_grade() -> dict:
    result = _run(
        [
            "sudo",
            "env",
            "ARDA_SOVEREIGN_MODE=1",
            str(REPO_ROOT / "arda_os/bin/arda"),
            "os-grade",
            "--json",
        ]
    )
    payload = None
    if result["stdout"]:
        try:
            payload = json.loads(result["stdout"])
        except json.JSONDecodeError:
            payload = None
    return {
        "ok": result["returncode"] == 0,
        "result": payload,
        "raw": result["text"],
    }


def _initramfs_status(kernel: str) -> dict:
    path = Path(f"/boot/initrd.img-{kernel}")
    return {"path": str(path), "present": path.is_file(), "size_bytes": path.stat().st_size if path.is_file() else 0}


def _boot_image_status(kernel: str) -> dict:
    path = Path(f"/boot/vmlinuz-{kernel}")
    return {"path": str(path), "present": path.is_file(), "size_bytes": path.stat().st_size if path.is_file() else 0}


def build_report(expected_kernel: str) -> dict:
    kernel = platform.release()
    modules = _lsmod_names()
    active_lsms = _read_text(Path("/sys/kernel/security/lsm")) or ""
    installed_broken = [release for release in BROKEN_RELEASES if _exists(f"/boot/vmlinuz-{release}")]
    image_pkg = f"linux-image-{expected_kernel}"
    headers_pkg = f"linux-headers-{expected_kernel}"

    dri_nodes_visible = Path("/dev/dri/card0").exists() and Path("/dev/dri/renderD128").exists()
    graphics_stack_live = dri_nodes_visible or ("i915" in modules and "drm" in modules)

    checks = {
        "expected_kernel_live": kernel == expected_kernel,
        "valinor_kernel_live": "valinor" in kernel,
        "boot_image_present": _boot_image_status(expected_kernel)["present"],
        "initramfs_present": _initramfs_status(expected_kernel)["present"],
        "graphics_stack_live": graphics_stack_live,
        "i915_loaded": "i915" in modules,
        "bpf_lsm_active": "bpf" in active_lsms.split(","),
        "lockdown_lsm_active": "lockdown" in active_lsms.split(","),
        "image_package_installed": _package_installed(image_pkg),
        "headers_package_installed": _package_installed(headers_pkg),
        "root_disk_has_20g_free": _disk("/")["free_bytes"] >= 20 * 1024**3,
        "post_boot_gate": _post_boot_gate()["ok"],
        "hardware_rooted_os_grade": _hardware_rooted_os_grade()["ok"],
    }
    warnings = []
    theme = _grub_theme_status()
    if theme["warnings"]:
        warnings.append("grub_theme_possible_pixmap_error")
    if installed_broken:
        warnings.append("broken_valinor_kernel_still_installed")

    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "schema_version": "arda.valinor_health.v1",
        "ok": not blockers,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "uid": os.getuid(),
        "expected_kernel": expected_kernel,
        "kernel": kernel,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "active_lsms": active_lsms,
        "modules": {
            "i915": "i915" in modules,
            "drm": "drm" in modules,
            "zfs": "zfs" in modules,
            "spl": "spl" in modules,
        },
        "graphics": {
            "dev_dri_visible_to_report": dri_nodes_visible,
            "i915_loaded": "i915" in modules,
            "drm_loaded": "drm" in modules,
        },
        "boot": {
            "image": _boot_image_status(expected_kernel),
            "initramfs": _initramfs_status(expected_kernel),
            "broken_valinor_releases": installed_broken,
        },
        "packages": {
            "image": {"name": image_pkg, "installed": _package_installed(image_pkg)},
            "headers": {"name": headers_pkg, "installed": _package_installed(headers_pkg)},
        },
        "storage": {"root": _disk("/")},
        "grub_theme": theme,
        "post_boot_gate": _post_boot_gate(),
        "os_grade": _hardware_rooted_os_grade(),
        "next_actions": _next_actions(blockers, warnings, installed_broken),
    }


def _next_actions(blockers: list[str], warnings: list[str], installed_broken: list[str]) -> list[str]:
    if blockers:
        return ["Do not remove fallback kernels; resolve blockers first."]
    actions = [
        "Capture and archive the hardware-rooted os-grade JSON as release evidence.",
        "Keep one known-good Debian fallback kernel until a second clean Valinor reboot passes.",
    ]
    if installed_broken:
        actions.append("After one more clean reboot, remove linux-image/headers for 6.12.96-valinor-valinor.")
    if "grub_theme_possible_pixmap_error" in warnings:
        actions.append("Fix or temporarily disable the ARDA GRUB theme before Secure Boot work.")
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Valinor Phase 1 health report")
    parser.add_argument("--expected-kernel", default=DEFAULT_RELEASE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args.expected_kernel)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("VALINOR HEALTH REPORT")
        print(f"ok: {report['ok']}")
        print(f"kernel: {report['kernel']}")
        print("blockers:")
        for blocker in report["blockers"] or ["none"]:
            print(f"- {blocker}")
        print("warnings:")
        for warning in report["warnings"] or ["none"]:
            print(f"- {warning}")
        print("next_actions:")
        for action in report["next_actions"]:
            print(f"- {action}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
