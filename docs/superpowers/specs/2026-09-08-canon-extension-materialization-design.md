# Canon Extension Materialization Design

## Purpose

Close the missing provenance stage for the 11 receipt-bound canon extensions without fabricating historical Gamma provenance.

The current ProductGrade workflow assumes that each receipt-bound extension already has:

- `state/product_portfolio/canon_extensions/<slug>/site/index.html`
- a generation receipt beside it

Those files are not present after checkout, are not created by the ProductGrade tests, and are not created by the current acceptance workflow. The sealer therefore refuses before native 15x3 execution begins.

## Truth boundary

This repair proves deterministic engineering provenance only.

It does not prove buyer demand, payment, legal approval, publication authority, investment interest, funding approval, market performance, or commercial validation. All materialization and downstream receipts must preserve:

- `authority_created: false`
- `external_effects: false`
- `commercial_validation: UNPROVED`

The four `studio_product_grade` extensions retain their existing upstream Studio ProductGrade provenance and are not rematerialized by this subsystem.

## Architecture

For the 11 `receipt_bound` canon extensions, introduce a deterministic canon materializer between the immutable historical 53x3 anchor and the existing provenance sealer.

```text
immutable historical 53x3 anchor
        +
canon extension spec + native profile
        |
        v
CANON EXTENSION MATERIALIZER
        |
        +-- site/index.html
        +-- CANON_EXTENSION_MATERIALIZATION_RECEIPT.json
        |
        v
CANON EXTENSION PROOF SEAL
        |
        v
native 15 x 3 ProductGrade
        |
        v
45 buyer artifacts
        |
        v
68 x 3 portfolio / 204 journeys
```

The materializer must never emit a `GAMMA_RECEIPT.json`, because Gamma is not the source of these canon artifacts.

## Canon artifact inputs

Each receipt-bound materialization is derived from:

1. The extension row in `products/canon_extension_product_grade.py`.
2. The matching profile in `products/canon_extension_native_profiles.py`.
3. The immutable historical anchor at `evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json`.

The historical anchor is a lineage root, not a claim that the extension existed in the historical 53-product corpus.

## Canon artifact output

Each receipt-bound extension gets:

`state/product_portfolio/canon_extensions/<slug>/site/index.html`

The HTML is deterministic and buyer-readable. It contains the extension identity, buyer, purpose, bounded normal-case evidence content, and explicit human/authority boundary derived from the native profile. It has no timestamp, random identifier, network dependency, or external effect.

The canonical surface is a stable product-definition artifact. The downstream normal/messy/adversarial ProductGrade artifacts remain separate execution outputs under `state/product_grade/canon_extensions/.../variants/.../customer_delivery/index.html`.

## Materialization receipt

Each generated canon site receives:

`state/product_portfolio/canon_extensions/<slug>/site/CANON_EXTENSION_MATERIALIZATION_RECEIPT.json`

Schema:

`dio.canon_extension.materialization_receipt.v1`

Required fields:

- `status: PASS`
- `canon_id`
- `name`
- `slug`
- `primary_artifact`
- `primary_artifact_sha256`
- `profile_fingerprint`
- `historical_anchor`
- `historical_anchor_sha256`
- `authority_created: false`
- `external_effects: false`
- `commercial_validation: UNPROVED`
- `claim_boundary`
- deterministic `receipt_fingerprint`

A batch receipt records exactly 11 targets and emits acceptance token:

`DIO_CANON_EXTENSION_11_MATERIALIZED`

only when all 11 artifacts and receipts are created successfully.

## Product spec change

For the 11 `receipt_bound` rows in `CANON_EXTENSIONS`, change `proof_receipt` from `GAMMA_RECEIPT.json` to `CANON_EXTENSION_MATERIALIZATION_RECEIPT.json`.

Do not change the four Studio rows.

## Seal hardening

`products/canon_extension_proof_seal.py` must continue to bind the current artifact bytes to the source receipt, but it must additionally refuse when the source receipt does not itself bind the current artifact SHA-256.

This preserves compatibility with existing test fixtures that already declare an artifact SHA while preventing a materialization receipt from being detached from the artifact it claims to describe.

The existing seal remains a provenance-custody receipt and does not itself create ProductGrade or commercial validation.

## Workflow

Update `.github/workflows/dio-canon-extension-productgrade.yml` so the acceptance sequence is explicitly:

1. Install dependencies.
2. Run ProductGrade and materializer tests.
3. Capture immutable historical 53x3 anchor hash.
4. Materialize the 11 receipt-bound canon extensions with `--require-all`.
5. Assert 11 canon sites and 11 materialization receipts exist.
6. Seal all 11 receipt-bound canon extensions.
7. Execute native 15x3 ProductGrade.
8. Assert 45 customer-delivery HTML artifacts exist.
9. Aggregate all 15 extensions.
10. Seal the 68x3 portfolio.
11. Verify 15/15, 45/45, 68/68, 204/204 and unchanged historical anchor hash.
12. Upload JSON evidence plus the generated canon and buyer HTML artifacts so CI proof is inspectable rather than receipt-only.

## Tests

Add materializer tests proving:

- exactly 11 receipt-bound extensions materialize;
- exactly 11 canonical HTML artifacts and 11 materialization receipts are produced;
- each receipt binds the live artifact SHA;
- each receipt binds the immutable historical anchor SHA;
- each receipt binds a deterministic native-profile fingerprint;
- rerunning materialization produces byte-identical artifact and receipt hashes;
- materialization never creates authority or external effects;
- commercial validation remains `UNPROVED`;
- the sealer refuses after artifact tampering because the source receipt no longer binds the live artifact.

Existing 15x3 and 68x3 tests must remain green.

## Exit condition

The repair is complete only when CI proves, from a clean checkout:

```text
11/11 canon extensions materialized
11/11 provenance seals written
15/15 extensions ProductGrade verified
45/45 controlled extension journeys verified
68/68 canon products ProductGrade verified
204/204 controlled portfolio journeys verified
historical 53x3 anchor unchanged
```

The public-site live-proof wiring is a subsequent task. This repair's job is to make the underlying artifacts and receipts real, reproducible, inspectable, and truth-bound first.
