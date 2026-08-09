#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ARDA_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
BPF_DIR="$ARDA_ROOT/backend/services/bpf"
LOADER_SRC="$BPF_DIR/arda_lsm_loader.c"
LOADER_BIN="$BPF_DIR/arda_lsm_loader"

if ! command -v cc >/dev/null 2>&1; then
  echo "ARDA_BUILD: missing C compiler 'cc'" >&2
  exit 1
fi

if ! command -v pkg-config >/dev/null 2>&1; then
  echo "ARDA_BUILD: missing 'pkg-config' for libbpf discovery" >&2
  exit 1
fi

LIBBPF_CFLAGS=$(pkg-config --cflags libbpf 2>/dev/null || true)
LIBBPF_LIBS=$(pkg-config --libs libbpf 2>/dev/null || true)

if [ -z "$LIBBPF_LIBS" ]; then
  echo "ARDA_BUILD: libbpf development files not found via pkg-config" >&2
  exit 1
fi

echo "ARDA_BUILD: compiling $LOADER_SRC -> $LOADER_BIN"
# shellcheck disable=SC2086
cc -O2 -Wall -Wextra $LIBBPF_CFLAGS -o "$LOADER_BIN" "$LOADER_SRC" $LIBBPF_LIBS
echo "ARDA_BUILD: loader ready at $LOADER_BIN"
