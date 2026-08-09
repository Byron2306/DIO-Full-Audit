#!/bin/sh
set -eu

GRUB_DEFAULTS="/etc/default/grub"

usage() {
  cat <<'EOF'
Usage:
  arda_secure_boot_diagnostic.sh [--disable-grub-theme]

What it does:
  - reports UEFI runtime and efivarfs availability
  - checks Secure Boot visibility through mokutil when possible
  - shows EFI boot entries when efibootmgr is available
  - inspects the configured GRUB theme and expected assets
  - optionally comments out GRUB_THEME in /etc/default/grub

Notes:
  - BIOS/firmware Secure Boot toggles cannot be automated from Linux here
  - --disable-grub-theme edits /etc/default/grub and requires root
EOF
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "error: this action requires root" >&2
    exit 1
  fi
}

print_section() {
  echo
  echo "[$1]"
}

theme_path_from_defaults() {
  if [ ! -r "$GRUB_DEFAULTS" ]; then
    return 0
  fi

  sed -n 's/^GRUB_THEME="\([^"]*\)".*/\1/p; s/^GRUB_THEME=\(.*\)/\1/p' "$GRUB_DEFAULTS" | head -n 1
}

comment_out_grub_theme() {
  require_root

  if [ ! -f "$GRUB_DEFAULTS" ]; then
    echo "error: $GRUB_DEFAULTS not found" >&2
    exit 1
  fi

  cp "$GRUB_DEFAULTS" "${GRUB_DEFAULTS}.arda-secure-boot.bak"
  sed -i '/^GRUB_THEME=/s/^/# disabled by arda_secure_boot_diagnostic.sh: /' "$GRUB_DEFAULTS"

  echo "Updated $GRUB_DEFAULTS"
  echo "Backup saved to ${GRUB_DEFAULTS}.arda-secure-boot.bak"
  echo "Next: run update-grub as root, then reboot."
}

DISABLE_THEME=0

for arg in "$@"; do
  case "$arg" in
    --disable-grub-theme)
      DISABLE_THEME=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

echo "ARDA SECURE BOOT DIAGNOSTIC"
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "host: $(hostname 2>/dev/null || echo unknown)"

print_section "platform"
printf 'virt: '
if command -v systemd-detect-virt >/dev/null 2>&1; then
  systemd-detect-virt || true
else
  echo "unavailable"
fi
printf 'vendor: '
cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo "unavailable"
printf 'product: '
cat /sys/class/dmi/id/product_name 2>/dev/null || echo "unavailable"

print_section "uefi"
if [ -d /sys/firmware/efi ]; then
  echo "boot mode: UEFI"
else
  echo "boot mode: not UEFI"
fi

if [ -d /sys/firmware/efi/efivars ]; then
  echo "efivars directory: present"
  if mount | grep -q ' on /sys/firmware/efi/efivars '; then
    echo "efivarfs mount: present"
  else
    echo "efivarfs mount: missing"
  fi
  echo "efivars sample:"
  ls /sys/firmware/efi/efivars 2>/dev/null | sed -n '1,10p' || true
else
  echo "efivars directory: missing"
fi

print_section "secure boot"
if command -v mokutil >/dev/null 2>&1; then
  mokutil --sb-state 2>&1 || true
else
  echo "mokutil: unavailable"
fi

print_section "efi boot entries"
if command -v efibootmgr >/dev/null 2>&1; then
  efibootmgr -v 2>&1 || true
else
  echo "efibootmgr: unavailable"
fi

print_section "grub theme"
if [ -r "$GRUB_DEFAULTS" ]; then
  THEME_PATH=$(theme_path_from_defaults || true)
  if [ -n "${THEME_PATH:-}" ]; then
    echo "configured theme: $THEME_PATH"
    if [ -f "$THEME_PATH" ]; then
      echo "theme file: present"
      THEME_DIR=$(dirname "$THEME_PATH")
      for asset in background.png seal.png crown-bar.png; do
        if [ -f "$THEME_DIR/$asset" ]; then
          echo "asset ok: $THEME_DIR/$asset"
        else
          echo "asset missing: $THEME_DIR/$asset"
        fi
      done
    else
      echo "theme file: missing"
    fi
  else
    echo "configured theme: none"
  fi
else
  echo "$GRUB_DEFAULTS not readable"
fi

print_section "assessment"
if [ -d /sys/firmware/efi ] && ! mount | grep -q ' on /sys/firmware/efi/efivars '; then
  echo "UEFI boot is present, but efivarfs is not mounted or not supported."
  echo "This is why mokutil cannot confirm Secure Boot state."
fi

if command -v mokutil >/dev/null 2>&1; then
  SB_OUTPUT=$(mokutil --sb-state 2>&1 || true)
  case "$SB_OUTPUT" in
    *"EFI variables are not supported"*)
      echo "EFI runtime variables are unavailable from Linux."
      echo "Likely causes: firmware setup mismatch, broken runtime services, or nonstandard boot path."
      ;;
    *"SecureBoot enabled"*)
      echo "Secure Boot appears enabled."
      ;;
    *"SecureBoot disabled"*|*"disabled"*)
      echo "Secure Boot appears disabled or inactive."
      ;;
  esac
fi

if [ "$DISABLE_THEME" -eq 1 ]; then
  print_section "grub theme change"
  comment_out_grub_theme
fi
