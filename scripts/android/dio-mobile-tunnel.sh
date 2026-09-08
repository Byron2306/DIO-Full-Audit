#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

DIO_USER="${DIO_USER:-byron}"
DIO_HOST="${DIO_HOST:-${1:-}}"
DIO_SSH_PORT="${DIO_SSH_PORT:-22}"
DIO_URL="http://127.0.0.1:8764/"

if [[ -z "${DIO_HOST}" ]]; then
  echo "DIO Mobile needs the Debian host."
  echo "Usage: DIO_HOST=192.168.x.x $0"
  echo "   or: $0 192.168.x.x"
  exit 2
fi

cleanup() {
  if [[ -n "${SSH_PID:-}" ]] && kill -0 "${SSH_PID}" 2>/dev/null; then
    kill "${SSH_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "DIO Mobile · opening encrypted localhost tunnel to ${DIO_USER}@${DIO_HOST}:${DIO_SSH_PORT}"
ssh -N \
  -p "${DIO_SSH_PORT}" \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 8764:127.0.0.1:8764 \
  -L 8765:127.0.0.1:8765 \
  -L 8766:127.0.0.1:8766 \
  -L 8770:127.0.0.1:8770 \
  "${DIO_USER}@${DIO_HOST}" &
SSH_PID=$!

for _ in $(seq 1 40); do
  if curl -fsS --max-time 1 "${DIO_URL}heartbeat" >/dev/null 2>&1; then
    echo "DIO Mobile · tunnel ready · ${DIO_URL}"
    if command -v termux-open-url >/dev/null 2>&1; then
      termux-open-url "${DIO_URL}"
    else
      echo "Open ${DIO_URL} in Chrome and install DIO to your home screen."
    fi
    wait "${SSH_PID}"
    exit $?
  fi

  if ! kill -0 "${SSH_PID}" 2>/dev/null; then
    echo "DIO Mobile · SSH tunnel exited before the launcher became reachable." >&2
    wait "${SSH_PID}" || true
    exit 1
  fi
  sleep 0.25
done

echo "DIO Mobile · launcher did not become reachable; closing tunnel." >&2
exit 1
