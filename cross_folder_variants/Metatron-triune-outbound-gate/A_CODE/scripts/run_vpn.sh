#!/bin/bash
# Seraph AI VPN Startup Script (WireGuard)
# Optimized for privileged Docker environments

set -e

CONFIG_SOURCE="/var/lib/anti-ai-defense/vpn/wg0.conf"
CONFIG_DEST="/etc/wireguard/wg0.conf"

echo "[VPN] Starting WireGuard initialization..."

if [ ! -f "$CONFIG_SOURCE" ]; then
    echo "[VPN] ERROR: Configuration at $CONFIG_SOURCE not found."
    exit 1
fi

# Ensure /etc/wireguard exists and has correct permissions
mkdir -p /etc/wireguard
chmod 700 /etc/wireguard

# Link or copy config
cp "$CONFIG_SOURCE" "$CONFIG_DEST"
chmod 600 "$CONFIG_DEST"

# Bring up the interface
echo "[VPN] Executing wg-quick up wg0..."
wg-quick up wg0 || {
    echo "[VPN] wg-quick failed. Attempting manual interface setup..."
    # Fallback to manual setup if wg-quick has issues with route-metrics in containers
    ip link add dev wg0 type wireguard 2>/dev/null || true
    wg setconf wg0 "$CONFIG_DEST"
    
    # Explicitly set address and routes since wg-quick failed
    # Note: 10.200.200.2/32 is the standard agent IP in this deployment
    ip -4 address add 10.200.200.2/32 dev wg0 2>/dev/null || true
    ip link set mtu 1420 up dev wg0
    ip -4 route add 10.200.200.0/24 dev wg0 2>/dev/null || true
}

echo "[VPN] Interface wg0 is UP."
wg show wg0

# Monitor connectivity (optional background loop)
while true; do
    if ! ip link show wg0 >/dev/null 2>&1; then
        echo "[VPN] ERROR: Interface wg0 disappeared. Attempting restart..."
        wg-quick down wg0 || true
        wg-quick up wg0 || true
    fi
    sleep 60
done
