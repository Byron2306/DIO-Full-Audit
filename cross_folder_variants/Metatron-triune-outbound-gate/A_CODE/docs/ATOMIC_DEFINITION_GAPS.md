# Atomic Definition Gaps (Sigma → Atomic Red Team)

This repo’s MITRE technique list (driven by `sigma_engine`) is larger than the set of techniques that have a vendored Atomic Red Team YAML definition under `atomic-red-team/atomics/`.

## Current snapshot (auto-generated)

The canonical JSON report for the current container runtime is:

- `artifacts/reports/atomic_definition_gaps.json`

At the time of generation (see `generated_at` in the JSON):

- `sigma_technique_count`: techniques referenced by `sigma_engine`
- `present_atomic_yaml_count`: technique IDs with `atomic-red-team/atomics/<TID>/<TID>.yaml`
- `missing_atomic_yaml_count`: technique IDs referenced by sigma but **no matching YAML** in this Atomic snapshot
- `linux_supported_count`: technique IDs with at least one Atomic test supporting `linux`
- `non_linux_only_count`: technique IDs that have an Atomic YAML, but **no Linux-supported** tests (Windows/macOS/cloud-only)

## How to regenerate

Run inside the backend container (so `sigma_engine` is available):

```bash
docker exec -i seraph-backend python3 /app/scripts/report_atomic_definition_gaps.py \
  --atomics-root /opt/atomic-red-team/atomics \
  --out /var/lib/seraph-ai/artifacts/reports/atomic_definition_gaps.json
```

## How to act on the gaps

- For `missing_atomic_yaml`: you either need to **vendor a newer Atomic snapshot**, or create **custom atomics** for those technique IDs.
- For `non_linux_only`: validation requires a non-Linux runner (WinRM for Windows, SSH for macOS, or cloud-native accounts/tools).

