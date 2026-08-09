#!/bin/sh
set -eu

echo "ARDA PHASE 1 ROOT TEST"
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "cwd: $(pwd)"
echo ""

if [ "$(id -u)" != "0" ]; then
  echo "ARDA_ROOT_TEST: must be run as root" >&2
  exit 1
fi

: "${ARDA_LOADER_TIMEOUT_SECONDS:=20}"
export ARDA_LOADER_TIMEOUT_SECONDS
echo "loader_timeout_seconds: ${ARDA_LOADER_TIMEOUT_SECONDS}"
echo ""

echo "[1/5] host diagnostic"
sh bin/arda_phase1_host_diagnostic.sh
echo ""

echo "[2/5] rebuild canonical loader"
sh bin/build_arda_loader.sh
echo ""

echo "[3/5] rebuild canonical BPF object"
sh bin/build_arda_bpf.sh
echo ""

echo "[4/4] single-process status + native denial probe"
python3 bin/phase1_root_probe.py
