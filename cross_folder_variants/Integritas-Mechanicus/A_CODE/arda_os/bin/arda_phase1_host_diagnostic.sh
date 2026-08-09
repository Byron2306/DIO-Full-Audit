#!/bin/sh
set -eu

echo "ARDA PHASE 1 HOST DIAGNOSTIC"
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "cwd: $(pwd)"
echo ""

echo "[kernel]"
uname -r
echo ""

echo "[identity]"
id
echo ""

echo "[memlock]"
sh -c 'ulimit -l'
echo ""

echo "[bpf sysctl]"
if [ -r /proc/sys/kernel/unprivileged_bpf_disabled ]; then
  cat /proc/sys/kernel/unprivileged_bpf_disabled
else
  echo "unavailable"
fi
echo ""

echo "[active lsm]"
if [ -r /sys/kernel/security/lsm ]; then
  cat /sys/kernel/security/lsm
else
  echo "unavailable"
fi
echo ""

echo "[toolchain]"
command -v bpftool || true
command -v clang || true
command -v cc || true
echo ""

echo "[arda artifacts]"
ls -l backend/services/bpf/arda_physical_lsm.c || true
ls -l backend/services/bpf/arda_physical_lsm.o || true
ls -l backend/services/bpf/arda_lsm_loader.c || true
ls -l backend/services/bpf/arda_lsm_loader || true
