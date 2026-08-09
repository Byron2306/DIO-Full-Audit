# Evidex Outlook-First Intake

Updated: 2026-08-07T16:25:20+00:00

## Why This Matters

The Google Form and Drive/paygate route can stay, but it must not be the first blocker. The Outlook bot already produces the exact kind of triage records AutoRelease can route.

## Live Spine

```text
ad or direct message
-> prospect replies with EVIDEX PILOT PACK REQUEST
-> Outlook bot triages mailbox or exported messages
-> triage_summary.csv / triage JSON
-> scripts/route_intake.py
-> Evidex job envelope
-> review pack
-> deterministic Evidex pack generation
-> operator approval
-> invoice/paygate or manual PAID.txt before final delivery
```

## Operator Rule

Use Outlook for discovery, qualification, and packet creation. Use Google Form/Drive for structured upload when it is working. Use payment links only after a human has checked the lead is real and scoped.

## Subject Marker

```text
EVIDEX PILOT PACK REQUEST
```

## Buyer Reply Template

```text
Hi Evidex,

I want to test a non-sensitive or redacted evidence pack.

Organization:
Reporting context: donor report / grant evidence / audit / compliance / M&E
Deadline:
Files available: emails / invoices / photos / spreadsheets / notes
What the pack should help prove:
Upload link or delivery arrangement:

I understand this is review-ready support, not automatic auditor/donor sign-off.
```

## Verification

The dummy packet in this folder was run through two paths:

```text
dummy JSON -> AutoRelease -> Evidex ZIP
dummy JSON -> KnowEdge Outlook Triage 2.0.0 -> triage_summary.csv -> AutoRelease -> Evidex ZIP
```

The second path is the important commercial proof because the Outlook bot is actually in the middle.
