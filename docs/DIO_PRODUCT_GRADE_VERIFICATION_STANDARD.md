# DIO Product-Grade Verification Standard

## Purpose

DIO's execution receipts prove that governed compositions execute. They do **not** prove that the resulting customer artifact is professionally useful, generalises beyond a canned fixture, or is good enough for a real buyer to purchase.

Product-Grade Verification (PGV) is the next gate.

It is a verification layer over existing Studio execution. It is **not** a new product engine and creates no new external authority.

## Maturity ladder

```text
REGISTERED
  -> COMPOSITION PROVED
  -> CONTROLLED EXECUTION PROVED
  -> NATIVE MULTI-ORGAN EXECUTION PROVED
  -> PRODUCT-GRADE VERIFIED
  -> CONTROLLED PILOT READY
  -> REAL BUYER REVIEWED
  -> REAL PAYMENT VERIFIED
  -> REPEATABLE COMMERCIAL PROOF
```

A product may not skip a rung by inference.

## Product-grade rule

A Studio is `PRODUCT_GRADE_VERIFIED` only when:

1. its native capability closure is already proved;
2. its product-grade score is at least **85 / 100**;
3. it has **zero critical blockers**;
4. an unseen-input mutation produces the correct changed customer artifact without cross-job leakage;
5. the customer-facing artifact is separated from internal DIO proof artifacts;
6. domain-specific truth and authority boundaries remain intact.

Product-grade verification does **not** claim that customers will pay. Payment remains unproved until a real buyer accepts a real offer and DIO records a verified payment event.

## 100-point rubric

| Dimension | Points | Question |
|---|---:|---|
| Native execution integrity | 15 | Did the already-proved composition close every declared capability and preserve artifact integrity? |
| Job fidelity and completeness | 20 | Does the artifact actually solve the buyer job and contain the required deliverables? |
| Unseen-input generalisation | 15 | Does a materially changed job/input produce the corresponding changed output without stale fixture leakage? |
| Professional customer artifact | 20 | Is the customer artifact coherent, polished, readable and free of internal engineering/proof language? |
| Domain-specific quality | 15 | Does the output satisfy the important domain checks for this Studio? |
| Truth and authority | 10 | Are unsupported claims, fabricated evidence and consequential authority still refused? |
| Delivery readiness | 5 | Is there an obvious customer artifact/package that can be opened and reviewed without reading DIO internals? |

## Critical blockers

Any critical blocker forces `PRODUCT_GRADE_REFUSE` regardless of numeric score.

- **CANNED_FINAL_COPY**: the supposed execution result is materially pre-authored in the test manifest instead of being produced from buyer/source inputs.
- **INTERNAL_PROOF_LANGUAGE_LEAK**: customer-facing output exposes DIO laboratory tokens such as `CONTROLLED COMPOSITION PROOF`, `SOURCE_BOUND`, `NEEDS_YOU`, raw `REFUSE`, schema/debug IDs or fixture labels.
- **CROSS_JOB_LEAKAGE**: an unseen-input run retains customer-specific content from the baseline job.
- **BROKEN_CUSTOMER_ARTIFACT**: the primary customer deliverable is missing, empty or structurally unusable.
- **FABRICATED_OR_UNBOUND_CLAIM**: the output invents evidence, sources, quotations, facts or consequential claims.
- **AUTHORITY_LEAKAGE**: the product creates send, publication, spend, payment, lender, legal, employment or other human-held authority.
- **DOMAIN_SAFETY_FAILURE**: the product makes a forbidden domain conclusion, such as lender approval/affordability or automatic publication.

## Studio-specific product-grade checks

### Site Studio

The customer website must be responsive, coherent and buyer-oriented; contain the requested brand/job information; contain no DIO proof-lab language; avoid invented clients/testimonials/credentials; and survive an unseen brand/brief mutation without baseline brand leakage.

A static proof page that merely displays pre-authored `brand` and `sections` text is **not yet sufficient** evidence of a product-grade Site Studio transformation.

### Professional Correspondence Studio

The customer draft must preserve supplied facts, tone and commitments; avoid admissions, waivers, promises or legal positions not supplied by the user; and change correctly when the disputed facts/tone change.

A manifest that already contains the final email subject and body is **not yet sufficient** evidence that the Studio can draft from raw correspondence facts.

### Finance Readiness Studio

The dossier must compute evidence gaps from the supplied requirement/evidence set; distinguish evidence, assumptions and decisions; update correctly when evidence changes; and never infer lender approval, affordability, underwriting, credit conclusions or regulated financial advice.

### Article & Publication Studio

The article package must derive prose and claim/source relationships from supplied source material; preserve references and unsupported-claim refusals; avoid fabricated sources/quotations; and remain human-held for publication.

A manifest that already contains the final article section prose is **not yet sufficient** evidence of source-to-article generation.

## Human buyer review

Automated PGV measures engineering and objective product quality. Subjective usefulness and willingness to pay require real human evidence.

A later blind buyer review should record, against an immutable artifact fingerprint:

- target-buyer fit;
- correctness/trust;
- edit burden;
- usefulness;
- presentation quality;
- whether the reviewer would use the artifact;
- whether the reviewer would request a paid pilot at the quoted price.

A positive review is **not** a verified payment.

## Commercial truth

The following claims remain forbidden until directly evidenced:

```text
customers_will_pay = UNPROVED
verified_payment = UNPROVED
repeatable_customer_outcome = UNPROVED
commercial_validation = UNPROVED
```

The strongest permissible statement after an automated PGV pass is:

> This Studio has passed DIO product-grade engineering and output verification on controlled and unseen-input cases. Real buyer demand and payment remain unproved until observed.
