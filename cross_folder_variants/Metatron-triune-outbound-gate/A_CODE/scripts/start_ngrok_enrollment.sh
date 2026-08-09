#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_PORT="${DASHBOARD_PORT:-3000}"
PUBLIC_PORT="${PUBLIC_PORT:-3000}"
NGROK_BIN="${NGROK_BIN:-ngrok}"
LOG_DIR="${SERAPH_LOG_DIR:-./logs}"
NGROK_DOMAIN="${SERAPH_NGROK_DOMAIN:-devious-viability-linked.ngrok-free.dev}"
DEFAULT_NGROK_CONFIG="${HOME}/.config/ngrok/ngrok.yml"
ENABLE_DASHBOARD_TUNNEL="${SERAPH_ENABLE_DASHBOARD_TUNNEL:-0}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: SERAPH_NGROK_DOMAIN=devious-viability-linked.ngrok-free.dev PUBLIC_PORT=3000 SERAPH_ENABLE_DASHBOARD_TUNNEL=0 $0"
  echo "Requires: ngrok config add-authtoken <token>"
  exit 0
fi

mkdir -p "$LOG_DIR"

if ! command -v "$NGROK_BIN" >/dev/null 2>&1; then
  echo "ngrok is not installed or not on PATH."
  echo "Install it, then run: ngrok config add-authtoken <token>"
  exit 127
fi

if ! "$NGROK_BIN" config check >/dev/null 2>&1; then
  echo "ngrok config is missing or invalid. Run: ngrok config add-authtoken <token>"
  exit 1
fi

cat > "$LOG_DIR/ngrok-seraph.yml" <<YAML
version: "2"
tunnels:
  seraph-public:
    proto: http
    addr: ${PUBLIC_PORT}
    domain: ${NGROK_DOMAIN}
YAML

if [[ "$ENABLE_DASHBOARD_TUNNEL" == "1" ]]; then
cat >> "$LOG_DIR/ngrok-seraph.yml" <<YAML
  seraph-dashboard-local:
    proto: http
    addr: ${DASHBOARD_PORT}
YAML
fi

echo "Starting ngrok tunnels:"
echo "  public enrollment/API -> https://${NGROK_DOMAIN}/enroll"
echo "  backend API           -> https://${NGROK_DOMAIN}/api"
if [[ "$ENABLE_DASHBOARD_TUNNEL" == "1" ]]; then
  echo "  local dashboard tunnel -> random ngrok URL -> localhost:${DASHBOARD_PORT}"
fi
echo "Export SERAPH_PUBLIC_URL=https://${NGROK_DOMAIN}"
echo "Export SERAPH_BACKEND_URL=https://${NGROK_DOMAIN}"

# Avoid duplicate ngrok sessions that can leave stale or conflicting tunnels.
pkill -f "ngrok start --all" >/dev/null 2>&1 || true

# Keep the default config in scope so authtoken is not lost when using a custom tunnel file.
exec "$NGROK_BIN" start --all --config "${DEFAULT_NGROK_CONFIG}" --config "$LOG_DIR/ngrok-seraph.yml"
