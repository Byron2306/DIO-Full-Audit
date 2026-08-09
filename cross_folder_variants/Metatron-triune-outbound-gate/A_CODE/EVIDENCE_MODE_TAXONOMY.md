# Evidence Mode Taxonomy & Certification Rules
## Metatron Seraph Honest Labeling Framework

**Purpose:** Ensure evidence labels reflect actual proof strength, not aspirations.

---

## Evidence Mode Classification

```
H-Series: Host Execution Evidence
├─ H0: Direct observed host execution (attacker command ran, telemetry captured)
│  └─ Strength: HARD_POSITIVE (can certify alone)
│  └─ Example: osquery saw process launch, Sysmon fired
│
├─ H1: Host telemetry + deception lure interaction
│  └─ Strength: STRONG_SUPPORT (corroborating only)
│  └─ Example: Honeypot file was accessed, log shows access time
│
└─ H2: Host telemetry without execution proof
   └─ Strength: CONTEXTUAL_SUPPORT
   └─ Example: Network connection observed, but not proven to be technique

D-Series: Detection Evidence
├─ D0: Direct detection fired (Sigma, EDR, IDS rule triggered)
│  └─ Strength: HARD_POSITIVE (can certify alone)
│  └─ Example: Sigma rule for T1082 fired, matched process + args
│
├─ D1: Detection rule mapped to technique
│  └─ Strength: STRONG_SUPPORT (corroborating)
│  └─ Example: Rule exists, would detect, but didn't fire in this run
│
└─ D2: Detection capability only
   └─ Strength: CONTEXTUAL_SUPPORT
   └─ Example: Rule exists for technique, but coverage unknown

K-Series: Kernel Enforcement Evidence
├─ K0: Observed Arda kernel denial (EPERM at syscall boundary)
│  └─ Strength: HARD_POSITIVE (can certify alone)
│  └─ Proof: deny_count_delta > 0, exec rc != 0, auditd EPERM log
│  └─ Label: "Observed kernel denial"
│
├─ K1: Arda substrate proof only (cryptographic pinning)
│  └─ Strength: SUBSTRATE_ONLY (cannot certify alone)
│  └─ Proof: BPF program hash, harmony allowlist hash, loader hash match
│  └─ Label: "Arda substrate proof (not observed execution)"
│
└─ K2: Deductive Arda prevention (untrusted /tmp → denied by logic)
   └─ Strength: STRONG_CORROBORATION (supporting evidence)
   └─ Logic: (payload_in_/tmp AND NOT in_harmony_map) → EPERM_certain
   └─ Label: "Deductive prevention: untrusted /tmp form would be denied"

L-Series: Audit Log Evidence
├─ L0: Real vendor audit log (raw CloudTrail, real Azure Monitor, real Okta)
│  └─ Strength: HARD_POSITIVE (if raw, not pre-processed)
│  └─ Example: AWS CloudTrail API call with RequestID, timestamp, IAM role
│
├─ L1: Lab tenant audit log pulled from vendor API
│  └─ Strength: HARD_POSITIVE (if raw API export)
│  └─ Example: Lab's O365 audit log pulled via Graph API
│
├─ L2: Lab-synthetic audit event (generator created, not from API)
│  └─ Strength: STRONG_SUPPORT (good grammar, synthetic data)
│  └─ Example: Lab-sim generated CloudTrail-format event
│
└─ L3: Audit mock/stub only
   └─ Strength: CONTEXTUAL_SUPPORT
   └─ Example: Audit record template, no actual event

A-Series: Arkime/PCAP Evidence
├─ A0: Simulated Arkime session metadata (constructed from example data)
│  └─ Strength: PIPELINE_SUPPORT (proves schema/structure only)
│  └─ Example: Generated session record with fake IP, flow metadata
│
├─ A1: Lab-generated PCAP (captured in lab, hash-verified)
│  └─ Strength: STRONG_SUPPORT (real capture, lab-scoped)
│  └─ Example: tcpdump from lab VM, SHA256 hash verified
│
└─ A2: Real Arkime-indexed PCAP (production capture, query-verified)
   └─ Strength: HARD_POSITIVE (real network evidence)
   └─ Example: Arkime query export with session ID, packet count, hash

C-Series: Context/Correlation Evidence
├─ C0: Context telemetry only (no direct proof)
│  └─ Strength: CONTEXTUAL_SUPPORT
│  └─ Example: "Process was running, but we didn't see exec"
│
└─ C1: Multi-source correlation (multiple sources point same direction)
   └─ Strength: STRONG_SUPPORT (corroborating multiple sources)
   └─ Example: Sigma + EDR + osquery all indicate technique

M-Series: Mapping Evidence
├─ M0: Mapped query/rule (rule exists for technique)
│  └─ Strength: PIPELINE_SUPPORT
│  └─ Example: "We have a Sigma rule for this"
│
└─ M1: Successful rule firing (rule was tested, confirmed working)
   └─ Strength: STRONG_SUPPORT
   └─ Example: Sigma rule tested against Atomic Red Team, fired
```

---

## Certification Rules (Tier Promotion)

```
PLATINUM tier requires:
  ✅ At least ONE source from {H0, D0, K0, L0, L1, A2}
  ✅ Plus corroborating sources from {K2, L2, A1, C1, D1}
  ✅ No PIPELINE_SUPPORT or CONTEXTUAL_SUPPORT alone

GOLD tier requires:
  ✅ Strong corroboration from {K2, L2, A1, C1, D1}
  ✅ Plus supporting evidence from lower tiers
  ✅ No hard-positive source

SILVER tier requires:
  ✅ At least two different source types
  ✅ Can include context and mapping evidence

BRONZE tier:
  ✅ Rule/capability exists
  ✅ May be entirely M0 or theoretical
```

---

## Namespace Flags

Every technique MUST include:

```json
{
  "technique_id": "T1082",
  "id_namespace": "mitre_attack_enterprise",
  "id_status": "canonical",
  "evidence": [...]
}
```

Valid namespaces:
- `mitre_attack_enterprise` — Official ATT&CK enterprise
- `mitre_attack_mobile` — Official ATT&CK mobile
- `mitre_attack_cloud` — Official ATT&CK cloud
- `mitre_attack_ics` — Official ATT&CK ICS
- `internal_metatron` — Metatron lab technique (not ATT&CK)
- `deprecated` — No longer in canonical ATT&CK
- `unknown` — Cannot classify

Invalid: naked T-numbers without namespace flag will be rejected.

---

## Bundle Honest Labeling

**OLD (inaccurate):**
> "Metatron Seraph: Complete 691-Technique Validation at Platinum Tier"

**NEW (honest):**
> "Metatron-Seraph Multi-Source Corroboration Bundle: Evidence scaffold for 691 canonical ATT&CK techniques using Arda substrate proof, deductive prevention logic, lab-synthetic audit events, and network-forensic pipeline scaffolding. Designed to strengthen multi-technique corroboration, not replace observed hard-positive validation."

**The claim:**
This bundle does NOT claim all 691 techniques are live-validated or platinum-certified.
It DOES provide:
- K0 evidence for 14 techniques (observed kernel denials)
- K2 evidence for 677 techniques (deductive prevention)
- L2 evidence for cloud/SaaS techniques (synthetic audit events in correct grammar)
- A0/A1 evidence for network techniques (forensic scaffolding + lab PCAP)
- D0 evidence for 81 techniques (direct Sigma firing)

This is **powerful multi-source support**, but honest about what each layer proves.

---

## Implementation Checklist

- [ ] Add `evidence_mode` label to every evidence artifact
- [ ] Add `id_namespace` to every technique record
- [ ] Update TVR regenerator: corroboration ≠ auto-promotion
- [ ] Add evidence strength classifier to bundle
- [ ] Document which techniques have K0 vs K2 vs K1
- [ ] Flag L2 events as "synthetic" in label
- [ ] Distinguish A0/A1/A2 PCAP evidence
- [ ] Update README with honest capability statement
- [ ] Create evidence audit checklist for reviewers
