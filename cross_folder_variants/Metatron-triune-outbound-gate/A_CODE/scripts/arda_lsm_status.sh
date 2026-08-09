#!/usr/bin/env bash
set -euo pipefail

NAME="${ARDA_LSM_CONTAINER_NAME:-arda-lsm-loader}"

if ! command -v docker >/dev/null 2>&1; then
  echo '{"running":false,"error":"docker not found"}'
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  echo '{"running":false,"error":"docker daemon unavailable"}'
  exit 0
fi

running="false"
status=""
if docker ps --filter "name=^/${NAME}$" --format '{{.Names}}' | grep -qx "$NAME"; then
  running="true"
  status="$(docker ps --filter "name=^/${NAME}$" --format '{{.Status}}' | head -1)"
fi

logs="$(docker logs "$NAME" 2>&1 || true)"
seed_total="$(sed -nE 's/^SEED_TOTAL:[[:space:]]*([0-9]+).*/\1/p' <<<"$logs" | tail -1)"
mode="unknown"
if grep -q 'ENFORCEMENT_SET: PERMANENT' <<<"$logs"; then
  mode="permanent"
elif grep -q 'ENFORCEMENT_SET: ENFORCE' <<<"$logs"; then
  mode="enforce"
elif grep -q 'ENFORCEMENT_REFUSED:' <<<"$logs"; then
  mode="audit_refused"
elif grep -q 'Mode=AUDIT' <<<"$logs" || grep -q 'ENFORCEMENT_SET: AUDIT' <<<"$logs"; then
  mode="audit"
fi

python3 - "$running" "$status" "${seed_total:-}" "$mode" "$NAME" <<'PY'
import json
import sys

running, status, seed_total, mode, name = sys.argv[1:6]
payload = {
    "container": name,
    "running": running == "true",
    "status": status,
    "mode_hint": mode,
    "seed_total": int(seed_total) if seed_total.isdigit() else None,
    "rescue_command": f"docker rm -f {name}",
}
print(json.dumps(payload, sort_keys=True))
PY
