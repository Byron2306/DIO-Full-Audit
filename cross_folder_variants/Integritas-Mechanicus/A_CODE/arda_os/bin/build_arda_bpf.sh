#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ARDA_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SERVICE_BPF_DIR="$ARDA_ROOT/backend/services/bpf"
ROOT_BPF_DIR=$(CDPATH= cd -- "$ARDA_ROOT/.." && pwd)/bpf

SRC="$SERVICE_BPF_DIR/arda_physical_lsm.c"
OBJ="$SERVICE_BPF_DIR/arda_physical_lsm.o"
TMP_OBJ="$SERVICE_BPF_DIR/arda_physical_lsm.o.tmp.$$"
VMLINUX_HEADER="$ROOT_BPF_DIR/vmlinux.h"

if ! command -v clang >/dev/null 2>&1; then
  echo "ARDA_BUILD: missing clang for BPF compilation" >&2
  exit 1
fi

if [ ! -f "$VMLINUX_HEADER" ]; then
  echo "ARDA_BUILD: missing vmlinux.h at $VMLINUX_HEADER" >&2
  exit 1
fi

cleanup() {
  rm -f "$TMP_OBJ"
}
trap cleanup EXIT

echo "ARDA_BUILD: compiling $SRC -> $TMP_OBJ"
clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
  -I"$ROOT_BPF_DIR" \
  -c "$SRC" -o "$TMP_OBJ"

if mv "$TMP_OBJ" "$OBJ" 2>/dev/null; then
  :
else
  echo "ARDA_BUILD: compiled object is valid, but cannot replace $OBJ" >&2
  echo "ARDA_BUILD: run with sufficient permissions or install manually:" >&2
  echo "  sudo install -m 0644 $TMP_OBJ $OBJ" >&2
  trap - EXIT
  exit 1
fi
echo "ARDA_BUILD: BPF object ready at $OBJ"
