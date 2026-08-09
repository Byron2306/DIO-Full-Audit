#!/bin/sh
set -eu

GRUB_THEME_DIR="${1:-/boot/grub/themes/arda-sovereign}"
PLYMOUTH_THEME_DIR="${2:-/usr/share/plymouth/themes/arda-sovereign}"
PLYMOUTH_MIRROR_THEME_DIR="${3:-/usr/share/plymouth/themes/arda-mirror-gate}"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

mkdir -p "${GRUB_THEME_DIR}" "${PLYMOUTH_THEME_DIR}"

cp "${SCRIPT_DIR}/themes/arda-grub/theme.txt" "${GRUB_THEME_DIR}/theme.txt"
cp "${SCRIPT_DIR}/themes/arda-grub/background.png" "${GRUB_THEME_DIR}/background.png"
cp "${SCRIPT_DIR}/themes/arda-grub/seal.png" "${GRUB_THEME_DIR}/seal.png"
cp "${SCRIPT_DIR}/themes/arda-grub/crown-bar.png" "${GRUB_THEME_DIR}/crown-bar.png"

cp "${SCRIPT_DIR}/themes/arda-plymouth/arda.plymouth" "${PLYMOUTH_THEME_DIR}/arda.plymouth"
cp "${SCRIPT_DIR}/themes/arda-plymouth/arda.plymouth" "${PLYMOUTH_THEME_DIR}/arda-sovereign.plymouth"
cp "${SCRIPT_DIR}/themes/arda-plymouth/arda.script" "${PLYMOUTH_THEME_DIR}/arda.script"
cp "${SCRIPT_DIR}/themes/arda-plymouth/background.png" "${PLYMOUTH_THEME_DIR}/background.png"
cp "${SCRIPT_DIR}/themes/arda-plymouth/seal.png" "${PLYMOUTH_THEME_DIR}/seal.png"

mkdir -p "${PLYMOUTH_MIRROR_THEME_DIR}"
cp "${SCRIPT_DIR}/themes/arda-plymouth-mirror/arda-mirror.plymouth" "${PLYMOUTH_MIRROR_THEME_DIR}/arda-mirror.plymouth"
cp "${SCRIPT_DIR}/themes/arda-plymouth-mirror/arda-mirror.plymouth" "${PLYMOUTH_MIRROR_THEME_DIR}/arda-mirror-gate.plymouth"
cp "${SCRIPT_DIR}/themes/arda-plymouth-mirror/arda-mirror.script" "${PLYMOUTH_MIRROR_THEME_DIR}/arda-mirror.script"
cp "${SCRIPT_DIR}/themes/arda-plymouth-mirror/background.png" "${PLYMOUTH_MIRROR_THEME_DIR}/background.png"
cp "${SCRIPT_DIR}/themes/arda-plymouth-mirror/mirror-gate.png" "${PLYMOUTH_MIRROR_THEME_DIR}/mirror-gate.png"
cp "${SCRIPT_DIR}/themes/arda-plymouth-mirror/seal.png" "${PLYMOUTH_MIRROR_THEME_DIR}/seal.png"

ln -sfn "${PLYMOUTH_MIRROR_THEME_DIR}" "$(dirname "${PLYMOUTH_MIRROR_THEME_DIR}")/arda-mirror"

cat <<EOF
ARDA boot themes installed.

Next steps:
  1. Set GRUB_THEME=\"${GRUB_THEME_DIR}/theme.txt\" in /etc/default/grub
  2. Run update-grub
  3. Run plymouth-set-default-theme -R arda-sovereign
     or plymouth-set-default-theme -R arda-mirror-gate
EOF
