#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BPF_DIR="${BPF_DIR:-$ROOT_DIR/backend/services/bpf}"
IMAGE="${ARDA_LSM_IMAGE:-seraph-sandbox-tools:latest}"
NAME="${ARDA_LSM_CONTAINER_NAME:-arda-lsm-loader}"
ENFORCE_PERMANENT="${ARDA_ENFORCE_PERMANENT:-0}"
CONFIRM_PERMANENT="${ARDA_CONFIRM_PERMANENT:-}"
DISABLE_PERMANENT_FAILSAFE="${ARDA_DISABLE_PERMANENT_FAILSAFE:-0}"
ENFORCE_SECONDS="${ARDA_ENFORCE_SECONDS:-0}"
DELAY_SECONDS="${ARDA_ENFORCE_DELAY_SECONDS:-0}"
FAILSAFE_SECONDS="${ARDA_FAILSAFE_SECONDS:-120}"
MAX_SEED="${ARDA_MAX_SEED:-8000}"
MIN_SEED="${ARDA_MIN_SEED:-64}"
READY_TIMEOUT_SECONDS="${ARDA_READY_TIMEOUT_SECONDS:-30}"
LOADER_BIN="${ARDA_LSM_LOADER_BIN:-/bpf/arda_lsm_loader}"
SEED_POLICY_FILE="${ARDA_SEED_POLICY_FILE:-$ROOT_DIR/config/arda/harmony_seed_policy.json}"

if [[ ! -d "$BPF_DIR" ]]; then
  echo "[ARDA_LSM] BPF dir not found: $BPF_DIR" >&2
  exit 1
fi

if [[ "$ENFORCE_PERMANENT" == "1" && "$CONFIRM_PERMANENT" != "I_UNDERSTAND_LOCKOUT_RISK" ]]; then
  echo "[ARDA_LSM] Refusing permanent enforcement without ARDA_CONFIRM_PERMANENT=I_UNDERSTAND_LOCKOUT_RISK" >&2
  echo "[ARDA_LSM] Start AUDIT mode first, verify SEED_TOTAL, then use a short ARDA_ENFORCE_SECONDS pulse." >&2
  exit 2
fi

echo "[ARDA_LSM] Starting loader container: $NAME"
echo "[ARDA_LSM] Image: $IMAGE"
echo "[ARDA_LSM] BPF dir: $BPF_DIR"
echo "[ARDA_LSM] Loader bin: $LOADER_BIN"
if [[ "$ENFORCE_PERMANENT" == "1" ]]; then
  echo "[ARDA_LSM] Mode: PERMANENT enforcement requested with explicit confirmation"
  echo "[ARDA_LSM] Permanent failsafe seconds: $FAILSAFE_SECONDS"
  echo "[ARDA_LSM] ESCAPE HATCH: docker stop $NAME  — disables enforcement immediately"
else
  echo "[ARDA_LSM] NOTE: Defaults to AUDIT mode unless enforcement is enabled."
  echo "[ARDA_LSM] Enforcement pulse seconds: $ENFORCE_SECONDS"
  echo "[ARDA_LSM] Enforcement delay seconds: $DELAY_SECONDS"
  echo "[ARDA_LSM] Enforcement failsafe seconds: $FAILSAFE_SECONDS"
fi
echo "[ARDA_LSM] Max seed entries: $MAX_SEED"
echo "[ARDA_LSM] Min seed entries for enforcement: $MIN_SEED"
echo "[ARDA_LSM] Ready timeout seconds: $READY_TIMEOUT_SECONDS"
echo "[ARDA_LSM] Seed policy file: $SEED_POLICY_FILE"

docker rm -f "$NAME" >/dev/null 2>&1 || true

SEED_ARGS=()
if [[ -f "$SEED_POLICY_FILE" ]]; then
  # Convert JSON policy -> loader args (keeps the loader CLI stable and simple).
  mapfile -t SEED_ARGS < <(
    python3 - "$SEED_POLICY_FILE" <<'PY'
import json, sys, os, pwd

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    policy = json.load(f)

max_seed = int(policy.get("max_seed", 8000))
print("--max-seed")
print(str(max_seed))

policy_min_seed = int(policy.get("min_seed_for_enforce", 0))
env_min_seed = int(os.environ.get("ARDA_MIN_SEED", 64))
min_seed = max(policy_min_seed, env_min_seed)
print("--min-seed")
print(str(min_seed))

# Explicit individual paths
for p in policy.get("seed_paths", []) or []:
    if not isinstance(p, str) or not p:
        continue
    print("--seed-path")
    print(p)

# Flat directories
for d in policy.get("seed_exec_dirs", []) or []:
    if not isinstance(d, str) or not d:
        continue
    print("--seed-exec-dir")
    print(d)

# Recursive directories
for d in policy.get("seed_exec_dirs_recursive", []) or []:
    if not isinstance(d, str) or not d:
        continue
    print("--seed-exec-dir-recursive")
    print(d)

# Expand user home paths: ~user/bin, ~user/.local/bin for all real users
if policy.get("seed_user_home_bins", False):
    for pw in pwd.getpwall():
        if pw.pw_uid < 1000:
            continue
        for subdir in ["bin", ".local/bin", "go/bin", ".cargo/bin"]:
            p = os.path.join(pw.pw_dir, subdir)
            # Emit as host path — the container mounts / at /host
            print("--seed-exec-dir")
            print(f"/host{p}")

# Running processes (always on when seed_running_processes is set)
if policy.get("seed_running_processes", False):
    print("--seed-running-procs")
PY
  )
else
  SEED_ARGS=(--max-seed "$MAX_SEED" --min-seed "$MIN_SEED" --seed-path /opt/pwsh/pwsh \
    --seed-exec-dir /host/bin --seed-exec-dir /host/sbin \
    --seed-exec-dir /host/usr/bin --seed-exec-dir /host/usr/sbin \
    --seed-exec-dir /host/usr/local/bin --seed-exec-dir /host/usr/local/sbin \
    --seed-running-procs)
fi

# Build enforcement args
ENFORCE_ARGS=()
if [[ "$ENFORCE_PERMANENT" == "1" ]]; then
  ENFORCE_ARGS=(--permanent --confirm-permanent --failsafe-seconds "$FAILSAFE_SECONDS")
  if [[ "$DISABLE_PERMANENT_FAILSAFE" == "1" ]]; then
    ENFORCE_ARGS+=(--no-failsafe)
  fi
elif [[ "$ENFORCE_SECONDS" -gt 0 ]]; then
  ENFORCE_ARGS=(
    --delay-seconds "$DELAY_SECONDS"
    --failsafe-seconds "$FAILSAFE_SECONDS"
    --enforce-seconds "$ENFORCE_SECONDS"
  )
fi

docker run -d \
  --name "$NAME" \
  --privileged \
  --ulimit memlock=-1:-1 \
  -v "/:/host:ro" \
  -v "$ROOT_DIR/tools/powershell:/opt/pwsh:ro" \
  -v "$BPF_DIR:/bpf:ro" \
  "$IMAGE" \
  "$LOADER_BIN" /bpf/arda_physical_lsm.o \
    "${SEED_ARGS[@]}" \
    "${ENFORCE_ARGS[@]}" >/dev/null

echo "[ARDA_LSM] Loader started. Waiting for SEED_TOTAL..."
deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
ready=0
while [[ "$SECONDS" -lt "$deadline" ]]; do
  logs="$(docker logs "$NAME" 2>&1 || true)"
  if grep -q '^SEED_TOTAL:' <<<"$logs"; then
    ready=1
    break
  fi
  if grep -qE 'ERROR:|ENFORCEMENT_REFUSED:' <<<"$logs"; then
    ready=1
    break
  fi
  if ! docker ps --filter "name=^/${NAME}$" --format '{{.Names}}' | grep -qx "$NAME"; then
    break
  fi
  sleep 1
done

echo "[ARDA_LSM] Loader logs:"
docker logs --tail 80 "$NAME" || true

if [[ "$ready" != "1" ]]; then
  echo "[ARDA_LSM] Loader did not report SEED_TOTAL before timeout; stopping to avoid unsafe state." >&2
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  exit 3
fi
