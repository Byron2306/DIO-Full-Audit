# Production Engine Attachment Audit

Date: 2026-08-16
Audit tool: `scripts/audit_product_engines.py`

## Corrected Verdict

The previous audit treated source-code wiring as equivalent to production attachment. That was too generous.

The active audit now grades each engine by evidence level:

1. `detached`
2. `code_attached_runtime_missing`
3. `structural_proof`
4. `execution_proof`

A function import, dashboard action, path check, or string match can support **structural** evidence. It cannot by itself create execution proof.

## Execution-Proof Requirements

| Engine | Minimum execution evidence |
| --- | --- |
| Evidex | successful `EVIDEX_RUN_RECEIPT.json` |
| HOMS | completed `HOMS_HYMARK_BATCH_RECEIPT.json` with at least one submission |
| Sophia | `SOPHIA_REVIEW_RECEIPT.json` plus completed grounded reviewer commentary |
| VAMP | review-ready snapshot job with concrete output lineage |
| Document Studio | `DOCUMENT_STUDIO_RECEIPT.json` plus automated QA pass; translation delivery has a separate language-authority gate |
| NicheFoundry media | media receipt `ready` plus actual reel file plus native reel receipt |

## Important Consequences

- HOMS code is attached to HyMark, but source directories must survive promotion and resolve to a valid batch folder before execution.
- Document Studio has a commercial route, but translation approval is not equivalent to target-language authority.
- The media bridge may report `render_ready` when inputs are valid but rendering is skipped. That is not a rendered artifact.
- Product-class profile extensions may name likely processors without being considered attached executable products.

## Dashboard Meaning

Engine cards should be interpreted as evidence status, not marketing readiness.

`structural_proof` means “the route appears wired and runtime prerequisites are present.”

`execution_proof` means “a qualifying execution receipt and artifact lineage were found.”

Neither state creates customer authority, public-release authority, or proof of repeatable commerce.

## Remaining Work

Run and retain current controlled execution receipts for each major engine under the corrected contracts, then surface the latest valid receipt rather than a hard-coded readiness percentage.
