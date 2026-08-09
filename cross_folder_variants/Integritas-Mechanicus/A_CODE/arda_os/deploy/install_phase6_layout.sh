#!/bin/sh
set -eu

PREFIX="${1:-/opt/arda}"
ETC_DIR="${2:-/etc/arda}"
VAR_LIB_DIR="${3:-/var/lib/arda}"
VAR_LOG_DIR="${4:-/var/log/arda}"
SYSTEMD_DIR="${5:-/etc/systemd/system}"
BPF_FS_DIR="${6:-/sys/fs/bpf/arda}"

mkdir -p "${PREFIX}"
mkdir -p "${ETC_DIR}/policy" "${ETC_DIR}/sealed"
mkdir -p "${VAR_LIB_DIR}/attestation/latest" "${VAR_LIB_DIR}/projection" "${VAR_LIB_DIR}/ledger"
mkdir -p "${VAR_LOG_DIR}" "${VAR_LOG_DIR}/exports"
mkdir -p "${SYSTEMD_DIR}"
if [ -d /sys/fs/bpf ]; then
    mkdir -p "${BPF_FS_DIR}" || true
fi

echo "Phase 6 layout prepared:"
echo "  prefix: ${PREFIX}"
echo "  etc: ${ETC_DIR}"
echo "  var_lib: ${VAR_LIB_DIR}"
echo "  var_log: ${VAR_LOG_DIR}"
echo "  systemd: ${SYSTEMD_DIR}"
echo "  bpffs: ${BPF_FS_DIR}"
echo
echo "Next steps:"
echo "  1. Copy the repository to ${PREFIX}/arda_os"
echo "  2. Install ${ETC_DIR}/arda.env from deploy/etc/arda.env.example"
echo "  3. Place active_bundle.json and active_projection_plan.json under ${ETC_DIR}/policy/"
echo "  4. Copy systemd units from deploy/systemd/ into ${SYSTEMD_DIR}"
echo "  5. If auditd is present, ensure execve rules are enabled for ${VAR_LIB_DIR} and ${VAR_LOG_DIR} evidence paths"
