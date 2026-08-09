# KnowEdge AutoRelease System Audit

Audit date: 2026-08-08  
Audit intent: release-readiness and operational-truth review  
Overall assessment: controlled-pilot ready; not yet externally validated at scale

## Executive Finding

KnowEdge AutoRelease has crossed the line from a set of demonstrations into a functioning controlled service platform. The suite has a shared intake, approval, commerce, delivery, campaign and telemetry spine; four product adapters have fulfilment evidence; Microsoft and Cloudflare infrastructure is connected; and PayPal production webhooks have been verified.

The largest remaining risk is no longer missing plumbing. It is the difference between controlled proof and external commercial proof. The system has one controlled R950 Evidex loop and one USD 1.00 live PayPal validation, but it does not yet have a complete paid external customer case with measured revisions, delivery acknowledgement and retained margin.

## Verification Snapshot

| Area | Result | Evidence |
|---|---|---|
| Automated tests | PASS, 45 tests | `./.venv/bin/python -m pytest -q` |
| Commercial release verifier | PASS | `campaigns/phase3/COMMERCIAL_CAMPAIGN_RELEASE_RECEIPT.json` |
| Control Deck | Online at audit time | `http://127.0.0.1:8765/api/control/state` |
| Control metrics | 1 lead, 1 order, R950, 5 active jobs, 9 actions, 0 failures | Control Deck state |
| Microsoft Graph | Connected; drafts created successfully | `state/mail_intents/` and DIO event ledger |
| Edge ingress | Worker and D1 connected | `config/dio_edge.local.json`, `config/dio_edge.live.json` |
| PayPal sandbox | Verified | `state/commerce/orders/DIO-PAYPAL-SANDBOX-USD-001.json` |
| PayPal live | Signed USD 1.00 event accepted | `state/commerce/live/orders/DIO-PAYPAL-LIVE-USD-001.json` |
| HOMS marking | Completed controlled NIM batch | `deliverables/homs_live_batch_test/homs-live-dummy-20260807T173535Z/` |
| HOMS assessment | Tight-eight Grade 12 Term 3 release passed | `deliverables/homs_fet_tight8_release_candidates/FET_TIGHT8_FINAL_RELEASE/` |
| Evidex | Controlled transaction loop complete | `docs/EVIDEX_TRANSACTION_LOOP_PROOF.md` |
| Sophia | Gemini review approved and delivery draft ready | `state/sophia_jobs/SOPHIA-COMMERCIAL-DEMO-001/JOB.json` |
| VAMP | NWU and generic university profiles approved | `state/vamp_jobs/` |
| Gamma media | Six campaign assets plus two polished video masters | NicheFoundry episode receipts |

## Architecture Assessment

### Strong

- Product jobs use explicit envelopes, schemas, receipts and output directories.
- Approval state is separated from processing, payment and delivery state.
- Outlook sending is fail-closed. DIO creates drafts but does not silently send.
- Browser redirects are not accepted as payment proof.
- Cloudflare D1 buffers public events while the local computer is unavailable.
- The DIO event log is hash-linked and records causation across mail, payment and product operations.
- Gamma imagery is labelled illustrative and is not treated as customer evidence.
- VAMP's profile layer successfully separates institution-specific objectives from the evidence engine.

### Needs hardening

- There is no canonical external-customer acceptance receipt yet.
- Controlled telemetry and live payment validation are separate proofs; they must be joined in a real order.
- The Control Deck has nine unresolved operator actions, which will become noisy if campaigns expand now.
- YouTube OAuth is not configured, so the media lane ends at local editorial masters.
- The procedural beds have been replaced. Evidex uses **Soft Corporate** and HOMS uses **Warm Sunset**, both by MusicLFiles under CC BY 4.0, with source, hash, licence, attribution and selection receipts.
- The current `en-US-GuyNeural` narration is technically clean, but the voice is not yet editorially approved. Matching `en-ZA-LukeNeural` and `en-ZA-LeahNeural` auditions are available for a South African-market decision.
- The suite is not a Git repository, reducing change traceability and rollback confidence.
- The root documentation drifted materially behind implementation before this audit.

## Product Findings

### Evidex

Readiness: strongest immediate commercial lane.

The golden case proves ad, reply, triage, approved intake, generation, human review, payment state, delivery and closeout. A second controlled route proves Outlook draft creation with the reviewed ZIP attached. The product promise is narrow and understandable.

Remaining gate: one external paid, bounded evidence pack with delivery acknowledgement and real manual-time measurement.

### HOMS Marking Relief

Readiness: technically proven controlled pilot.

The latest controlled NIM run processed three fake submissions in 63.97 seconds with no provider errors. It produced criterion-level results, marks, individual feedback, a lecturer summary and a review ZIP.

Remaining gate: an educator must review a redacted real batch, change what is wrong, approve the final result, and leave a correction ledger. Model output quality cannot be inferred from pipeline completion alone.

### HOMS Exam Studio

Readiness: strong Grade 12 Term 3 release candidate, narrow scope.

The tight-eight audit passes Afrikaans FAL, English FAL, History, Geography, Life Sciences, Physical Sciences, Mathematics and Life Orientation. It verifies mark totals, A4 output, source counts and embedded media where required.

Remaining gate: external subject-expert review. Claims must stay limited to the demonstrated grade, term and subjects until downward scaling is validated.

### Sophia

Readiness: controlled paid-pilot candidate.

The commercial job records ownership consent, remote Gemini processing consent, a grounding pass, human approval and an Outlook delivery draft. Its strongest position is technical reference checking, literature support and reviewer commentary without ghostwriting.

Remaining gate: external academic user feedback and explicit revision telemetry.

### VAMP

Readiness: controlled organisational pilot candidate.

The NWU run processed 190 evidence records, 61 objectives, 116 accepted mappings and 24 candidates. The generic university proof demonstrates portability through a separate profile, rather than hard-coding NWU rules into the engine.

Remaining gate: profile-onboarding economics, privacy review and one external organisational pilot.

## Marketing And Media Findings

Hivenance has registered and scored Evidex and HOMS campaign hypotheses. NicheFoundry has generated campaign packs, Gamma visuals, ads, landing pages, metadata and video episodes. Outreach and publication remain operator-controlled.

The original HOMS and Evidex previews are valid proof-of-route assets. They were not deleted. The audit added separate polished masters that:

- use completed Gamma campaign photography;
- retain the original 66-second scripts and narration;
- embed the controlled Evidex evidence table and HOMS marking table in proof scenes;
- render at 1920x1080 rather than 1280x720;
- use H.264 CRF 20 rather than CRF 28;
- use AAC 192k stereo with a -16 LUFS target;
- preserve human-approval boundaries;
- carry separate visual and media receipts.

The new videos remain editorial-review assets. Gamma-generated document text is illustrative and must not be presented as an actual client record. The local proof overlays are the evidence-bearing elements. Music now passes the automated commercial rights gate and runs continuously rather than restarting at each scene boundary.

## Risk Triage

| Severity | Finding | Required action |
|---|---|---|
| High | Controlled success is not external customer validation | Close one real paid Evidex loop before scaling spend |
| High | HOMS quality has not been corrected and approved by an external educator | Run one redacted batch and retain the correction ledger |
| Medium | Nine operator actions are open | Clear, close or archive them before increasing campaign volume |
| Medium | HOMS scope can easily be marketed beyond demonstrated coverage | Publish only the proven Grade 12 Term 3 and controlled marking claims |
| Medium | YouTube publishing credentials are absent | Configure private-first OAuth only after editorial approval |
| Medium | Final narrator and end-to-end watch-through are not approved | Compare the three loudness-matched voices, choose one, rerender if needed, then record human approval |
| Medium | Repository uses 1.8 GB on a disk at 89% utilisation | Archive quarantined and duplicate generated runs after review |
| Low | No Git history exists for the suite | Initialise version control after excluding secrets and generated corpora |

## Commercial Recommendation

Do not launch every product simultaneously.

1. Lead with one bounded Evidex pilot offer and one proof-led video.
2. Offer HOMS through two clearly separate strands: Marking Relief and Grade 12 Term 3 Exam Studio.
3. Keep Sophia and VAMP invite-only until one external pilot each is complete.
4. Publish through permission-safe channels first: founder LinkedIn, YouTube demonstrations, association or educator communities that allow the post, and high-intent search content.
5. Measure qualified replies, intake completion, paid checkout, manual minutes, processing time, revisions, acknowledgement and net revenue.

## Next Acceptance Gates

### Gate 1: media approval

- Watch both polished masters end to end.
- Choose and approve the narrator from the three audition files.
- Check Gamma imagery at full resolution.
- Configure private-first YouTube upload credentials.

### Gate 2: external Evidex pilot

- Real prospect and bounded non-sensitive evidence.
- Verified payment linked to the same order.
- Human-approved delivery.
- Customer acknowledgement and revisions.
- Closeout economics.

### Gate 3: external HOMS pilot

- Redacted or non-sensitive batch.
- Rubric or memo supplied by educator.
- NIM/Gemini marking support.
- Educator correction ledger.
- Final approval and safe delivery.

### Gate 4: disciplined expansion

- Expand only the product that converts.
- Scale HOMS by validated subject, grade and term.
- Promote VAMP profiles only after onboarding effort is measured.
- Keep every outbound action permission-aware and operator-approved.

## Audit Conclusion

The system is real enough to sell controlled pilots now. It is not yet justified to run broad autonomous marketing or claim mature production coverage. The most valuable next action is not another architecture layer; it is one external transaction that joins acquisition, payment, fulfilment, human correction, delivery acknowledgement and profit telemetry in the same evidence chain.
