# CI workflow activation and dependency review — 2026-10-27

This is a source/workflow inspection and isolated-runner verification, not a claim that
GitHub Actions executed all restored jobs. The inspected checkout represents the pushed
integrated production-handoff source plus these proposed CI changes.

## Inventory and actual dispatch boundary

There are **38 workflow definitions**, all with `pull_request` triggers. Before this
repair, the vast majority of `push` triggers were pinned to old `agent/...` branches;
normal pushes to `integrated/production-handoff-20261027` could not start them.
PR events with path filters still worked independently. A workflow's mere presence is
not evidence of an executed job or of GitHub branch-protection enforcement.

Three proved, local-only critical gates now respond to scoped `integrated/**` pushes,
retain their PR triggers and can be dispatched manually once present on GitHub's
default branch:

| Workflow | Evidence and repair |
| --- | --- |
| Canon Extension ProductGrade | 44 focused tests passed. Source changes in the materializer now trigger it. Its clean runner required `python-docx`, `python-pptx` and `pillow`, absent from its previous `pytest`-only install. |
| Obligation Family Phase 6 | 11 focused tests and the offline acceptance script passed. Its real PDF output required `reportlab` and document output `python-docx`, absent from the original dependency list. |
| Customer Journey Phase 4 | Eight offline contract tests passed. Integrated pushes and previously missing PR paths now activate the lane. |

The Phase 5 workflow was *not* put on integrated auto-push: the live-ingress test
`test_live_ingress_uses_send_bind_finalize` stalled in this isolated environment,
despite 21 preceding tests passing. That needs a properly scoped service test and
an explicit expected runtime contract before automatic promotion. The workflow's
`pytest | tee` command also lost pytest's exit status; `set -o pipefail` now prevents
false-green diagnostics. `fastapi`, `uvicorn` and `httpx` were missing from its
dependencies. Job execution is now bounded by a timeout.

## Important gates still requiring separate repair

- **38-route Product Class Execution Proof:** the batch test fails in this checkout
  with `ai_incidentroom: persisted controlled review receipt/proof drifted`. Do not
  mark all 38 routes proved or promote this to a required green gate until its
  receipt invariants are repaired and independently rerun.
- **Commercial Truth Phase 10:** three focused tests fail against the expanded
  portfolio/observation baseline (including assumptions about which products exist
  and that a controlled observation count is nonzero). Fix and verify the factual
  test baseline before enabling this historical composite gate on every push.
- **Phase 7 cross-repository golden journeys:** depend on externally pinned Evidex,
  HOMS, NicheFoundry and Sophia checkouts, Ollama installation/model downloads,
  and active local services. These are **integration** gates, not safe replacements
  for quick offline source/receipt tests. The external revisions, network and
  service prerequisites must be verified before automatic enablement.
- **Repository-wide pytest:** in this isolated checkout it fails collection with
  579 errors, including missing BEAST runtime configuration and duplicate test
  basenames across vendor/cross-folder trees. This is not a clean full-suite result.

## Verification and guardrails

- The workflow-activation regression failed four expected assertions before repair,
  then passed all four afterward.
- 63 canon-extension, obligation-family and Phase 4 tests passed in a minimal venv
  after installing the now-declared dependencies.
- The combined focused checks passed **156/156** in 8.22 seconds.
- Existing runtime, local secrets, telemetry, business evidence and historical
  acceptance receipts were not modified or promoted.
- CI job results remain distinct from professional, customer and commercial proof.

GitHub Actions still needs its own run results after installation. Review live run
logs for each enabled lane, and avoid interpreting a skipped path-filtered workflow
as a successful test.
