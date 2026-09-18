#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_SYSTEMD="${HOME}/.config/systemd/user"
DIO_CONFIG="${HOME}/.config/dio"
ENV_FILE="${DIO_CONFIG}/sovereign.env"

ENABLE=0
PUBLIC_EDGE=0
DISABLE_LEGACY=0
TELEGRAM_CUTOVER=0

usage() {
  cat <<'EOF'
Usage: scripts/install_phase9_local_runtime.sh [options]

Options:
  --enable              Enable/start core local Phase 9 services.
  --public-edge         Also enable local public intake service.
  --telegram-cutover    Delete Telegram webhook and begin long polling.
  --disable-legacy      Disable legacy Cloudflare edge/reconciler services.
  -h, --help            Show this help.

Safe order:
  1. run without flags to install service definitions
  2. edit ~/.config/dio/sovereign.env
  3. run --enable
  4. verify local health
  5. run --telegram-cutover
  6. only after live proof, run --disable-legacy
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --enable) ENABLE=1 ;;
    --public-edge) PUBLIC_EDGE=1 ;;
    --disable-legacy) DISABLE_LEGACY=1 ;;
    --telegram-cutover) TELEGRAM_CUTOVER=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$USER_SYSTEMD" "$DIO_CONFIG"
chmod 700 "$DIO_CONFIG"

for service in "$ROOT"/deploy/systemd/phase9/*.service; do
  target="$USER_SYSTEMD/$(basename "$service")"
  # Phase 9 may be deployed from /srv/dio/repo, ~/DIO-Full-Audit, or another
  # checkout. Bind the installed unit to the checkout that actually ran this
  # installer rather than assuming a home-directory clone.
  sed "s|%h/DIO-Full-Audit|$ROOT|g" "$service" > "$target"
done

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/config/dio_sovereign.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Created $ENV_FILE from the safe template."
  echo "Fill its REPLACE_* values before enabling services."
fi

systemctl --user daemon-reload

if [[ "$ENABLE" -eq 1 ]]; then
  if grep -q 'REPLACE_' "$ENV_FILE"; then
    echo "Refusing to enable Phase 9 services while $ENV_FILE contains REPLACE_* placeholders." >&2
    exit 2
  fi
  systemctl --user enable --now dio-presence-local.service
  systemctl --user enable --now dio-telegram-operator-poller.service
  systemctl --user enable --now dio-outlook-delta-poller.service
  systemctl --user enable --now dio-paypal-poller.service
  if [[ "$PUBLIC_EDGE" -eq 1 ]]; then
    systemctl --user enable --now dio-public-edge-local.service
  fi
fi

if [[ "$TELEGRAM_CUTOVER" -eq 1 ]]; then
  if grep -q 'REPLACE_' "$ENV_FILE"; then
    echo "Refusing Telegram cutover while sovereign.env contains placeholders." >&2
    exit 2
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  "$ROOT/.venv/bin/python" "$ROOT/scripts/poll_vesper_telegram.py"     --surface operator     --drop-webhook     --once     --timeout 1
  systemctl --user restart dio-telegram-operator-poller.service
fi

if [[ "$DISABLE_LEGACY" -eq 1 ]]; then
  for unit in     dio-edge-reconciler.service     dio-commerce-processor.service     dio-graph-mail-processor.service     dio-graph-subscription-renew.timer
  do
    systemctl --user disable --now "$unit" 2>/dev/null || true
  done
fi

echo
echo "DIO Phase 9 service state:"
for unit in   dio-presence-local.service   dio-telegram-operator-poller.service   dio-outlook-delta-poller.service   dio-paypal-poller.service   dio-public-edge-local.service
do
  printf '%-42s %s\n' "$unit" "$(systemctl --user is-active "$unit" 2>/dev/null || true)"
done

echo
echo "Legacy edge state:"
for unit in   dio-edge-reconciler.service   dio-commerce-processor.service   dio-graph-mail-processor.service   dio-graph-subscription-renew.timer
do
  printf '%-42s %s\n' "$unit" "$(systemctl --user is-active "$unit" 2>/dev/null || true)"
done
