#!/bin/bash
# ==============================================================================
# Atomic Red Team Dependency Installer (Local Mode)
# ==============================================================================
# This script installs PowerShell and Atomic Red Team in the local project dir
# to avoid requiring sudo.
# ==============================================================================

set -e

PROJECT_ROOT="/home/byron/Downloads/Metatron-triune-outbound-gate"
TOOLS_DIR="$PROJECT_ROOT/tools"
PWSH_DIR="$TOOLS_DIR/powershell"
ATOMIC_DIR="$PROJECT_ROOT/atomic-red-team"
INVOKE_ATOMIC_DIR="$TOOLS_DIR/invoke-atomicredteam"

mkdir -p "$TOOLS_DIR"
mkdir -p "$PWSH_DIR"

echo "--- Setting up PowerShell ---"
PWSH_URL="https://github.com/PowerShell/PowerShell/releases/download/v7.6.0/powershell-7.6.0-linux-x64.tar.gz"
if [ ! -f "$TOOLS_DIR/powershell.tar.gz" ]; then
    echo "Downloading PowerShell..."
    curl -L "$PWSH_URL" -o "$TOOLS_DIR/powershell.tar.gz"
fi

if [ ! -f "$PWSH_DIR/pwsh" ]; then
    echo "Extracting PowerShell..."
    tar -xzf "$TOOLS_DIR/powershell.tar.gz" -C "$PWSH_DIR"
    chmod +x "$PWSH_DIR/pwsh"
fi

echo "--- Cloning Atomic Red Team Technqiue Library ---"
if [ ! -d "$ATOMIC_DIR" ]; then
    git clone https://github.com/redcanaryco/atomic-red-team.git "$ATOMIC_DIR"
else
    echo "Atomic Red Team already exists, skipping clone."
fi

echo "--- Cloning Invoke-AtomicRedTeam ---"
if [ ! -d "$INVOKE_ATOMIC_DIR" ]; then
    git clone https://github.com/redcanaryco/invoke-atomicredteam.git "$INVOKE_ATOMIC_DIR"
else
    echo "Invoke-AtomicRedTeam already exists, skipping clone."
fi

echo "--- Configuration ---"
echo "Add the following to your .env file or environment:"
echo "ATOMIC_RUNNER=$PWSH_DIR/pwsh"
echo "ATOMIC_RED_TEAM_PATH=$ATOMIC_DIR/atomics"
echo "PWSH_MODULE_PATH=$INVOKE_ATOMIC_DIR/Invoke-AtomicRedTeam"

echo "Installation Complete!"
