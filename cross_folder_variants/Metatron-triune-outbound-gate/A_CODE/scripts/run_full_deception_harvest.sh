#!/usr/bin/env bash
# run_full_deception_harvest.sh
# =============================
# Master orchestrator for deception + BPF prevention evidence collection.
#
# Runs all three layers and imports results into the evidence bundle:
#   1. Falco BPF detection harvest   → T1003, T1046, T1556, T1548, T1082, ...
#   2. Deception/canary/honey-token  → T1083, T1005, T1078, T1110, T1595, T1046
#   3. ARDA BPF prevention suite     → All 14 tactics (requires sudo)
#   4. Import all run_*.json → regen TVRs → print tier promotion report
#
# Usage:
#   bash scripts/run_full_deception_harvest.sh
#   bash scripts/run_full_deception_harvest.sh --skip-arda      # skip ARDA (no sudo)
#   bash scripts/run_full_deception_harvest.sh --dry-run        # no writes
#   bash scripts/run_full_deception_harvest.sh --no-import      # harvest only
#
# Output:
#   artifacts/evidence/falco/           Falco run_*.json
#   artifacts/evidence/deception/       Canary + honey token run_*.json
#   artifacts/evidence/arda_prevention/ ARDA BPF prevention run_*.json
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"

# Defaults
DRY_RUN=""
SKIP_ARDA=0
SKIP_IMPORT=0
SINCE=""

for arg in "$@"; do
  case "$arg" in
    --dry-run)      DRY_RUN="--dry-run" ;;
    --skip-arda)    SKIP_ARDA=1 ;;
    --no-import)    SKIP_IMPORT=1 ;;
    --since=*)      SINCE="${arg#--since=}" ;;
  esac
done

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "=== Metatron Deception + BPF Prevention Evidence Harvest ==="
log "Repo: $REPO_ROOT"
log "Timestamp: $TIMESTAMP"
log ""

# ─────────────────────────────────────────────────────────────────────────────
# Layer 1: Falco BPF Detection Harvest
# ─────────────────────────────────────────────────────────────────────────────
log "=== Layer 1: Falco BPF Detection Harvest ==="
FALCO_ARGS=()
if [[ -n "$SINCE" ]]; then FALCO_ARGS+=(--since "$SINCE"); fi
if [[ -n "$DRY_RUN" ]]; then FALCO_ARGS+=("$DRY_RUN"); fi

python3 "$REPO_ROOT/scripts/harvest_falco_evidence.py" \
  --out-dir artifacts/evidence/falco \
  "${FALCO_ARGS[@]}" && FALCO_OK=1 || FALCO_OK=0

if [[ "$FALCO_OK" -eq 1 ]]; then
  FALCO_COUNT=$(find "$REPO_ROOT/artifacts/evidence/falco" -name "run_*.json" 2>/dev/null | wc -l)
  log "[OK] Falco: $FALCO_COUNT run records"
else
  log "[WARN] Falco harvest had errors (continuing)"
  FALCO_COUNT=0
fi
log ""

# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: Deception / Canary / Honey Token
# ─────────────────────────────────────────────────────────────────────────────
log "=== Layer 2: Deception Layer (canary + honeypot + honey-token) ==="
DECEPTION_ARGS=(--mode all)
if [[ -n "$DRY_RUN" ]]; then DECEPTION_ARGS+=("$DRY_RUN"); fi

python3 "$REPO_ROOT/scripts/harvest_deception_evidence.py" \
  --out-dir artifacts/evidence/deception \
  "${DECEPTION_ARGS[@]}" && DECEPTION_OK=1 || DECEPTION_OK=0

if [[ "$DECEPTION_OK" -eq 1 ]]; then
  DECEPTION_COUNT=$(find "$REPO_ROOT/artifacts/evidence/deception" -name "run_*.json" 2>/dev/null | wc -l)
  log "[OK] Deception: $DECEPTION_COUNT run records"
else
  log "[WARN] Deception harvest had errors (continuing)"
  DECEPTION_COUNT=0
fi
log ""

# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: ARDA BPF Prevention Suite (requires root)
# ─────────────────────────────────────────────────────────────────────────────
ARDA_COUNT=0
if [[ "$SKIP_ARDA" -eq 1 ]]; then
  log "=== Layer 3: ARDA BPF (SKIPPED — use --skip-arda=0 to enable) ==="
else
  log "=== Layer 3: ARDA BPF LSM Prevention Suite (requires sudo) ==="
  ARDA_ARGS=()
  if [[ -n "$DRY_RUN" ]]; then ARDA_ARGS+=("$DRY_RUN"); fi

  if [[ "$(id -u)" -ne 0 ]]; then
    log "[WARN] Not root. Using sudo for ARDA BPF suite..."
    sudo python3 "$REPO_ROOT/scripts/run_arda_bpf_suite.py" \
      --out-dir artifacts/evidence/arda_prevention \
      "${ARDA_ARGS[@]}" && ARDA_OK=1 || ARDA_OK=0
  else
    python3 "$REPO_ROOT/scripts/run_arda_bpf_suite.py" \
      --out-dir artifacts/evidence/arda_prevention \
      "${ARDA_ARGS[@]}" && ARDA_OK=1 || ARDA_OK=0
  fi

  if [[ "$ARDA_OK" -eq 1 ]]; then
    ARDA_COUNT=$(find "$REPO_ROOT/artifacts/evidence/arda_prevention" -name "run_*.json" 2>/dev/null | wc -l)
    log "[OK] ARDA: $ARDA_COUNT run records"
  else
    log "[WARN] ARDA suite had errors (continuing)"
  fi
fi
log ""

# ─────────────────────────────────────────────────────────────────────────────
# Layer 4: Import all evidence into TVR system
# ─────────────────────────────────────────────────────────────────────────────
TOTAL_RECORDS=$(( FALCO_COUNT + DECEPTION_COUNT + ARDA_COUNT ))
log "=== Summary: $TOTAL_RECORDS total run records ==="
log "  Falco:     $FALCO_COUNT"
log "  Deception: $DECEPTION_COUNT"
log "  ARDA BPF:  $ARDA_COUNT"
log ""

if [[ "$SKIP_IMPORT" -eq 1 ]]; then
  log "=== Import SKIPPED (--no-import). Run manually:"
  log "    python3 scripts/import_gha_artifacts.py --artifacts-dir artifacts/evidence/falco"
  log "    python3 scripts/import_gha_artifacts.py --artifacts-dir artifacts/evidence/deception"
  log "    python3 scripts/import_gha_artifacts.py --artifacts-dir artifacts/evidence/arda_prevention"
elif [[ -n "$DRY_RUN" ]]; then
  log "=== Import SKIPPED (dry-run mode)"
elif [[ "$TOTAL_RECORDS" -eq 0 ]]; then
  log "[WARN] No run records to import."
else
  log "=== Layer 4: Importing evidence into TVR system ==="

  for evidence_dir in \
    "$REPO_ROOT/artifacts/evidence/falco" \
    "$REPO_ROOT/artifacts/evidence/deception" \
    "$REPO_ROOT/artifacts/evidence/arda_prevention"; do

    if [[ ! -d "$evidence_dir" ]]; then continue; fi
    count=$(find "$evidence_dir" -name "run_*.json" 2>/dev/null | wc -l)
    if [[ "$count" -eq 0 ]]; then continue; fi

    layer=$(basename "$evidence_dir")
    log "  Importing $count records from $layer..."
    python3 "$REPO_ROOT/scripts/import_gha_artifacts.py" \
      --artifacts-dir "$evidence_dir" \
      --container seraph-backend && log "  [OK] $layer imported" || log "  [WARN] $layer import had errors"
  done

  log ""
  log "=== Import complete. TVRs regenerated. ==="
  log "    Check tier promotions in the Seraph dashboard or run:"
  log "    python3 scripts/cloud_sweep_import.py --local-only"
fi

log ""
log "=== Harvest complete: $TIMESTAMP ==="
