#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a macOS lab host for Seraph Atomic Validation over SSH.
# Run on the macOS machine (not inside Docker).

ATOMICS_ROOT="${ATOMICS_ROOT:-/Users/Shared/AtomicRedTeam/atomics}"
INVOKE_MODULE_PATH="${INVOKE_MODULE_PATH:-/Users/Shared/AtomicRedTeam/invoke-atomicredteam}"
WORKDIR="${WORKDIR:-/tmp/seraph-macos-lab-bootstrap}"

echo "[*] Using:"
echo "    ATOMICS_ROOT=$ATOMICS_ROOT"
echo "    INVOKE_MODULE_PATH=$INVOKE_MODULE_PATH"
echo "    WORKDIR=$WORKDIR"

mkdir -p "$WORKDIR"

if ! command -v git >/dev/null 2>&1; then
  echo "[!] git is required. Install Xcode Command Line Tools (xcode-select --install)." >&2
  exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "[!] Homebrew not found. Install from https://brew.sh and re-run." >&2
  exit 1
fi

if ! command -v pwsh >/dev/null 2>&1; then
  echo "[*] Installing PowerShell (pwsh) via Homebrew..."
  brew install --cask powershell
fi

echo "[*] Staging Atomic Red Team..."
rm -rf "$WORKDIR/atomic-red-team"
git clone --depth 1 https://github.com/redcanaryco/atomic-red-team.git "$WORKDIR/atomic-red-team"

echo "[*] Staging Invoke-AtomicRedTeam module..."
rm -rf "$WORKDIR/invoke-atomicredteam"
git clone --depth 1 https://github.com/redcanaryco/invoke-atomicredteam.git "$WORKDIR/invoke-atomicredteam"

sudo mkdir -p "$(dirname "$ATOMICS_ROOT")" "$(dirname "$INVOKE_MODULE_PATH")"
sudo rm -rf "$ATOMICS_ROOT" "$INVOKE_MODULE_PATH"
sudo cp -R "$WORKDIR/atomic-red-team/atomics" "$ATOMICS_ROOT"
sudo cp -R "$WORKDIR/invoke-atomicredteam" "$INVOKE_MODULE_PATH"
sudo chown -R root:wheel "/Users/Shared/AtomicRedTeam" || true

echo "[*] Verifying pwsh + module import..."
pwsh -NoProfile -NonInteractive -Command "Import-Module \"$INVOKE_MODULE_PATH/Invoke-AtomicRedTeam.psd1\" -ErrorAction Stop; 'ok'"

echo "[+] Done. Configure Seraph backend env vars:"
echo "    MACOS_ATOMIC_ROOT=$ATOMICS_ROOT"
echo "    MACOS_INVOKE_ATOMICREDTEAM_MODULE_PATH=$INVOKE_MODULE_PATH/Invoke-AtomicRedTeam.psd1"

