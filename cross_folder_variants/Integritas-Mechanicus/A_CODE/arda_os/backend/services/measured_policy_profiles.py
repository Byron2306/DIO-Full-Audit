"""Critical-host profile expansion for measured manifests and policy projection."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[3]
ADDENDUM_PATH = Path(__file__).with_name("arda_harmony_addendum.json")
DISCOVERY_ALLOWED_PREFIXES = (
    "/bin/",
    "/sbin/",
    "/usr/bin/",
    "/usr/sbin/",
    "/usr/lib/",
    "/usr/libexec/",
    "/lib/",
    "/lib64/",
    "/etc/",
    "/boot/",
    str(REPO_ROOT / "arda_os") + "/",
)
DISCOVERY_ALLOWED_SYSTEMD_BASENAMES = {
    "systemd",
    "systemd-fstab-generator",
    "systemd-journald",
    "systemd-logind",
    "systemd-modules-load",
    "systemd-networkd",
    "systemd-networkd-wait-online",
    "systemd-pcrextend",
    "systemd-random-seed",
    "systemd-remount-fs",
    "systemd-sysctl",
    "systemd-tpm2-setup",
    "systemd-udevd",
    "systemd-user-runtime-dir",
    "systemd-user-sessions",
}
DISCOVERY_EXCLUDED_BASENAMES = {
    "avahi-daemon",
    "containerd",
    "cups-browsed",
    "cupsd",
    "firefox-esr",
    "gnome-keyring-daemon",
    "ibus-daemon",
    "lightdm",
    "libvirtd",
    "light-locker",
    "ModemManager",
    "netbird",
    "nginx",
    "nm-applet",
    "node",
    "ollama",
    "pavucontrol",
    "postgres",
    "pulseaudio",
    "redis-check-rdb",
    "ristretto",
    "speech-dispatcher",
    "ssh-agent",
    "thunar",
    "tor",
    "virtlockd",
    "virtlogd",
    "watch",
    "xfce4-terminal.wrapper",
    "xfce4-notes",
    "xfce4-panel",
    "xfce4-power-manager",
    "xfce4-session",
    "xfce4-terminal",
    "xfce4-terminal.wrapper",
    "xfdesktop",
    "xfsettingsd",
    "xfwm4",
    "Xorg",
}
DISCOVERY_EXCLUDED_SYSTEMD_BASENAMES = {
    "systemd-fsck",
    "systemd-growfs",
    "systemd-hostnamed",
    "systemd-localed",
    "systemd-machined",
    "systemd-makefs",
    "systemd-reply-password",
    "systemd-shutdown",
    "systemd-sleep",
    "systemd-sulogin-shell",
    "systemd-timedated",
}
DISCOVERY_EXCLUDED_PATH_SUBSTRINGS = (
    "/home/byron/.local/",
    "xfce4-terminal",
    "/usr/lib/firefox-esr/",
    "/usr/lib/postgresql/",
    "/usr/lib/speech-dispatcher-modules/",
    "/usr/lib/x86_64-linux-gnu/xfce4/",
    "/usr/libexec/nm-dispatcher",
    "/usr/libexec/bluetooth/",
    "/usr/libexec/colord",
    "/usr/libexec/dconf-service",
    "/usr/libexec/udisks2/",
    "/usr/libexec/upowerd",
    "/usr/libexec/at-spi",
    "/usr/libexec/geoclue-2.0/",
    "/usr/libexec/gvfs",
    "/usr/libexec/ibus",
    "/usr/libexec/polkit-mate-authentication-agent-1",
    "/usr/libexec/rtkit-daemon",
    "/usr/libexec/xdg-",
    "/usr/local/bin/ollama-runner",
    "/usr/local/bin/ollama",
)

CRITICAL_SHARED_OBJECTS = (
    "/lib/x86_64-linux-gnu/libc.so.6",
    "/lib/x86_64-linux-gnu/libm.so.6",
    "/lib/x86_64-linux-gnu/libcap.so.2",
    "/lib/x86_64-linux-gnu/libselinux.so.1",
    "/lib/x86_64-linux-gnu/libpcre2-8.so.0",
    "/lib/x86_64-linux-gnu/libsystemd.so.0",
    "/lib/x86_64-linux-gnu/libzstd.so.1",
    "/lib/x86_64-linux-gnu/liblzma.so.5",
    "/lib64/ld-linux-x86-64.so.2",
    "/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
)

CRITICAL_REPO_FILES = (
    "arda_os/bin/arda",
    "arda_os/bin/arda_os_grade_gate.py",
    "arda_os/bin/arda_phase4_rollout.py",
    "arda_os/bin/arda_rescue_mode.py",
    "arda_os/bin/arda_compact_measured_ledger.py",
    "arda_os/bin/arda_lockdown_confidentiality_probe.py",
    "arda_os/bin/arda_lockdown_confidentiality_lane.py",
    "arda_os/arda_policy.json",
    "arda_os/arda_policy_bundle.json",
    "arda_os/bin/arda_phase4_remote_verify.py",
    "arda_os/bin/arda_phase4_live_attestation.py",
    "arda_os/bin/arda_project_policy.py",
    "arda_os/bin/arda_build_measured_manifest.py",
    "arda_os/bin/arda_phase4_verifier_service.py",
    "arda_os/deploy/systemd/arda-phase4-remote-verifier.service",
    "arda_os/kernel/valinor/releases/systemd/arda-phase4-remote-verifier.service",
    "arda_os/kernel/valinor/releases/systemd/arda-valinor-postboot.service",
    "arda_os/kernel/valinor/PRODUCTION_OPERATIONS.md",
    "arda_os/backend/services/phase4_rollout_control.py",
    "arda_os/backend/services/arda_phase4_verifier_service.py",
    "arda_os/backend/services/measured_identity.py",
    "arda_os/backend/services/measured_policy_profiles.py",
    "arda_os/backend/services/phase4_attestation_gate.py",
    "arda_os/backend/services/os_enforcement_service.py",
    "arda_os/backend/services/attestation_service.py",
    "arda_os/backend/services/boot_measurement.py",
    "arda_os/backend/services/arda_discover.py",
    "arda_os/backend/services/arda_harmony_addendum.json",
    "arda_os/backend/services/harmonic_engine.py",
    "arda_os/backend/services/voice_registry.py",
    "arda_os/backend/services/polyphonic_governance.py",
    "arda_os/backend/services/schemas/polyphonic_models.py",
    "arda_os/backend/services/earendil_flow.py",
    "arda_os/backend/services/gates_of_night.py",
    "arda_os/backend/services/arda_fabric_middleware.py",
)

CRITICAL_SYSTEM_FILES = (
    "/etc/default/arda-valinor",
    "/etc/arda/arda-verifier.env",
    "/etc/arda/verifier/verifier-key.pub.pem",
    "/etc/arda/policy/active_bundle.json",
    "/etc/arda/policy/active_projection_plan.json",
    "/etc/arda/policy/rescue_projection_plan.json",
    "/boot/vmlinuz-6.12.96-valinor",
    "/boot/initrd.img-6.12.96-valinor",
    "/boot/grub/grub.cfg",
    "/boot/efi/EFI/debian/shimx64.efi",
    "/boot/efi/EFI/debian/grubx64.efi",
    "/usr/lib/systemd/systemd",
    "/usr/lib/systemd/systemd-logind",
    "/usr/lib/systemd/systemd-udevd",
    "/usr/lib/systemd/systemd-networkd-wait-online",
    "/usr/lib/systemd/systemd-journald",
    "/usr/lib/systemd/systemd-modules-load",
)

CRITICAL_INTERPRETERS_AND_TOOLS = (
    "/usr/bin/python3",
    "/usr/bin/sudo",
    "/usr/bin/bash",
    "/usr/bin/dash",
    "/usr/bin/sh",
    "/usr/bin/env",
    "/usr/bin/systemctl",
    "/usr/bin/ls",
    "/usr/bin/cat",
    "/usr/bin/findmnt",
    "/usr/bin/mokutil",
    "/usr/bin/bpftool",
    "/usr/sbin/bpftool",
    "/usr/bin/openssl",
    "/usr/bin/curl",
    "/usr/bin/sha256sum",
    "/usr/bin/systemd-detect-virt",
    "/usr/bin/efibootmgr",
    "/usr/bin/sbverify",
    "/usr/bin/sbsign",
    "/usr/bin/dbus-send",
    "/usr/bin/dbus-monitor",
)

CRITICAL_TPM_TOOLS = (
    "/usr/bin/tpm2",
    "/usr/bin/tpm2_getcap",
    "/usr/bin/tpm2_pcrread",
    "/usr/bin/tpm2_createek",
    "/usr/bin/tpm2_createak",
    "/usr/bin/tpm2_create",
    "/usr/bin/tpm2_nvreadpublic",
    "/usr/bin/tpm2_load",
    "/usr/bin/tpm2_readpublic",
    "/usr/bin/tpm2_quote",
    "/usr/bin/tpm2_pcrextend",
    "/usr/bin/tpm2_certifycreation",
    "/usr/bin/tpm2_checkquote",
    "/usr/bin/tpm2_sign",
    "/usr/bin/tpm2_verifysignature",
    "/usr/bin/tpm2_loadexternal",
)


def _load_addendum_binaries() -> list[str]:
    try:
        payload = json.loads(ADDENDUM_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    binaries: list[str] = []
    for category in (payload.get("categories") or {}).values():
        for path in category.get("binaries") or ():
            if isinstance(path, str):
                normalized = os.path.abspath(os.path.expanduser(path))
                if os.path.basename(normalized) in DISCOVERY_EXCLUDED_BASENAMES:
                    continue
                if os.path.basename(normalized) in DISCOVERY_EXCLUDED_SYSTEMD_BASENAMES:
                    continue
                if any(fragment in normalized for fragment in DISCOVERY_EXCLUDED_PATH_SUBSTRINGS):
                    continue
                binaries.append(normalized)
    return binaries


def _dedupe_existing(paths: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    resolved: list[str] = []
    for raw in paths:
        path = os.path.abspath(os.path.expanduser(str(raw)))
        if not os.path.exists(path):
            continue
        canonical = os.path.realpath(path)
        basename = os.path.basename(canonical)
        if basename in DISCOVERY_EXCLUDED_BASENAMES:
            continue
        if basename in DISCOVERY_EXCLUDED_SYSTEMD_BASENAMES:
            continue
        if any(fragment in canonical for fragment in DISCOVERY_EXCLUDED_PATH_SUBSTRINGS):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        resolved.append(canonical)
    return sorted(resolved)


def merge_discovered_manifest_paths(
    manifest: dict | None,
    *,
    include_tiers: Iterable[str] = ("critical", "operational", "ai_stack"),
) -> List[str]:
    payload = manifest or {}
    allowed = {str(tier).strip().lower() for tier in include_tiers}
    resolved: list[str] = []
    for entry in payload.get("entries") or []:
        if str(entry.get("tier") or "").strip().lower() not in allowed:
            continue
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        normalized = str(path)
        if not normalized.startswith(DISCOVERY_ALLOWED_PREFIXES):
            continue
        if normalized.startswith("/usr/lib/systemd/"):
            if os.path.basename(normalized) not in DISCOVERY_ALLOWED_SYSTEMD_BASENAMES:
                continue
        if os.path.basename(normalized) in DISCOVERY_EXCLUDED_SYSTEMD_BASENAMES:
            continue
        if os.path.basename(normalized) in DISCOVERY_EXCLUDED_BASENAMES:
            continue
        if any(fragment in normalized for fragment in DISCOVERY_EXCLUDED_PATH_SUBSTRINGS):
            continue
        resolved.append(normalized)
    return _dedupe_existing(resolved)


def expand_projection_profile(
    profile: str,
    *,
    repo_root: str | None = None,
    base_paths: Iterable[str] = (),
) -> List[str]:
    if profile != "critical-host":
        return _dedupe_existing(base_paths)
    root = Path(repo_root or REPO_ROOT)
    candidates = list(base_paths)
    candidates.extend(_load_addendum_binaries())
    candidates.extend(str(root / relpath) for relpath in CRITICAL_REPO_FILES)
    candidates.extend(CRITICAL_INTERPRETERS_AND_TOOLS)
    candidates.extend(CRITICAL_TPM_TOOLS)
    candidates.extend(
        [
            "/lib/systemd/systemd",
        ]
    )
    return _dedupe_existing(candidates)


def expand_measurement_profile(
    profile: str,
    *,
    repo_root: str | None = None,
    base_paths: Iterable[str] = (),
) -> List[str]:
    if profile != "critical-host":
        return _dedupe_existing(base_paths)
    root = Path(repo_root or REPO_ROOT)
    candidates = list(expand_projection_profile(profile, repo_root=str(root), base_paths=base_paths))
    candidates.extend(str(root / relpath) for relpath in CRITICAL_REPO_FILES)
    candidates.extend(CRITICAL_SYSTEM_FILES)
    candidates.extend(CRITICAL_SHARED_OBJECTS)
    candidates.extend(
        [
            "/lib/x86_64-linux-gnu/libpam.so.0",
            "/lib/x86_64-linux-gnu/libaudit.so.1",
            "/lib/x86_64-linux-gnu/libcap-ng.so.0",
            "/lib/x86_64-linux-gnu/libgcrypt.so.20",
            "/lib/x86_64-linux-gnu/libjson-c.so.5",
            "/lib/x86_64-linux-gnu/libapparmor.so.1",
            "/lib/x86_64-linux-gnu/libmount.so.1",
            "/lib/x86_64-linux-gnu/libblkid.so.1",
            "/lib/x86_64-linux-gnu/libcrypto.so.3",
            "/lib/x86_64-linux-gnu/libssl.so.3",
            "/lib/x86_64-linux-gnu/libcurl.so.4",
            "/lib/x86_64-linux-gnu/libdbus-1.so.3",
            "/lib/x86_64-linux-gnu/libpam_misc.so.0",
            "/lib/x86_64-linux-gnu/libpamc.so.0",
        ]
    )
    return _dedupe_existing(candidates)
