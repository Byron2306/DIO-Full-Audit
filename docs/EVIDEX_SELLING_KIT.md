# Evidex Selling Kit

Updated: 2026-08-07

## Positioning

Evidex Evidence Pack turns scattered reporting proof into a review-ready evidence pack.

It is not sold as "AI magic." It is sold as relief from evidence chaos.

## Primary Buyer

Start with people who already feel the pain:

- NGO programme managers.
- Grant consultants.
- Monitoring and evaluation officers.
- Donor reporting assistants.
- Compliance administrators.
- Small teams preparing audit or funder evidence.

## Offer

### Pilot Pack

```text
Send one non-sensitive evidence folder.
Get back a review-ready evidence table, source pack, narrative draft, QA receipt, and delivery ZIP.
```

Suggested pilot price:

```text
R950-R1,500 for a normal pilot pack
R350-R750 for a tiny proof pack
R2,500-R5,000 for urgent or messy manual cleanup
```

## Landing Page Copy

Current generated landing page:

```text
sites/evidex/index.html
```

Current visual assets:

```text
sites/evidex/assets/evidex-thumbnail.png
sites/evidex/assets/evidex-hero.png
sites/evidex/assets/evidex-output.png
sites/evidex/assets/free_preview.mp4
```

The MP4 asset is a symlink to the NicheFoundry episode output so the suite does not duplicate generated video bulk.

Current commercial ops bridge:

```text
campaigns/phase3/evidex/commercial_ops/COMMERCIAL_OPS_BRIDGE.md
campaigns/phase3/evidex/commercial_ops/linked_ad_rotation.json
campaigns/phase3/evidex/commercial_ops/COMMERCIAL_OPS_RECEIPT.json
campaigns/phase3/evidex/commercial_ops/outlook_first/OUTLOOK_FIRST_INTAKE.md
campaigns/phase3/evidex/commercial_ops/outlook_first/OUTLOOK_FIRST_AD.md
```

The bridge reads the existing Evidex Google Form configuration and now also exposes an Outlook-first reply path through:

```text
sites/evidex/assets/commercial-links.js
```

Payment links and secrets are not copied into public page copy. The fastest public sales path is now: proof page, reply with `EVIDEX PILOT PACK REQUEST`, Outlook triage, then structured upload/payment once the lead is real. Invoice/payment links are still issued by the Evidex Google Apps Script flow after intake when that route is used.

### Hero

```text
Evidex Evidence Pack
```

```text
Send the evidence mess. Get back a review-ready donor, audit, or compliance pack.
```

CTA:

```text
Request a Pilot Pack
```

### Problem

```text
Most reporting work does not fail because people did nothing.
It fails because the evidence is scattered across emails, attachments, spreadsheets, folders, and half-remembered conversations.
```

### What You Get

- Structured evidence table.
- Source file index.
- Narrative draft.
- Quality and completeness receipt.
- Delivery ZIP.
- Operator review before release.

### Boundary

```text
Evidex prepares review-ready evidence support.
It does not replace donor approval, auditor judgement, legal advice, or your final sign-off.
```

### Proof Section

Use the current preview:

```text
/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6/free_preview.mp4
```

Use the current thumbnail:

```text
/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6/thumbnail.png
```

Use the demo pack:

```text
deliverables/phase2_demo/evidex/evidex-120d089d3bce3548e92d
```

### Closing CTA

```text
Send one non-sensitive folder. I will return a pilot evidence pack and tell you honestly what the workflow can and cannot handle.
```

## Intake Form

Minimum fields:

- Name.
- Organization.
- Email.
- Reporting context.
- Deadline.
- Evidence type.
- Desired output.
- Number of files.
- Any sensitive data present.
- Permission to process a non-sensitive sample.
- Upload link or delivery arrangement.

Suggested form copy:

```text
Please do not upload private, medical, legal, or highly sensitive records for the first pilot. Use a redacted or non-sensitive sample where possible.
```

## Lead Magnet

### Grant Evidence Readiness Checklist

Checklist sections:

- What outcome are you proving?
- Which files support that outcome?
- Are dates visible?
- Are source names visible?
- Are approvals or signatures visible?
- Are gaps clearly marked?
- Can a reviewer trace every claim back to a file?
- Which evidence should not be shared yet?

## Outreach Message

### Short Version

```text
Hi [Name],

I am testing a small evidence-pack service for donor, grant, audit, and compliance reporting.

The idea is simple: you send one non-sensitive evidence folder, and I return a structured evidence table, source index, narrative draft, QA receipt, and delivery ZIP.

It is review-ready support, not automatic sign-off.

Would you be open to letting me run a tiny pilot pack on a non-sensitive sample?
```

### Slightly Warmer Version

```text
Hi [Name],

I have been building a practical workflow for teams who have to prove work after the fact: donor reports, grant evidence, M&E proof, compliance prep, that kind of thing.

The pain I am targeting is the evidence mess: emails, attachments, folders, spreadsheets, and screenshots that all need to become a clean reportable pack.

For the first pilot, I am keeping it small and review-first:

- one non-sensitive evidence folder,
- evidence table,
- source index,
- narrative draft,
- QA receipt,
- delivery ZIP.

No automatic sign-off, no pretending the system replaces judgement.

Would a tiny pilot pack be useful to you or someone in your network?
```

## First Prospect List

Build the first list manually. Do not automate scraping yet.

Targets:

- 5 grant consultants.
- 5 NGO/admin contacts.
- 5 M&E or compliance-adjacent people.
- 5 academics or project admins who have donor/reporting obligations.

Goal:

```text
20 highly relevant messages
-> 3 conversations
-> 1 pilot
```

## Fulfilment Loop

```text
lead replies
-> Outlook bot triages the reply
-> AutoRelease routes it as an Evidex candidate
-> send landing page, upload instructions, or Google intake form
-> receive non-sensitive sample through email/export or Drive uploads folder
-> invoice/payment request is sent if configured
-> wait for PAID.txt if payment gating is enabled
-> route as Evidex job
-> generate pack
-> operator review
-> send preview result
-> ask for payment or testimonial depending on pilot deal
```

## Invoice And Paygate

Existing Evidex support:

- Invoice artifacts: `INVOICE.docx`, `INVOICE.txt`, `INVOICE_ID.txt`.
- Intake email stage: `INVOICE_SENT.txt` prevents duplicate invoice/payment emails.
- Payment links: Stripe Checkout, PayPal Checkout/PayPal.me, and PayFast are supported by the Apps Script layer.
- Payment marker: `PAID.txt` plus `PAYMENT_RECEIPT.txt`.
- Processing gate: `REQUIRE_PAYMENT=1` makes the watcher ignore jobs until `PAID.txt` exists.
- Delivery gate: the Drive delivery emailer can also require `PAID.txt` before emailing `DELIVERABLE.zip`.

## Outlook-First Verification

Verified on 2026-08-07:

```text
campaigns/phase3/evidex/commercial_ops/outlook_first/dummy_outlook_evidex_intake.json
-> KnowEdge Outlook Triage 2.0.0
-> campaigns/phase3/evidex/commercial_ops/outlook_first/outlook_bot_output/triage_summary.csv
-> runs/evidex_outlook_bot_csv_dry_run
-> deliverables/evidex_outlook_bot_csv_dry_run/evidex/evidex-b0a30dd37214755b47d9
```

Result:

```text
1 Outlook-style lead processed by the Outlook bot
triage_summary.csv routed to Evidex
review pack created
Evidex engine returned code 0
Evidex ZIP and service/payment wrapper generated
```

## Decision Rule

Keep pushing Evidex if:

```text
people understand the offer in under 30 seconds
and at least one person agrees to send a sample
```

Pause or reposition if:

```text
people like the tech but cannot name a current evidence pain
or the work required is mostly bespoke consulting
```
