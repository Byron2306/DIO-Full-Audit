# Canon Extension Native ProductGrade Design

## Purpose

Move the eleven receipt-bound DIO canon extensions from provenance-only proof to native ProductGrade without weakening the 15/15 canon-extension proof already established.

The new proof must answer a stronger question than "does the canon landing page exist?" A product reaches ProductGrade only when DIO executes a controlled buyer job, produces a separate buyer-facing artifact, proves semantic custody through Lingua, passes BEAST mechanical checks, survives an unseen-input mutation, and preserves all external-authority holds.

## Scope

The eleven target extensions are:

1. Article Publication
2. Contract Desk
3. Corporate Readiness
4. EntrepreneurProof
5. Finance Readiness
6. FundingFinder
7. InvestorProof
8. Launch Studio
9. POPIA Readiness
10. Professional Correspondence
11. Report & Pitch Studio

The four already verified Studio extensions remain unchanged.

## Core invariant: dual binding

A native ProductGrade receipt must bind two different artifacts:

- **Canon surface**: the already sealed extension artifact at `state/product_portfolio/canon_extensions/<slug>/site/index.html`. This proves product identity and continuity with the 15/15 canon-extension provenance chain.
- **Customer artifact**: a newly generated controlled buyer deliverable under `state/product_grade/canon_extensions/<slug>/customer_delivery/`. This is the artifact that earns ProductGrade.

The canon surface must never be substituted for the customer artifact, and the existing `CANON_EXTENSION_PROOF_RECEIPT.json` must not be rewritten by the native ProductGrade run.

## Proof families

The eleven products share one native proof spine but use four product-family adapters.

### Publication and professional artifact family

Products: Article Publication, Contract Desk, Professional Correspondence, Report & Pitch Studio.

Controlled jobs produce publication drafts, contract review briefs, professional correspondence, and report/pitch briefs. Family checks require the buyer request and evidence anchors to appear, internal proof language to remain absent, and unsafe commitments or unsupported claims to remain held.

### Readiness and assurance family

Products: Corporate Readiness, Finance Readiness, POPIA Readiness.

Controlled jobs produce readiness assessments from declared requirements and supplied evidence. Family checks require supported/missing requirement distinctions, explicit decision boundaries, and no fabricated approval, legal conclusion, affordability conclusion, or compliance certification.

### Opportunity and venture intelligence family

Products: EntrepreneurProof, FundingFinder, InvestorProof.

Controlled jobs produce evidence-bound venture, funding, or investor dossiers from supplied venture facts and opportunity criteria. Family checks require the supplied venture identity, criteria, evidence gaps, and human decision boundary to remain visible, with no invented investor interest, guaranteed funding, valuation, or approval claim.

### Launch orchestration family

Product: Launch Studio.

The controlled job produces a launch brief from supplied audience, proposition, channels, and constraints. Family checks require the supplied offer/audience anchors, channel plan, held spend/publication authority, and no fabricated performance claim.

## Native execution pipeline

For each product:

1. Verify the canon surface and the existing canon proof seal are present.
2. Load a product profile containing family, controlled baseline fixture, unseen fixture, semantic anchors, and forbidden claims.
3. Convert the fixture into product-family semantic units.
4. Register those units through `adapters.lingua.lifecycle.register_product_source` using an isolated ProductGrade state root. The resulting `dio.lingua.semantic_object.v1` and `dio.lingua.product_registration_receipt.v1` are persisted with the case.
5. Render a deterministic HTML buyer artifact from the registered Lingua semantic units. The renderer is a native DIO ProductGrade adapter, not a copied final-answer fixture.
6. Run `adapters.beast_product_grade.run_beast_artifact_checks` over the generated customer-delivery workspace.
7. Execute family-specific semantic/domain checks over the generated artifact.
8. Re-run the same pipeline with the unseen fixture. The unseen artifact must have a different SHA-256, contain the unseen mutation anchor, omit the baseline-only anchor, retain Lingua custody, and pass BEAST.
9. Write `state/product_grade/canon_extensions/<slug>/PRODUCT_GRADE_RECEIPT.json` only after all gates have been measured.

## Native receipt schema

New receipts use `dio.product_grade.canon_extension_native.v2` and contain at minimum:

- `slug`, `canon_id`, `family`
- `status`
- `canon_artifact`, `canon_artifact_sha256`
- `canon_proof_receipt`, `canon_proof_receipt_sha256`
- `customer_artifact`, `customer_artifact_sha256`
- `lingua_semantic_custody`
- Lingua object and registration receipt fingerprints
- `beast_mechanical_pass` and BEAST evidence
- `unseen_input_generalisation` plus baseline/unseen hashes and anchor checks
- family/domain checks
- `external_effects: false`
- `authority_created: false`
- `customers_will_pay: "UNPROVED"`
- `verified_payment: "UNPROVED"`
- `commercial_validation: "UNPROVED"`

`PRODUCT_GRADE_VERIFIED` is permitted only when every required gate passes.

## Gauntlet compatibility

`products/canon_extension_product_grade.py` is extended to understand the v2 dual-bound native receipt.

For v2 receipts it must verify against live bytes:

- canon surface hash equals `canon_artifact_sha256`
- canon proof-seal file hash equals `canon_proof_receipt_sha256`
- customer artifact path remains inside the repo root
- customer artifact exists and its live SHA-256 equals `customer_artifact_sha256`
- `primary_artifact_sha256` equals the customer artifact hash, not the canon surface hash
- BEAST, Lingua, unseen-input, authority and external-effect gates are truthful

Legacy native receipts remain supported only under the old single-artifact checks so existing tests and historical evidence are not rewritten.

## Unseen-input rule

Unseen-input generalisation is evidence, not a declared flag. Each profile supplies a baseline fixture and a materially different unseen fixture. The same family renderer must execute both.

A pass requires all of:

- unseen customer artifact SHA differs from baseline SHA
- unseen mutation anchor appears
- baseline-only anchor disappears
- unseen Lingua object binds the unseen semantic units
- unseen BEAST mechanical checks pass
- no forbidden family claim appears

## Error handling and fail-closed behavior

A product remains `PRODUCT_GRADE_REFUSE` when any required path is missing, any path escapes the repo root, any hash drifts, Lingua registration is invalid, BEAST fails, unseen-input checks fail, a forbidden domain claim appears, or external authority/effects are promoted.

The batch runner may complete with mixed results, but `--require-all` exits non-zero unless all eleven native cases verify.

## Truth boundary

This work proves controlled native execution and buyer-artifact quality for the eleven extensions. It does not prove buyer demand, willingness to pay, verified payment, legal approval, publication authority, investment interest, funding approval, POPIA compliance certification, or market performance. Those remain unproved until independently observed.

## Acceptance

The work is complete only when:

- synthetic TDD tests prove dual-binding, tamper refusal, Lingua custody, BEAST gating, unseen-input gating, and all eleven profile identities;
- GitHub Actions is green for the new tests;
- the user runs the native batch against the real local 15-extension state;
- eleven native receipts verify;
- the existing canon-extension gauntlet reports `product_grade_verified_count: 15`, `product_grade_refuse_count: 0`, and `DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED` while `commercial_validation` remains `UNPROVED`.
