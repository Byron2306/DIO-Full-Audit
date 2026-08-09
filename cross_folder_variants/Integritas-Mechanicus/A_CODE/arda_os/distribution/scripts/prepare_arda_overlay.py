#!/usr/bin/env python3
"""Build a rootfs overlay for the ARDA distribution layer."""

from __future__ import annotations

import argparse
import json
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
REPO_ROOT = DISTRIBUTION_DIR.parents[1]
DEFAULT_PROFILE = DISTRIBUTION_DIR / "distribution_profile.json"


def _copy_file(src: Path, dest: Path, copied: list[dict]) -> None:
    if not src.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    copied.append(
        {
            "source": str(src),
            "destination": str(dest),
            "size": src.stat().st_size,
        }
    )


def _write_text(dest: Path, text: str, copied: list[dict], source_label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    copied.append(
        {
            "source": source_label,
            "destination": str(dest),
            "size": len(text.encode("utf-8")),
        }
    )


def _write_executable(dest: Path, text: str, copied: list[dict], source_label: str) -> None:
    _write_text(dest, text, copied, source_label)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _copy_tree(src: Path, dest: Path, copied: list[dict]) -> None:
    if not src.is_dir():
        return
    for path in sorted(src.rglob("*")):
        relative = path.relative_to(src)
        target = dest / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        _copy_file(path, target, copied)


def _live_postboot_unit() -> str:
    return """[Unit]
Description=ARDA Valinor post-boot kernel parity gate
Documentation=file:/opt/arda/arda_os/kernel/valinor/README.md
After=local-fs.target systemd-modules-load.service network-online.target tpm2-abrmd.service arda-phase4-remote-verifier.service plymouth-quit.service getty@tty1.service lightdm.service graphical.target
Wants=network-online.target tpm2-abrmd.service arda-phase4-remote-verifier.service graphical.target
ConditionPathExists=/opt/arda/arda_os/kernel/valinor/scripts/post_boot_valinor_gate.py

[Service]
Type=oneshot
WorkingDirectory=/opt/arda
Environment=ARDA_SOVEREIGN_MODE=1
Environment=PYTHONPATH=/opt/arda/arda_os
EnvironmentFile=-/etc/arda/attested-host.env
EnvironmentFile=-/etc/default/arda-valinor
Environment=ARDA_POSTBOOT_REQUIRE_VERIFIER=0
Environment=ARDA_POSTBOOT_ALLOW_LOCAL_FALLBACK=1
Environment=ARDA_POSTBOOT_PROMOTE_STRICT=0
Environment=ARDA_POSTBOOT_LIVE_MEDIA=1
ExecStart=/usr/bin/python3 /opt/arda/arda_os/kernel/valinor/scripts/post_boot_valinor_gate.py --require-arda-gate --json
RemainAfterExit=yes

[Install]
WantedBy=graphical.target
"""


def _live_boot_audit_unit() -> str:
    return """[Unit]
Description=ARDA Valinor early boot audit reset
Documentation=file:/opt/arda/arda_os/kernel/valinor/README.md
DefaultDependencies=no
After=local-fs.target systemd-modules-load.service
Before=sysinit.target systemd-user-sessions.service plymouth-quit.service plymouth-quit-wait.service getty-pre.target getty@tty1.service getty.target lightdm.service display-manager.service graphical.target multi-user.target
ConditionPathExists=/opt/arda/arda_os/kernel/valinor/scripts/force_boot_audit_mode.py

[Service]
Type=oneshot
WorkingDirectory=/opt/arda
Environment=ARDA_SOVEREIGN_MODE=1
Environment=ARDA_ENFORCEMENT_MODE=audit
Environment=PYTHONPATH=/opt/arda/arda_os
ExecStart=/usr/bin/python3 /opt/arda/arda_os/kernel/valinor/scripts/force_boot_audit_mode.py
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
"""


def _live_verifier_unit() -> str:
    return """[Unit]
Description=ARDA Phase 4 Remote Verifier
Documentation=file:/opt/arda/arda_os/kernel/valinor/PRODUCTION_OPERATIONS.md
After=network.target

[Service]
Type=simple
EnvironmentFile=-/etc/arda/arda-verifier.env
EnvironmentFile=-/etc/default/arda-valinor
WorkingDirectory=/opt/arda
ExecStart=/usr/bin/env PYTHONPATH=/opt/arda/arda_os /usr/bin/python3 /opt/arda/arda_os/bin/arda_phase4_verifier_service.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=arda-phase4-remote-verifier

[Install]
WantedBy=multi-user.target
"""


def _live_service_after_boot_audit_override() -> str:
    return """[Unit]
After=arda-valinor-boot-audit.service
"""


def _live_attested_host_env() -> str:
    return """# ARDA Valinor live media defaults.
# The live image uses its loopback verifier so first boot remains demonstrable
# without importing the operator host's private off-box verifier material.
ARDA_VERIFIER_URL=http://127.0.0.1:8094/verify/phase4
ARDA_VERIFIER_ID=arda-phase4-remote-verifier
ARDA_VERIFIER_KEY_ID=arda-phase4-verifier
ARDA_POSTBOOT_REQUIRE_VERIFIER=0
ARDA_POSTBOOT_ALLOW_LOCAL_FALLBACK=1
ARDA_POSTBOOT_PROMOTE_STRICT=0
ARDA_POSTBOOT_LIVE_MEDIA=1
"""


def _live_emergency_shell_override() -> str:
    return """[Service]
ExecStart=
ExecStart=-/bin/bash -l
"""


def _live_lightdm_conf() -> str:
    return """[Seat:*]
autologin-user=arda
autologin-user-timeout=0
autologin-session=arda-xfce
user-session=arda-xfce
greeter-session=lightdm-gtk-greeter
"""


def _live_xfce_desktop_xml() -> str:
    wallpaper = "/usr/share/backgrounds/xfce/arda-valinor.png"
    monitor_names = (
        "monitor0",
        "monitor1",
        "monitorVGA-1",
        "monitorVirtual-1",
        "monitorVirtual1",
        "monitorVirtual-0",
        "monitorQXL-1",
        "monitorqxl-1",
        "monitorHDMI-1",
        "monitorHDMI-A-1",
        "monitorDP-1",
        "monitoreDP-1",
        "monitorLVDS-1",
        "monitorDVI-1",
        "monitorDefault",
    )
    monitor_blocks = "\n".join(
        f"""      <property name="{monitor}" type="empty">
        <property name="workspace0" type="empty">
          <property name="color-style" type="int" value="0"/>
          <property name="image-style" type="int" value="5"/>
          <property name="last-image" type="string" value="{wallpaper}"/>
          <property name="last-single-image" type="string" value="{wallpaper}"/>
          <property name="image-path" type="string" value="{wallpaper}"/>
        </property>
      </property>"""
        for monitor in monitor_names
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>

<channel name="xfce4-desktop" version="1.0">
  <property name="backdrop" type="empty">
    <property name="single-workspace-mode" type="bool" value="true"/>
    <property name="backdrop-cycle-enable" type="bool" value="false"/>
    <property name="screen0" type="empty">
{monitor_blocks}
    </property>
  </property>
  <property name="desktop-icons" type="empty">
    <property name="style" type="int" value="0"/>
  </property>
</channel>
"""


def _live_xfce_session_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>

<channel name="xfce4-session" version="1.0">
  <property name="general" type="empty">
    <property name="FailsafeSessionName" type="string" value="Failsafe"/>
    <property name="LockCommand" type="string" value=""/>
  </property>
  <property name="sessions" type="empty">
    <property name="Failsafe" type="empty">
      <property name="IsFailsafe" type="bool" value="true"/>
      <property name="Count" type="int" value="4"/>
      <property name="Client0_Command" type="array">
        <value type="string" value="xfwm4"/>
      </property>
      <property name="Client0_Priority" type="int" value="15"/>
      <property name="Client0_PerScreen" type="bool" value="false"/>
      <property name="Client1_Command" type="array">
        <value type="string" value="xfsettingsd"/>
      </property>
      <property name="Client1_Priority" type="int" value="20"/>
      <property name="Client1_PerScreen" type="bool" value="false"/>
      <property name="Client2_Command" type="array">
        <value type="string" value="xfce4-panel"/>
      </property>
      <property name="Client2_Priority" type="int" value="25"/>
      <property name="Client2_PerScreen" type="bool" value="false"/>
      <property name="Client3_Command" type="array">
        <value type="string" value="Thunar"/>
        <value type="string" value="--daemon"/>
      </property>
      <property name="Client3_Priority" type="int" value="30"/>
      <property name="Client3_PerScreen" type="bool" value="false"/>
    </property>
    <property name="FailsafeWayland" type="empty">
      <property name="IsFailsafe" type="bool" value="true"/>
      <property name="Count" type="int" value="3"/>
      <property name="Client0_Command" type="array">
        <value type="string" value="xfsettingsd"/>
      </property>
      <property name="Client0_Priority" type="int" value="15"/>
      <property name="Client0_PerScreen" type="bool" value="false"/>
      <property name="Client1_Command" type="array">
        <value type="string" value="xfce4-panel"/>
      </property>
      <property name="Client1_Priority" type="int" value="15"/>
      <property name="Client1_PerScreen" type="bool" value="false"/>
      <property name="Client2_Command" type="array">
        <value type="string" value="Thunar"/>
        <value type="string" value="--daemon"/>
      </property>
      <property name="Client2_Priority" type="int" value="15"/>
      <property name="Client2_PerScreen" type="bool" value="false"/>
    </property>
  </property>
</channel>
"""


def _live_xfce_wallpaper_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
  <rect width="1920" height="1080" fill="#02050b"/>
  <image href="/usr/share/arda/identity/arda-wallpaper.png" x="0" y="0" width="1920" height="1080" preserveAspectRatio="xMidYMid slice"/>
</svg>
"""


def _live_xsettings_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>

<channel name="xsettings" version="1.0">
  <property name="Net" type="empty">
    <property name="ThemeName" type="string" value="Adwaita-dark"/>
    <property name="IconThemeName" type="string" value="arda-valinor"/>
    <property name="SoundThemeName" type="string" value="freedesktop"/>
    <property name="PreferDarkTheme" type="bool" value="true"/>
  </property>
  <property name="Gtk" type="empty">
    <property name="FontName" type="string" value="Sans 10"/>
    <property name="MonospaceFontName" type="string" value="Monospace 11"/>
  </property>
</channel>
"""


def _live_xfwm4_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>

<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="theme" type="string" value="Default"/>
    <property name="title_font" type="string" value="Sans Bold 10"/>
    <property name="button_layout" type="string" value="O|HMC"/>
    <property name="use_compositing" type="bool" value="false"/>
  </property>
</channel>
"""


def _live_terminalrc() -> str:
    return """[Configuration]
ColorForeground=#dce8ee
ColorBackground=#02050b
ColorCursor=#63e6ff
ColorSelection=#0d2235
ColorPalette=#02050b;#d84146;#2bd786;#f0a53b;#63e6ff;#b99455;#19bfaf;#dce8ee;#071426;#d84146;#2bd786;#f0a53b;#63e6ff;#b99455;#19bfaf;#e8f0f4
FontName=Monospace 11
MiscAlwaysShowTabs=FALSE
MiscBell=FALSE
MiscMenubarDefault=FALSE
MiscToolbarDefault=FALSE
MiscBordersDefault=FALSE
MiscDefaultGeometry=118x32
"""


def _live_icon_theme_index() -> str:
    return """[Icon Theme]
Name=ARDA Valinor
Comment=ARDA operator identity icons
Inherits=Adwaita,hicolor
Directories=apps/64,places/64,devices/64

[apps/64]
Size=64
Context=Applications
Type=Fixed

[places/64]
Size=64
Context=Places
Type=Fixed

[devices/64]
Size=64
Context=Devices
Type=Fixed
"""


def _live_gtk_greeter_conf() -> str:
    return """[greeter]
background=/usr/share/arda/identity/arda-wallpaper.png
theme-name=Adwaita-dark
icon-theme-name=Adwaita
font-name=Sans 10
indicators=~host;~spacer;~clock;~spacer;~session;~power
"""


def _live_plymouthd_conf() -> str:
    return """[Daemon]
Theme=details
ShowDelay=0
"""


def _live_arda_xfce_desktop() -> str:
    return """[Desktop Entry]
Version=1.0
Name=ARDA Valinor
Comment=ARDA Valinor live XFCE session
Exec=/usr/local/bin/arda-xfce-session
TryExec=/usr/local/bin/arda-xfce-session
Type=Application
DesktopNames=XFCE
"""


def _live_arda_xfce_session() -> str:
    return """#!/bin/sh
set -u

export XDG_CURRENT_DESKTOP=XFCE
export XDG_SESSION_DESKTOP=arda-xfce
export DESKTOP_SESSION=arda-xfce

LOG="/tmp/arda-xfce-session.log"
{
  printf 'ARDA_XFCE_SESSION: start=%s user=%s display=%s\\n' "$(date -Is 2>/dev/null || date)" "$(id -un 2>/dev/null || true)" "${DISPLAY:-}"
} >>"$LOG" 2>&1

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

start_audio_stack() {
  if pgrep -u "$(id -u)" -x pipewire >/dev/null 2>&1; then
    return 0
  fi
  command -v pipewire >/dev/null 2>&1 && (pipewire >>/tmp/arda-pipewire.log 2>&1 &) || true
  command -v wireplumber >/dev/null 2>&1 && (wireplumber >>/tmp/arda-wireplumber.log 2>&1 &) || true
  command -v pipewire-pulse >/dev/null 2>&1 && (pipewire-pulse >>/tmp/arda-pipewire-pulse.log 2>&1 &) || true
}

start_audio_stack

if [ -x /usr/local/bin/arda-live-debug-snapshot ]; then
  (
    sleep 3
    /usr/local/bin/arda-live-debug-snapshot >>/tmp/arda-live-debug-snapshot.launch.log 2>&1
  ) &
fi

if [ -x /usr/local/bin/arda-live-desktop-awakening ]; then
  (
    sleep 6
    /usr/local/bin/arda-live-desktop-awakening >>/tmp/arda-live-desktop-awakening.wrapper.log 2>&1
  ) &
fi

if [ -x /usr/local/bin/arda-live-wallpaper-guardian ]; then
  (
    sleep 10
    /usr/local/bin/arda-live-wallpaper-guardian >>/tmp/arda-live-wallpaper-guardian.wrapper.log 2>&1
  ) &
fi

exec startxfce4 >>"$LOG" 2>&1
"""


def _live_update_initramfs_conf_disabled() -> str:
    return """# ARDA live-image build guard.
# Package maintainer scripts must not regenerate initramfs opportunistically
# inside the chroot. The image builder flips this to yes for the single
# controlled Valinor initramfs generation step after Plymouth is selected.
update_initramfs=no
"""


def _live_xsession() -> str:
    return """#!/bin/sh
set -eu
exec startxfce4
"""


def _live_xsessionrc() -> str:
    return """#!/bin/sh
# Awakening is owned by /usr/local/bin/arda-xfce-session so it only runs once.
export ARDA_XSESSION_SEEN=1
"""


def _live_xsession_hook() -> str:
    return """# ARDA live desktop finalization hook intentionally left inert.
# The arda-xfce-session wrapper owns desktop awakening.
"""


def _live_awakening_script() -> str:
    return """#!/bin/sh
set -u

TARGET_DIR="$HOME/.local/share/backgrounds/arda-valinor"
SOURCE_DIR="/usr/share/arda/identity"
SYSTEM_WALLPAPER="/usr/share/backgrounds/xfce/arda-valinor.png"
STATE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/arda-valinor"
STATE_FILE="$STATE_DIR/awakening.state"
BOOT_ID_FILE="/proc/sys/kernel/random/boot_id"
JINGLE="/usr/share/arda/identity/arda-awakening.wav"
LOG_FILE="/tmp/arda-live-desktop-awakening.log"
WALLPAPER="$SYSTEM_WALLPAPER"

mkdir -p "$TARGET_DIR" "$STATE_DIR" "$HOME/.config/autostart"
LOCK_DIR="/tmp/arda-live-desktop-awakening.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf 'ARDA_AWAKENING: duplicate invocation skipped=%s\\n' "$(date -Is 2>/dev/null || date)" >>"$LOG_FILE" 2>&1
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM
{
  printf 'ARDA_AWAKENING: start=%s user=%s display=%s xdg=%s\\n' "$(date -Is 2>/dev/null || date)" "$(id -un 2>/dev/null || true)" "${DISPLAY:-}" "${XDG_CURRENT_DESKTOP:-}"
} >>"$LOG_FILE" 2>&1

set_wallpaper() {
  wallpaper_path="$1"
  [ -f "$wallpaper_path" ] || wallpaper_path="$SYSTEM_WALLPAPER"

  command -v xfconf-query >/dev/null 2>&1 || {
    printf 'ARDA_AWAKENING: xfconf-query unavailable; not touching root window\\n' >>"$LOG_FILE"
    return 0
  }

  # XFCE creates monitor names dynamically. Seed the common names used by
  # QEMU, VirtualBox, laptops, and generic fallback sessions before updating
  # whatever already exists in xfconf.
  for monitor in monitor0 monitor1 monitorVGA-1 monitorVirtual-1 monitorVirtual1 monitorVirtual-0 monitorQXL-1 monitorqxl-1 monitorHDMI-1 monitorHDMI-A-1 monitorDP-1 monitoreDP-1 monitorLVDS-1 monitorDVI-1 monitorDefault; do
    base="/backdrop/screen0/$monitor/workspace0"
    xfconf-query -c xfce4-desktop -p "/backdrop/single-workspace-mode" -n -t bool -s true >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "/backdrop/backdrop-cycle-enable" -n -t bool -s false >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/color-style" -n -t int -s 0 >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/image-style" -n -t int -s 5 >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/last-image" -n -t string -s "$wallpaper_path" >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/last-single-image" -n -t string -s "$wallpaper_path" >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/image-path" -n -t string -s "$wallpaper_path" >/dev/null 2>&1 || true
  done

  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep -E '/(last-image|last-single-image|image-path)$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s "$wallpaper_path" >/dev/null 2>&1 || true
  done
  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep '/image-style$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s 5 >/dev/null 2>&1 || true
  done
  for base in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | sed -n 's#^\\(/backdrop/screen[0-9][0-9]*/monitor[^/]*/workspace[0-9][0-9]*\\)/.*#\\1#p' | sort -u || true); do
    xfconf-query -c xfce4-desktop -p "$base/color-style" -n -t int -s 0 >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/image-style" -n -t int -s 5 >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/last-image" -n -t string -s "$wallpaper_path" >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/last-single-image" -n -t string -s "$wallpaper_path" >/dev/null 2>&1 || true
    xfconf-query -c xfce4-desktop -p "$base/image-path" -n -t string -s "$wallpaper_path" >/dev/null 2>&1 || true
  done
  xfconf-query -c xfce4-desktop -lv 2>/dev/null | grep -E 'last-image|last-single-image|image-path|image-style' >>"$LOG_FILE" 2>&1 || true
  printf 'ARDA_AWAKENING: wallpaper state staged=%s\\n' "$wallpaper_path" >>"$LOG_FILE" 2>&1
}

force_root_pixmap() {
  wallpaper_path="$1"
  [ -f "$wallpaper_path" ] || wallpaper_path="$SYSTEM_WALLPAPER"

  if command -v feh >/dev/null 2>&1; then
    feh --no-fehbg --bg-fill "$wallpaper_path" >>"$LOG_FILE" 2>&1 || true
    printf 'ARDA_AWAKENING: feh bg-fill attempted=%s\\n' "$wallpaper_path" >>"$LOG_FILE" 2>&1
  fi
}

set_panel_rgba() {
  r="$1"; g="$2"; b="$3"; a="$4"
  command -v xfconf-query >/dev/null 2>&1 || return 0
  for panel_path in $(xfconf-query -c xfce4-panel -l 2>/dev/null | grep '^/panels/panel-[0-9]\\+$' || true); do
    xfconf-query -c xfce4-panel -p "$panel_path/background-style" -n -t int -s 1 >/dev/null 2>&1 || true
    xfconf-query -c xfce4-panel -p "$panel_path/background-rgba" \
      -n -t double -t double -t double -t double \
      -s "$r" -s "$g" -s "$b" -s "$a" >/dev/null 2>&1 || true
  done
}

disable_compositor() {
  command -v xfconf-query >/dev/null 2>&1 || return 0
  xfconf-query -c xfwm4 -p /general/use_compositing -n -t bool -s false >/dev/null 2>&1 || true
  printf 'ARDA_AWAKENING: compositor disabled request sent\\n' >>"$LOG_FILE" 2>&1
}

retire_xfdesktop() {
  command -v xfconf-query >/dev/null 2>&1 || return 0
  xfconf-query -c xfce4-desktop -p /desktop-icons/style -n -t int -s 0 >/dev/null 2>&1 || true
  if pgrep -x xfdesktop >/dev/null 2>&1; then
    pkill xfdesktop >/dev/null 2>&1 || true
    printf 'ARDA_AWAKENING: xfdesktop retired\\n' >>"$LOG_FILE" 2>&1
  fi
}

play_jingle() {
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  [ -f "$JINGLE" ] || {
    printf 'ARDA_AWAKENING: jingle missing: %s\\n' "$JINGLE" >>"$LOG_FILE"
    return 0
  }
  (
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      if command -v paplay >/dev/null 2>&1; then
        paplay "$JINGLE" >>"$LOG_FILE" 2>&1 && exit 0
      elif command -v pw-play >/dev/null 2>&1; then
        pw-play "$JINGLE" >>"$LOG_FILE" 2>&1 && exit 0
      elif command -v aplay >/dev/null 2>&1; then
        aplay "$JINGLE" >>"$LOG_FILE" 2>&1 && exit 0
      fi
      sleep 1
    done
    printf 'ARDA_AWAKENING: no playable jingle path or audio server not ready\\n' >>"$LOG_FILE"
  ) &
}

boot_id="unknown-boot"
[ -r "$BOOT_ID_FILE" ] && boot_id=$(cat "$BOOT_ID_FILE")
already_awakened=0
[ -f "$STATE_FILE" ] && grep -qx "$boot_id" "$STATE_FILE" 2>/dev/null && already_awakened=1
JINGLE_ONCE_FILE="$STATE_DIR/jingle.$boot_id.done"

for _ in 1 2 3 4 5 6 7 8 9 10; do
  pgrep -x xfdesktop >/dev/null 2>&1 && command -v xfconf-query >/dev/null 2>&1 && xfconf-query -c xfce4-desktop -l >/dev/null 2>&1 && break
  sleep 1
done

set_panel_rgba 0.02 0.04 0.09 0.94
disable_compositor
retire_xfdesktop
if [ "$already_awakened" -eq 0 ]; then
  if [ ! -f "$JINGLE_ONCE_FILE" ]; then
    : >"$JINGLE_ONCE_FILE"
    play_jingle
  else
    printf 'ARDA_AWAKENING: jingle already emitted for boot=%s\\n' "$boot_id" >>"$LOG_FILE" 2>&1
  fi
fi

# XFCE/live-config may create or rewrite monitor-specific backdrop keys late in
# session startup. Reassert the final ARDA wallpaper over a short settling
# window while keeping xfdesktop retired, because it has proven to repaint the
# desktop black in the live/QEMU lane.
for delay in 0 1 2 4 8 16 32 48; do
  sleep "$delay"
  retire_xfdesktop
  set_wallpaper "$WALLPAPER"
  force_root_pixmap "$WALLPAPER"
done
set_panel_rgba 0.09 0.11 0.16 0.88
printf '%s\\n' "$boot_id" >"$STATE_FILE"
printf 'ARDA_AWAKENING: complete=%s\\n' "$(date -Is 2>/dev/null || date)" >>"$LOG_FILE" 2>&1
"""


def _live_wallpaper_guardian_script() -> str:
    return """#!/bin/sh
set -u

WALLPAPER="/usr/share/backgrounds/xfce/arda-valinor.png"
LOG="/tmp/arda-live-wallpaper-guardian.log"

[ -f "$WALLPAPER" ] || exit 0
command -v feh >/dev/null 2>&1 || exit 0

printf 'ARDA_WALLPAPER_GUARDIAN: start=%s display=%s\\n' "$(date -Is 2>/dev/null || date)" "${DISPLAY:-}" >>"$LOG" 2>&1

# Some live XFCE/QEMU combinations briefly paint the right wallpaper and then
# replace it with a black root window. Keep asserting the pixmap while the
# session settles, and keep xfdesktop out of the lane entirely.
for delay in 0 1 2 2 3 5 8 13 21 34 55; do
  sleep "$delay"
  if command -v xfconf-query >/dev/null 2>&1; then
    xfconf-query -c xfce4-desktop -p /desktop-icons/style -n -t int -s 0 >>"$LOG" 2>&1 || true
  fi
  if pgrep -x xfdesktop >/dev/null 2>&1; then
    pkill xfdesktop >>"$LOG" 2>&1 || true
  fi
  feh --no-fehbg --bg-fill "$WALLPAPER" >>"$LOG" 2>&1 || true
done

if command -v xfconf-query >/dev/null 2>&1; then
  xfconf-query -c xfwm4 -p /general/use_compositing -n -t bool -s false >>"$LOG" 2>&1 || true
fi

printf 'ARDA_WALLPAPER_GUARDIAN: complete=%s\\n' "$(date -Is 2>/dev/null || date)" >>"$LOG" 2>&1
"""


def _live_wallpaper_probe_script() -> str:
    return """#!/bin/sh
set -u
WALL="${1:-/usr/share/arda/identity/arda-wallpaper.png}"
LOG="/tmp/arda-wallpaper-probe.log"
{
  echo "ARDA_WALLPAPER_PROBE: date=$(date -Is 2>/dev/null || date)"
  echo "ARDA_WALLPAPER_PROBE: user=$(id)"
  echo "ARDA_WALLPAPER_PROBE: display=${DISPLAY:-}"
  echo "ARDA_WALLPAPER_PROBE: session=${XDG_CURRENT_DESKTOP:-}"
  echo "ARDA_WALLPAPER_PROBE: wall=$WALL exists=$([ -f "$WALL" ] && echo yes || echo no)"
  ls -l /usr/share/backgrounds/xfce/arda-valinor.png /usr/share/arda/identity/arda-wallpaper.png 2>&1 || true
  pgrep -a xfdesktop || true
  pgrep -a xfconfd || true
  command -v xfconf-query || true
  command -v paplay || true
  command -v pw-play || true
  command -v aplay || true
  xfconf-query -c xfce4-desktop -lv 2>&1 || true
} >"$LOG"
/usr/local/bin/arda-live-desktop-awakening >>"$LOG" 2>&1 || true
{
  echo "--- after ---"
  xfconf-query -c xfce4-desktop -lv 2>&1 || true
} >>"$LOG"
cat "$LOG"
"""


def _live_debug_snapshot_script() -> str:
    return """#!/bin/sh
set -u

OUT="/tmp/arda-live-debug-snapshot.log"
STATE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/arda-valinor"
mkdir -p "$STATE_DIR"

log() {
  printf '%s %s\\n' "$(date -Is 2>/dev/null || date)" "$*" >>"$OUT"
}

sample() {
  log "----- sample begin -----"
  log "id=$(id 2>/dev/null || true)"
  log "pwd=$(pwd 2>/dev/null || true)"
  log "display=${DISPLAY:-} xdg_current=${XDG_CURRENT_DESKTOP:-} xdg_session=${XDG_SESSION_DESKTOP:-} desktop_session=${DESKTOP_SESSION:-}"
  log "dbus_session=${DBUS_SESSION_BUS_ADDRESS:-}"
  log "runtime_dir=${XDG_RUNTIME_DIR:-}"
  log "wallpaper_exists=$([ -f /usr/share/arda/identity/arda-wallpaper.png ] && echo yes || echo no)"
  log "jingle_exists=$([ -f /usr/share/arda/identity/arda-awakening.wav ] && echo yes || echo no)"
  pgrep -a lightdm >>"$OUT" 2>&1 || true
  pgrep -a xfce4-session >>"$OUT" 2>&1 || true
  pgrep -a xfdesktop >>"$OUT" 2>&1 || true
  pgrep -a xfconfd >>"$OUT" 2>&1 || true
  pgrep -a Thunar >>"$OUT" 2>&1 || true
  pgrep -a pipewire >>"$OUT" 2>&1 || true
  pgrep -a pulseaudio >>"$OUT" 2>&1 || true
  command -v xrandr >/dev/null 2>&1 && xrandr --query >>"$OUT" 2>&1 || true
  command -v xfconf-query >/dev/null 2>&1 && xfconf-query -c xfce4-desktop -lv >>"$OUT" 2>&1 || true
  command -v xfconf-query >/dev/null 2>&1 && xfconf-query -c xfce4-panel -lv >>"$OUT" 2>&1 || true
  command -v loginctl >/dev/null 2>&1 && loginctl session-status >>"$OUT" 2>&1 || true
  log "----- sample end -----"
}

: >"$OUT"
log "ARDA_LIVE_DEBUG: starting"
for delay in 0 3 8 15 30 45 60 90; do
  sleep "$delay"
  sample
done
log "ARDA_LIVE_DEBUG: complete"
"""


def _live_awakening_desktop() -> str:
    return """[Desktop Entry]
Type=Application
Version=1.0
Name=ARDA Awakening
Comment=Bring the sovereign desktop from dusk into silver light
Exec=/bin/true
X-GNOME-Autostart-enabled=true
StartupNotify=false
Terminal=false
Hidden=true
"""


def _live_fstab() -> str:
    return """# ARDA Valinor live-image pseudo-filesystem baseline.
# The live root itself is supplied by live-boot; these API mounts must be
# available before normal systemd userspace can stand up cleanly.
proc /proc proc nosuid,nodev,noexec 0 0
sysfs /sys sysfs nosuid,nodev,noexec 0 0
devpts /dev/pts devpts gid=5,mode=620,ptmxmode=000 0 0
tmpfs /run tmpfs nosuid,nodev,mode=0755 0 0
tmpfs /run/lock tmpfs nosuid,nodev,noexec,mode=1777,size=5M 0 0
tmpfs /tmp tmpfs nosuid,nodev,mode=1777 0 0
hugetlbfs /dev/hugepages hugetlbfs mode=1770,gid=0 0 0
mqueue /dev/mqueue mqueue nosuid,nodev,noexec 0 0
debugfs /sys/kernel/debug debugfs nosuid,nodev,noexec,mode=0700 0 0
tracefs /sys/kernel/tracing tracefs nosuid,nodev,noexec,mode=0700 0 0
configfs /sys/kernel/config configfs nosuid,nodev,noexec 0 0
fusectl /sys/fs/fuse/connections fusectl nosuid,nodev,noexec 0 0
binfmt_misc /proc/sys/fs/binfmt_misc binfmt_misc nosuid,nodev,noexec 0 0
"""


def build_overlay(profile_path: Path, output_root: Path) -> dict:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    copied: list[dict] = []

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    overlay_root = output_root / "rootfs"
    overlay_root.mkdir(parents=True, exist_ok=True)

    # Core runtime
    # Live media needs the real ARDA runtime tree under /opt/arda so the
    # post-boot gate and verifier can import their backend dependencies.
    _copy_tree(
        REPO_ROOT / "arda_os" / "backend",
        overlay_root / "opt" / "arda" / "arda_os" / "backend",
        copied,
    )
    _copy_tree(
        REPO_ROOT / "arda_os" / "bin",
        overlay_root / "opt" / "arda" / "arda_os" / "bin",
        copied,
    )
    _copy_tree(
        REPO_ROOT / "arda_os" / "kernel" / "valinor" / "scripts",
        overlay_root / "opt" / "arda" / "arda_os" / "kernel" / "valinor" / "scripts",
        copied,
    )

    # Service units
    _write_text(
        overlay_root / "etc" / "systemd" / "system" / "arda-phase4-remote-verifier.service",
        _live_verifier_unit(),
        copied,
        "generated:arda-phase4-remote-verifier.service",
    )
    _write_text(
        overlay_root / "etc" / "systemd" / "system" / "arda-valinor-boot-audit.service",
        _live_boot_audit_unit(),
        copied,
        "generated:arda-valinor-boot-audit.service",
    )
    _write_text(
        overlay_root / "etc" / "systemd" / "system" / "arda-valinor-postboot.service",
        _live_postboot_unit(),
        copied,
        "generated:arda-valinor-postboot.service",
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "kernel" / "valinor" / "releases" / "systemd" / "arda-bombadil-valinor.service",
        overlay_root / "etc" / "systemd" / "system" / "arda-bombadil-valinor.service",
        copied,
    )
    # Live ISO bring-up must never lock the operator out of emergency mode.
    # Remove these overrides before a hardened public release image.
    _write_text(
        overlay_root / "etc" / "systemd" / "system" / "emergency.service.d" / "override.conf",
        _live_emergency_shell_override(),
        copied,
        "generated:emergency-debug-shell",
    )
    _write_text(
        overlay_root / "etc" / "systemd" / "system" / "rescue.service.d" / "override.conf",
        _live_emergency_shell_override(),
        copied,
        "generated:rescue-debug-shell",
    )
    for service_name in (
        "display-manager.service",
        "getty@tty1.service",
        "lightdm.service",
        "systemd-user-sessions.service",
    ):
        _write_text(
            overlay_root / "etc" / "systemd" / "system" / f"{service_name}.d" / "override.conf",
            _live_service_after_boot_audit_override(),
            copied,
            f"generated:{service_name}:boot-audit-ordering",
        )
    _write_text(
        overlay_root / "etc" / "fstab",
        _live_fstab(),
        copied,
        "generated:live-fstab",
    )
    _write_text(
        overlay_root / "etc" / "initramfs-tools" / "update-initramfs.conf",
        _live_update_initramfs_conf_disabled(),
        copied,
        "generated:update-initramfs-build-guard",
    )
    _write_text(
        overlay_root / "etc" / "lightdm" / "lightdm.conf.d" / "90-arda-live-autologin.conf",
        _live_lightdm_conf(),
        copied,
        "generated:lightdm-autologin",
    )
    _write_text(
        overlay_root / "etc" / "lightdm" / "lightdm-gtk-greeter.conf.d" / "90-arda-live-greeter.conf",
        _live_gtk_greeter_conf(),
        copied,
        "generated:lightdm-greeter",
    )
    _write_text(
        overlay_root / "usr" / "share" / "xsessions" / "arda-xfce.desktop",
        _live_arda_xfce_desktop(),
        copied,
        "generated:arda-xfce-session-desktop",
    )
    _write_executable(
        overlay_root / "usr" / "local" / "bin" / "arda-xfce-session",
        _live_arda_xfce_session(),
        copied,
        "generated:arda-xfce-session",
    )
    _write_text(
        overlay_root / "home" / "arda" / ".xsession",
        _live_xsession(),
        copied,
        "generated:arda-xsession",
    )
    _write_executable(
        overlay_root / "home" / "arda" / ".xsessionrc",
        _live_xsessionrc(),
        copied,
        "generated:arda-xsessionrc",
    )
    _write_text(
        overlay_root / "etc" / "X11" / "Xsession.d" / "99arda-live-desktop-awakening",
        _live_xsession_hook(),
        copied,
        "generated:xsessiond-arda-awakening",
    )
    _write_text(
        overlay_root / "home" / "arda" / ".config" / "autostart" / "arda-awakening.desktop",
        _live_awakening_desktop(),
        copied,
        "generated:arda-awakening-autostart",
    )
    _write_text(
        overlay_root / "etc" / "xdg" / "autostart" / "arda-awakening.desktop",
        _live_awakening_desktop(),
        copied,
        "generated:arda-awakening-system-autostart",
    )
    _write_text(
        overlay_root / "etc" / "skel" / ".config" / "autostart" / "arda-awakening.desktop",
        _live_awakening_desktop(),
        copied,
        "generated:arda-awakening-skel-autostart",
    )
    _write_executable(
        overlay_root / "usr" / "local" / "bin" / "arda-live-desktop-awakening",
        _live_awakening_script(),
        copied,
        "generated:arda-live-desktop-awakening",
    )
    _write_executable(
        overlay_root / "usr" / "local" / "bin" / "arda-live-wallpaper-guardian",
        _live_wallpaper_guardian_script(),
        copied,
        "generated:arda-live-wallpaper-guardian",
    )
    _write_executable(
        overlay_root / "usr" / "local" / "bin" / "arda-wallpaper-probe",
        _live_wallpaper_probe_script(),
        copied,
        "generated:arda-wallpaper-probe",
    )
    _write_executable(
        overlay_root / "usr" / "local" / "bin" / "arda-live-debug-snapshot",
        _live_debug_snapshot_script(),
        copied,
        "generated:arda-live-debug-snapshot",
    )
    xfconf_dir = (
        overlay_root
        / "home"
        / "arda"
        / ".config"
        / "xfce4"
        / "xfconf"
        / "xfce-perchannel-xml"
    )
    _write_text(
        xfconf_dir / "xfce4-desktop.xml",
        _live_xfce_desktop_xml(),
        copied,
        "generated:xfce4-desktop",
    )
    _write_text(
        overlay_root / "etc" / "skel" / ".config" / "xfce4" / "xfconf" / "xfce-perchannel-xml" / "xfce4-desktop.xml",
        _live_xfce_desktop_xml(),
        copied,
        "generated:skel-xfce4-desktop",
    )
    _write_text(
        overlay_root / "etc" / "xdg" / "xfce4" / "xfconf" / "xfce-perchannel-xml" / "xfce4-desktop.xml",
        _live_xfce_desktop_xml(),
        copied,
        "generated:system-xfce4-desktop",
    )
    _write_text(
        xfconf_dir / "xfce4-session.xml",
        _live_xfce_session_xml(),
        copied,
        "generated:xfce4-session",
    )
    _write_text(
        overlay_root / "etc" / "skel" / ".config" / "xfce4" / "xfconf" / "xfce-perchannel-xml" / "xfce4-session.xml",
        _live_xfce_session_xml(),
        copied,
        "generated:skel-xfce4-session",
    )
    _write_text(
        overlay_root / "etc" / "xdg" / "xfce4" / "xfconf" / "xfce-perchannel-xml" / "xfce4-session.xml",
        _live_xfce_session_xml(),
        copied,
        "generated:system-xfce4-session",
    )
    _write_text(
        xfconf_dir / "xsettings.xml",
        _live_xsettings_xml(),
        copied,
        "generated:xsettings",
    )
    _write_text(
        xfconf_dir / "xfwm4.xml",
        _live_xfwm4_xml(),
        copied,
        "generated:xfwm4",
    )
    _write_text(
        overlay_root / "home" / "arda" / ".config" / "xfce4" / "terminal" / "terminalrc",
        _live_terminalrc(),
        copied,
        "generated:xfce4-terminal",
    )
    _write_text(
        overlay_root / "home" / "arda" / ".gtkrc-2.0",
        'gtk-theme-name="Adwaita-dark"\ngtk-icon-theme-name="ARDA Valinor"\n',
        copied,
        "generated:gtkrc",
    )

    # Environment templates
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "etc" / "arda.env.example",
        overlay_root / "etc" / "arda" / "arda.env",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "etc" / "arda-verifier.env.example",
        overlay_root / "etc" / "arda" / "arda-verifier.env",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "etc" / "arda-attested-host.env.example",
        overlay_root / "etc" / "arda" / "attested-host.env",
        copied,
    )
    _write_text(
        overlay_root / "etc" / "arda" / "attested-host.env",
        _live_attested_host_env(),
        copied,
        "generated:live-attested-host-env",
    )

    # Policy bundle
    _copy_file(
        REPO_ROOT / "arda_os" / "kernel" / "valinor" / "releases" / "phase2" / "active_bundle.json",
        overlay_root / "etc" / "arda" / "policy" / "active_bundle.json",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "kernel" / "valinor" / "releases" / "phase2" / "projection-legacy_inode.json",
        overlay_root / "etc" / "arda" / "policy" / "active_projection_plan.json",
        copied,
    )

    # Identity and boot assets
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "boot" / "assets" / "arda-wallpaper.png",
        overlay_root / "usr" / "share" / "arda" / "identity" / "arda-wallpaper.png",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "boot" / "assets" / "arda-wallpaper.png",
        overlay_root / "usr" / "share" / "backgrounds" / "xfce" / "arda-valinor.png",
        copied,
    )
    for dest in (
        overlay_root / "usr" / "share" / "images" / "desktop-base" / "desktop-background",
        overlay_root / "usr" / "share" / "images" / "desktop-base" / "default",
        overlay_root / "usr" / "share" / "images" / "desktop-base" / "desktop-grub.png",
        overlay_root / "usr" / "share" / "backgrounds" / "xfce" / "xfce-blue.jpg",
    ):
        _copy_file(
            REPO_ROOT / "arda_os" / "deploy" / "boot" / "assets" / "arda-wallpaper.png",
            dest,
            copied,
        )
    for stock_xfce_svg in (
        "xfce-cp-dark.svg",
        "xfce-flower.svg",
        "xfce-leaves.svg",
        "xfce-light.svg",
        "xfce-mouserace.svg",
        "xfce-shapes.svg",
        "xfce-stripes.svg",
        "xfce-teal.svg",
        "xfce-verticals.svg",
        "xfce-x.svg",
    ):
        _write_text(
            overlay_root / "usr" / "share" / "backgrounds" / "xfce" / stock_xfce_svg,
            _live_xfce_wallpaper_svg(),
            copied,
            f"generated:xfce-stock-wallpaper:{stock_xfce_svg}",
        )
    for stage in ("dusk", "ember", "silver", "crown", "dawn", "wallpaper"):
        _copy_file(
            REPO_ROOT / "arda_os" / "deploy" / "boot" / "assets" / "arda-wallpaper.png",
            overlay_root / "usr" / "share" / "arda" / "identity" / f"arda-valinor-{stage}.png",
            copied,
        )
    _copy_tree(
        REPO_ROOT / "arda_os" / "deploy" / "boot" / "themes" / "arda-plymouth",
        overlay_root / "usr" / "share" / "plymouth" / "themes" / "arda-sovereign",
        copied,
    )
    _copy_tree(
        REPO_ROOT / "arda_os" / "deploy" / "boot" / "themes" / "arda-plymouth-mirror",
        overlay_root / "usr" / "share" / "plymouth" / "themes" / "arda-mirror-gate",
        copied,
    )
    _write_text(
        overlay_root / "usr" / "share" / "plymouth" / "themes" / "arda-mirror-gate" / "arda-mirror-gate.plymouth",
        (REPO_ROOT / "arda_os" / "deploy" / "boot" / "themes" / "arda-plymouth-mirror" / "arda-mirror.plymouth").read_text(encoding="utf-8"),
        copied,
        "generated:arda-mirror-gate-plymouth-alias",
    )
    _write_text(
        overlay_root / "etc" / "plymouth" / "plymouthd.conf",
        _live_plymouthd_conf(),
        copied,
        "generated:plymouthd-conf",
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "identity" / "assets" / "arda-awakening.wav",
        overlay_root / "usr" / "share" / "arda" / "identity" / "arda-awakening.wav",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "identity" / "gtk.css",
        overlay_root / "usr" / "share" / "arda" / "identity" / "gtk.css",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "identity" / "gtk.css",
        overlay_root / "home" / "arda" / ".config" / "gtk-3.0" / "gtk.css",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "identity" / "gtk.css",
        overlay_root / "home" / "arda" / ".config" / "gtk-4.0" / "gtk.css",
        copied,
    )
    _copy_file(
        REPO_ROOT / "arda_os" / "deploy" / "identity" / "arda_os_identity.json",
        overlay_root / "usr" / "share" / "arda" / "identity" / "arda_os_identity.json",
        copied,
    )
    icon_root = overlay_root / "usr" / "share" / "icons" / "arda-valinor"
    _write_text(
        icon_root / "index.theme",
        _live_icon_theme_index(),
        copied,
        "generated:arda-icon-theme-index",
    )
    for category in ("apps", "places", "devices"):
        for icon_name in (
            "folder",
            "inode-directory",
            "folder-documents",
            "folder-download",
            "user-home",
            "user-trash",
            "user-trash-full",
            "system-file-manager",
            "drive-harddisk",
            "utilities-terminal",
            "applications-system",
        ):
            _copy_file(
                REPO_ROOT / "arda_os" / "deploy" / "boot" / "assets" / "arda-seal.png",
                icon_root / category / "64" / f"{icon_name}.png",
                copied,
            )

    # Distribution identity
    os_release = "\n".join(
        [
            'NAME="ARDA Valinor"',
            'ID="arda-valinor"',
            'PRETTY_NAME="ARDA Valinor (Debian-based)"',
            'ID_LIKE="debian"',
            'HOME_URL="https://github.com/Byron2306/Integritas-Mechanicus"',
            "",
        ]
    )
    _write_text(
        overlay_root / "etc" / "os-release",
        os_release,
        copied,
        "generated:etc-os-release",
    )
    _write_text(
        overlay_root / "usr" / "lib" / "os-release.d" / "arda-valinor.conf",
        os_release,
        copied,
        "generated:os-release",
    )

    # Build marker
    build_info = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "distribution_id": profile["distribution_id"],
        "distribution_name": profile["distribution_name"],
        "copied_file_count": len(copied),
    }
    build_info_path = output_root / "overlay-build-info.json"
    build_info_path.write_text(json.dumps(build_info, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "profile": str(profile_path),
        "output_root": str(output_root),
        "overlay_root": str(overlay_root),
        "copied_files": copied,
        "copied_file_count": len(copied),
        "build_info": str(build_info_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the ARDA distribution overlay")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--output-root", default=str(DISTRIBUTION_DIR / "build" / "overlay"))
    args = parser.parse_args()

    payload = build_overlay(Path(args.profile), Path(args.output_root))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
