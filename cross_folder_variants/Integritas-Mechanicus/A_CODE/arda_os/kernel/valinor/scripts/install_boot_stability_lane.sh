#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VALINOR_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ARDA_OS_DIR=$(CDPATH= cd -- "$VALINOR_DIR/../.." && pwd)
SYSTEMD_SRC="$VALINOR_DIR/releases/systemd"
SYSTEMD_DST="/etc/systemd/system"
ENV_FILE="/etc/arda/attested-host.env"

if [ "$(id -u)" -ne 0 ]; then
  echo "ARDA_BOOT_STABILITY: run with sudo" >&2
  exit 1
fi

install -d -m 0755 /etc/arda
if [ ! -f "$ENV_FILE" ]; then
  install -m 0644 "$ARDA_OS_DIR/deploy/etc/arda-attested-host.env.example" "$ENV_FILE"
fi

if grep -q '^ARDA_POSTBOOT_PROMOTE_STRICT=' "$ENV_FILE"; then
  sed -i 's/^ARDA_POSTBOOT_PROMOTE_STRICT=.*/ARDA_POSTBOOT_PROMOTE_STRICT=0/' "$ENV_FILE"
else
  printf '\nARDA_POSTBOOT_PROMOTE_STRICT=0\n' >> "$ENV_FILE"
fi

install -m 0644 "$SYSTEMD_SRC/arda-valinor-boot-audit.service" "$SYSTEMD_DST/arda-valinor-boot-audit.service"
install -m 0644 "$SYSTEMD_SRC/arda-valinor-postboot.service" "$SYSTEMD_DST/arda-valinor-postboot.service"

for unit in getty@tty1.service lightdm.service display-manager.service systemd-user-sessions.service; do
  install -d -m 0755 "$SYSTEMD_DST/$unit.d"
  install -m 0644 "$SYSTEMD_SRC/$unit.d/override.conf" "$SYSTEMD_DST/$unit.d/override.conf"
done

systemctl daemon-reload
systemctl enable arda-valinor-boot-audit.service
systemctl enable arda-valinor-postboot.service

echo "ARDA_BOOT_STABILITY: installed"
echo "ARDA_BOOT_STABILITY: ARDA_POSTBOOT_PROMOTE_STRICT=0"
echo "ARDA_BOOT_STABILITY: reboot, then inspect systemctl --failed"
