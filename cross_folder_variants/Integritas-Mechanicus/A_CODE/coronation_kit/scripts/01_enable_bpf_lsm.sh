#!/bin/bash
# ═══════════════════════════════════════════════════════
# ARDA OS — Enable BPF LSM and Reboot
# Run this if Gate 5 says "BPF LSM not in active LSM list"
# ═══════════════════════════════════════════════════════
set -e

echo "=== ARDA: Enabling BPF LSM Boot Parameter ==="

if [ "$EUID" -ne 0 ]; then
    echo "Run as root: sudo $0"
    exit 1
fi

CURRENT_LSMS=$(cat /sys/kernel/security/lsm 2>/dev/null || echo "unknown")
echo "Current LSMs: $CURRENT_LSMS"

if echo "$CURRENT_LSMS" | grep -q "bpf"; then
    echo "BPF LSM is already active. No reboot needed."
    exit 0
fi

# Method 1: GRUB (persistent install)
if [ -f /etc/default/grub ]; then
    echo "Updating GRUB..."
    
    # Backup
    cp /etc/default/grub /etc/default/grub.bak
    
    # Add BPF LSM to kernel command line
    CURRENT_CMDLINE=$(grep "^GRUB_CMDLINE_LINUX=" /etc/default/grub | cut -d'"' -f2)
    if echo "$CURRENT_CMDLINE" | grep -q "lsm="; then
        # Replace existing lsm= parameter
        NEW_CMDLINE=$(echo "$CURRENT_CMDLINE" | sed 's/lsm=[^ ]*/lsm=landlock,lockdown,yama,integrity,bpf/')
    else
        NEW_CMDLINE="$CURRENT_CMDLINE lsm=landlock,lockdown,yama,integrity,bpf"
    fi
    
    sed -i "s|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"$NEW_CMDLINE\"|" /etc/default/grub
    update-grub 2>/dev/null || grub-mkconfig -o /boot/grub/grub.cfg
    
    echo "GRUB updated. Rebooting in 5 seconds..."
    echo "(Press Ctrl+C to cancel)"
    sleep 5
    reboot
fi

# Method 2: Direct kernel parameter (for live USB without GRUB)
echo ""
echo "No GRUB found (Live USB?). To enable BPF LSM on a live session:"
echo ""
echo "  1. Reboot the machine"
echo "  2. At the GRUB boot menu, press 'e' to edit"
echo "  3. Find the line starting with 'linux'"
echo "  4. Add at the end: lsm=landlock,lockdown,yama,integrity,bpf"
echo "  5. Press Ctrl+X or F10 to boot"
echo ""
echo "After boot, verify with: cat /sys/kernel/security/lsm"
echo "Then re-run: ./scripts/00_coronation.sh"
