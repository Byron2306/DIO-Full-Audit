# ContractProof Release-Grade Golden Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one recoverable, release-grade ContractProof journey from authenticated Vesper web upload through accepted ZAR/USD terms, verified PayPal settlement, professionalized artifacts, human release, and authenticated download.

**Architecture:** Extend the existing Presence Core case as the single journey spine and add small content-addressed contracts at each side-effect boundary. Reuse canonical quote v2, Edge Commerce, settlement truth, universal fulfilment, and deliverable release v2; add source clearance, exact customer acceptance, professionalization/QA, and web-download adapters around them.

**Tech Stack:** Python 3.13, pytest, JSON state/receipts, SQLite ingress ledger, Microsoft-style SHA-256 lineage, DIO Edge Worker JavaScript, PayPal sandbox, HTML/DOCX/PDF renderers.

**Spec:** `docs/superpowers/specs/2026-10-25-contractproof-release-grade-golden-lane-design.md`

## Global Constraints

- Preserve all existing user changes; the starting worktree is dirty and must not be reset or broadly reformatted.
- The pilot is web-only, PayPal-only, ContractProof-only, accepts PDF/DOCX customer sources, and requires manual release.
- The commercial offer is ZAR; PayPal settlement is a customer-accepted, locked USD conversion with a hash-bound FX receipt.
- Browser return is diagnostic only; production payment truth is the DIO Edge record created from a verified PayPal webhook.
- Fulfilment requires canonical `dio.settlement_receipt.v1`; release requires passing QA and one-use human authority bound to exact bytes.
- Vesper and finishers cannot manufacture payment, fulfilment, legal, or release authority.
- HTML targets WCAG 2.2 AA; PDF targets PDF/UA-1 structure and metadata.
- Critical semantic, lineage, secret, broken-action, and manifest-integrity failures cannot be waived.

## Review Focus

- A file is replaced after scope assessment: invalidate quote/acceptance and refuse order creation; Task 1 and Task 3 tests pin this.
- FX expires or rounds at a half-cent boundary: require a fresh receipt/acceptance and use `ROUND_HALF_UP`; Task 2 tests pin this.
- PayPal reports a matching order but a conflicting capture/event: create a commercial hold and no settlement; Task 4 tests pin this.
- A finisher changes semantic findings or final bytes change after approval: fail QA or invalidate release; Task 6 and Task 7 tests pin this.
- A download grant is replayed, expired, or used by another session: refuse bytes and preserve the authority; Task 7 tests pin this.

---

### Task 1: Cleared ContractProof Source Manifest

**Files:**
- Create: `presence_core/source_manifests.py`
- Modify: `products/attachment_intake.py`
- Modify: `products/vesper_web_chat.py`
- Test: `tests/test_contractproof_source_manifest.py`

**Interfaces:**
- Consumes: current web quarantine rows from `quarantine_attachments(...)`.
- Produces: `clear_source_manifest(state_root: Path, *, case_id: str, intake_id: str, attachment_ids: list[str], cleared_by: str, scan_receipts: list[dict[str, Any]]) -> dict[str, Any]` returning `dio.source_manifest.v1`; `load_source_manifest(state_root: Path, manifest_id: str) -> dict[str, Any]`.

- [ ] **Step 1: Write failing source-custody tests**

Add tests asserting PDF/DOCX magic/structure verification, no extraction before clearance, hash-bound clearance, deterministic exact replay, rejection of changed bytes, and quote invalidation/successor requirement when the accepted source set changes.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest -q tests/test_contractproof_source_manifest.py`
Expected: FAIL because `presence_core.source_manifests` and the clearance flow do not exist.

- [ ] **Step 3: Implement immutable source manifests**

Store detected type, declared type, size, SHA-256, quarantine path, scan receipt hashes, clearance actor/time, and a canonical manifest SHA-256. Permit local PDF/DOCX extraction only after clearance; keep originals immutable and `authority_created: false`.

- [ ] **Step 4: Bind the cleared manifest to the Vesper case**

Update web-chat processing so the canonical case holds the source-manifest ID/hash, and any pre-acceptance change returns the case to scope assessment while any post-acceptance material change requires amendment/successor handling.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_contractproof_source_manifest.py tests/test_vesper_web_chat.py tests/test_presence_wave2_attachments.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add presence_core/source_manifests.py products/attachment_intake.py products/vesper_web_chat.py tests/test_contractproof_source_manifest.py
git commit -m "feat: add cleared ContractProof source manifests"
```

### Task 2: Governed Locked ZAR-to-USD Terms

**Files:**
- Modify: `presence_core/commercial_fx.py`
- Create: `presence_core/commercial_terms.py`
- Test: `tests/test_contractproof_commercial_terms.py`

**Interfaces:**
- Consumes: canonical `dio.customer_quote.v2`, source-manifest hash, and scope-receipt hash.
- Produces: `lock_commercial_terms(state_root: Path, *, case_id: str, rate: str, rate_source: str, observed_at: str, expires_at: str) -> dict[str, Any]` returning `dio.commercial_terms.v1`; `validate_live_terms(terms: dict[str, Any], *, at: str) -> None`.

- [ ] **Step 1: Write failing FX and lineage tests**

Assert ZAR input, USD output, `ROUND_HALF_UP_TO_MINOR_UNIT`, mandatory expiry, quote/scope/source hashes, deterministic replay, and refusal for stale, mismatched, non-USD, or hash-tampered terms.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_contractproof_commercial_terms.py`
Expected: FAIL because locked commercial terms are absent.

- [ ] **Step 3: Extend the FX receipt and add commercial terms**

Keep `build_fx_receipt` non-authoritative, add expiry and lineage fields without accepting naive timestamps, and persist one immutable terms receipt per quote/source/scope/rate basis.

- [ ] **Step 4: Verify**

Run: `pytest -q tests/test_contractproof_commercial_terms.py tests/test_commercial_fx.py tests/test_customer_journey_phase3.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/commercial_fx.py presence_core/commercial_terms.py tests/test_contractproof_commercial_terms.py
git commit -m "feat: lock governed ZAR to USD commercial terms"
```

### Task 3: Authenticated Exact Customer Acceptance

**Files:**
- Create: `presence_core/customer_acceptance.py`
- Modify: `products/vesper_web_chat.py`
- Modify: `scripts/serve_vesper_web_chat.py`
- Test: `tests/test_contractproof_customer_acceptance.py`

**Interfaces:**
- Consumes: authenticated web session, case, `dio.customer_quote.v2`, `dio.source_manifest.v1`, scope receipt, and `dio.commercial_terms.v1`.
- Produces: `accept_commercial_terms(state_root: Path, *, case_id: str, customer_session_id: str, quote_sha256: str, source_manifest_sha256: str, scope_receipt_sha256: str, commercial_terms_sha256: str, accepted_at: str) -> dict[str, Any]` returning `dio.customer_acceptance.v1`.

- [ ] **Step 1: Write failing acceptance tests**

Assert the customer session owns the case; every submitted hash matches current truth; expired FX, source replacement, scope change, replay with different bytes, and operator-substituted acceptance are refused.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_contractproof_customer_acceptance.py`
Expected: FAIL because the acceptance contract and web action do not exist.

- [ ] **Step 3: Implement the content-addressed acceptance receipt**

Persist customer identity/session, all accepted hashes, ZAR and USD display terms, acceptance time, and `authority_created: false`; exact replay returns the original receipt.

- [ ] **Step 4: Expose the authenticated Vesper action**

Add one server route that uses the existing owning-session check and accepts only the explicit hash bundle. Do not accept price or currency values supplied independently of the canonical receipts.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_contractproof_customer_acceptance.py tests/test_vesper_web_chat.py tests/test_canonical_vesper_web_launcher.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add presence_core/customer_acceptance.py products/vesper_web_chat.py scripts/serve_vesper_web_chat.py tests/test_contractproof_customer_acceptance.py
git commit -m "feat: bind web acceptance to exact commercial terms"
```

### Task 4: Edge Checkout and Canonical Settlement Projection

**Files:**
- Modify: `presence_core/commerce.py`
- Modify: `presence_core/settlement_truth.py`
- Modify: `scripts/process_commerce_events.py`
- Create: `presence_core/commercial_holds.py`
- Modify: `edge/dio-edge-gateway/src/index.js`
- Modify: `edge/dio-edge-gateway/test/payment.test.js`
- Test: `tests/test_contractproof_edge_settlement.py`

**Interfaces:**
- Consumes: accepted commercial terms and verified Edge order/event/capture records.
- Produces: `create_accepted_checkout(state_root: Path, *, case_id: str, order_id: str, edge_config_path: Path) -> dict[str, Any]`; `project_edge_settlement(state_root: Path, *, order: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]`; `record_fx_real_settlement(state_root: Path, case_id: str, *, provider: str, provider_receipt_id: str, quoted_amount_minor: int, quoted_currency: str, settlement_amount_minor: int, settlement_currency: str, fx_receipt_sha256: str, acceptance_sha256: str, evidence_ref: str) -> dict[str, Any]`.

- [ ] **Step 1: Write failing order/webhook/recovery tests**

Cover order-before-link, retained ZAR/USD terms, accepted hashes in Edge metadata, exact checkout replay, browser-return non-authority, signature/mismatch refusal, duplicate event replay, conflicting capture hold, refund/reversal freeze, and verified-settlement idempotency.

- [ ] **Step 2: Run Python and Worker tests and confirm failure**

Run: `pytest -q tests/test_contractproof_edge_settlement.py && npm test --prefix edge/dio-edge-gateway`
Expected: new assertions FAIL.

- [ ] **Step 3: Require accepted terms at checkout**

Replace the raw quote-only production call with accepted FX payload validation. Persist order/checkout receipt and case binding before returning the approval URL. Keep the local PayPal store out of the production path.

- [ ] **Step 4: Project verified Edge truth into settlement truth**

Validate provider order/event/capture IDs, USD amount/currency, quote/source/scope/FX/acceptance hashes, and event type before calling settlement persistence. Store both quoted and settlement terms in the receipt.

- [ ] **Step 5: Add orthogonal commercial holds**

Implement immutable hold/open/resolve receipts that freeze order, settlement, fulfilment, or release as appropriate without rewriting the last valid case stage.

- [ ] **Step 6: Verify**

Run: `pytest -q tests/test_contractproof_edge_settlement.py tests/test_presence_commerce.py tests/test_customer_journey_phase3.py tests/test_m2_phase7_commercial_settlement.py && npm test --prefix edge/dio-edge-gateway`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add presence_core/commerce.py presence_core/settlement_truth.py presence_core/commercial_holds.py scripts/process_commerce_events.py edge/dio-edge-gateway/src/index.js edge/dio-edge-gateway/test/payment.test.js tests/test_contractproof_edge_settlement.py
git commit -m "feat: reconcile accepted Edge payments into settlement truth"
```

### Task 5: ContractProof Customer-Document Fulfilment Adapter

**Files:**
- Create: `products/contractproof/source_adapter.py`
- Create: `products/contractproof/fulfilment_adapter.py`
- Modify: `products/contractproof/runner.py`
- Modify: `config/products/manifests/contractproof.json`
- Test: `tests/test_contractproof_fulfilment_adapter.py`

**Interfaces:**
- Consumes: canonical fulfilment request, execution profile, and cleared source manifest.
- Produces: `extract_contractproof_source(manifest: dict[str, Any]) -> dict[str, Any]`; `execute_contractproof_fulfilment(request: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]` compatible with `dispatch_fulfilment`.

- [ ] **Step 1: Write failing adapter tests**

Assert PDF/DOCX extraction uses only cleared files, retains page/paragraph locators, rejects untrusted or changed bytes, invokes the compiler-selected executor, and returns held artifacts with journey case/job/source lineage.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_contractproof_fulfilment_adapter.py`
Expected: FAIL because customer-document and universal-fulfilment adapters do not exist.

- [ ] **Step 3: Add the source adapter**

Translate cleared local documents into the existing structured executor input without making legal conclusions or losing source locators. Record extraction warnings as review requirements.

- [ ] **Step 4: Add the fulfilment adapter and semantic manifest**

Call `run_contractproof`, emit the raw semantic digest, candidate file hashes, required disclaimers, source/evidence references, and all artifacts as `HELD`. Leave the internal executor's external-release gate at `REFUSE`.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_contractproof_fulfilment_adapter.py tests/test_contractproof_phase5.py tests/test_customer_journey_phase4.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add products/contractproof/source_adapter.py products/contractproof/fulfilment_adapter.py products/contractproof/runner.py config/products/manifests/contractproof.json tests/test_contractproof_fulfilment_adapter.py
git commit -m "feat: adapt cleared customer documents to ContractProof fulfilment"
```

### Task 6: Professionalization Policy and Artifact QA

**Files:**
- Create: `config/professionalization/contractproof.json`
- Create: `products/professionalization.py`
- Create: `products/artifact_qa.py`
- Create: `products/contractproof/professionalizer.py`
- Test: `tests/test_contractproof_professionalization.py`
- Test: `tests/test_contractproof_artifact_qa.py`

**Interfaces:**
- Consumes: raw semantic artifact manifest and held ContractProof files.
- Produces: `professionalize(manifest: dict[str, Any], *, policy_path: Path, output_dir: Path) -> dict[str, Any]` returning `dio.professionalization_receipt.v1`; `evaluate_artifact_package(package: dict[str, Any], *, profile: dict[str, Any]) -> dict[str, Any]` returning `dio.artifact_qa.v1`; `publish_review_package(state_root: Path, *, case_id: str, fulfilment_result_sha256: str, professionalization: dict[str, Any], qa: dict[str, Any]) -> dict[str, Any]` returning immutable `dio.review_package.v1` without rewriting the raw fulfilment result.

- [ ] **Step 1: Write failing semantic-preservation and quality tests**

Assert declared acyclic Format Core routing, deterministic output inventory, matching semantic digests, required ContractProof sections, metadata/brand, working links, no placeholders/secrets/temp files, representative PDF renders, WCAG 2.2 AA checks, and PDF/UA-1 structure checks.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_contractproof_professionalization.py tests/test_contractproof_artifact_qa.py`
Expected: FAIL because the router, receipt, and QA profile do not exist.

- [ ] **Step 3: Implement the ContractProof professionalization route**

Use Format Core to produce customer HTML, PDF, and DOCX plus package manifest. Permit presentation changes only; compare canonical semantic projections before and after and fail unexplained differences.

- [ ] **Step 4: Implement QA results and waiver rules**

Return `PASS`, `REVIEW_REQUIRED`, `FAIL`, or `WAIVED` per rule, bind results to exact file hashes, and make critical failures non-waivable. A missing accessibility validator must never become `PASS` by default.

- [ ] **Step 5: Publish the immutable review package**

Bind the final customer-file inventory, professionalization receipt, QA receipt, raw semantic digest, and original fulfilment-result hash in `dio.review_package.v1`. Store it beside—not over—the raw fulfilment result.

- [ ] **Step 6: Verify**

Run: `pytest -q tests/test_contractproof_professionalization.py tests/test_contractproof_artifact_qa.py tests/test_format_core.py tests/test_contractproof_execution_proof.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add config/professionalization/contractproof.json products/professionalization.py products/artifact_qa.py products/contractproof/professionalizer.py tests/test_contractproof_professionalization.py tests/test_contractproof_artifact_qa.py
git commit -m "feat: professionalize and quality-gate ContractProof artifacts"
```

### Task 7: QA-Gated Release and Authenticated Vesper Download

**Files:**
- Modify: `presence_core/deliverable_release_v2.py`
- Create: `presence_core/web_delivery.py`
- Modify: `products/vesper_web_chat.py`
- Modify: `scripts/serve_vesper_web_chat.py`
- Test: `tests/test_contractproof_web_delivery.py`

**Interfaces:**
- Consumes: passing `dio.review_package.v1`, exact deliverable manifest, release authority, and owning Vesper session. `build_deliverable_manifest` must manifest the review-package files while retaining the raw fulfilment-result hash as lineage.
- Produces: `issue_download_grant(state_root: Path, *, authority_id: str, customer_session_id: str, expires_at: str, max_downloads: int = 1) -> dict[str, Any]`; `consume_download_grant(state_root: Path, *, grant_token: str, customer_session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]`.

- [ ] **Step 1: Write failing release/download tests**

Assert release refuses absent/non-passing QA; one named operator receipt is distinct from customer acceptance; token storage is hashed; wrong session, expiry, replay, path traversal, hold, and byte mutation refuse delivery; success records exact manifest/authority/grant hashes.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_contractproof_web_delivery.py`
Expected: FAIL because QA gating and the web transport do not exist.

- [ ] **Step 3: Gate manifest release on exact QA receipt**

Bind QA receipt/hash into the deliverable manifest and release authority. Revalidate the final file inventory immediately before grant issuance and download.

- [ ] **Step 4: Implement the authenticated download transport**

Return opaque expiring grants, never filesystem paths. Stream only manifest-listed files to the owning session and complete `deliver_manifest` with a durable local provider receipt after successful transfer acknowledgement.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_contractproof_web_delivery.py tests/test_customer_journey_phase5.py tests/test_fulfilment_release_consumption.py tests/test_vesper_web_chat.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add presence_core/deliverable_release_v2.py presence_core/web_delivery.py products/vesper_web_chat.py scripts/serve_vesper_web_chat.py tests/test_contractproof_web_delivery.py
git commit -m "feat: deliver approved ContractProof packages through Vesper web"
```

### Task 8: Golden-Lane Orchestration and Reconciliation

**Files:**
- Create: `presence_core/contractproof_journey.py`
- Create: `scripts/manage_contractproof_journey.py`
- Modify: `products/vesper_web_chat.py`
- Test: `tests/test_contractproof_golden_lane.py`
- Test: `tests/test_contractproof_recovery.py`

**Interfaces:**
- Consumes: Tasks 1-7 receipts and the existing case transition functions.
- Produces: explicit orchestration commands `assess`, `quote`, `lock-terms`, `accept`, `checkout`, `reconcile-payment`, `fulfil`, `professionalize`, `qa`, `approve-release`, `issue-download`, `inspect-hold`, and `resolve-hold`.

- [ ] **Step 1: Write failing end-to-end and fault-injection tests**

Exercise one complete fake-provider journey plus lost response, stale ingress claim, duplicate checkout, duplicate/conflicting webhook, executor crash, renderer failure, refund at three timings, byte mutation, expired grant, and ambiguous delivery.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_contractproof_golden_lane.py tests/test_contractproof_recovery.py`
Expected: FAIL because no single orchestrator joins the receipts.

- [ ] **Step 3: Implement receipt-driven orchestration**

Each command reads current receipts, validates prerequisites, performs at most one external effect, persists the resulting receipt, and returns the prior receipt on exact replay. It must never infer authority from the case stage alone.

- [ ] **Step 4: Add operator reconciliation commands**

Support inspect, safe retry, resolve-as-completed with evidence, abandon, and successor/amendment creation. Every resolution records named actor, reason, before/after state, and original hashes.

- [ ] **Step 5: Verify**

Run: `pytest -q tests/test_contractproof_golden_lane.py tests/test_contractproof_recovery.py tests/test_customer_journey_phase{1,2,3,4,5,6,7,8}*.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add presence_core/contractproof_journey.py scripts/manage_contractproof_journey.py products/vesper_web_chat.py tests/test_contractproof_golden_lane.py tests/test_contractproof_recovery.py
git commit -m "feat: orchestrate the ContractProof golden lane"
```

### Task 9: Deployment Proof and Pilot Runbook

**Files:**
- Create: `scripts/verify_contractproof_pilot.py`
- Create: `docs/runbooks/contractproof-pilot.md`
- Create: `tests/test_contractproof_pilot_readiness.py`

**Interfaces:**
- Consumes: configured Vesper web, Edge/PayPal sandbox, local state root, professionalization dependencies, and operator identity.
- Produces: redacted `dio.contractproof.pilot_readiness.v1` and retained sandbox/recovery evidence directories.

- [ ] **Step 1: Write failing readiness tests**

Assert the verifier reports configuration presence without secrets, canonical route selection, required external tools, no local-PayPal production fallback, hold counts, stuck stages, failed QA, pending approvals, and unresolved ambiguous effects.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest -q tests/test_contractproof_pilot_readiness.py`
Expected: FAIL because the verifier is absent.

- [ ] **Step 3: Implement verifier and runbook**

Document sandbox setup, named roles, backup/rollback, quote/FX expiry, webhook verification, controlled refund/reversal drill, manual release, download confirmation, evidence retention, and stop conditions.

- [ ] **Step 4: Run all automated verification**

Run: `pytest -q tests/test_contractproof_*.py tests/test_presence_commerce.py tests/test_customer_journey_phase*.py tests/test_vesper_web_chat.py && npm test --prefix edge/dio-edge-gateway`
Expected: PASS with no stale contradictory tests.

- [ ] **Step 5: Run controlled external acceptance**

Run the verifier, one PayPal sandbox journey, one duplicate webhook replay, one controlled recovery drill, and one authenticated download. Retain only redacted receipts and exact artifact hashes.

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_contractproof_pilot.py docs/runbooks/contractproof-pilot.md tests/test_contractproof_pilot_readiness.py
git commit -m "docs: add ContractProof pilot verification and runbook"
```

