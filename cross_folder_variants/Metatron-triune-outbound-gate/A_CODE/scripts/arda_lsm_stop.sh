#!/usr/bin/env bash
set -euo pipefail

NAME="${ARDA_LSM_CONTAINER_NAME:-arda-lsm-loader}"

echo "[ARDA_LSM] Stopping loader container: $NAME"
docker rm -f "$NAME" >/dev/null 2>&1 || true
echo "[ARDA_LSM] Stopped."

