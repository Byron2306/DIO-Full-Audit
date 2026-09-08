# DIO 68-Product Portfolio Truth and Local Launcher Design

**Date:** 2026-09-08  
**Status:** Approved design  
**Target:** DIO-Full-Audit PR #36 branch `agent/dio-control-deck-68-productgrade`

## Objective

Make every live DIO portfolio surface derive the full verified portfolio as 53 historical canonical incarnations plus 15 frozen canon extensions, while preserving the historical 53-row crosswalk byte-for-byte. Provide one local launcher for GoldenEye, Control Deck, Market Command, and Production Studio.

## Portfolio truth model

The portfolio has two distinct evidence inputs:

1. `config/atlas/dio_meta_incarnation_crosswalk.csv` is the immutable historical anchor containing 53 rows.
2. `state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json` is the frozen verified summary containing 15 unique extensions.

`portfolio_runtime.import_portfolio()` validates both inputs and derives one runtime projection:

- `base_canonical_incarnation_count = 53`
- `canon_extension_count = 15`
- `canonical_incarnation_count = 68`
- `len(incarnations) = 68`
- `extension_summary_state = VERIFIED`

The runtime must fail closed to the 53 historical rows when the extension receipt is missing, invalid, duplicated, commercially overclaimed, authority-creating, externally effectful, or not fully ProductGrade/proof verified. This fallback must remain visible and must never be presented as the verified 68-product state.

## Root cause addressed

PR #36 currently proves the derivation with synthetic temporary test receipts, but the branch does not contain the canonical receipt at the path consumed by `portfolio_runtime.py`. CI therefore passes while a real checkout reports `extension_summary_state = MISSING` and derives 53. The PR is also draft, merge-conflicted, and based on the canon-extension gauntlet branch rather than `main`; a running checkout receives the change only after the branch chain is integrated and deployed.

## Required portfolio changes

1. Persist and commit the already-verified frozen 15-extension receipt at the canonical runtime path.
2. Do not edit or append to the 53-row crosswalk.
3. Add a repository-fixture integration test that imports the actual committed crosswalk and receipt and asserts the full 53/15/68 invariant.
4. Update older tests that hard-code 53 when they are testing current portfolio state. Preserve explicit tests of the missing/unverified receipt fallback at 53.
5. Expose the component counts and extension source state through Business Workbench, Market Command, GoldenEye, and launcher health responses.
6. Ensure the relevant CI workflow runs the real-source integration test.
7. Resolve PR branch conflicts before integration, without flattening or mutating the historical anchor.

## Launcher architecture

Use user-level systemd supervision and a single local launcher entry point. Do not collapse the applications into one process.

### Runtime services

| Surface | URL | Process |
|---|---|---|
| GoldenEye | `http://127.0.0.1:8766/` | `scripts/serve_goldeneye_ms10.py` |
| Control Deck | `http://127.0.0.1:8765/` | `scripts/serve_business_workbench.py` |
| Market Command | `http://127.0.0.1:8770/` | `scripts/serve_market_command_ms10.py` |
| Production Studio | `http://127.0.0.1:8765/dashboard/production.html` | Business Workbench route |

Control Deck and Production Studio intentionally share the Business Workbench service. GoldenEye remains projection-oriented, and Market Command retains its own control boundary.

### Components

- `dio-goldeneye.service`: user service for port 8766.
- Existing or normalized `dio-control-deck.service`: user service for port 8765.
- Existing or normalized `dio-market-command.service`: user service for port 8770.
- `dio-apps.target`: starts the three services together.
- `scripts/launch_dio_apps.py`: starts the target, waits on bounded health checks, validates portfolio truth, and opens the launcher.
- A local launcher page with four tiles, service state, endpoint health, and portfolio truth.
- A Debian `.desktop` entry invoking the launcher command.

## Startup and health behavior

1. Start `dio-apps.target`.
2. Poll bounded health endpoints; do not sleep indefinitely.
3. Force one portfolio import so stale cached state cannot mask a changed receipt.
4. Require the 53/15/68 invariant before displaying “portfolio verified.”
5. Show each tile as ready, unavailable, or truth-blocked.
6. Opening a tile never creates execution, publication, outreach, spend, payment, or release authority.
7. A failed service or invalid portfolio receipt remains visible with a corrective action; the launcher must not invent success.

## Safety and authority boundaries

All servers remain localhost-only. Existing confirmation gates and policy controls remain authoritative. The launcher may start, stop, restart, inspect, and open local surfaces, but may not authorize commercial actions or external effects.

No secret values appear in the launcher page, logs, command line, or systemd unit files. Existing environment-loading behavior remains within the services that own it.

## Validation

Automated coverage must include:

- historical crosswalk remains exactly 53 rows;
- frozen summary validates exactly 15 unique extensions;
- derived portfolio is exactly 68 rows;
- missing or invalid extension receipt yields visible 53-row fallback;
- source fingerprint changes when either input changes;
- Control Deck, Market Command, GoldenEye, and launcher health agree on 68;
- all three user services bind only to localhost and use distinct ports;
- Production Studio resolves through the shared Business Workbench service;
- launcher timeout and partial-service failure are truthful;
- no launcher action changes commercial or external authority.

Manual acceptance on Debian:

```text
one click -> services ready -> launcher opens
GoldenEye opens on 8766
Control Deck opens on 8765
Market Command opens on 8770
Production Studio opens on the 8765 production route
all portfolio surfaces display 68 = 53 historical + 15 verified extensions
```

## Non-goals

- Rewriting the historical 53-row crosswalk.
- Promoting candidates beyond the frozen 15 extensions.
- Claiming commercial validation, willingness to pay, revenue, or legal authority.
- Exposing services beyond localhost.
- Replacing the existing DIO operator surfaces.
