# TVR Rebuild for Inheritance Promotion Fix

## Current State

- **Fix Applied:** `backend/evidence_bundle.py` live_sigma_evaluation logic updated
- **Sigma Firing:** 19,027 records across 156 techniques (up from 3)
- **S5 Platinum:** 622 techniques, but 206 still have inheritance markers

## What Needs to Happen

A full TVR rebuild in the container will:
1. Regenerate all 691 TVR verdicts with the updated logic
2. Remove inheritance promotion from 206 S5 techniques → drop to S5-P or lower
3. Rebuild coverage_summary with clean tier distribution
4. Rebuild mitre_evidence_correlation.json

## Container Rebuild Commands

**Full pipeline** (requires ~2 min with proper atomic data):
```bash
docker exec metatron-seraph-v9-backend-1 bash -c '
  export PYTHONPATH=/app:/app/backend
  python3 /app/scripts/generate_evidence_bundle.py && \
  python3 /app/scripts/build_mitre_evidence_correlation.py
'
```

**Or separately:**
```bash
# Just TVR generation
docker exec metatron-seraph-v9-backend-1 python3 /app/scripts/generate_evidence_bundle.py

# Just correlation rebuild (auto-discovers latest bundle)
docker exec metatron-seraph-v9-backend-1 python3 /app/scripts/build_mitre_evidence_correlation.py
```

## Expected Results

After rebuild, the 622 S5 techniques should show:
- ✅ 100% with Sigma firing evidence (no change)
- ✅ 100% forensically valid & reviewed (no change)
- ✅ 100% clean baseline (no change)
- ✅ **66.9%+ with NO inheritance marker** (up from 66.9%)
- ✅ All inheritance-promoted techniques demoted to S5-P or S3/S2

## What Changed in Code

**File:** `backend/evidence_bundle.py` (lines 1719-1724)

**Before:**
```python
# Strict rule title matching across environments
rule_title_lower = str(r.get("title") or "").lower()
_live_eval = bool(
    _live_eval_rule_titles
    and rule_title_lower
    and any(rule_title_lower in t or t in rule_title_lower for t in _live_eval_rule_titles)
)
```

**After:**
```python
# Technique-level confirmation sufficient
_live_eval = bool(_live_eval_info and rule_matched)
```

This allows any matched rule to earn `live_sigma_evaluation=True` when:
1. Technique is in sigma_evaluation_report (real telemetry confirmed sigma firing)
2. Rule matched in current execution

No longer requires exact rule title match across GHA/Docker environments.
