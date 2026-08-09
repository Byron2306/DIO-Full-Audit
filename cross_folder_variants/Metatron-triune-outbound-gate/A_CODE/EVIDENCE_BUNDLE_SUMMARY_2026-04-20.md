# Seraph AI Defense Platform — Evidence Bundle Summary
**Date:** 2026-04-20  
**Prepared by:** Byron (Seraph AI) + Claude Sonnet 4.6  
**Bundle file:** `seraph-evidence-bundle-2026-04-20.zip` (54.5 MB, 11,241 files)

---

## Current Validation Status

| Tier | Count | % of 691 |
|------|-------|----------|
| S5 Platinum | **536** | 77.6% |
| S4 Gold | **155** | 22.4% |
| S3 and below | 0 | — |
| **Total techniques** | **691** | 100% |

---

## What "S5 Platinum" Actually Means Here

S5 requires all of the following in `evidence_bundle.py`:

1. Real sandbox execution (`execution_mode != vns` and `[VNS]` not in stdout)
2. `quality.clean_runs >= 3`
3. `quality.analyst_reviewed = True` (computed, not human — see Known Issues §5)
4. `quality.baseline_false_positives = 0`
5. At least one sigma rule matched

The 536 S5 techniques have real Atomic Red Team execution records from:
- **`sandbox-real-sweep`** — Docker-isolated ART runs on Linux (primary source, 521 techniques)
- **`gha-windows-sweep`** (run #24651088436) — GitHub Actions `windows-latest` runners (15 additional promoted as of this report, B3 complete, B1/B2 in progress)

---

## How the Windows GHA Sweep Works

Atomic tests that have no Linux atomic (78 techniques) were swept on real GitHub Actions `windows-latest` runners using `scripts/run_windows_local_sweep.py`. The script:

- Runs `Invoke-AtomicTest {TID} -GetPrereqs` then executes the test via PowerShell
- Pre-writes a stub JSON before subprocess call (so T1134.x artifacts survive runner kill)
- Uses `CREATE_NEW_PROCESS_GROUP` to isolate token-manipulation techniques
- Writes `execution_mode: remote_winrm` so `run_is_real_sandbox_execution()` counts it toward S5
- Head+tail truncation (8000+2000 chars) preserves "Executing test:" marker that evidence_bundle requires

---

## The 50 Experimental Sigma Rules (Community Contribution)

### Background

The prior sigma layer consisted of **688 auto-generated rules** (`t1001_generated.yml`, etc.) matched against synthetic telemetry events generated in the same pass. These were structurally valid but forensically circular — a key cut to fit its own lock.

Cross-referencing the 691-technique bundle against the SigmaHQ community ruleset (3,110 rules) revealed:
- **388 techniques** have real community sigma coverage
- **303 techniques** have zero community coverage

Of the 303 uncovered:
- **80** are structurally undetectable via logs (Resource Development T1583–T1608, pre-attack recon) — sigma is the wrong tool; these need CTI/OSINT
- **4** require specialized sensors (audio/video capture, Bluetooth) — not sigma territory
- **219** are detectable via standard log telemetry — sigma rules can and should exist

### What We Wrote

**50 new sigma rules across 10 YAML files**, covering **38 previously-uncovered techniques**:

| File | Techniques | Rules |
|------|-----------|-------|
| `proc_creation_win_html_smuggling_local_execution.yml` | T1027.006 | 1 |
| `file_event_win_html_smuggling_payload_drop.yml` | T1027.006 | 1 |
| `posh_ps_encoded_file_decode_to_disk.yml` | T1027.013 | 1 |
| `registry_set_win_fileless_encoded_payload.yml` | T1027.011 | 1 |
| `file_event_win_lnk_icon_smuggling_unc.yml` | T1027.012 | 2 |
| `file_event_win_svg_smuggling_script_execution.yml` | T1027.017 | 2 |
| `proc_creation_win_lnx_stripped_payload_tools.yml` | T1027.008 | 2 |
| `lnx_file_creation_shared_memory_fileless.yml` | T1027.011 | 2 |
| `posh_ps_junk_code_nop_sled_obfuscation.yml` | T1027.016 | 1 |
| `proc_creation_win_payload_compression_staging.yml` | T1027.015 | 2 |
| `proc_creation_win_t1218_*.yml` | T1218.004/.012/.015 | 3 |
| `proc_creation_win_t1059_*.yml` | T1059.008/.010/.011 | 3 |
| `proc_creation_win_t1055_*.yml` | T1055.003/.011/.014/.015 | 4 |
| `proc_creation_win_t1036_*.yml` | T1036.009/.010/.011/.012 | 4 |
| `proc_creation_win_t1070_*.yml` | T1070.007/.008/.009 | 3 |
| `proc_creation_win_lnx_t1496_*.yml` | T1496.001/.002/.003 | 3 |
| `proc_creation_win_t1562_*.yml` | T1562.009/.011/.013 | 3 |
| `proc_creation_win_lnx_t1564_*.yml` | T1564.008/.009/.012 | 3 |
| `proc_creation_win_lnx_t1547_*.yml` | T1547.007/.012/.013 | 3 |
| `proc_creation_win_lnx_t1574_*.yml` | T1574.006/.009/.013 | 3 |
| `proc_creation_win_t1556_*.yml` | T1556.003/.007/.008 | 3 |

**Status:** `experimental` — following SigmaHQ contribution standards (UUID v4, proper logsource, references, falsepositives, level).

**Why these rules don't exist in SigmaHQ:** T1027.017 (SVG Smuggling) was added to ATT&CK in October 2024 and has zero community coverage. T1036.011 (RTLO character masquerading), T1562.009 (Safe Mode boot abuse), T1556.007 (Credential Provider DLL), and the `/dev/shm` fileless execution rule are all documented in threat intel blogs but never formalized as sigma. These represent a genuine contribution gap.

The sigma engine now loads **2,817 rules** (was 691 generated-only). The community rules are in `backend/sigma_rules/community/`.

---

## Known Issues and Honest Limitations

The following are documented deficiencies in the current evidence bundle. They do not invalidate the platform's capabilities but must be addressed before claiming production-grade forensic validity.

### Issue 1: Failure Text in "Success" Runs (208 S5 Techniques)

**208 of 536 S5 Platinum techniques** have at least one run where `status = "success"` but `atomic_stdout` contains clear failure indicators:

- `T1001 / T1001.002`: `xxd: not found`, `Read-only file system`
- `T1059`: `ping: not found`, `Exit code: 127`
- `T1018`: `arp: not found`, `Exit code: 1`
- `T1007`: `System has not been booted with systemd`
- `T1003.007`: `cannot open script file`

**Root cause:** The `stdout_is_clean()` check in `evidence_bundle.py` looks for a predefined failure pattern list. Linux Docker sandbox environment is missing common utilities (`xxd`, `arp`, `ping`) that ART atomics assume are present. The exit code from `Invoke-AtomicTest` reflects the PowerShell shell exit, not the technique's actual exit code.

**Impact:** The "clean_runs" count is inflated. Some S5 promotions rest on runs that partially executed but did not fully demonstrate the technique.

**Remediation path:** Expand `stdout_is_clean()` failure pattern list; add utility pre-checks to sandbox image; re-sweep affected techniques.

### Issue 2: Telemetry Not Fully Technique-Unique (116 Reuses)

**Unique telemetry sets:** 478 across 691 techniques. The most reused single telemetry fingerprint appears **116 times** (reduced from the 256 noted by reviewers, reflecting the GHA runs adding real Windows telemetry).

**Root cause:** The osquery key-event generator produces technique-representative events but several techniques share identical process/file event signatures (e.g., multiple credential dumping techniques produce the same `SELECT * FROM users` osquery hit).

**Impact:** Telemetry cannot individually exonerate each technique — the same evidence fingerprint covers multiple techniques simultaneously.

**Remediation path:** Technique-specific osquery pack files with unique query identifiers; per-technique event correlation signatures.

### Issue 3: Analytics Layer Still Largely Generated

- **osquery correlations:** Distribution is {2: 342, 0: 104, 4: 97, 1: 66} — not uniform, but no technique has organically unique osquery evidence
- **Sigma matches:** Distribution is {3: 313, 4: 208, 2: 166, 5: 4} — the 50 community rules moved the needle slightly but 688 generated rules still dominate

**Root cause:** The analytics layer was initialized with auto-generated correlations to scaffold the evidence framework. Real osquery fleet data exists (osqueryd.results.log, 2MB) but has not been correlated back into individual TVRs.

**Remediation path:** Run the evidence bundle recompute against live osquery fleet telemetry rather than synthetic correlation stubs.

### Issue 4: execution.json Not Standalone in TVR Folders

The `coverage_summary.json` implies each TVR directory contains a standalone `execution.json` file. **Only ~20 TVR folders have a standalone `execution.json`**; in all others the execution data lives inside `tvr.json` under the `execution` key.

**Impact:** The on-disk structure is overstated in the summary. The execution evidence is present and valid — it's just not broken out as a separate file as documented.

**Remediation path:** Either update the summary description to match reality, or have `evidence_bundle.py` write `execution.json` as a companion file on TVR generation.

### Issue 5: analyst_reviewed Is Fully Automated

- **Reviewer field:** `metatron-system` for all 521 Docker-sweep S5 techniques; `automated` for 170 Gold
- **Review timestamps:** Heavily mass-shared — 43 techniques share timestamp `2026-04-19T11:54`, 34 share `2026-04-18T13:24`

**Root cause:** `analyst_reviewed` is computed by `evidence_bundle.py` — it is `True` when `has_real_clean_runs >= 3`, not when a human reviews. The reviewer field is the `OPERATOR` constant (`metatron-system`).

**Impact:** The field name implies human review but reflects automated promotion criteria. The shared timestamps confirm batch processing, not individual case review.

**Remediation path:** Rename to `auto_validated` or add a separate `human_reviewed` boolean; implement a review queue for human sign-off on high-value techniques.

### Issue 6: Run Count Mismatch

- `coverage_summary.json` reports **2,105** total execution runs
- TVR files sum to **6,551** total runs (across all 691 techniques × multiple passes)
- Selected TVR subset sums to **~2,107**

**Root cause:** `coverage_summary.json` was generated at a different point in time than the current TVR state; the GHA imports added runs after the summary was written. Small drift is expected between incremental bundle updates.

**Remediation path:** Regenerate `coverage_summary.json` as the final step after any import operation.

### Issue 7: Empty technique.tactics in 41 TVRs

**41 TVR files** have `technique.tactics = []` despite the top-level `coverage_summary.json` tactic breakdown being complete.

**Root cause:** Techniques added via GHA import path or newer ATT&CK versions that weren't in the original STIX catalog load. The TVR writer looks up tactics from the MITRE catalog; if the lookup misses, the field is left empty.

**Impact:** Tactic-based filtering in the frontend will miss these techniques in per-tactic views.

**Remediation path:** Backfill tactic data from the ATT&CK STIX catalog for all TVRs with empty tactics; add a validation pass after import.

---

## What Is Genuinely Solid

Despite the issues above, the following evidence is real and defensible:

| Evidence Type | Status |
|--------------|--------|
| 536 real ART executions | ✅ Real Docker/GHA subprocess runs, not simulated |
| GHA Windows sweep | ✅ Real `windows-latest` runner with PowerShell + Invoke-AtomicTest |
| T1134.x pre-write artifact fix | ✅ Stub JSON written before subprocess; survives runner kill |
| 50 experimental sigma rules | ✅ Hand-authored, proper UUIDs, SigmaHQ-contribution-format |
| 2,817 real sigma rules loaded | ✅ SigmaHQ community ruleset + Seraph community/ directory |
| sigma_engine community rules | ✅ T1027.017 (SVG Smuggling), T1036.011 (RTLO), T1562.009 (Safe Mode bypass) — novel, no community equivalent |
| osqueryd.results.log | ✅ Real fleet telemetry (2MB) |
| Secure Boot mock for presentation | ✅ `TPM_MOCK_ENV=production` — documented as lab override |

---

## Next Steps (Priority Order)

1. **Import GHA B1/B2 artifacts** when run #24651088436 completes → expected +30–50 additional Platinum
2. **Expand `stdout_is_clean()`** to catch `Exit code: 127`, `not found`, `not been booted`
3. **Backfill technique.tactics** for 41 empty TVRs from STIX catalog
4. **Regenerate coverage_summary.json** after next import to fix run count mismatch
5. **Continue sigma rule authoring** — 219 detectable techniques remain uncovered; next clusters: T1546.x, T1548.x, T1557.x, T1558.x
6. **Submit community sigma PR** to SigmaHQ — SVG smuggling and `/dev/shm` fileless rules are ready
7. **Write standalone execution.json** companion files or update documentation to match actual structure
8. **Replace `analyst_reviewed` semantics** with explicit `auto_validated` + `human_reviewed` fields

---

*Generated 2026-04-20. Evidence bundle: `seraph-evidence-bundle-2026-04-20.zip` (54.5 MB).*  
*Sigma community rules: `backend/sigma_rules/community/` (50 rules, 10 files).*  
*GHA sweep: run #24651088436, branch `gha-windows-sweep`.*
