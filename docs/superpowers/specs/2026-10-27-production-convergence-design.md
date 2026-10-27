# DIO Production Convergence Design

## Intent

Bring the DIO runtime and public surfaces to one coherent production standard. The work closes immediate security failures, makes Sophia and Vesper use enforceable LLM policies, connects Microsoft Graph Outlook ingress to the canonical Vesper customer journey, repairs Hivenance/Lingua/Legalis seams, and publishes the resulting professional evidence to `dioworkflows.co.za` with verified dashboards and rollback evidence.

The customer should be able to enter through web or Outlook, receive a stable customer and conversation identity, submit quarantined material, pass through deterministic routing and bounded LLM processing, receive a held professional package, approve the exact delivery, and obtain a return message whose receipt reconstructs the complete journey.

## Selected approach

Three sequences were considered:

1. **Safety-first staged convergence** — close credential and authorization failures, then Sophia, Vesper/Outlook, market layers, and public surfaces.
2. **Vesper-first after P0** — complete the customer journey before the other integration repairs.
3. **Public-surface-first after P0** — ship visible improvements while backend convergence continues.

The selected approach is safety-first staged convergence. It prevents a polished surface from outrunning execution truth and makes each later cutover depend on a verified lower layer.

## Goals

- Remove deployable secret material and prevent recurrence.
- Make Legalis authorization tamper-evident and enforce it on real external-action boundaries.
- Give every Sophia entry point one sovereign, bounded LLM client and one current receipt contract.
- Connect Graph Outlook capture to canonical Vesper conversation, customer, case, fulfilment, manifest, approval, delivery, and reconciliation records.
- Make native Hivenance Commercial Phoenix the canonical market engine while preserving exact historical compatibility.
- Let Lingua reuse human-approved crystallized translations and respect the configured state root.
- Publish current professional offer and evidence truth to `dioworkflows.co.za`.
- Fix observed website and dashboard gaps and prove the deployed public result.

## Non-goals

- No autonomous publication, send, spend, legal judgement, customer identity merge, or commercial validation.
- No silent migration of ambiguous Outlook send results.
- No claim that route-family proof is named-product customer proof.
- No public exposure of operator dashboards.
- No repository-history rewrite without a separate reviewed operation.
- No exchange-key rotation through source code or chat; provider-side revocation is an operator action.

## Phase 0 — security and repository containment

### Hivenance credential incident

Remove the tracked legacy `api_keys.json` from the deployable tree, replace it with a redacted example contract, ignore runtime key files, and add a secret-scanning test covering all tracked files. The release gate must fail while known key-shaped values remain. Record only that provider-side revocation is required; never copy or display the values.

Historical purge is a separate shared-history operation. The implementation prepares an inventory and exact purge plan but does not rewrite remote history in this programme.

### Legalis and Valinor

Replace caller-supplied decision maps with a persisted decision envelope containing request digest, evidence digest, identity/capability binding, policy version, trusted evaluation time, verdict, and canonical decision digest. The envelope is authenticated with an HMAC-SHA-256 key held in the existing mode-0600 secret store and appended to a hash-chained decision ledger under `DIO_STATE_ROOT`. Key identity and rotation epoch are public metadata; key material is never stored in the receipt. `authorize_valinor_boundary` must load and verify the ledger entry or recompute it from trusted inputs. A schema-plus-`ALLOW` dictionary is always refused.

Every executable path capable of external publish, send, spend, purchase, deployment, or provider mutation is in scope, including Outlook, public/social publishing, media upload, advertising, payment, and cloud deployment scripts. A generated executor inventory and static gate test prevent uncovered paths. A decision receipt cannot itself create authority; it can only satisfy one named precondition in an existing governed case and one-use release authority.

### Public repository state

Stop tracking operational state and dashboard snapshots containing contact identifiers, absolute host paths, drafts, conversations, leads, orders, or transactions. Classify tracked `state/`, `runs/`, `deliverables/`, and dashboard material file by file as retained proof, redacted fixture, generated output, or private operational state; do not delete whole trees. Preserve retained proof and redacted deterministic fixtures under dedicated paths. Add a tracked-state privacy gate.

## Phase 1 — sovereign LLM and Sophia convergence

Create one shared sovereign LLM client contract used by Sophia Review, Sophia Tutor, Vesper, Document Studio, and new production integrations. It enforces:

- local-only HTTP endpoints in sovereign mode: loopback plus explicit container aliases `ollama`, `seraph-ollama`, and `host.docker.internal` after DNS/IP locality checks;
- the production provider/model pair `ollama` + `granite3.2:2b`; any additional model requires a reviewed allowlist change and new evaluation receipt;
- explicit connect, read, and total timeout ceilings;
- one bounded retry only for pre-effect connection and transient 5xx failures;
- maximum request bytes, maximum source characters, and maximum output tokens;
- structured JSON output where downstream decisions depend on fields;
- redacted errors and persisted attempt receipts;
- no retry for policy refusal, schema failure, or ambiguous effects.

Sophia repairs:

- replace the obsolete operator consent key with `local_reasoned_processing_approved`;
- add separate `external_scholarly_retrieval_approved`, default false;
- use the embedded canonical Sophia root everywhere and verify source pins at startup;
- remove Gemini/NIM defaults from Tutor and reject non-loopback endpoints in every path;
- enforce the same policy inside `/api/speak` when DIO sovereign mode is active;
- emit a versioned JSON review result with per-finding source anchors, evidence state, severity, and author-owned action;
- render human-readable Markdown from the validated JSON;
- emit `dio.sophia_review_result.v2` and `dio.sophia_review_receipt.v2`, keep a read-only v1 decoder for retained evidence, migrate current `reasoned_processing` receipts, and verify artifact bytes against hashes;
- apply private modes to the full review workspace and archive.

Vesper uses the same client for classification and drafting. Deterministic fallback remains available, but fallback state is explicit in the response receipt rather than silently presented as equivalent inference.

## Phase 2 — Outlook-to-Vesper customer journey

### Immutable capture

Graph delta polling writes an immutable content-addressed capture. The provider message ID is an index, not the evidence key. Every version records canonical content digest, provider version/etag, received time, observation time, sender hint, conversation hint, attachment metadata, tombstone state, and prior-version lineage. Exact replay is idempotent; conflicting reuse creates a hold.

### Attachment custody

Attachments enter immutable quarantine. Clearance validates declared and detected type, safe filename, size, archive depth and expansion, PDF/Office structure, content hash, scanner result, and mutation after scan. ClamAV is the production scanner. Readiness records its engine version, daemon availability, and signature age; an absent daemon or stale signatures create `NEEDS_YOU`. Only a hash-bound cleared copy may enter Presence custody.

### Identity and case binding

Normalized email and Graph conversation IDs are unverified hints. A durable Outlook binding maps provider identities to a canonical customer only after one of three recorded verification methods: a signed customer/session token, a one-time reply challenge, or an identified operator approval. Shared mailboxes require the token or identified operator path. Shared addresses, multiple candidate cases, and changed identities create `NEEDS_YOU`; they never merge automatically.

### Canonical ingress

An Outlook ingress adapter claims the capture digest through `LocalIngressLedger`, constructs the canonical Presence envelope, calls `process_envelope`, and records provider message → capture → Presence conversation → customer → case lineage. The existing Outlook convergence plan supplies the capture and preview baseline; this design supersedes its preview-only limit only after shadow acceptance authorizes the controlled-send increment. Legacy raw-mail job staging is disabled after shadow comparison proves parity.

### Processing and packaging

The production journey coordinator maps typed Vesper actions into the existing intake, scope, quote, settlement, fulfilment, Format Core/Production Studio finish, deliverable manifest, exact approval, and one-use release contracts. It uses a registered production handler map and durable outbox. It cannot use Phase 7 controlled-test settlement or automatic approval.

### Return delivery

The outbound Outlook intent is sealed over normalized recipients, subject, chosen body representation, ordered attachment names and byte hashes, case ID, manifest digest, release-authority ID, customer binding, and Graph conversation marker. Approval binds that digest, approver, expiry, and action.

Before any Graph effect, the system persists an atomic delivery attempt and acquires an attempt lease on the one-use release authority. A proven pre-effect failure releases the lease; success consumes it; an ambiguous effect retains it until reconciliation. Draft/send timeouts enter `DRAFT_IN_DOUBT` or `SEND_IN_DOUBT`. Reconciliation searches the provider using a stable correlation marker before any retry. Only definite pre-effect failures may retry directly.

The final `dio.delivery_receipt.v3` records capture, conversation, customer, case, fulfilment result, manifest, release authority, exact content digest, attachment hashes, provider message/conversation evidence, attempt history, and reconciliation state. Existing v2 receipts remain readable and immutable; no writer emits v2.

The configured production mailbox and tenant live only in secret state. Graph permissions progress by increment: `Mail.Read` for capture, `Mail.ReadWrite` for controlled draft and reconciliation, and `Mail.Send` only for the tested controlled-send increment. No broader delegated scope is accepted.

Separate capture, dispatch, and reconciliation services run from the same pinned release root and virtual environment. Cutover explicitly disables or replaces the legacy Graph capture-to-job dispatcher, legacy raw-mail job staging, and any service that can send outside the sealed outbox path; the host verifier fails if a superseded unit is active.

## Phase 3 — Hivenance, Lingua, and Legalis market layer

### Hivenance

Native Sensorium Commercial Phoenix becomes the canonical market provider. Its input and output receive versioned schemas. The legacy Hivenance runner becomes a compatibility importer only. Compatibility mapping preserves `generated_at`, full `triune_assessments`, source lineage, and event time; ingest time never substitutes for known event time.

### Lingua

Define one translation lifecycle enum shared by lifecycle, communicator, Format Core, and Document Studio. `human_approved_crystallized` is reusable without falling back to English. All Lingua and Document Studio state writes resolve through `DIO_STATE_ROOT`; repository-relative operational state is refused in production mode.

### Legalis external-action gate

Market outreach, publication, and spend paths must use the verified Legalis/Valinor boundary from Phase 0. The gate consumes trusted evidence and a governed-case identity, records the exact decision digest, and returns a held or allowed precondition without manufacturing release authority.

All service units use one versioned release root, one environment file, one virtual environment, and one state mount. Absolute `/Downloads` checkout paths are removed.

## Phase 4 — professional evidence website and dashboard quality

### Evidence publication

Generate a public-safe portfolio export from the canonical 68 offer contracts and artifact-proof registry. Publish buyer job, bounded outcome, primary deliverable, acceptance criteria, route-family proof scope, named-product proof state, and CTA. Redact internal paths and operational identifiers. The site must continue to distinguish engineering proof, customer artifact proof, and market validation.

Repair base-canon provenance so public receipts include source repository, commit, workflow/run or local verification class, artifact ID, and digest. Publish referenced proof snapshots or remove unreachable references.

### Website repairs

- replace all generated `/sites/...` URLs with canonical `/products/...` URLs and forbid legacy paths in tests;
- fix Vesper horizontal overflow at 390 px;
- prevent the mobile Vesper floating control from obscuring the primary CTA;
- improve Products hero contrast and header CTA readability;
- replace the 52,000 px mobile catalogue wall with search, suite filters, proof-state filters, and progressive disclosure;
- give blocked video embeds a useful poster/fallback link;
- retain keyboard navigation, visible focus, reduced motion, and meaningful alternative text.

### Dashboard audit and repairs

Audit Launcher, GoldenEye, Canonical Portfolio, Business, Production, Connections, Market, and Vesper API surfaces on the actual local services. Capture desktop and narrow screenshots for the primary operator flow. Add a single host readiness command that verifies state mount, pinned release, systemd units, loopback listeners, dashboard cross-links, secret-presence metadata, public health endpoints, CORS, and non-allowlisted-route refusal.

The dashboards remain loopback-only. Screenshots and audit fixtures must contain redacted operational data.

### Deployment

`DIO-Workflows` remains the GitHub Pages source with `CNAME=dioworkflows.co.za`. Consolidate the duplicate Pages workflows into one workflow whose deploy job depends on public contract, proof-hash, route, JavaScript, accessibility, responsive-overflow, and screenshot checks.

The public API/Presence ingress receives a redacted, reproducible deployment manifest covering DNS target class, tunnel or proxy service identity, upstream loopback port, health route, release commit, and rollback command. Secrets and provider tokens stay in host secret state. If the current `api.dioworkflows.co.za` backend path cannot be confirmed from that manifest and host checks, backend cutover stops; the independently verified static-site release may still proceed.

Deployment uses a review branch and a merge to `main`. After Pages completes, verify:

- deployed commit and homepage checksum;
- homepage, portfolio, Vesper, trust pages, and all 68 product routes;
- public proof receipt and artifact hashes;
- API and Presence health;
- allowed Vesper session creation and foreign-origin refusal;
- desktop and 390 px screenshots;
- absence of legacy `/sites/...` links.

The previous Pages artifact/commit is recorded before merge. Rollback restores that commit and re-runs the single deployment workflow.

## Delivery increments and gates

1. **Security containment:** no tracked secrets; forged Legalis decision refused; public operational state removed.
2. **Sophia/LLM:** all entry points use the sovereign client; consent and receipt migrations pass.
3. **Vesper shadow path:** immutable capture through held outbound preview, with no external send.
4. **Vesper controlled send:** exact approved content, in-doubt reconciliation, full delivery receipt.
5. **Market convergence:** native Phoenix, Lingua reuse, enforced Legalis gate, pinned services.
6. **Public release:** evidence export, visual repairs, dashboard audit, single Pages deploy, live verification.

No increment advances while its Critical or Important review findings remain open.

## Verification strategy

- TDD for every seam and security regression.
- Security tests for secret patterns, forged decisions, approval mutation, shared identity, attachment mutation, archive abuse, replay, concurrent send, and ambiguous provider effects.
- Contract tests for structured LLM outputs, receipt migrations, byte-hash verification, market provenance, translation-state reuse, and state-root isolation.
- Integration tests that trace one Outlook message from capture to a held package and one approved reply to a reconciled Graph receipt.
- Browser screenshots and DOM checks for the live public flow and all operator dashboards.
- Fresh independent review before each cutover and before public deployment.

## Known operator actions

- Revoke and rotate the exposed exchange credentials at the providers.
- Supply production Graph/LLM/Cloudflare credentials only through the existing secret stores.
- Approve any future shared-history purge as a separate operation.
- Perform human content/release approval where the contracts require it.

