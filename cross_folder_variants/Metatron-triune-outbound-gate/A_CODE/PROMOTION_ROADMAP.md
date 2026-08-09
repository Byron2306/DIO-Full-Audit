# MITRE Evidence Tier Promotion Roadmap

**Goal:** Promote 119 techniques from S2/S3 → S5 (or as high as possible)

**Current State:** 475 S5 (Platinum) | 37 S3 (Silver) | 179 S2 (Bronze)

---

## Phase 1: Quick Wins (S3→S5) - 16 Atomic Runs

These 7 techniques already have execution evidence and just need reproducibility + baseline validation.

### 1.1 URGENT: T1480.002 (1 run = S5 immediately)
- **Current:** S3, 12 successful runs
- **Status:** Already meets reproducibility threshold
- **Action:** Run clean baseline validation + analyst review
- **Result:** S5 Platinum

### 1.2 EASY: T1176 (Browser Extensions) - 3 runs
- **Current:** S3, 4 runs, newly created Linux sigma rules
- **Runs needed:** 2-3 more for reproducibility + baseline
- **Includes:** 
  - T1176 parent (4 runs)
  - T1176.001 (need 3 direct runs, currently has 4 inherited)
  - T1176.002 (need 3 direct runs, currently has 4 inherited)
- **Action:** Execute T1176 atomic tests 3x to get direct evidence
- **Result:** T1176 + sub-techs → S5 Platinum

### 1.3 QUICK: T1037.003, T1543.005, T1569.003 (9 runs)
- **Current:** S3, 1 run each
- **Runs needed:** 2-3 more each for reproducibility
- **Action:** Execute each 2-3x + baseline validation
- **Result:** Each → S5 Platinum

**Phase 1 Total:** 16 atomic runs × 2-3 min avg = ~30-50 min execution time
**Expected Outcome:** 7 techniques → S5 Platinum (takes us to **482 S5 total**)

---

## Phase 2: Bulk Promotion (S2→S3+) - 67+ Atomic Runs

### 2.1 S2 Bronze (67 techniques with zero execution evidence)

All 67 have:
- 0 successful atomic execution runs
- Mixed sigma/osquery coverage (most unmapped)

#### Subset A: High-Value Tactics (estimate 25-30 techs)
- Command & Control
- Lateral Movement
- Exfiltration
- Persistence

**Action:** Run 1x each to reach S3, then 2-3x more for S5
- **Phase 2A-i:** 25-30 × 1 run = S3 Bronze→Silver
- **Phase 2A-ii:** 25-30 × 2-3 runs = S3→S4 (if sigma available)
- **Estimated:** 75-90 runs total for high-value subset

#### Subset B: Medium-Value Tactics (remaining ~40 techs)
- Discovery
- Reconnaissance  
- Resource Development
- Defense Evasion

**Action:** Run 1x minimum to reach S3, optional 2+ for higher tiers
- **Phase 2B:** 40 × 1 run minimum = S3 baseline
- **Optional:** +40-80 runs for S3→S4→S5 promotion

**Phase 2 Total (Minimum):** 67 runs (all to S3)
**Phase 2 Total (Maximum):** 150+ runs (target S4-S5 for high-value)

---

## Execution Strategy

### Week 1: Phase 1 (Quick Wins)
```bash
# Day 1-2: T1480.002 baseline + T1176 family
./scripts/run_inherited_technique_sweep.py \
  --techniques T1480.002,T1176,T1176.001,T1176.002 \
  --runs 3

# Day 3: T1037.003, T1543.005, T1569.003
./scripts/run_inherited_technique_sweep.py \
  --techniques T1037.003,T1543.005,T1569.003 \
  --runs 3
```

**Result:** 7 techniques promoted to S5 (482 total S5)

### Week 2-3: Phase 2 (Bulk Promotion)
```bash
# High-value tactics first
./scripts/run_inherited_technique_sweep.py \
  --techniques T1059,T1570,T1041,T1570,... (exec/lateral/exfil)
  --runs 3

# Then medium-value (as bandwidth allows)
./scripts/run_inherited_technique_sweep.py \
  --techniques T1082,T1580,... (discovery/reconnaissance)
  --runs 1  # Minimum to S3
```

---

## Success Metrics

| Milestone | Techs | S5 Count | Timeline |
|-----------|-------|----------|----------|
| Start | 696 | 475 | Day 0 |
| After Phase 1 | 696 | 482 | Day 3-5 |
| After Phase 2A (high-value) | 696 | 507-520 | Day 10-14 |
| After Phase 2B (full) | 696 | 540-560+ | Day 20-30 |

**Target:** 540+ S5 techniques (77%+ platinum rate)

---

## Blockers & Mitigations

| Blocker | Impact | Mitigation |
|---------|--------|-----------|
| Atomic tests timeout | T1176, others may exceed 120s | Increase timeout, run in container |
| No sigma rules | Blocks S4+ for unmapped techniques | Create sigma rules as needed |
| Baseline contamination | Fails clean baseline check | Fresh container between runs |
| Analyst review capacity | Final S5 sign-off bottleneck | Batch reviews after each phase |

---

## Implementation Notes

1. **T1176 Linux Sigma Rules:** Already created (file_event_lnx_browser_extension_install.yml, proc_creation_lnx_browsers_chromium_load_extension.yml)
2. **Inheritance Fix:** T1176.001/002 currently inherit from T1176—this is acceptable, but direct runs preferred
3. **Container Rebuild:** After each phase, rebuild coverage_summary and correlation index
4. **Analyst Review:** Schedule reviewers after Phase 1 to validate S5 verdicts

---

**Next Action:** Proceed with Phase 1 (Week 1)
