#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_SYSTEMD="${HOME}/.config/systemd/user"
DIO_CONFIG="${HOME}/.config/dio"
ENV_FILE="${DIO_CONFIG}/sovereign.env"

# Resolve the Python runtime from the deployment that actually exists.
# Operators may override this with DIO_PHASE9_PYTHON.
if [[ -n "${DIO_PHASE9_PYTHON:-}" ]]; then
  PYTHON_BIN="${DIO_PHASE9_PYTHON}"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
elif [[ -x "/srv/dio/presence/.venv/bin/python" ]]; then
  PYTHON_BIN="/srv/dio/presence/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3 || true)"
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "No usable Python runtime found for Phase 9." >&2
  exit 2
fi

ENABLE=0
ENABLE_PRESENCE=0
ENABLE_TELEGRAM=0
ENABLE_MAIL=0
ENABLE_PAYPAL=0
PUBLIC_EDGE=0
DISABLE_LEGACY=0
DISABLE_LEGACY_SYSTEM=0
TELEGRAM_CUTOVER=0

usage() {
  cat <<'EOF'
Usage: scripts/install_phase9_local_runtime.sh [options]

Options:
  --enable              Enable/start all core local Phase 9 services.
  --enable-presence     Enable/start only local Presence Core.
  --enable-telegram     Enable/start only Telegram long polling.
  --enable-mail         Enable/start only Outlook delta polling.
  --enable-paypal       Enable/start only PayPal provider polling.
  --public-edge         Also enable local public intake service.
  --telegram-cutover    Delete Telegram webhook and begin long polling.
  --disable-legacy      Disable legacy user-level edge/reconciler services.
  --disable-legacy-system
                        Disable the legacy system-level Vesper Cloudflare
                        reconciler (requires sudo/root authority).
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
    --enable-presence) ENABLE_PRESENCE=1 ;;
    --enable-telegram) ENABLE_TELEGRAM=1 ;;
    --enable-mail) ENABLE_MAIL=1 ;;
    --enable-paypal) ENABLE_PAYPAL=1 ;;
    --public-edge) PUBLIC_EDGE=1 ;;
    --disable-legacy) DISABLE_LEGACY=1 ;;
    --disable-legacy-system) DISABLE_LEGACY_SYSTEM=1 ;;
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
  sed \
    -e "s|%h/DIO-Full-Audit/.venv/bin/python|$PYTHON_BIN|g" \
    -e "s|%h/DIO-Full-Audit|$ROOT|g" \
    "$service" > "$target"
done

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/config/dio_sovereign.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Created $ENV_FILE from the safe template."
  echo "Fill its REPLACE_* values before enabling services."
fi

systemctl --user daemon-reload

echo "Phase 9 checkout: $ROOT"
echo "Phase 9 Python:   $PYTHON_BIN"

require_env_values() {
  local missing=0 key value
  for key in "$@"; do
    value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
    if [[ -z "$value" || "$value" == REPLACE_* || "$value" == *"REPLACE_"* ]]; then
      echo "Missing/placeholder Phase 9 value: $key" >&2
      missing=1
    fi
  done
  [[ "$missing" -eq 0 ]]
}

enable_presence() {
  require_env_values \
    DIO_PRESENCE_LLM_PROVIDER \
    OLLAMA_URL \
    OLLAMA_MODEL \
    DIO_PRESENCE_OPERATOR_SHARED_SECRET \
    DIO_PRESENCE_PUBLIC_SHARED_SECRET \
    DIO_PRESENCE_IDENTITY_SALT \
    DIO_PRESENCE_OPERATOR_TOKEN
  systemctl --user enable --now dio-presence-local.service
}

enable_telegram() {
  require_env_values \
    DIO_PRESENCE_OPERATOR_SHARED_SECRET \
    DIO_TELEGRAM_OPERATOR_BOT_TOKEN \
    DIO_OPERATOR_TELEGRAM_IDS
  systemctl --user enable --now dio-telegram-operator-poller.service
}

enable_mail() {
  systemctl --user enable --now dio-outlook-delta-poller.service
}

enable_paypal() {
  require_env_values PAYPAL_CLIENT_ID PAYPAL_CLIENT_SECRET
  systemctl --user enable --now dio-paypal-poller.service
}

if [[ "$ENABLE" -eq 1 ]]; then
  enable_presence
  enable_telegram
  enable_mail
  enable_paypal
elif [[ "$ENABLE_PRESENCE" -eq 1 || "$ENABLE_TELEGRAM" -eq 1 || "$ENABLE_MAIL" -eq 1 || "$ENABLE_PAYPAL" -eq 1 ]]; then
  [[ "$ENABLE_PRESENCE" -eq 1 ]] && enable_presence
  [[ "$ENABLE_TELEGRAM" -eq 1 ]] && enable_telegram
  [[ "$ENABLE_MAIL" -eq 1 ]] && enable_mail
  [[ "$ENABLE_PAYPAL" -eq 1 ]] && enable_paypal
fi

if [[ "$PUBLIC_EDGE" -eq 1 ]]; then
  systemctl --user enable --now dio-public-edge-local.service
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
  "$PYTHON_BIN" "$ROOT/scripts/poll_vesper_telegram.py" \
    --surface operator \
    --drop-webhook \
    --once \
    --timeout 1
  systemctl --user restart dio-telegram-operator-poller.service
fi

if [[ "$DISABLE_LEGACY" -eq 1 ]]; then
  for unit in \
    dio-edge-reconciler.service \
    dio-commerce-processor.service \
    dio-graph-mail-processor.service \
    dio-graph-subscription-renew.timer
  do
    systemctl --user disable --now "$unit" 2>/dev/null || true
  done
fi

if [[ "$DISABLE_LEGACY_SYSTEM" -eq 1 ]]; then
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required for --disable-legacy-system." >&2
    exit 2
  fi
  sudo systemctl disable --now dio-vesper-reconciler.service
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
