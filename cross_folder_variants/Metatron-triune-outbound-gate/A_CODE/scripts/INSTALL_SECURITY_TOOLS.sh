#!/bin/bash
# ==============================================================================
# Seraph AI Defense - Security Tool Installer
# ==============================================================================
# This script installs the missing discovery and scanning tools required for
# full operational integrity of the Unified Agent.
# ==============================================================================

set -e

echo "------------------------------------------------------------"
echo " Seraph Security Tool Installer (Debian/Ubuntu)"
echo "------------------------------------------------------------"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)."
  exit 1
fi

echo "[1/3] Updating package lists..."
apt-get update -y

echo "[2/3] Installing discovery tools..."
apt-get install -y \
    wireless-tools \
    iw \
    arp-scan \
    nmap \
    fping \
    net-tools

echo "[3/3] Setting capabilities for non-root execution..."
# Allow fping and arp-scan to run without full sudo where possible
chmod u+s $(which fping) 2>/dev/null || true
# Note: arp-scan usually needs raw socket access which capabilities can handle
setcap cap_net_raw,cap_net_admin=eip $(which arp-scan) 2>/dev/null || true
setcap cap_net_raw,cap_net_admin=eip $(which nmap) 2>/dev/null || true

echo "------------------------------------------------------------"
echo " Installation Complete!"
echo "------------------------------------------------------------"
echo "The Unified Agent can now perform thorough scans for:"
echo " - WiFi Access Points (iwlist/iw)"
echo " - LAN Devices (arp-scan/nmap)"
echo " - Host Availability (fping)"
echo "------------------------------------------------------------"
