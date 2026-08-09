#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$ROOT_DIR/.venv"

if [[ -f "$VENV_PATH/bin/activate" ]]; then
  # shellcheck disable=SC1090
  source "$VENV_PATH/bin/activate"
fi

echo "Starting canonical local dashboard on http://localhost:5000"
exec python "$ROOT_DIR/unified_agent/ui/web/app.py" --host 0.0.0.0 --port 5000
