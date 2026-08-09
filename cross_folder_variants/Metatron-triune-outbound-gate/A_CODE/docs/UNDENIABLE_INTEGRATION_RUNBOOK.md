# Undeniable Integration Runbook

This runbook integrates ARDA and the broader Seraph/Metatron telemetry stack into one auditable pipeline.

The goal is strict evidence integrity:
- one operator command
- one provenance trail
- one manifest with explicit claim boundaries

## What This Integrates

The pipeline wraps existing project scripts, in order:

1. Optional collection refresh:
- ARDA prevention sweep
- live telemetry sweep
- optional integration sweep

2. Detection evaluation:
- Sigma against real osquery telemetry
- multi-source correlation across Falco, Zeek, Suricata, osquery, deception, YARA, and related integrations

3. Evidence graph and public artifacts:
- MITRE evidence correlation build
- honest public report regeneration
- bundle reconciliation (dry-run by default)

4. Integrity summary:
- false-flag audit from honest TVR classification
- canonical-count drift check (local MITRE list vs classification entries)

## New Entry Point

Use scripts/run_undeniable_evidence_pipeline.py.

### Conservative mode (recommended default)

This mode integrates existing evidence without risky promotion side effects:

```bash
.venv/bin/python scripts/run_undeniable_evidence_pipeline.py \
  --profile integrate-existing
```

### Full collection mode

This mode reruns heavy collection and then performs full integration:

```bash
.venv/bin/python scripts/run_undeniable_evidence_pipeline.py \
  --profile full-run \
  --run-integration-sweep
```

### Controlled mutation flags

By default the pipeline is non-mutating for sensitive promotion/reconciliation paths.

Only enable these when explicitly intended:

```bash
# Allow TVR updates during multi-source correlation
--promote-detections

# Allow reconcile_bundle.py to write patches
--allow-reconcile-write
```

## Outputs

Each run writes a timestamped directory under artifacts/undeniable_pipeline/:

- undeniable_evidence_manifest.json
- README.md
- per-stage stdout/stderr logs
- mitre_evidence_correlation.json
- metatron_honest_tvr_classification.json
- metatron_public_claim_summary.json
- sigma rule/match snapshots

The manifest includes:
- stage commands and return codes
- key artifact paths
- metrics from Sigma and multi-source reports
- false-flag summary
- canonical technique drift (including extra IDs)
- claim boundaries (observed vs correlated vs support-only)

## Claim Model (Use This in Public Statements)

Only make direct claims from observed evidence:
- ARDA kernel EPERM denials
- direct Sigma firings
- multi-source detections with concrete events

Use correlated evidence for narrative support:
- cross-source joins in MITRE evidence correlation
- stitched timelines across sensors

Never present support-only evidence as direct proof:
- ATT&CK tag/rule coverage without firing
- query mappings without direct event proof
- archive-only support records without direct run linkage

## Why This Makes It "Undeniable"

- Every stage command is logged.
- Every claim category is explicit and separated.
- Promotion/reconciliation writes are opt-in.
- False flags are surfaced in the same run output.
- Canonical MITRE count drift is measured each run.

## Operator Checklist

Before run:
- ensure .venv is active
- ensure required containers are running for desired sensors
- ensure evidence-bundle path is correct

After run:
- inspect undeniable_evidence_manifest.json
- verify required stages are status=ok
- review false-flag summary and extra_vs_canonical IDs
- use README.md as the operator-facing digest
