#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage: build_valinor_kernel.sh --source-dir PATH [--jobs N] [--localversion -valinor] [--pkg-version VERSION] [--skip-config-check]

Build a Debian-compatible Valinor kernel package from an existing Linux source
tree. This script does not install packages or mutate boot entries.
EOF
}

SOURCE_DIR=
JOBS=1
LOCALVERSION=-valinor
PKG_VERSION=
SKIP_CONFIG_CHECK=0
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VALINOR_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source-dir)
      SOURCE_DIR=$2
      shift 2
      ;;
    --jobs)
      JOBS=$2
      shift 2
      ;;
    --localversion)
      LOCALVERSION=$2
      shift 2
      ;;
    --pkg-version)
      PKG_VERSION=$2
      shift 2
      ;;
    --skip-config-check)
      SKIP_CONFIG_CHECK=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$SOURCE_DIR" ]; then
  echo "Missing --source-dir" >&2
  usage >&2
  exit 2
fi

if [ ! -d "$SOURCE_DIR" ]; then
  echo "Source directory not found: $SOURCE_DIR" >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/Makefile" ]; then
  echo "Source directory does not look like a Linux tree: $SOURCE_DIR" >&2
  exit 1
fi

cd "$SOURCE_DIR"

if [ ! -f .config ]; then
  echo "No .config found in source tree. Copy Valinor config.base first." >&2
  exit 1
fi

if [ "$SKIP_CONFIG_CHECK" -ne 1 ]; then
  "$SCRIPT_DIR/check_valinor_config.py" \
    --config "$SOURCE_DIR/.config" \
    --fragment "$VALINOR_DIR/config.fragment"
fi

make olddefconfig
if [ -n "$PKG_VERSION" ]; then
  make -j"$JOBS" bindeb-pkg LOCALVERSION="$LOCALVERSION" KDEB_PKGVERSION="$PKG_VERSION"
else
  make -j"$JOBS" bindeb-pkg LOCALVERSION="$LOCALVERSION"
fi
