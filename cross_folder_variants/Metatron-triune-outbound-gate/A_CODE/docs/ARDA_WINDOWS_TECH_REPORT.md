# ARDA Windows Port Technical Report

Date: 2026-05-03
Author: GitHub Copilot (GPT-5.3-Codex)
Scope: Windows-deployable ARDA architecture preserving constitutional logic while replacing Linux-only kernel enforcement dependencies.

## Executive Summary

This report delivers three concrete outputs:

1. A transfer matrix mapping ARDA components to Windows portability status and required replacement backends.
2. A prioritized rewrite plan identifying exactly which services to rework first for maximum architectural preservation with minimum effort.
3. A Windows-native ARDA architecture draft that preserves conceptual layers (Tree of Truth/Order, Ainur Choir, Manwe Herald, Tulkas, Aule, Secret Fire) while replacing Linux kernel dependencies with WDAC/AppLocker, Sysmon/ETW/Event Log, Defender, and Windows TPM/Secure Boot attestation.

Core conclusion:

- ARDA constitutional logic is portable.
- ARDA Linux kernel sovereignty implementation is not directly portable.
- A high-integrity Windows edition is feasible by replacing evidence and actuator backends while keeping governance and constitutional semantics.

---

## Part I: ARDA-to-Windows Transfer Matrix

### Status Legend

- Portable: Can transfer with minimal changes.
- Partial: Transfers conceptually; backend adapters required.
- Re-implementation required: Current implementation is Linux-coupled and needs a Windows-native equivalent.

| ARDA Component | Current Plane | Primary Current Dependency | Windows Transfer Status | Windows-Native Replacement Backend | Notes |
|---|---|---|---|---|---|
| Tree of Truth (Formation Verifier) | Constitutional truth | Linux TPM + EFI + manifest checks | Partial | Windows TPM attestation (Get-Tpm/Win32_Tpm/CNG), Secure Boot (Confirm-SecureBootUEFI), measured boot event sources | Keep verifier semantics; replace source adapters.
| Tree of Order (Formation Order + Vaire chronology) | Constitutional order | Sequence/transition checks | Portable | Existing logic + Windows event and transition sources | Mostly data-model and source normalization.
| Ainur Choir Orchestrator | Constitutional synthesis | Inspector and collector pipeline | Portable | Existing choir + Windows collectors | Keep verdict model intact.
| Ainur Collectors (Varda/Ulmo/Manwe/Mandos/Lorien) | Evidence ingestion | Mixed Linux services | Partial | Sysmon, ETW, Event Log, Defender, osquery for Windows | Collector adapters are key seam.
| Aule Final Forger | Constitutional arbitration | Verdict fusion and contradiction logic | Portable | Existing Aule logic | No kernel dependency.
| Secret Fire Forge | Challenge/witness protocol | Nonce, freshness, replay + TPM quote source | Partial | Keep protocol; replace quote and host identity source with Windows implementations | Strong candidate for near drop-in with backend swap.
| Manwe Herald | Runtime identity and activation | Covenant + attested identity + world model | Partial | Existing herald flow + Windows attestation adapters | Depends on Tree of Truth quality.
| World Manifold | Global fused state | Includes Linux kernel sovereignty fields | Partial | Platform-specific manifold profiles and metric taxonomy | Split Linux vs Windows sovereignty fields.
| Tulkas Executor (decision ladder) | Enforcement policy | Linux process/network/kernel hooks | Partial | Keep posture ladder; replace actuators with WDAC/AppLocker/PowerShell/Firewall/Defender actions | Core logic survives, actuation changes.
| Constitutional Projection | Verdict-to-runtime bridge | Arda fabric and optional kernel bridge | Partial | Keep projection; add Windows policy bridge target | Add feature-gated target adapters.
| Bombadil (Law daemon) | Sovereignty monitor | LSM, bpftool, /sys, Linux TPM probes | Re-implementation required | Windows Sovereignty Sentinel (WDAC state, Defender tamper state, Sysmon health, TPM/Secure Boot state) | Preserve role, replace implementation.
| ARDA BPF LSM + loader + map seeding | Ring-0 kernel enforcement | Linux LSM hooks, libbpf, BPF maps | Re-implementation required | WDAC/AppLocker policy control as execution governance substrate | Not a refactor; this is a backend replacement.
| Linux Valinor kernel modules/hooks | Kernel-adjacent enforcement | Linux process/syscall/flow controls | Re-implementation required | Windows policy and telemetry enforcement adapters | Port semantics, not code.

### Transfer Implications

1. The constitutional model can be preserved with high fidelity.
2. Enforcement and attestation trustworthiness on Windows depends on native data sources, not Linux compatibility layers.
3. Claims language must be split by platform:
   - Linux: Ring-0 BPF/LSM-backed enforcement.
   - Windows: Policy-backed execution governance (WDAC/AppLocker) with telemetry corroboration.

---

## Part II: Rewrite Priority Plan (Maximum Preservation, Minimum Effort)

### Prioritization Heuristic

Prioritize services that:

1. Unlock the largest number of dependent components.
2. Sit at architecture seams (adapters/interfaces), not policy cores.
3. Allow immediate field-deployable Windows runs without kernel rewrite.

### Priority Wave 0: Make Windows Edition Honest and Stable

Goal: Ship a reliable Windows mode with explicit capability profile and no Linux hard-fail paths.

1. Add platform capability registry and mode profile.
2. Hard gate Linux-only runtime features behind capability checks.
3. Introduce explicit sovereignty level enums:
   - `linux_ring0_authoritative`
   - `windows_policy_authoritative`
   - `simulation`

Expected impact:

- Immediate reduction in runtime breakage.
- Clear user expectations in UI and reports.

### Priority Wave 1: Truth and Evidence Adapters (Highest Leverage)

Goal: Preserve Trees and Choir integrity with Windows-native evidence.

1. `secure_boot_state_service` Windows path hardening.
   - Standardize PowerShell and fallback handling.
2. `tpm_attestation_service` Windows implementation.
   - Implement Windows TPM snapshot and quote flow.
3. `boot_eventlog_reader` Windows backend.
   - Replace mock-only path with measured-boot event acquisition.
4. Ainur collector adapter set for Windows.
   - Varda/Ulmo/Manwe/Mandos collector backend mappings.

Expected impact:

- Tree of Truth becomes materially defensible on Windows.
- Choir can operate on real Windows evidence instead of synthetic placeholders.

### Priority Wave 2: Tulkas Actuator Backends

Goal: Preserve constitutional enforcement logic while replacing Linux actuation.

1. Introduce `EnforcementActuator` interface:
   - `LinuxKernelActuator`
   - `WindowsPolicyActuator`
2. Implement Windows posture actions:
   - Restrain: alert-only + scoped monitoring escalation.
   - Throttle: firewall restrictions/QoS controls where feasible.
   - Contain: WDAC/AppLocker rule tightening + process isolation actions.
   - Purge/Exile: process kill, account/session controls, host isolation playbooks.
3. Bind Tulkas to platform actuator via dependency injection.

Expected impact:

- Existing constitutional ladder survives unchanged.
- Execution governance is real on Windows.

### Priority Wave 3: Bombadil Replacement

Goal: Restore sovereign posture monitoring semantics on Windows.

1. Replace Linux-specific checks with Windows Sovereignty Sentinel checks:
   - WDAC/AppLocker policy active state.
   - Defender tamper protection and realtime state.
   - Sysmon/Event collection health.
   - Secure Boot and TPM state continuity.
2. Emit platform-specific covenant state reasons.

Expected impact:

- Keeps operational narrative coherent without false Linux assumptions.

### Priority Wave 4: World Manifold Platform Normalization

Goal: Prevent Linux field leakage into Windows sovereign state representation.

1. Define platform-aware manifold metric schema.
2. Replace hardcoded Linux interceptor assumptions with platform metric bundles.
3. Keep canonical high-level manifold outputs stable.

Expected impact:

- Comparable governance behavior across platforms with honest underlying evidence semantics.

---

## Part III: Windows-Native ARDA Architecture Draft

### Design Goals

1. Preserve constitutional governance semantics.
2. Replace Linux kernel controls with robust Windows-native policy and telemetry controls.
3. Keep cross-platform comparability at the verdict layer.

### Proposed Layered Architecture

1. Constitutional Layer (unchanged semantics):
   - Trees (Truth/Order), Ainur Choir, Aule, Secret Fire protocol, Manwe Herald, governance executor.

2. Evidence Layer (Windows adapters):
   - Varda evidence: TPM/Secure Boot/measured-boot events.
   - Ulmo evidence: Sysmon + ETW + Defender anomaly streams.
   - Manwe evidence: liveness and cadence from runtime + host process telemetry.
   - Mandos evidence: expected/observed process and service continuity from Windows telemetry.

3. Enforcement Layer (Windows policy actuators):
   - WDAC primary execution control backend.
   - AppLocker fallback where WDAC is unavailable.
   - Windows Firewall and Defender response actions.
   - PowerShell/WinRM remediation runner for orchestration.

4. Sovereignty Layer (Windows sentinel):
   - Policy posture, telemetry integrity, and attestation continuity checks replacing BPF/LSM checks.

### Windows Evidence and Enforcement Mapping

| ARDA Role | Linux Source Today | Windows Source Target |
|---|---|---|
| Truth (Varda) | tpm2-tools + EFI vars | Get-Tpm/Win32_Tpm + Confirm-SecureBootUEFI + measured boot logs |
| Deep Signals (Ulmo) | kernel signal adapters + audit-like sources | Sysmon + ETW + Defender security events |
| Breath/Liveness (Manwe) | cadence + runtime signals | cadence + process/service + event health |
| Absence/Memory (Mandos) | process lineage + expected entities | process/service continuity + event log persistence checks |
| Force (Tulkas) | kernel map sync + process severance | WDAC/AppLocker policy transitions + process/firewall/defender actions |
| Sovereign monitor (Bombadil role) | LSM/bpftool/sysfs checks | policy-state/telemetry-state/attestation-state sentinel |

### Suggested Interface Contracts

1. `AttestationProvider`
   - `get_pcr_snapshot(indices)`
   - `get_secure_boot_state()`
   - `get_boot_event_log()`

2. `EvidenceProvider`
   - `collect_varda_evidence(context)`
   - `collect_ulmo_evidence(context)`
   - `collect_manwe_evidence(context)`
   - `collect_mandos_evidence(context)`

3. `PolicyEnforcementProvider`
   - `apply_posture(node_id, posture, verdict)`
   - `trust_workload(identity)`
   - `distrust_workload(identity)`

4. `SovereigntyMonitor`
   - `evaluate_sovereignty_state()`
   - `explain_state_reasons()`

### Reference Runtime Flow (Windows Edition)

1. Tree of Truth gathers Windows attestation and measured boot state.
2. Tree of Order validates lawful sequencing and freshness.
3. Secret Fire issues challenge and binds witness packet.
4. Ainur collectors gather Windows evidence packets.
5. Ainur Choir evaluates and Aule synthesizes constitutional verdict.
6. Manwe Herald manifests runtime identity if allowed.
7. Tulkas executes posture through Windows policy actuator.
8. Windows Sovereignty Sentinel verifies ongoing policy and telemetry integrity.

---

## Implementation Blueprint

### Milestone A: Adapter and Capability Foundation

Deliverables:

1. Platform capability registry.
2. Adapter interfaces for attestation, evidence, enforcement, sovereignty monitor.
3. Feature flags for Linux-specific paths.

Success criteria:

1. Windows stack starts with no Linux dependency exceptions.
2. Capability profile is emitted in health and report endpoints.

### Milestone B: Real Windows Truth/Evidence

Deliverables:

1. Windows attestation provider implementation.
2. Windows boot event provider implementation.
3. Windows Ainur collector backends.

Success criteria:

1. Tree of Truth outputs non-mock verified states on Windows test hosts.
2. Choir verdict confidence is derived from real host evidence.

### Milestone C: Tulkas Windows Actuation

Deliverables:

1. WDAC/AppLocker actuation backend.
2. Firewall/Defender remediation actions.
3. Policy transition audit logging.

Success criteria:

1. Withheld/vetoed verdicts cause deterministic policy actions.
2. Action evidence is attached to post-verdict telemetry.

### Milestone D: Bombadil Role Replacement and Manifold Normalization

Deliverables:

1. Windows Sovereignty Sentinel service.
2. Platform-aware manifold metric schema.

Success criteria:

1. Sovereignty state remains meaningful without Linux ring-0 artifacts.
2. Reports cleanly distinguish Linux ring-0 and Windows policy-authoritative postures.

---

## Risks and Mitigations

| Risk | Description | Mitigation |
|---|---|---|
| False equivalence claims | Claiming Linux ring-0 parity on Windows | Explicit platform capability labels and report-level claim constraints |
| Telemetry integrity gap | ETW/Sysmon pipeline drift or tampering | Health checks, redundancy, signed forwarding where possible |
| Policy complexity | WDAC/AppLocker rollout can lock out legitimate workloads | Staged policy rollout and simulation-to-enforce transition gates |
| Architecture regression | Refactor accidentally rewires constitutional logic | Adapter pattern with unchanged Choir/Aule/Secret Fire semantics and test baselines |

---

## Definition of Done for Windows ARDA Edition

A Windows ARDA edition is considered complete when:

1. Trees, Choir, Aule, Manwe Herald, Secret Fire, and Tulkas posture logic operate end-to-end with Windows-native evidence and actuation.
2. No runtime path relies on Linux-only kernel interfaces.
3. Sovereignty posture is auditable, reproducible, and accurately labeled as policy-authoritative on Windows.
4. Documentation and evidence bundles separate Linux ring-0 claims from Windows policy-backed claims.

---

## Recommended Immediate Next Actions

1. Implement adapter interfaces and capability registry.
2. Build Windows attestation provider for Tree of Truth.
3. Build Windows enforcement provider for Tulkas.
4. Replace Bombadil Linux checks with a Windows Sovereignty Sentinel.
5. Add platform claim labels to all governance and evidence reports.
