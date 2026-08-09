# Seraph/Arda High-Confidence Validation Runbook

## Goal

This runbook operationalizes five confidence dimensions:

1. Independent validation
2. Longitudinal (nightly) stability
3. Mutation robustness
4. Cross-environment consistency
5. Dependency hygiene

All commands assume repository root and virtualenv:

```bash
cd /home/byron/Downloads/Metatron-triune-outbound-gate
source .venv/bin/activate
```

## 1) Independent Validation

Run independent read-only audit over prevention corpus + latest Dagor report:

```bash
python backend/scripts/seraph_independent_validator.py --repo-root .
```

Primary output:

- backend/scripts/telemetry_logs/seraph_independent_validator_latest.json

Then build a formal scorecard from current evidence artifacts:

```bash
python backend/scripts/seraph_confidence_scorecard.py --repo-root .
```

Outputs:

- docs/scorecards/seraph_confidence_scorecard_*.json
- docs/scorecards/seraph_confidence_scorecard_*.md

Use both artifacts as the independent reviewer packet.

## 2) Nightly Longitudinal Stability

Run 1 cycle now (standard + live Dagor) and append to history:

```bash
python backend/scripts/seraph_nightly_validator.py --repo-root . --iterations 1 --aab-replay-limit 10
```

History file:

- backend/scripts/telemetry_logs/seraph_nightly_history.jsonl

Suggested cron (02:00 daily):

```bash
0 2 * * * cd /home/byron/Downloads/Metatron-triune-outbound-gate && /home/byron/Downloads/Metatron-triune-outbound-gate/.venv/bin/python backend/scripts/seraph_nightly_validator.py --repo-root . --iterations 1 --aab-replay-limit 10 >> backend/scripts/telemetry_logs/seraph_nightly_cron.log 2>&1
```

## 3) Mutation Robustness

Execute mutated hostile-path tests through outbound gate mapping:

```bash
python backend/scripts/seraph_mutation_validator.py --repo-root . --samples 200 --seed 42
```

Output:

- backend/scripts/telemetry_logs/seraph_mutation_validator_latest.json

Pass condition:

- failed == 0

## 4) Cross-Environment Consistency

Generate scorecards independently per environment and compare:

1. Produce scorecard JSON on each environment.
2. Collect those JSON files in one place.
3. Compare them:

```bash
python backend/scripts/seraph_cross_env_compare.py \
  envA_scorecard.json envB_scorecard.json envC_scorecard.json \
  --max-spread 0.5
```

Output:

- backend/scripts/telemetry_logs/seraph_cross_env_compare_latest.json

Pass condition:

- consistency == high

## 5) Dependency Hygiene

Check runtime warnings (including oqs mismatch):

```bash
python backend/scripts/seraph_dependency_hygiene.py --repo-root .
```

Output:

- backend/scripts/telemetry_logs/seraph_dependency_hygiene_latest.json

Pass condition:

- status == pass
- oqs_mismatch_detected == false

## Recommended Promotion Gate

Promote only if all are true:

1. Latest scorecard composite score >= 9.5
2. Independent validator overall_status == pass
3. Nightly history has no failed runs in the most recent 14 days
4. Mutation validator failed == 0 for >=200 samples
5. Cross-env comparison consistency == high
6. Dependency hygiene status == pass

## Reviewer Packet Checklist

Provide these files for handover review:

1. seraph_independent_validator_latest.json
2. Latest scorecard markdown + json from docs/scorecards/
3. seraph_nightly_history.jsonl
4. seraph_mutation_validator_latest.json
5. seraph_cross_env_compare_latest.json
6. seraph_dependency_hygiene_latest.json
7. DAGOR_DAGORLACH_ULTIMATE_GAUNTLET_report.json
8. DAGOR_DAGORLACH_ULTIMATE_GAUNTLET_summary.md
