# DIO Obligation Family Expansion — Phase 6

## Status

Phase 6 turns the Phase 5 ContractProof golden incarnation into a product family. TenderProof, GrantProof and PermitProof are independently compiled products over the same shared Evidence, Obligation, Governed Case and proof-pack machinery.

The factory test is strict: `dio/obligations/*` remains unchanged. Product variation belongs in source-bound framework profiles, manifests, fixtures and the small `products/obligationfamily` adapter.

## Incarnations

| Product | Authoritative source type | Human judgement retained |
|---|---|---|
| DIO TenderProof | `tender` | eligibility interpretation, submission approval and award representations |
| DIO GrantProof | `grant` | award-condition interpretation, cost acceptance and funder reporting |
| DIO PermitProof | `permit` | permit-condition interpretation, regulatory submission and operating authority |

All three select WP01 Evidence, WP05 Obligation and WP11 Proof; META Evidence, Assurance, Authority and Room; the read-only file connector; the evidence-pack output; and the internal-proof commercial policy.

## Shared family adapter

`obligation_family_internal_runner_v1` is explicitly scoped to the three Phase 6 products. It validates the product/source-type pairing, requires an explicit operator, invokes Obligation Core without modifying it, materialises a Governed Case, binds locator-specific evidence, assesses review readiness, and emits the five artifacts required by `output.evidence_pack`.

The executor cannot decide eligibility, award, allowability, compliance, legal validity, waiver, permit issuance, operating authority, disclosure or release. Compiler execution remains `NEEDS_YOU`; external release remains `REFUSE`.

`obligation_family_proof_pack_v1` is likewise scoped to the three family products. CapitalRoom is not broadened to PermitProof and does not become the family executor.

## Maturity truth

Each incarnation enters at `internal_proof`, not pilot or customer maturity. The fixtures prove repeatable internal composition only. They are not real tenders, grants, permits, customer evidence, regulator approval, legal advice, revenue proof or product-market validation.

## Acceptance

Run:

```bash
pytest -q tests/test_obligation_family_phase6.py
python3 scripts/validate_obligation_family_phase6.py
```

Acceptance token:

```text
DIO_OBLIGATION_FAMILY_READY
```

Phase 6 is complete when all three manifests compile with complete WP01/WP05/WP11 composition, all three golden sources preserve mixed truth, every proof pack matches the output profile, explicit human gates remain, provider scope is bounded, and a source-type/product mismatch is refused.
