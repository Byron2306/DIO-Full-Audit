#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
TARGET_DIR="${ARDA_OS_VIBE_TARGET_DIR:-$HOME/.local/share/backgrounds/arda-valinor}"
DUSK_WALLPAPER="$TARGET_DIR/arda-valinor-dusk.png"
EMBER_WALLPAPER="$TARGET_DIR/arda-valinor-ember.png"
SILVER_WALLPAPER="$TARGET_DIR/arda-valinor-silver.png"
CROWN_WALLPAPER="$TARGET_DIR/arda-valinor-crown.png"
DAWN_WALLPAPER="$TARGET_DIR/arda-valinor-dawn.png"
JINGLE="${ARDA_OS_JINGLE_PATH:-$REPO_ROOT/arda_os/deploy/identity/assets/arda-awakening.wav}"
STATE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/arda-valinor"
STATE_FILE="$STATE_DIR/awakening.state"
BOOT_ID_FILE="/proc/sys/kernel/random/boot_id"

mkdir -p "$STATE_DIR"

set_wallpaper() {
  wallpaper_path="$1"
  if ! command -v xfconf-query >/dev/null 2>&1; then
    return 0
  fi
  for property in $(xfconf-query -c xfce4-desktop -l 2>/dev/null | grep -E '/(last-image|last-single-image|image-path)$' || true); do
    xfconf-query -c xfce4-desktop -p "$property" -s "$wallpaper_path" >/dev/null 2>&1 || true
  done
}

set_panel_rgba() {
  r="$1"
  g="$2"
  b="$3"
  a="$4"
  if ! command -v xfconf-query >/dev/null 2>&1; then
    return 0
  fi
  for panel_path in $(xfconf-query -c xfce4-panel -l 2>/dev/null | grep '^/panels/panel-[0-9]\+$' || true); do
    xfconf-query -c xfce4-panel -p "$panel_path/background-rgba" \
      -t double -t double -t double -t double \
      -s "$r" -s "$g" -s "$b" -s "$a" >/dev/null 2>&1 || true
  done
}

play_jingle() {
  if [ -f "$JINGLE" ] && command -v paplay >/dev/null 2>&1; then
    paplay "$JINGLE" >/dev/null 2>&1 &
    return 0
  fi
  if [ "${ARDA_OS_ALLOW_SYSTEM_CHIME:-0}" = "1" ] && command -v canberra-gtk-play >/dev/null 2>&1; then
    canberra-gtk-play -i complete -d "ARDA Awakening" >/dev/null 2>&1 &
    return 0
  fi
}

boot_id="unknown-boot"
if [ -r "$BOOT_ID_FILE" ]; then
  boot_id=$(cat "$BOOT_ID_FILE")
fi

if [ -f "$STATE_FILE" ] && grep -qx "$boot_id" "$STATE_FILE" 2>/dev/null; then
  exit 0
fi

if [ -f "$DUSK_WALLPAPER" ]; then
  set_wallpaper "$DUSK_WALLPAPER"
  set_panel_rgba 0.02 0.04 0.09 0.94
fi

sleep 1
play_jingle

if [ -f "$EMBER_WALLPAPER" ]; then
  sleep 1
  set_wallpaper "$EMBER_WALLPAPER"
  set_panel_rgba 0.05 0.07 0.12 0.92
fi

if [ -f "$SILVER_WALLPAPER" ]; then
  sleep 1
  set_wallpaper "$SILVER_WALLPAPER"
  set_panel_rgba 0.07 0.09 0.14 0.90
fi

if [ -f "$CROWN_WALLPAPER" ]; then
  sleep 1
  set_wallpaper "$CROWN_WALLPAPER"
  set_panel_rgba 0.08 0.10 0.15 0.89
fi

if [ -f "$DAWN_WALLPAPER" ]; then
  sleep 2
  set_wallpaper "$DAWN_WALLPAPER"
  set_panel_rgba 0.09 0.11 0.16 0.88
fi

printf '%s\n' "$boot_id" >"$STATE_FILE"
