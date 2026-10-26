# ContractProof Release-Grade Golden Lane Design

Status: approved design baseline  
Date: 2026-10-25  
Initial product: ContractProof  
Initial surface: Vesper web  
Initial provider: PayPal through DIO Edge Commerce

## Intent

DIO already contains most of the organs required to take a customer from conversation to delivery, and it contains several capable artifact renderers. The missing property is one authoritative, recoverable path joining those organs together.

This design establishes one production-shaped golden lane:

```text
Vesper web ingress
  -> canonical customer case
  -> quarantined and cleared PDF/DOCX source set
  -> accepted ContractProof scope and exact ZAR quote
  -> governed locked ZAR-to-USD conversion
  -> Edge USD order and PayPal checkout
  -> signed PayPal webhook
  -> canonical settlement receipt
  -> ContractProof execution
  -> professional finishing
  -> artifact quality assurance
  -> hash-bound release manifest
  -> human release approval
  -> customer delivery receipt
```

The first goal is not broad portfolio activation. It is a complete, inspectable commercial proof that can later be reused by the other exact-bound products and then by Studio-native, composed, and profile-extension products.

## Why this is needed

The inspected repository has strong individual components but several disconnected truths:

- Vesper can create and advance customer cases, but does not orchestrate order creation.
- Edge Commerce can create PayPal checkouts and treats the signed webhook as payment authority, but production code does not join that result to the full customer journey.
- settlement truth produces the receipt required by fulfilment, while older payment reconciliation advances a case without producing that canonical receipt.
- `attach_order_to_case`, checkout registration, and payment reconciliation are not called from a live production orchestration path.
- Format Core, Document Studio, Production Studio, and product-specific renderers overlap without one policy-controlled professionalization stage.
- release v2 can bind human authority to exact file hashes, but artifact quality and professionalization are not universally placed before that boundary.
- Vesper web currently has both an edge-reconciled lane and an untracked direct public API implementation.

Representative artifact inspection found a real quality gradient. ContractProof and AgentAuthority reports are clean internal review documents but are one-page, untagged PDFs with anonymous metadata. HOMS Learning outputs are considerably closer to customer publication quality. Studio HTML can be visually polished while still containing nonfunctional forms, placeholder addresses, repeated copy, or copy defects. Therefore successful rendering cannot be treated as professional release readiness.

## Goals

1. Provide one canonical Vesper-web-to-delivery journey for ContractProof.
2. Make Edge Commerce and its verified signed provider webhook the production payment truth.
3. Create exactly one canonical settlement receipt for an accepted provider capture.
4. Bind conversation, case, quote, order, settlement, fulfilment, artifact, release, and delivery identities.
5. Route ContractProof output through a governed professional finishing stage.
6. Preserve semantic truth while improving presentation, accessibility, metadata, and packaging.
7. Prevent fulfilment before valid settlement and delivery before exact human-approved release.
8. Make duplicate, ambiguous, failed, refunded, and reversed events operationally recoverable.
9. Retain evidence sufficient to prove a real sandbox journey and a controlled recovery drill.
10. Establish reusable contracts for later product activation without wiring 68 bespoke commerce paths.

## Non-goals

- Activating all 68 products in the first release.
- Adding Telegram, voice, PayFast, subscriptions, or autonomous release to the first slice.
- Replacing the Product Compiler or existing canonical product definitions.
- Letting a presentation capability decide product semantics.
- Treating a browser payment return as payment authority.
- Automatically delivering artifacts without named human approval.
- Rebuilding the entire customer journey platform before proving one path.
- Making the local PayPal store a second production ledger.

## Anti-goals

The implementation is considered a failure if it creates duplicate customer charges, advances a case from an unverified payment signal, loses the relationship between payment and delivered bytes, allows a finisher to change semantic findings silently, releases a package with broken customer actions, or requires routine manual editing of state files to recover ordinary failures.

## Constraints

- Existing customer-case stages and authority boundaries remain in force.
- Existing user changes in the working tree must be preserved.
- Production payment truth comes from the DIO Edge Commerce record produced by a verified signed PayPal webhook.
- PayPal browser return is diagnostic/customer feedback only.
- The local PayPal implementation remains a controlled test or operator diagnostic path.
- Vesper interprets and presents journey truth but cannot manufacture payment, fulfilment, or release authority.
- Fulfilment requires `dio.settlement_receipt.v1` and a case at `PAYMENT_VERIFIED`.
- Finishing may improve presentation but may not silently alter facts, findings, evidence relationships, uncertainty, or authority boundaries.
- Customer artifacts remain held until an exact manifest has passed QA and received one-use human release authority.
- Critical failures cannot be waived.
- The first production pilot is web-only, PayPal-only, ContractProof-only, and manually released.
- Customer source material for the pilot is uploaded as PDF or DOCX; pre-structured JSON is not a customer-facing input contract.
- The customer explicitly accepts the exact quote hash, ZAR amount, locked USD settlement amount, FX rate/source/timestamp/expiry, scope hash, and source-manifest hash in an authenticated Vesper web action before order creation.
- The pilot delivery channel is an authenticated, expiring Vesper web download; Outlook is not a delivery authority for the pilot.
- One named pilot operator may perform intake clearance, commercial review, artifact review, and release approval, but each action is a separately identified receipt. Customer quote acceptance is a distinct customer action and cannot be supplied by the operator.

## Approaches considered

### A. Golden-lane, spine-first — selected

Complete one genuine ContractProof journey, prove its recovery behaviour, and generalize the contracts outward. This gives the strongest commercial evidence and exposes integration defects before portfolio expansion.

### B. Artifact-first portfolio upgrade

Apply a central finishing registry to all executable products before joining commerce. This improves visible quality sooner but leaves the commercial journey disconnected.

### C. Full convergence before release

Unify every ingress, payment store, product binding, and renderer in one programme. This is architecturally broad but creates excessive coupling and delays the first end-to-end proof.

Approach A was selected because the costliest defects are boundary defects, not isolated renderer defects, and a complete trace provides a reusable proof standard for later products.

## Authority architecture

### Vesper and ingress

Vesper owns conversation, intake, identity continuity, attachment quarantine, and explicit customer acceptance. The edge-reconciled web lane is the first canonical public ingress. Any direct public API must remain a thin transport adapter over the same durable ingress and may not bypass it.

The pilot accepts actual PDF and DOCX uploads. Files first enter quarantine and are bound into an immutable source manifest containing byte length, SHA-256, detected type, declared type, and customer-visible filename. They must pass type/structure checks and explicit operator clearance before local text extraction or ContractProof execution. A pre-structured JSON payload is an internal executor contract only.

Files received before quote acceptance may update the current source set and force scope and pricing to be recalculated. A material file, scope, product, or commercial change after acceptance invalidates the acceptance and creates an amendment or successor case; it may never mutate the accepted basis silently.

### Presence Core

Presence Core owns the canonical customer case, immutable product and scope binding, quote lineage, and customer-facing journey stage. A material source, scope, or product change after quote creation creates a successor case rather than mutating the existing commercial basis.

### Edge Commerce

Edge Commerce owns the production order, checkout, and provider-verified payment state. The order is attached to the case before the checkout URL is shown. Only a verified, matched PayPal webhook can mark the order paid.

The commercial offer remains denominated in ZAR. Because the selected PayPal path does not support ZAR, a governed FX receipt locks the corresponding USD settlement amount before acceptance. The receipt binds quoted ZAR minor units, USD settlement minor units, rate, source, observed time, expiry, rounding method, quote hash, scope hash, and source-manifest hash. Expired or changed FX terms require a new acceptance. The Edge order stores both quoted and settlement terms and charges only the accepted USD amount.

### Settlement Truth

Settlement Truth projects one verified paid capture into one `dio.settlement_receipt.v1`. The receipt must be bound to provider capture, Edge order, canonical quote, case, product, amount, and currency. Repetition returns the existing receipt; conflicting reuse creates a hold.

### Product execution

ContractProof owns semantic execution: obligations, clauses, evidence relationships, conflicts, gaps, findings, uncertainty, and review status. It emits a structured semantic artifact plus candidate output files.

### Professionalization

A shared professionalization router selects approved finishing capabilities from product policy. ContractProof initially routes through Format Core to accessible HTML, PDF, and editable DOCX. Document Studio may later add richer publication packaging, but it is not required for the first proof.

### Release and delivery

Artifact QA produces a machine-readable result. Passing output is incorporated into an exact file manifest. A human grants one-use release authority for that manifest hash. Delivery transports only that approved manifest and returns a durable receipt.

The first delivery transport is an authenticated Vesper web download. It issues an expiring, one-use or explicitly bounded download grant tied to customer session, case, final manifest SHA-256, and release-authority ID. The download handler revalidates the file hashes immediately before streaming and records a durable delivery receipt. It never exposes raw filesystem paths. Outlook delivery remains out of scope for the first pilot.

Commercial holds are an orthogonal overlay rather than extra journey stages. A hold records type, affected authority boundary, evidence, actor, and resolution. An active hold freezes the relevant transitions without erasing the last valid case stage.

## Canonical lineage

Every successful journey retains the following ancestry:

```text
conversation_id
  <-> case_id
  <-> quote_id and quote hash
  <-> order_id
  <-> provider order, event, and capture IDs
  <-> settlement receipt ID and hash
  <-> fulfilment request and job IDs
  <-> raw semantic artifact digest
  <-> professionalization receipt
  <-> final manifest SHA-256
  <-> release authority
  <-> delivery receipt
```

No downstream identifier substitutes for an upstream identifier. Provider IDs never replace DIO IDs.

## Journey state model

The customer case stage is a summary projection. Durable receipts are the authoritative evidence behind transitions.

| Case stage | Required evidence | Permitted next action |
|---|---|---|
| `SCOPE_ASSESSED` | Immutable product, scope hash, and attachment set | Calculate price |
| `PRICE_RECOMMENDED` | Pricing-policy version and recommendation | Create bounded quote |
| `QUOTE_READY` / `NEEDS_YOU` | Canonical quote and explicit acceptance | Create order |
| `PAYMENT_PENDING` | Order bound to quote and checkout receipt | Await provider truth |
| `PAYMENT_VERIFIED` | Verified webhook and canonical settlement receipt | Build fulfilment request |
| `WORK_QUEUED` | Fulfilment request and execution profile | Execute ContractProof |
| `PROCESSING` | Job claim and execution attempt | Produce held artifacts |
| `REVIEW_READY` | Raw artifacts and professionalization receipt | Run artifact QA |
| `RELEASE_APPROVAL` | Passing QA and hashed release manifest | Request human approval |
| `DELIVERED` | Consumed release authority and transport receipt | Close case |
| `CLOSED` | Complete retained lineage | No further mutation |

## Idempotency

Stable operation keys are derived as follows:

- ingress: channel plus provider event or request ID;
- quote: case ID, product ID, scope hash, and pricing-policy version;
- acceptance: authenticated customer identity, quote hash, source-manifest hash, scope hash, and FX receipt hash;
- order: canonical quote hash;
- checkout: DIO order ID;
- webhook: PayPal event ID;
- settlement: PayPal capture ID plus quote hash;
- fulfilment: settlement receipt hash plus execution-profile hash;
- professionalization: raw artifact manifest hash plus finishing-policy version;
- release: final artifact manifest hash;
- delivery grant: approved manifest hash, release-authority ID, customer session, and expiry;
- delivery: approved manifest hash plus delivery channel and grant ID.

An exact replay returns the existing receipt. The same key with different content creates a reconciliation hold.

## Payment reconciliation

1. Explicit quote acceptance creates one Edge order.
2. Acceptance is an authenticated Vesper web action over the exact quote, source, scope, and unexpired FX hashes.
3. The accepted FX receipt creates one USD Edge order while retaining the ZAR quoted terms.
4. The order is attached to the case before checkout presentation.
5. The PayPal browser return reports submission only.
6. The signed webhook is verified and matched to provider order, DIO order, accepted quote, accepted FX receipt, USD amount, currency, product, and case.
7. A completed matching capture creates exactly one settlement receipt containing both quote and settlement terms.
8. Only that receipt advances the case to `PAYMENT_VERIFIED`.
9. Fulfilment independently validates that receipt before accepting work.

Mismatch, missing lineage, refund, reversal, and duplicate conflicts enter a commercial hold and cannot start fulfilment.

A refund or reversal before execution cancels or holds fulfilment. During execution it freezes release and creates an operator exception. After delivery it preserves the historical delivery and creates a post-delivery financial exception.

## Ingress and side-effect recovery

The durable ingress ledger uses these operational states:

```text
RECEIVED -> PROCESSING -> COMPLETED
                    \-> FAILED_RETRYABLE
                    \-> HELD_RECONCILIATION
```

Completed duplicate events return their previous response. A stale processing claim is retryable only when no external side effect was possible. Ambiguous work enters `HELD_RECONCILIATION`.

Operator tooling must support inspect, replay, resolve, and abandon. Every action records actor, reason, timestamp, original body hash, previous state, and resulting receipt. Vesper must not create a second order or ask for a second payment merely because a response was lost.

Equivalent rules apply at every side-effect boundary. An ambiguous order creation queries by idempotency key before retry. Duplicate webhooks return prior reconciliation. Execution retries use retained attempt directories. Finishing never overwrites semantic source artifacts. Ambiguous delivery is queried at the transport before resend.

## Professional artifact model

The executor supplies a semantic artifact manifest containing:

- product, case, job, and execution-profile identifiers;
- structured semantic output and semantic digest;
- evidence and source references;
- required disclaimers and authority boundaries;
- audience and document purpose;
- candidate files and supported formats;
- internal or sensitive material excluded from customer packaging.

Product policy declares the required enhancer sequence, output formats, brand and accessibility profile, QA profile, reviewer role, and release eligibility. Multiple finishers may run only in a declared acyclic order.

ContractProof's first package contains an executive review summary, obligation and clause matrix, evidence reconciliation, missing or conflicting evidence, priority human decisions, source index, limitations, release status, and package manifest.

## Semantic preservation

Finishers may alter typography, layout, navigation, pagination, accessibility markup, metadata, filenames, and packaging. They may not silently alter obligations, dates, amounts, parties, findings, confidence, evidence relationships, missing-information flags, legal boundaries, or human-review requirements.

The professionalization receipt records input and output semantic digests, capability versions, policy version, produced files, warnings, and whether material content changed. An unexplained semantic digest difference is a hard failure.

Professionalization and QA publish a separate immutable `dio.review_package.v1` bound to the raw fulfilment-result hash. The raw fulfilment result is never rewritten. Deliverable release v2 manifests the final customer files from this review package while retaining the raw execution and semantic lineage.

## Artifact quality gates

1. **Contract:** required sections, fields, sources, disclaimers, and formats exist.
2. **Semantic:** claims, values, evidence links, uncertainty, and authority boundaries are preserved.
3. **Rendering:** no clipping, overflow, broken tables, empty pages, orphaned headings, or unreadable density.
4. **Accessibility:** tagged PDF, declared language, valid heading order, readable tables, meaningful links, keyboard-operable HTML, sufficient contrast, and alt text where needed.
5. **Operational:** links, navigation, forms, downloads, and entry points work; placeholders and unfinished copy are prohibited.
6. **Metadata and brand:** correct title, organisation, subject, dates, product identity, version, filename, and approved visual system.
7. **Package integrity:** exact hashes, safe filenames, deterministic inventory, no secrets, no internal-only proof, and no temporary files.
8. **Human acceptance:** a named reviewer examines representative pages, high-risk findings, usability, and final package.

Gate results are `PASS`, `REVIEW_REQUIRED`, `FAIL`, or `WAIVED`. Waivers require named approver, reason, and expiry, and apply only to non-critical rules. Semantic integrity, broken customer actions, missing payment lineage, secret exposure, and manifest mismatch cannot be waived.

For the pilot, HTML targets WCAG 2.2 AA and PDF targets PDF/UA-1 structure and metadata. A validator limitation may yield `REVIEW_REQUIRED`, but missing document language, heading structure, table semantics, keyboard operation, contrast, or meaningful link text is not treated as a pass merely because the validator is unavailable.

## Verification strategy

Testing proceeds through contract, component, adjacent-boundary integration, fault-injection, artifact acceptance, and full-journey tests. Fault scenarios include lost responses, stale claims, provider timeouts, duplicate and conflicting events, amount mismatch, refund, executor crash, renderer failure, byte mutation after approval, and ambiguous delivery.

Artifact acceptance renders representative first, middle, and final PDF pages and responsive HTML breakpoints. It checks structure and accessibility without depending exclusively on brittle pixel-perfect snapshots.

## Rollout

1. Canonicalise Vesper public ingress and retire stale remote-ASR expectations.
2. Fuse quote acceptance, Edge order, checkout, case binding, webhook reconciliation, and settlement.
3. Fuse settlement-triggered fulfilment and ContractProof dispatch.
4. Add the policy router, Format Core route, semantic-preservation receipt, and artifact gates.
5. Prove controlled end-to-end execution with held delivery and recovery drills.
6. Prove a PayPal sandbox checkout and signed webhook.
7. Run a limited ContractProof/web/PayPal pilot with named operator and mandatory manual release.
8. Expand to the other exact-bound products, then Studio-native products, compositions, and profile extensions. Products without explicit bindings remain unavailable for automated sale.

## Release acceptance

ContractProof is release-ready only when:

- the implementation is tracked and reproducible from the canonical repository;
- focused and full relevant test suites pass without contradictory stale tests;
- one trace reconstructs the full journey lineage;
- duplicates and ambiguous outcomes are safe at every side-effect boundary;
- mismatched commercial facts cannot start fulfilment;
- refund and reversal behaviour has been exercised;
- operator reconciliation needs no manual state-file editing;
- the customer package passes all required artifact gates;
- byte mutation invalidates release approval;
- delivery requires matching settlement, manifest, human authority, and transport receipt;
- a sandbox journey and a controlled recovery drill are retained as evidence;
- the limited pilot has documented hold and rollback controls.

Operational reporting includes stuck ingress events, commercial holds, paid-but-not-queued cases, processing age, failed artifact gates, pending approvals, ambiguous deliveries, and refund exceptions.

## Builder decisions intentionally left open

- Internal module boundaries may follow existing repository conventions as long as commercial orchestration, professionalization policy, artifact QA, and operator reconciliation remain separately testable responsibilities.
- Existing state storage patterns should be reused for the first slice; introducing a new database is not required.
- Exact typography and brand tokens may reuse the current DIO visual system, provided the quality gates pass.
- Test fixtures may use deterministic local fakes except for the explicit PayPal sandbox acceptance run.

