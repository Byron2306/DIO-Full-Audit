# DIO Prospect Registry Commercial Extension

Status: additive extension to the Wave 4 prospect-intelligence registry

## Purpose

Wave 4 already treats the prospect registry as governed intelligence rather than a mailing list. This extension adds a commercial prioritisation plane without weakening that contract.

The new layer answers two independent questions:

1. **How valuable is this organisation as a potential pilot or channel?**
2. **What, if anything, are we currently allowed to do with the recorded route?**

A high commercial score never creates permission.

## Commercial score

Each extension record is scored out of 100:

| Dimension | Maximum | Meaning |
|---|---:|---|
| network_leverage | 25 | Ability to reach multiple qualified buyers or pilot sites through one relationship |
| product_fit | 25 | Strength of fit with HOMS or Evidex pain and proof assets |
| timing | 20 | Current seasonal, policy, reporting or operational urgency |
| evidence_confidence | 15 | Quality of evidence supporting the opportunity hypothesis |
| route_quality | 15 | Practical quality of the legitimate public or association route |

The score is for prioritisation only. It has no authority over outreach governance.

## Outreach classes

`CHANNEL_OK`

A public channel is explicitly intended for relevant submissions, opportunities, supplier enquiries or equivalent use. Operator review remains required and channel terms still apply.

`CONSENT_REQUEST_ONLY`

A public organisational route exists, but there is no recorded permission for electronic sales outreach. At most one governed consent request may be prepared, consistent with the existing Wave 4 consent-request workflow.

`RESEARCH_ONLY`

The record may be used for account research, pilot design, introductions, event strategy, association strategy or inbound planning. Electronic marketing is not released.

`BLOCKED`

Do not contact. Withdrawal, refusal, do-not-contact state or another hard block overrides score and fit.

## Governance projection

`scripts/prospect_registry_extensions.py` derives these booleans for every record:

- `research_allowed`
- `channel_submission_allowed`
- `consent_request_allowed`
- `sales_outreach_allowed`
- `operator_review_required`
- `public_source_is_permission`

`public_source_is_permission` is permanently false.

Sales outreach is allowed only when the permission state is `consented` or `existing_customer`, and the record is not blocked. This preserves the commercial operating plan and the existing once-off consent-request model in `scripts/manage_prospect_outreach.py`.

## Seed cohort

The first extension cohort concentrates on South African multiplier routes rather than arbitrary individual schools or NPOs. It includes school and governance networks, an M&E network, provincial education research routes, and the DSD NPO funding ecosystem.

These are commercial-intelligence records, not a claim that any named body endorses DIO, HOMS or Evidex.

## Usage

Show the highest-ranked records:

```bash
PYTHONPATH=. python3 scripts/prospect_registry_extensions.py
```

HOMS only:

```bash
PYTHONPATH=. python3 scripts/prospect_registry_extensions.py --product HOMS
```

Evidex only:

```bash
PYTHONPATH=. python3 scripts/prospect_registry_extensions.py --product EVIDEX
```

Only public-channel opportunities:

```bash
PYTHONPATH=. python3 scripts/prospect_registry_extensions.py --outreach-class CHANNEL_OK
```

Full records including component scores and governance projection:

```bash
PYTHONPATH=. python3 scripts/prospect_registry_extensions.py --full
```

## Next integration boundary

The extension is deliberately additive. The existing Wave 4 ZIP remains authoritative for its current targets and outreach state.

The next safe convergence step is to make the Wave 4 loader consume this extension as an additional read projection, while preserving stable Wave 4 target IDs and append-only permission evidence. No existing target should silently inherit a new permission state from an extension record.
