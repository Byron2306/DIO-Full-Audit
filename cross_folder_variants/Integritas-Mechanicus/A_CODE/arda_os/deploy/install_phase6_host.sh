#!/bin/sh
set -eu

SOURCE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PREFIX="${PREFIX:-/opt/arda}"
ARDA_HOME="${ARDA_HOME:-${PREFIX}/arda_os}"
ETC_DIR="${ETC_DIR:-/etc/arda}"
VAR_LIB_DIR="${VAR_LIB_DIR:-/var/lib/arda}"
VAR_LOG_DIR="${VAR_LOG_DIR:-/var/log/arda}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
BPF_FS_DIR="${BPF_FS_DIR:-/sys/fs/bpf/arda}"
ENABLE_UNITS=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  install_phase6_host.sh [--dry-run] [--enable-units]

Environment overrides:
  PREFIX=/opt/arda
  ARDA_HOME=/opt/arda/arda_os
  ETC_DIR=/etc/arda
  VAR_LIB_DIR=/var/lib/arda
  VAR_LOG_DIR=/var/log/arda
  SYSTEMD_DIR=/etc/systemd/system
  BPF_FS_DIR=/sys/fs/bpf/arda

This installs Arda as a host-integrated OS substrate:
  - copies arda_os into /opt/arda/arda_os
  - prepares /etc/arda, /var/lib/arda, /var/log/arda, and bpffs paths
  - installs systemd units
  - compiles active policy and projection artifacts when missing
  - optionally enables the boot-chain units
EOF
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'DRY-RUN:'
    printf ' %s' "$@"
    printf '\n'
  else
    "$@"
  fi
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "error: install_phase6_host.sh must run as root" >&2
    exit 1
  fi
}

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    --enable-units)
      ENABLE_UNITS=1
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

require_root

echo "Installing Arda Phase 6 host substrate"
echo "source: ${SOURCE_ROOT}"
echo "target: ${ARDA_HOME}"

run mkdir -p "$PREFIX" "$ETC_DIR/policy" "$ETC_DIR/sealed"
run mkdir -p "$VAR_LIB_DIR/attestation/latest" "$VAR_LIB_DIR/projection" "$VAR_LIB_DIR/ledger"
run mkdir -p "$VAR_LOG_DIR" "$VAR_LOG_DIR/exports" "$SYSTEMD_DIR"
if [ -d /sys/fs/bpf ]; then
  run mkdir -p "$BPF_FS_DIR"
fi

if command -v rsync >/dev/null 2>&1; then
  run rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' "${SOURCE_ROOT}/" "${ARDA_HOME}/"
else
  run mkdir -p "$ARDA_HOME"
  run cp -R "${SOURCE_ROOT}/." "$ARDA_HOME/"
fi

if [ ! -f "$ETC_DIR/arda.env" ]; then
  run cp "$SOURCE_ROOT/deploy/etc/arda.env.example" "$ETC_DIR/arda.env"
fi

run cp "$SOURCE_ROOT/deploy/systemd/arda-loader.service" "$SYSTEMD_DIR/arda-loader.service"
run cp "$SOURCE_ROOT/deploy/systemd/arda-policy-projection.service" "$SYSTEMD_DIR/arda-policy-projection.service"
run cp "$SOURCE_ROOT/deploy/systemd/arda-attestation.service" "$SYSTEMD_DIR/arda-attestation.service"
run cp "$SOURCE_ROOT/deploy/systemd/arda-ledger.service" "$SYSTEMD_DIR/arda-ledger.service"
run cp "$SOURCE_ROOT/deploy/systemd/arda-seraph-fabric.service" "$SYSTEMD_DIR/arda-seraph-fabric.service"

if [ "$DRY_RUN" -eq 0 ]; then
  PYTHONPATH="$ARDA_HOME" "$ARDA_HOME/bin/arda" policy compile \
    --policy "$ARDA_HOME/arda_policy.json" \
    --output "$ETC_DIR/policy/active_bundle.json" \
    --verify-after
  PYTHONPATH="$ARDA_HOME" "$ARDA_HOME/bin/arda" policy projection \
    --bundle "$ETC_DIR/policy/active_bundle.json" \
    --output "$ETC_DIR/policy/active_projection_plan.json" \
    --enforcement-mode "${ARDA_ENFORCEMENT_MODE:-audit}" \
    --path /usr/bin/python3 \
    --path /bin/sh
  systemctl daemon-reload
  if [ "$ENABLE_UNITS" -eq 1 ]; then
    systemctl enable arda-loader.service arda-policy-projection.service arda-attestation.service arda-ledger.service
  fi
fi

echo
echo "Arda Phase 6 host substrate installed."
echo "Readiness gate:"
echo "  PYTHONPATH=${ARDA_HOME} ${ARDA_HOME}/bin/arda readiness"
