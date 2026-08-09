#!/bin/sh
set -eu

REPO_ROOT="${1:-/home/byron/Integritas-Mechanicus}"

cd "${REPO_ROOT}"

sudo bash arda_os/deploy/boot/install_arda_boot_theme.sh \
  /boot/grub/themes/arda-sovereign \
  /usr/share/plymouth/themes/arda-sovereign \
  /usr/share/plymouth/themes/arda-mirror-gate

sudo sed -i 's|^GRUB_THEME=.*|GRUB_THEME="/boot/grub/themes/arda-sovereign/theme.txt"|' /etc/default/grub
sudo grep -q '^GRUB_THEME=' /etc/default/grub || \
  echo 'GRUB_THEME="/boot/grub/themes/arda-sovereign/theme.txt"' | sudo tee -a /etc/default/grub

sudo update-grub
sudo plymouth-set-default-theme -R arda-mirror-gate

echo
echo "ARDA boot themes refreshed."
echo "Reboot to test the corrected GRUB + Plymouth transition."
