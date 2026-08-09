# ARDA W5 Forensics Audit Manifest

Date: 2026-05-09T14:29:10.590814+00:00

## Scope

- Cohort: `100759`
- Records audited: `516`
- Verified: `516`
- Failed: `0`

## Deterministic Rules

- Path pattern: `/tmp/arda_(Tdddd|Tdddd_ddd).bin`
- Mode expected: `0o755`
- Payload template: `#!/bin/bash\necho <TECHNIQUE_TOKEN>\n`
- Token normalization: path token uses underscores for sub-techniques; payload token uses dots

## Timing Cohesion

- mtime count: `516`
- min mtime: `1777370914.263996`
- max mtime: `1777370915.5439959`
- spread seconds: `1.2799999713897705`

## Artifacts

- Full machine-readable manifest: `docs/ARDA_W5_FILE_FORENSICS_AUDIT_MANIFEST_2026-05-09.json`
