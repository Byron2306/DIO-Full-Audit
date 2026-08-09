# KnowEdge AutoRelease Suite

Updated: 2026-08-09

KnowEdge AutoRelease is the local command center for a suite of evidence-first, human-approved service products. It links Outlook and OneDrive intake, product-specific processing, operator approval, payment evidence, delivery drafts, campaign production, and business telemetry without copying the large source projects into one repository.

```text
market observation
-> operator-released public campaign
-> canonical public intake and lead ID
-> governed Outlook acknowledgement
-> Outlook Triage
-> product job
-> human review
-> verified payment or approved waiver
-> Outlook delivery draft
-> closeout evidence
-> commercial learning
```

## Current Position

The suite is at **controlled-pilot readiness**, not unattended production and not proven product-market fit.

Verified on 2026-08-09:

- 93 DIO Python tests, 47 focused EdgeK-BEAST tests, and the Control Deck Playwright workspaces pass.
- Commercial release verification passes for the HOMS, Evidex, and VAMP sites and eight campaign creatives.
- The local Control Deck reports 2 leads, 2 paid orders, R950 recorded revenue, 5 active jobs, 7 operator actions, and 0 failures.
- Microsoft Graph OAuth, Outlook draft creation, Graph webhook ingress, and OneDrive transport are connected.
- Cloudflare Worker and D1 provide public HTTPS ingress while the laptop is offline.
- Evidex, HOMS, Sophia, VAMP, and Document Studio submit one `dio.public_intake.v1` envelope to the edge instead of using `mailto:` as their primary transport. Document Studio is registered in the live Worker and D1 intake constraint.
- Controlled lead `EVIDEX-20260808-36BC59BF0F` proved live website intake to D1, local lead materialisation, and governed acknowledgement-intent creation.
- A signed live PayPal webhook was accepted for the USD 1.00 production validation order.
- Evidex, HOMS, Sophia, and VAMP all have controlled fulfilment evidence.
- The Wave 4 registry now controls five active product lines with 4,834 scored product opportunities, while electronic sales authority remains at zero.
- NicheFoundry and Gamma have produced eleven governed source images, eight rendered ad creatives, landing-page assets, and separate polished HOMS/Evidex video masters.
- DIO Lingua now exposes an actionable unit-and-flag review workspace. Four controlled language lanes were operator-approved and crystallised into 28 human-authorised BEAST translation credits.
- The shared Lingua object route is proven with registered HOMS, Sophia, Evidex, VAMP, NicheFoundry, and Document Studio artifacts. Their public intake forms now carry an explicit output-language request.
- DIO Format Core now projects typed semantic content through style, language and delivery profiles into DOCX, PDF, PPTX, accessible HTML and VTT, with stale-lane rejection and post-render completeness receipts.
- The BEAST bridge now uses evidence scoring, Chronicle, negative capability, capability-learning economics, sealed Memory Hull residue, PREC lifecycle records, exact reuse accounting, and source-drift quarantine in addition to durable credits and the crystal chain.
- Lilith Presence Wave 2 is installed with separated public/operator trust domains. The operator PA now returns a read-only DIO operating brief across jobs, mail, live/sandbox commerce, Market Command, leads, incidents and Needs You actions.

The dated evidence and risk assessment is in [SYSTEM_AUDIT_2026-08-08.md](docs/SYSTEM_AUDIT_2026-08-08.md).

The current cross-system scorecard is in [SYSTEM_READINESS_EVALUATION_2026-08-09.md](docs/SYSTEM_READINESS_EVALUATION_2026-08-09.md). It rates the suite at **68.6/100 risk-adjusted readiness**, **80.5/100 controlled-pilot readiness**, and **21.1/100 external-validation maturity**. Those scores are deliberately separate so controlled technical proof is not mistaken for product-market proof.

## Product Readiness

| Product | What is proven | Current boundary | Next commercial proof |
|---|---|---|---|
| Evidex | Full controlled transaction loop, golden evidence case, reviewed ZIP, Outlook delivery draft | The R950 loop is controlled evidence, not an external customer sale | One paid external bounded pilot from enquiry through acknowledged delivery |
| HOMS Marking Relief | Three-submission NIM marking run, marks CSV, feedback files, lecturer summary and review ZIP | Fake/non-sensitive batch; educator approval remains final | One redacted educator batch with recorded corrections and approval |
| HOMS Exam Studio | Passed Grade 12 Term 3 tight-eight release: Afrikaans FAL, English FAL, History, Geography, Life Sciences, Physical Sciences, Mathematics and Life Orientation | Release candidates require educator or subject-expert approval; this is not yet Grade 1-12 coverage | External review of selected packs, then controlled expansion by grade and term |
| HOMS Learning Studio | Grade 10 Physical Sciences Term 3 Motion companion: guide, practical, worksheet, mini-assessment, memoranda, eight meaningful visuals, captions and a 2:06 lesson | Golden review candidate only; subject-expert approval and external buyer evidence are still pending | Subject-expert review, then one paid one-topic pilot with revision and effort telemetry |
| Sophia | Consented Gemini-backed section review, grounding pass, human approval and Outlook delivery draft | Review support only; no ghostwriting or replacement of authorship | One paid researcher or postgraduate pilot with revision telemetry |
| VAMP | NWU private evidence snapshot and institution-neutral university profile proof, both approved with Outlook drafts | Sensitive performance evidence requires profile onboarding, consent and human review | One external organisation profile and approved snapshot |
| DIO Document Studio | English/Afrikaans plus dual-pass NVIDIA NIM isiZulu, Sesotho and Setswana packs; all four controlled lanes now have recorded language-practitioner approval and 28 crystallised units | These are operator-approved controlled proofs, not certified translations or independent external language validation; technical-editor, client and delivery gates remain distinct | Independent reviewer validation, then one paid authorised-document pilot with measured corrections and reuse |
| Lilith Presence / PA | Public concierge plus operator-only read briefs over jobs, mail, commerce, Market Command, leads, incidents and Needs You | PA is read-only; no sending, fulfilment release, campaign publication, attachment processing or spend authority | Wire operator Telegram credentials, then run daily operational brief and approval workflow |
| Outlook Triage | Graph inbox ingress, classification, routing and automatic draft creation | Sending remains approval-gated | Clear the controlled queue and run one real prospect conversation |
| NicheFoundry shared media layer | Campaign packs, Gamma assets, ad creatives, landing pages, MP4 previews and polished masters | It is infrastructure, not a standalone product; publication, voice and final editorial review remain human-gated | Use faceless proof shorts to support product campaigns, then prove one curriculum-linked video lesson |

## Product Thesis

```text
Evidence in.
Human judgment preserved.
Review-ready pack out.
```

Customers buy a bounded result from HOMS, Evidex, Sophia, VAMP, or Document Studio. DIO coordinates the shared commercial and operational path behind those products.

## Control Deck

Start the localhost-only operator surface:

```bash
python3 scripts/serve_control_deck.py
```

Open `http://127.0.0.1:8765`.

The deck exposes operator attention, inbound lead qualification, product approvals, actionable Outlook mail intents, market campaign publication gates, researched prospects, local commerce orders, and immutable DIO activity. Campaign publication and direct outreach are separate authorities: an operator can release a public creative while permission-unsafe direct outreach remains blocked. Control changes are persisted atomically in `state/control_policy.json` and appended to `telemetry/dio_events.jsonl`.

The **Transactions** tab is the canonical commercial spine. It correlates campaign attribution, lead, Outlook conversation, quarantined intake, job, order, payment, review and delivery state. Its Metatron/Michael/Loki projection shows the current belief, ranked next action, independent challenge and process cadence. **Reconcile now** performs internal correlation and safe staging only; it cannot send, charge, approve, process or release customer work.

Continuous reconciliation is installed as a user service:

```bash
systemctl --user status dio-commercial-orchestrator.service
```

See [METATRON_COMMERCIAL_ORCHESTRATION_AUDIT.md](docs/METATRON_COMMERCIAL_ORCHESTRATION_AUDIT.md) for the Metatron deep dive, complete transaction audit and remaining commercial gaps.

## Public Intake And Leads

All product sites project their own fields into one public contract:

```text
PRODUCT WEBSITE -> POST /api/public/intake -> D1 public_leads
-> local lead record -> acknowledgement mail intent -> exact Outlook draft
-> operator approve and send -> customer reply -> lead reference/conversation binding
```

The response contains a durable product-prefixed lead ID. Duplicate submissions return the original reference. The edge limits payload size, validates products and contact fields, uses a honeypot, and stores a request fingerprint. Public forms never accept files; private intake follows qualification. `mailto:` remains a visible fallback, not the system of record.

The long-running live reconciler also recovers leads directly from D1 if an event was acknowledged before local materialisation:

```bash
./.venv/bin/python scripts/sync_dio_edge_events.py --config config/dio_edge.live.json --watch
```

## Microsoft And Commerce

Microsoft Graph is the primary mail route. DIO may read, classify, route, extract attachments, and create drafts automatically. Final sending requires an exact provider draft ID, an explicit Control Deck confirmation, and a five-minute one-time approval lease that never enters browser JavaScript. Success or failure consumes the lease and writes a receipt. The Smart Outlook agent cannot execute `send_email`.

Inbound Graph file attachments are stored privately, capped, hashed and marked `captured_untrusted`. They remain quarantined from product processing until a later scanner or operator promotes their trust state. A confident direct email can create a deterministic unqualified lead and review-required job, but it cannot establish scope, processing consent, payment or delivery authority.

```text
Outlook -> Microsoft Graph webhook -> Cloudflare Worker -> D1
-> local reconciliation -> Triage -> product job -> Outlook draft
```

Useful commands:

```bash
python3 scripts/manage_graph_subscription.py status
python3 scripts/sync_dio_edge_events.py --watch
python3 scripts/sync_onedrive_jobs.py --watch
```

The Entra app must have delegated `Mail.Send` in addition to `Mail.ReadWrite`. After granting it, refresh the local MSAL cache once:

```bash
./.venv/bin/python scripts/sync_outlook_mail.py --device-login draft MAIL-<INTENT-ID>
```

Complete the device sign-in shown in the terminal. Subsequent exact-draft sends use the cached delegated consent; the Control Deck still retains final authority.

PayPal sandbox and live webhook paths have both been validated. The live provider check confirms that the configured webhook exists, targets the correct DIO URL, and includes all required commerce events. Browser returns are never treated as payment proof; only verified provider events may move payment state. PayFast and PayShap remain future provider adapters, not active payment claims.

Invoices are job-specific, not public website buttons. The operating route is:

```text
intake and consent -> operator scopes and accepts job -> invoice authority enabled
-> order registered -> HTML email with invoice summary and secure PayPal button
-> signed provider webhook -> processing authority -> human review -> delivery
```

The plain checkout URL remains in the text fallback, while Outlook drafts use a prominent `Pay securely with PayPal` button. A generic website payment button is deliberately prohibited because price, consent, scope, product and job ID must be fixed first.

See [DIO_MAIL_CORE_MICROSOFT_ONBOARDING.md](docs/DIO_MAIL_CORE_MICROSOFT_ONBOARDING.md) and [DIO_PAYMENT_ONBOARDING.md](docs/DIO_PAYMENT_ONBOARDING.md).

## HOMS Proof

Controlled marking proof:

```text
deliverables/homs_live_batch_test/homs-live-dummy-20260807T173535Z/
```

The NIM run completed three submissions in 63.97 seconds with no provider errors and produced `marks.csv`, three feedback files, `LECTURER_REVIEW_SUMMARY.md`, and `HOMS_REVIEW_PACK.zip`.

Grade 12 Term 3 tight-eight release:

```text
deliverables/homs_fet_tight8_release_candidates/FET_TIGHT8_FINAL_RELEASE/
```

The release audit passes all eight subjects with matched mark totals, A4 PDF review output, source counts, embedded media where required, and separate memoranda.

## Evidex Proof

Controlled transaction proof:

```text
deliverables/evidex_golden_transaction_loop/evidex/evidex-488c40b13ce3498ed076/
```

The loop contains evidence for:

```text
ad -> reply -> triage -> job -> approved intake -> generation
-> human review -> payment state -> delivery -> closeout receipt
```

The Outlook-controlled workflow also has an approved reviewed ZIP attached to a delivery draft. See [EVIDEX_TRANSACTION_LOOP_PROOF.md](docs/EVIDEX_TRANSACTION_LOOP_PROOF.md).

## Sophia And VAMP Proof

Sophia's controlled Gemini review is stored under:

```text
deliverables/sophia_academic_reviews/SOPHIA-COMMERCIAL-DEMO-001/
state/sophia_jobs/SOPHIA-COMMERCIAL-DEMO-001/
```

VAMP's private and portable proofs are stored under:

```text
deliverables/vamp_snapshots/VAMP-COMMERCIAL-PRIVATE-001/
deliverables/vamp_snapshots/VAMP-GENERIC-UNIVERSITY-PROOF-001/
```

The NWU profile mapped 190 evidence records to 61 objectives with 116 accepted mappings. The generic university profile proves that NWU is a configurable profile rather than a hard-coded product boundary.

## Document Studio Proof

The English-to-Afrikaans golden review candidate is stored under:

```text
deliverables/document_studio/DIO-DOC-GOLDEN-001/
```

It contains clean edited and translated copies, a visible redline, a bilingual review copy, change and terminology ledgers, provider output, local QA, human gates and a delivery ZIP. Six bilingual proof-review corrections are receipted rather than hidden. See [DOCUMENT_STUDIO_GOLDEN_PROOF.md](docs/DOCUMENT_STUDIO_GOLDEN_PROOF.md).

The configured isiZulu, Sesotho and Setswana routes use NVIDIA NIM DeepSeek V4 with a second semantic critic pass. DIO Lingua holds all four languages against one versioned semantic object. BEAST automatically crystallises deterministic guards and conservative risk-routing patterns; only approved linguistic meaning requires human authority. The controlled Afrikaans, isiZulu, Sesotho and Setswana lanes now have recorded language-practitioner approval. Product packs remain held at their separate technical-editor, client and delivery boundaries. See [DOCUMENT_STUDIO_MULTILINGUAL_ROUTES.md](docs/DOCUMENT_STUDIO_MULTILINGUAL_ROUTES.md).

The Control Deck's **Lingua QA** tab projects source alignment, stale units, deterministic integrity, material review signals, BEAST reuse, and release authority. **Review and approve** opens the source and target units side by side, requires a disposition for every material flag, records reviewer identity and role, and crystallises only after every unit is approved. Repeated validator and uncertainty observations are learned automatically; the Attention Queue creates one grouped semantic-review action per object rather than interrupting the operator for each machine flag.

The cross-product architecture and BEAST audit are documented in [DIO_LINGUA_SHARED_ORGAN_AND_BEAST.md](docs/DIO_LINGUA_SHARED_ORGAN_AND_BEAST.md).

The shared formatting architecture, client-template hooks and five-channel golden classroom proof are documented in [DIO_FORMAT_CORE.md](docs/DIO_FORMAT_CORE.md). The proof is stored under:

```text
deliverables/format_core/DIO-FORMAT-GOLDEN-001/
```

## NicheFoundry And Gamma Media

Gamma API access is configured in NicheFoundry and has completed eleven campaign image generations with receipts. The campaign imagery is illustrative; controlled local artifacts remain the source of proof. Rejected VAMP pseudo-document images remain recorded but are not used by the site or rendered ads.

Build the Gamma-assisted video frames:

```bash
python3 scripts/build_gamma_video_polish.py
```

The existing 720p previews are preserved. The new 1080p masters are:

```text
/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6/polished_preview.mp4
/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-homs-marking-relief-pack-send-the-batch-rubric-memo-and-marksheet-get-structured-marking-s-aec7fc9b/polished_preview.mp4
```

Each polished master is 1920x1080, H.264, AAC stereo, approximately 66 seconds, and targets -16 LUFS. Evidex now uses **Soft Corporate** and HOMS uses **Warm Sunset**, both by MusicLFiles under CC BY 4.0. The tracks were discovered through Openverse, downloaded from Wikimedia Commons, checked against a commercial-use and adaptation rights gate, mixed continuously beneath narration, and recorded in each episode's `COMMERCIAL_MUSIC_RECEIPT.json` and `MUSIC_ATTRIBUTION.md`.

The current narrator is Microsoft Edge TTS `en-US-GuyNeural`. Loudness-matched auditions for that voice, `en-ZA-LukeNeural`, and `en-ZA-LeahNeural` are under each episode's `imports/voice_auditions/` directory. Human voice selection and a final watch-through remain required. YouTube OAuth is connected to the intended DIO workflows channel. Upload and public release remain separate operator actions, and publication is claimed only after the returned channel and video state are verified.

Refresh governed music discovery or promote a known Openverse track:

```bash
cd /home/byron/Downloads/NicheFoundry_Phase11
npm run source:music -- --episode /path/to/episode --topic "professional evidence workflow"
npm run source:music -- --episode /path/to/episode --openverse-id <track-id>
```

Openverse is the default provider. Add `--provider mixed` to include the rights-filtered Jamendo catalogue.

Generate or refresh product campaigns:

```bash
python3 scripts/build_phase3_campaigns.py --out campaigns/phase3
python3 scripts/run_dio_marketing_integration.py
python3 scripts/build_operator_dashboard.py
```

Market priority never grants outreach permission. Electronic outreach remains blocked unless a valid consent or existing-customer basis is recorded and the operator approves release.

## Hivenance Market Intelligence

The Wave 4 campaign lane now uses Hivenance Phoenix's worker, oracle, competing-hypothesis, Triune and strategy-council architecture for market research rather than crypto. Registry evidence, Google News RSS web/blog discovery, YouTube public discovery and settled campaign outcomes are assessed independently. The result is a bounded `TEST`, `REFINE` or `HOLD` recommendation with no publishing, outreach, payment or commerce authority.

```bash
./.venv/bin/python scripts/run_hivenance_market_agents.py
```

The Campaigns tab's **Refresh research + agents** action refreshes live NicheFoundry evidence and then writes a Hivenance reasoning receipt. Search metadata is treated as opportunity evidence, not demand or revenue proof. See [HIVENANCE_MARKET_INTELLIGENCE.md](docs/HIVENANCE_MARKET_INTELLIGENCE.md).

The Campaigns tab can release or hold each Wave 4 publication independently. Every decision writes `OPERATOR_RELEASE.json`; direct outreach remains visibly blocked by the Hivenance gate. The Leads tab is reserved for actual inbound requests and must not be confused with the research-only Prospects tab.

## Market Command

Market Command is installed as the Control Deck's cross-channel commercial control plane. Five existing Hivenance hypotheses are imported as governed experiments, and their proof-led campaign content is registered with the shared Lingua lifecycle before approval or release.

YouTube reporting is live through NicheFoundry's existing channel credentials. Meta Ads, Facebook Page, Instagram, LinkedIn, TikTok Ads, Google Ads and Reddit Ads have explicit read adapters and setup states. Organic/community, Outlook, WhatsApp and South African publisher routes remain governed manual adapters. Automatic spend is off and the experiment cap is zero.

### Multichannel Creative Factory

Market Command now contains a proof-led Creative Factory driven by `config/marketing_audience_matrix.json`. Six product lines are mapped to 24 canonical buyer groups. Each family receives distinct LinkedIn, Facebook, Meta, Instagram, TikTok, Reddit, Google Ads and YouTube copy, five poster/thumbnail dimensions, and a 1080x1920 NicheFoundry proof reel with a recorded commercial-use music attribution. The current registry contains 240 channel packages, 120 poster assets and 24 reels.

The daily `dio-marketing-factory.timer` refreshes this inventory and rerenders only production requests whose hash changed. The weekly `dio-market-intelligence.timer` refreshes bounded web, blog and YouTube evidence for all five Hivenance campaigns and reruns the worker, oracle, strategist and council lane. Neither service publishes, buys media, personalises outreach, or enables spend. In the Control Deck, open **Market Command**, inspect a family, choose a channel, and use **Create governed draft** to promote exactly one package into the approval and measurement pipeline.

Manual rebuild:

```bash
./.venv/bin/python scripts/build_multichannel_campaign_factory.py
```

```bash
./.venv/bin/python scripts/import_hivenance_market_command.py
./.venv/bin/python scripts/sync_marketing_channels.py YOUTUBE_ORGANIC
./.venv/bin/python scripts/bind_owned_video_campaigns.py
./.venv/bin/python scripts/serve_market_command.py
```

See [MARKET_COMMAND_INTEGRATION_STATUS.md](docs/MARKET_COMMAND_INTEGRATION_STATUS.md) for the adapter and Lingua coverage matrix.

Notification routing is defined in `config/notification_policy.json`. Every event enters the dashboard feed. Action and critical phone/desktop delivery can be enabled later with an HTTPS ntfy endpoint and environment-held token:

```bash
./.venv/bin/python scripts/dispatch_notifications.py
```

## Verification

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python scripts/verify_commercial_release.py
```

## Repository Layout

```text
adapters/       Thin adapters for existing projects and shared evidence kernels.
campaigns/      Campaign packs, Gamma outputs, creatives and market experiments.
config/         Product, mail, commerce, release and route configuration.
corpora/        CAPS and assessment source material.
dashboard/      Static Control Deck build and state projection.
deliverables/   Controlled outputs, proofs, audits and release candidates.
docs/           Operating plans, proofs, audits and product guidance.
edge/           Cloudflare Worker and D1 public ingress.
runs/           Small orchestration run records.
schemas/        Shared job, event, marketing and evidence contracts.
scripts/        Orchestration, generation, approval and verification commands.
state/          Local operational projections and approval state.
telemetry/      Append-only DIO events and business-loop metrics.
```

## Immediate Gates

1. Grant delegated `Mail.Send`, complete one device login, and use the controlled lead to prove exact-draft **Approve & Send**.
2. Human-review the voice auditions and polished masters, then release one Wave 4 public campaign from the Campaigns tab.
3. Run one real paid Evidex pilot and capture acknowledgement, revisions, manual minutes and net revenue.
4. Run one redacted HOMS educator batch and record every educator correction before approval.
5. Obtain subject-expert approval for the HOMS Learning Studio golden proof, record corrections, then price one controlled one-topic pilot.
6. Extend the approved Afrikaans, isiZulu, Sesotho and Setswana proof into one real product artifact, retaining per-channel Lingua approval before release.
7. Issue checkout only after scope and consent are accepted; keep `invoice_authority` at `draft_only` between jobs.

## Space And Secret Rules

- Do not copy source-project databases into this folder.
- Keep API keys and OAuth tokens outside tracked configuration.
- Do not expose Microsoft token caches, provider secrets or private performance evidence.
- Keep generated media in NicheFoundry episode folders, with receipts linked from this suite.
- Quarantine failed HOMS visual runs; never promote them into release candidates.
- Review large corpora and deliverable archives before duplicating them. The suite currently uses about 1.8 GB and the host has about 49 GB free.
