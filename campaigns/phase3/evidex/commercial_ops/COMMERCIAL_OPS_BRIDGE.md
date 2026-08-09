# Evidex Commercial Ops Bridge

Updated: 2026-08-07T15:58:56+00:00

## Intake Link

- Landing page: `http://127.0.0.1:8787/`
- Outlook-first subject marker: `EVIDEX PILOT PACK REQUEST`
- Google intake form: configured
- Drive root: configured, kept internal

## Outlook-First Route

Use Outlook for the first commercial motion:

```text
outreach/ad
-> prospect replies with EVIDEX PILOT PACK REQUEST
-> Outlook bot triages the reply
-> AutoRelease routes the triage output
-> Evidex generates the review pack
-> operator checks scope, payment, and delivery
```

Verified dry run:

```text
runs/evidex_outlook_first_dry_run
-> 1 Outlook-style lead
-> 1 Evidex route
-> Evidex engine return code 0
-> service/payment wrapper generated
```

## Payment Gate

Evidex already has the right commercial skeleton:

- Google Form submission creates a Drive job folder under `EvidenceEngine/incoming/<job>/`.
- Apps Script writes `intake.yaml`, `CONTACT_EMAIL.txt`, upload instructions, `INVOICE_ID.txt`, and `INVOICE.txt`.
- Optional payment links are created for Stripe, PayPal, and PayFast depending on configured Script Properties.
- Webhooks or manual operator confirmation create `PAID.txt` and `PAYMENT_RECEIPT.txt`.
- The local watcher can run with `REQUIRE_PAYMENT=1`, which blocks processing until `PAID.txt` exists.
- Delivery emailer can also require `PAID.txt` before sending `DELIVERABLE.zip`.

## Immediate Sales Use

Use the landing page for proof and positioning. Ask prospects to reply with the Outlook subject marker first. Use the Google Form for live Drive/payment intake when ready.

Preview MP4: `/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6/free_preview.mp4`

## Linked Ad Slots

### 01. LinkedIn - CFO / Finance Director

**Headline:** Be audit-ready before anyone asks

**CTA:** Request sample structure

```text
For CFO / Finance Director: Pre-assemble your evidence packs so audits and reviews are smooth: categorized folders, policy/procedure docs, periodic snapshots, and an audit-friendly evidence map. When scrutiny arrives, nothing is missing.

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 02. Locanto - Tax / VAT Manager

**Headline:** Respond to regulators without panic

**CTA:** Get a callback

```text
For Tax / VAT Manager: If you’ve received a request (SARS/regulator/audit), we triage and re-package your documents into a coherent response pack: evidence extraction, gap flags, status tracking, and submission-ready formatting.

Links: LinkedIn https://www.linkedin.com/company/evidex23 | Locanto https://www.locanto.co.za/by/bboy2306/d10815/ | MyAdz https://myadz.co.za/post-free-ad/

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 03. MyAdz - NGO Director / M&E

**Headline:** Evidence that gets approved

**CTA:** Request a sample pack

```text
For NGO Director / M&E: For grants, ESG/impact, accreditation or performance review: we map evidence to criteria, assemble a clean portfolio, and produce summaries that help decision-makers approve confidently. White-label delivery available.

More: https://www.linkedin.com/company/evidex23

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 04. Locanto - Finance Manager

**Headline:** Be audit-ready before anyone asks

**CTA:** Request sample structure

```text
For Finance Manager: Pre-assemble your evidence packs so audits and reviews are smooth: categorized folders, policy/procedure docs, periodic snapshots, and an audit-friendly evidence map. When scrutiny arrives, nothing is missing.

Links: LinkedIn https://www.linkedin.com/company/evidex23 | Locanto https://www.locanto.co.za/by/bboy2306/d10815/ | MyAdz https://myadz.co.za/post-free-ad/

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 05. MyAdz - CFO / Finance Director

**Headline:** Respond to regulators without panic

**CTA:** Get a callback

```text
For CFO / Finance Director: If you’ve received a request (SARS/regulator/audit), we triage and re-package your documents into a coherent response pack: evidence extraction, gap flags, status tracking, and submission-ready formatting.

More: https://www.linkedin.com/company/evidex23

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 06. LinkedIn - University research office

**Headline:** Evidence that gets approved

**CTA:** Request a sample pack

```text
For University research office: For grants, ESG/impact, accreditation or performance review: we map evidence to criteria, assemble a clean portfolio, and produce summaries that help decision-makers approve confidently. White-label delivery available.

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 07. MyAdz - Finance Ops

**Headline:** Be audit-ready before anyone asks

**CTA:** Request sample structure

```text
For Finance Ops: Pre-assemble your evidence packs so audits and reviews are smooth: categorized folders, policy/procedure docs, periodic snapshots, and an audit-friendly evidence map. When scrutiny arrives, nothing is missing.

More: https://www.linkedin.com/company/evidex23

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 08. LinkedIn - Finance Ops

**Headline:** Respond to regulators without panic

**CTA:** Get a callback

```text
For Finance Ops: If you’ve received a request (SARS/regulator/audit), we triage and re-package your documents into a coherent response pack: evidence extraction, gap flags, status tracking, and submission-ready formatting.

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 09. Locanto - Grant consultancy

**Headline:** Evidence that gets approved

**CTA:** Request a sample pack

```text
For Grant consultancy: For grants, ESG/impact, accreditation or performance review: we map evidence to criteria, assemble a clean portfolio, and produce summaries that help decision-makers approve confidently. White-label delivery available.

Links: LinkedIn https://www.linkedin.com/company/evidex23 | Locanto https://www.locanto.co.za/by/bboy2306/d10815/ | MyAdz https://myadz.co.za/post-free-ad/

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 10. LinkedIn - Head of Internal Audit

**Headline:** Be audit-ready before anyone asks

**CTA:** Request sample structure

```text
For Head of Internal Audit: Pre-assemble your evidence packs so audits and reviews are smooth: categorized folders, policy/procedure docs, periodic snapshots, and an audit-friendly evidence map. When scrutiny arrives, nothing is missing.

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 11. Locanto - Compliance / Risk

**Headline:** Respond to regulators without panic

**CTA:** Get a callback

```text
For Compliance / Risk: If you’ve received a request (SARS/regulator/audit), we triage and re-package your documents into a coherent response pack: evidence extraction, gap flags, status tracking, and submission-ready formatting.

Links: LinkedIn https://www.linkedin.com/company/evidex23 | Locanto https://www.locanto.co.za/by/bboy2306/d10815/ | MyAdz https://myadz.co.za/post-free-ad/

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```

### 12. MyAdz - ESG / CSI lead

**Headline:** Evidence that gets approved

**CTA:** Request a sample pack

```text
For ESG / CSI lead: For grants, ESG/impact, accreditation or performance review: we map evidence to criteria, assemble a clean portfolio, and produce summaries that help decision-makers approve confidently. White-label delivery available.

More: https://www.linkedin.com/company/evidex23

Pilot intake: https://docs.google.com/forms/d/e/1FAIpQLSeG9LtRT8d8UBsIQAFGa-2K_zZKc6em7vGc33AzHYsn3obQGQ/viewform?usp=dialog
Preview: http://127.0.0.1:8787/#proof
```
