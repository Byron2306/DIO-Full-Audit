# Dagor Dagorlach Last-Test Assessment (2026-05-09)

## Scope
This assessment summarizes the most recent high-intensity containment tests run against the Seraph/Arda outbound control plane.

## Executed Test Runs

1. Standard ultimate gauntlet
- Command:
  - `python backend/scripts/e2e_dagor_dagorlach_gauntlet.py --aab-replay-limit 10`
- Verdict:
  - `pass`
- Metrics:
  - hostile_total: 14
  - hostile_denied: 14
  - hostile_queued: 0
  - hostile_approved: 0
  - checks_passed: 14
  - checks_failed: 0
  - global_strictness: lockdown

## Atomic Breadth Validation (Latest Evidence Rollup)

This rollup de-duplicates prevention artifacts by technique_id and keeps the latest record per technique.

- Source set:
  - artifacts/evidence/arda_prevention/arda_prevention_T*.json
- Results:
  - latest_unique_techniques: 684
  - latest verdict distribution: 684 kernel_prevented, 0 other verdicts
  - exec_attempt denied=true: 684
  - exec_attempt denied=false: 0
  - local Atomic top-level technique folder count (denominator reference): 412

Interpretation:
- The evidence set demonstrates broad ATT&CK technique and sub-technique coverage, not just a narrow gauntlet.
- Prevention consistency in the latest per-technique records is currently perfect in this corpus.

2. Live-harness ultimate gauntlet (model-driven adversarial behavior)
- Command:
  - `python backend/scripts/e2e_dagor_dagorlach_gauntlet.py --live-harness --live-agent-class jailbroken --aab-replay-limit 10`
- Verdict:
  - `pass`
- Metrics:
  - hostile_total: 21
  - hostile_denied: 21
  - hostile_queued: 0
  - hostile_approved: 0
  - checks_passed: 21
  - checks_failed: 0
  - global_strictness: lockdown

## Severity Rating of Tested Scenarios

Severity scale used: Low, Moderate, High, Critical.

1. Long poison baseline erosion
- Severity: High
- Reason: slow-cadence drift can bypass simplistic threshold detectors over time.

2. Beautiful fraud + ransomware drop
- Severity: Critical
- Reason: combines clean behavioral mimicry with destructive payload intent.

3. Split-brain / partial witness context
- Severity: Critical
- Reason: attacks trust model integrity and can induce policy inconsistencies.

4. Epoch replay / notation spoof
- Severity: Critical
- Reason: attempts to break cryptographic and governance freshness assumptions.

5. Privilege storm + shadow scrape
- Severity: Critical
- Reason: direct admin escalation and credential theft paths.

6. Benign-chaos with hidden dagger
- Severity: High
- Reason: mixed benign/malicious behavior can evade simplistic classifiers.

7. AAB replay detonation
- Severity: High to Critical
- Reason: reuses realistic adversarial traces from prior campaigns.

8. Cascading strain / lockdown pressure
- Severity: High
- Reason: probes autonomous hardening and degradation behavior under pressure.

9. Final world-ending burst chain
- Severity: Critical
- Reason: simultaneous high-impact operations (ransomware, exfiltration, privilege abuse).

Overall scenario severity: Critical.

## System Rating (Seraph/Arda)

### Containment Effectiveness (for this test scope)
- Rating: 9.7 / 10
- Basis:
  - 35/35 hostile actions denied across standard+live reruns in this assessment window.
  - 0 hostile approvals.
  - 0 hostile queued outcomes.
  - Lockdown escalation engaged under heavy anomaly pressure.
  - 684/684 latest de-duplicated Atomic technique records show kernel_prevented + denied=true.

### Production Confidence (handover-oriented)
- Rating: 9.2 / 10
- Why not higher:
  - These are still bounded gauntlets, not exhaustive real-world coverage.
  - Coverage is strongest for outbound/system hostile actions and policy-veto pathways, though breadth is now substantial.
  - Confidence should be increased with continuous regression runs and independent red-team variation.

## Residual Risk and Caveats

1. Non-exhaustive adversary space
- Passing these gauntlets does not prove absence of all unknown bypasses.

2. Dependency/runtime drift risk
- Runtime showed an oqs library version mismatch warning during execution.
- This did not block test completion, but dependency parity should be cleaned before formal handoff.

3. Environmental assumptions
- Results assume strict-mode semantics used in these runs (staging-like no-bypass posture).

## Recommendation for Handover Statement

Suggested wording:
- "In the latest Dagor Dagorlach standard and live-harness executions, all tested hostile high-impact actions were denied (35/35), with zero hostile approvals observed."
- "Across the latest de-duplicated Atomic prevention corpus, 684 of 684 techniques/sub-techniques recorded kernel_prevented with denied=true."
- "This demonstrates very strong containment for tested adversarial classes, while acknowledging that no finite campaign proves total absence of unknown future bypasses."

## Evidence Artifacts

- JSON report (latest run):
  - `backend/scripts/telemetry_logs/DAGOR_DAGORLACH_ULTIMATE_GAUNTLET_report.json`
- Markdown summary (latest run):
  - `backend/scripts/telemetry_logs/DAGOR_DAGORLACH_ULTIMATE_GAUNTLET_summary.md`
- This assessment:
  - `docs/DAGOR_DAGORLACH_LAST_TESTS_ASSESSMENT_2026-05-09.md`
