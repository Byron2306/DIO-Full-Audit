#!/usr/bin/env bash
set -euo pipefail

# Robust PurpleSharp launcher with:
# - local execution mode (PowerShell + PurpleSharp module/exe available on host)
# - winrm execution mode (delegates to run_purplesharp.py)
# - explicit failure semantics when prerequisites are missing

OUTDIR="${OUTDIR:-/tmp}"
TARGET="${PURPLESHARP_TARGET:-}"
MODE="${PURPLESHARP_MODE:-auto}"   # auto | local | winrm
HOST="${PURPLESHARP_WINRM_HOST:-}"
USERNAME="${PURPLESHARP_WINRM_USERNAME:-}"
PASSWORD="${PURPLESHARP_WINRM_PASSWORD:-}"
POWERSHELL_CMD="${PURPLESHARP_POWERSHELL_CMD:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_RUNNER="$SCRIPT_DIR/run_purplesharp.py"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-auto}"; shift 2 ;;
    --host) HOST="${2:-}"; shift 2 ;;
    --username) USERNAME="${2:-}"; shift 2 ;;
    --password) PASSWORD="${2:-}"; shift 2 ;;
    --powershell) POWERSHELL_CMD="${2:-}"; shift 2 ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$OUTDIR"
TS="$(date +%Y%m%d%H%M%S)"
OUTFILE="$OUTDIR/purplesharp_${TS}.json"

emit_failure() {
  local msg="$1"
  printf '{"results":[{"status":"failed","message":"%s","target":"%s","mode":"%s"}]}\n' "$msg" "$TARGET" "$MODE" > "$OUTFILE"
  echo "$OUTFILE"
  exit 1
}

run_local() {
  local pwsh_bin=""
  if command -v pwsh >/dev/null 2>&1; then
    pwsh_bin="pwsh"
  elif command -v powershell >/dev/null 2>&1; then
    pwsh_bin="powershell"
  elif [[ -x "/opt/pwsh/pwsh" ]]; then
    pwsh_bin="/opt/pwsh/pwsh"
  elif [[ -x "/usr/bin/pwsh" ]]; then
    pwsh_bin="/usr/bin/pwsh"
  elif [[ -x "/usr/local/bin/pwsh" ]]; then
    pwsh_bin="/usr/local/bin/pwsh"
  fi
  [[ -n "$pwsh_bin" ]] || emit_failure "PowerShell runtime not found for local PurpleSharp execution"

  local default_cmd='try { Import-Module C:\\Tools\\PurpleSharp\\PurpleSharp.psm1 -ErrorAction Stop; $r = Invoke-PurpleSharp -OutputJson; $r | ConvertTo-Json -Depth 8 } catch { @{status="failed"; message=$_.Exception.Message} | ConvertTo-Json -Depth 8 }'
  local ps_cmd="${POWERSHELL_CMD:-$default_cmd}"

  local stdout_file="$OUTDIR/purplesharp_stdout_${TS}.txt"
  local stderr_file="$OUTDIR/purplesharp_stderr_${TS}.txt"
  if "$pwsh_bin" -NoProfile -NonInteractive -Command "$ps_cmd" >"$stdout_file" 2>"$stderr_file"; then
    if [[ -s "$stdout_file" ]]; then
      cat "$stdout_file" > "$OUTFILE"
    else
      printf '{"results":[{"status":"completed","message":"PurpleSharp local run returned no stdout","target":"%s"}]}\n' "$TARGET" > "$OUTFILE"
    fi
    return 0
  fi

  local err
  err="$(tr '\n' ' ' < "$stderr_file" | sed 's/"/\\"/g' || true)"
  printf '{"results":[{"status":"failed","message":"%s","target":"%s","mode":"local"}]}\n' "${err:-local PurpleSharp execution failed}" "$TARGET" > "$OUTFILE"
  return 1
}

run_winrm() {
  [[ -n "$HOST" ]] || emit_failure "WinRM host is required (--host or PURPLESHARP_WINRM_HOST)"
  [[ -n "$USERNAME" ]] || emit_failure "WinRM username is required (--username or PURPLESHARP_WINRM_USERNAME)"
  [[ -n "$PASSWORD" ]] || emit_failure "WinRM password is required (--password or PURPLESHARP_WINRM_PASSWORD)"
  [[ -f "$PY_RUNNER" ]] || emit_failure "WinRM runner missing: $PY_RUNNER"
  command -v python3 >/dev/null 2>&1 || emit_failure "python3 is required for WinRM mode"

  local runner_args=(python3 "$PY_RUNNER" --host "$HOST" --username "$USERNAME" --password "$PASSWORD" --outfile "$OUTFILE")
  if [[ -n "$POWERSHELL_CMD" ]]; then
    runner_args+=(--ps-cmd "$POWERSHELL_CMD")
  fi

  "${runner_args[@]}" || emit_failure "WinRM PurpleSharp execution failed"
  [[ -s "$OUTFILE" ]] || emit_failure "WinRM PurpleSharp produced empty output"
  return 0
}

if [[ "$MODE" == "local" ]]; then
  run_local || exit 1
elif [[ "$MODE" == "winrm" ]]; then
  run_winrm || exit 1
else
  if [[ -n "$HOST" ]]; then
    run_winrm || exit 1
  else
    run_local || exit 1
  fi
fi

echo "$OUTFILE"
