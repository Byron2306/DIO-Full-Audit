#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ATOMIC_VM_ENV_FILE:-$ROOT_DIR/config/windows_validation_vm.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

DOWNLOAD_DIR="${DOWNLOAD_DIR:-/home/$SUDO_USER/Downloads/windows-vm-downloads}"
ARCHIVE_PATH="${WINDOWS_DEV_ARCHIVE_PATH:-$DOWNLOAD_DIR/WinDev2407Eval.HyperV.zip}"
EXTRACT_DIR="${WINDOWS_DEV_EXTRACT_DIR:-$DOWNLOAD_DIR/WinDev2407Eval.HyperV}"
VM_NAME="${VM_NAME:-metatron-winval-01}"
IMPORTED_DISK_PATH="${WINDOWS_IMPORT_DISK_PATH:-/var/lib/libvirt/images/${VM_NAME}.qcow2}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "This script must run as root. Use: sudo $0" >&2
    exit 1
  fi
}

main() {
  require_root
  need_cmd unzip
  need_cmd qemu-img

  if [[ ! -f "$ARCHIVE_PATH" ]]; then
    echo "Archive not found: $ARCHIVE_PATH" >&2
    exit 1
  fi

  mkdir -p "$EXTRACT_DIR"
  unzip -n "$ARCHIVE_PATH" -d "$EXTRACT_DIR"

  local source_disk
  local source_format
  source_disk="$(find "$EXTRACT_DIR" -type f \( -iname '*.vhdx' -o -iname '*.vhd' \) -printf '%s %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
  if [[ -z "$source_disk" ]]; then
    echo "No VHDX/VHD disk found under $EXTRACT_DIR" >&2
    exit 1
  fi
  if [[ "$source_disk" == *.vhd ]]; then
    source_format="vpc"
  else
    source_format="vhdx"
  fi

  mkdir -p "$(dirname "$IMPORTED_DISK_PATH")"
  if [[ ! -f "$IMPORTED_DISK_PATH" ]]; then
    qemu-img convert -p -f "$source_format" -O qcow2 "$source_disk" "$IMPORTED_DISK_PATH"
  else
    echo "Target disk already exists, skipping conversion: $IMPORTED_DISK_PATH"
  fi

  echo "Converted disk ready: $IMPORTED_DISK_PATH"
  echo "Run the VM creation step with:"
  echo "  sudo WINDOWS_IMPORT_DISK_PATH='$IMPORTED_DISK_PATH' ./scripts/setup_windows_validation_vm.sh"
}

main "$@"