# METATRON SERAPH REAL EVIDENCE UPGRADE PLAN
## From Scaffold to Forensic-Grade Proof

**Current State:** Multi-source corroboration scaffold (A0/L2/K2)  
**Target State:** Hard-positive validation (A2/L0/K0)  
**Timeline:** Parallel execution across 8 platforms

---

## Phase 1: REAL Kernel Prevention (K0 → observed)

### Current: 14 K0 (observed) + 653 K2 (deductive)
### Target: 100+ K0 by executing techniques live

**Execution Plan:**

1. **Expand Arda test suite**
   ```bash
   for technique in T1005 T1021 T1041 T1059 T1068 T1071 T1082 T1090 T1190 T1485 T1547 T1583 T1595 T1027 T1003
   do
     # Run 5 times each (not 3) to get more K0 samples
     run_atomic_red_team $technique --count 5 --capture-kernel-denial
     # Capture: deny_count_delta, auditd EPERM, exec rc, dmesg
   done
   ```

2. **Cover more tactic categories**
   - Currently: mainly Execution, Exfiltration, Persistence
   - Expand to: Discovery (T1018, T1046), Lateral Movement (T1021, T1570), Reconnaissance

3. **Target: 50-100 techniques with observed K0**
   - Each with 3-5 runs
   - Multi-witness corroboration (W1-W10)
   - Cryptographic pinning per run

**Effort:** 2-3 lab hours per platform (Linux already captured, expand on Windows/Container)

---

## Phase 2: REAL Arkime PCAP (A2 → indexed sessions)

### Current: A0/A1 (simulated/lab scaffold)
### Target: A2 (real Arkime-indexed PCAP with query exports)

**Setup:**

1. **Deploy Arkime in lab**
   ```bash
   docker-compose up arkime
   # Configure: pcap storage, indexing, query API
   # Retention: 90 days minimum
   ```

2. **Route lab traffic through Arkime**
   ```bash
   # Metatron lab network interface → Arkime capture
   # Include: external C2 sims, lateral movement, data exfil
   ```

3. **Execute techniques with network capture**
   ```bash
   for technique in T1018 T1041 T1071 T1090 T1135 T1190 T1570 T1571 T1572
   do
     arkime_start_capture $technique
     run_atomic $technique --simulate-c2
     arkime_stop_capture
     # Export: session ID, packet count, payload hash, threat intel correlation
   done
   ```

4. **Generate A2 evidence**
   - Real Arkime session export (not metadata)
   - Query results: "show me C2 connections for T1071"
   - PCAP hash verification
   - Payload inspection + redaction

**Target:** 30-50 techniques with A2 (real PCAP indexed)

**Effort:** 4-6 hours (one-time setup, then parallel collection)

---

## Phase 3: REAL Cloud/SaaS Execution (L2 → L0/L1)

### Current: L2 (lab-synthetic audit events)
### Target: L0/L1 (real API audit logs pulled from vendors)

**Cloud Coverage:**

1. **AWS (CloudTrail)**
   ```bash
   # Real lab AWS account
   aws s3 create-bucket --bucket metatron-test-lure-bucket
   
   # Run techniques
   for technique in T1526 T1537 T1538 T1539
   do
     run_cloud_atomic $technique --account metatron-lab
   done
   
   # Pull real CloudTrail logs
   aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=metatron-test-lure
   # Export: RequestID, timestamp, IAM role, action, resource
   ```

2. **Azure (Azure Monitor)**
   ```bash
   # Real lab Azure subscription
   az storage account create --name metatronlabstore
   
   # Run techniques
   for technique in T1526_azure T1537_azure T1538_azure
   do
     run_cloud_atomic $technique --provider azure
   done
   
   # Pull real audit logs
   az monitor activity-log list --resource-group metatron-lab
   ```

3. **SaaS (O365, GitHub, Okta)**
   ```bash
   # Real lab O365 tenant
   # Real lab GitHub org
   # Real lab Okta instance
   
   # Execute techniques: phishing, file sharing, permission changes
   # Pull real audit logs via API
   # Evidence: actor, target, action, timestamp, IP
   ```

**Target:** 20-30 techniques with L0/L1 (real audit logs from vendors)

**Effort:** 6-8 hours (requires cloud account access + vendor API setup)

---

## Phase 4: REAL Host Execution (H0 validation)

### Expand osquery + Sysmon coverage

1. **Windows (Sysmon)**
   ```bash
   for technique in T1098 T1110 T1547 T1556 T1098_persistence
   do
     enable_sysmon_logging
     run_purplesharp $technique
     export_sysmon_events --technique $technique
     # Capture: process creation, registry modification, service creation
   done
   ```

2. **Linux (Auditd + Falco)**
   ```bash
   for technique in T1053 T1078 T1134 T1078_lateral
   do
     enable_auditd + falco
     run_atomic $technique
     export_audit_events
     # Capture: execve, syscall context, security context
   done
   ```

**Target:** 50+ techniques with H0 (direct execution observed)

---

## Phase 5: REAL Detection Evidence (D0)

### Confirm Sigma + EDR rules actually fire

1. **For each technique with real execution**
   ```bash
   run_technique $technique --capture-all
   
   # Verify:
   # ✓ Sigma rule fired (confirm in sigma_evaluation_report.json)
   # ✓ EDR detected it (Velociraptor query returned results)
   # ✓ Network IDS saw it (Zeek/Suricata alert)
   # ✓ Kernel prevented it (Arda K0)
   ```

2. **Build D0 evidence for each**
   - Rule that fired
   - Exact match criteria
   - False positive rate (0 expected)

---

## HONEST Tier Distribution (Post-Upgrade)

```
Current:
  K0 (observed):     14 techniques    → K2 (deductive): 653
  A0/A1 (scaffold):  23 techniques    → Limited real PCAP
  L2 (synthetic):    20 techniques    → Real CloudTrail access unclear
  H0 (observed):     286 techniques   → Extended coverage needed
  D0 (real firing):  81 techniques    → Verify all still fire

POST-UPGRADE TARGET:
  K0 (observed):     100+ techniques  (expand lab execution)
  A2 (real PCAP):    50+ techniques   (Arkime indexed)
  L0/L1 (real API):  30+ techniques   (vendor audit logs)
  H0 (observed):     300+ techniques  (expand host telemetry)
  D0 (real firing):  150+ techniques  (verify all Sigma rules)
  
  Result: 400+ HARD_POSITIVE evidence across multiple sources
```

---

## Priority Order

1. **Phase 1 (K0 expansion)** — HIGHEST IMPACT
   - Ring-0 proof is the differentiator
   - Expand from 14 to 100+ observed denials
   - Effort: Medium, Impact: Maximum

2. **Phase 2 (Arkime A2)** — HIGHEST VALUE
   - Network forensics is forensically powerful
   - Real PCAP > metadata
   - Effort: High, Impact: High

3. **Phase 3 (Cloud/SaaS L0/L1)** — COMPLIANCE VALUE
   - Real audit logs beat synthetic
   - Regulatory audit requirement
   - Effort: High, Impact: Medium

4. **Phase 4 & 5** — SUPPORTING
   - Expand existing H0/D0 coverage
   - Fill gaps in corroboration

---

## Success Metrics

**Current → Target:**
- K0 evidence: 14 → 100+ observed kernel denials
- HARD_POSITIVE techniques: 14 → 200+ (K0 + A2 + L0/L1 + H0)
- STRONG_SUPPORT techniques: 677 → 491 (fewer synthetic, more real)
- Overall: Scaffold → Forensic-grade validation

**Honest claim (post-upgrade):**
> "Metatron-Seraph Hard-Positive Multi-Source Bundle: 200+ techniques with HARD_POSITIVE evidence (K0 kernel denial + A2 real PCAP + L0/L1 vendor audit + H0 execution proof). Remaining 491 techniques supported by deductive kernel proof + lab corroboration."

---

## To Execute

```bash
# 1. Expand kernel tests
python3 scripts/arda_kernel_prevention_harvester.py --runs-per-technique 5 --include-all

# 2. Deploy Arkime
docker-compose -f arkime-deploy.yml up

# 3. Execute cloud tests with real capture
python3 scripts/cloud_attack_executor.py --real-api --capture-audit

# 4. Regenerate with honest classification
python3 scripts/tvr_honest_regenerator.py

# 5. Rebuild bundle with real evidence
tar -czf metatron_seraph_hard_positive_20260427.tar.gz ...
```

---

**This turns the scaffold into REAL, FORENSIC-GRADE PROOF.**
