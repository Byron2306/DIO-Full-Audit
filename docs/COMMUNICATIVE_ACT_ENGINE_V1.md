# DIO Communicative Act Engine v1

## Purpose

C3 replaces universal commercial copy with explicit communicative acts.

The same Commercial Semantic Object may support many outward expressions, but each expression has a different rhetorical contract. A cold permission request, inbound reply, proposal, quote, delivery notice and paid ad are not interchangeable templates.

The governing rule remains:

> Deterministic meaning. Probabilistic expression. Governed execution.

C3 implements the deterministic expression contract and a deterministic fallback renderer. A future probabilistic writer may consume the same expression plan, but it may not add facts, fill unknowns, promote hypotheses into facts or grant itself execution authority.

## Supported communicative acts

```text
cold_permission_request
inbound_reply
qualified_lead_reply
pilot_invitation
follow_up
proposal
quote
invoice_notice
intake_request
delivery
request_for_quotation
linkedin_post
classified_listing
paid_ad
video_cta
```

Every act defines its own:

- channel;
- objective;
- relationship mode;
- maximum word count;
- assumption budget;
- inferred-need policy;
- inferred-strategy policy;
- proof mode;
- CTA mode;
- human-approval requirement; and
- personalisation boundary.

## Why this matters

Before C3, multiple commercial surfaces each contained their own hard-coded prose logic. The visible HTML branding was reusable, but the semantics and rhetoric were embedded inside channel-specific scripts.

That created two risks:

1. a generic copy pattern could be reused in a context where its assumptions were not valid; and
2. a writer could silently manufacture customer pain, urgency, scope, price or authority because the communication type had no machine-readable contract.

C3 separates these concerns:

```text
Commercial Semantic Object
          |
          v
Communicative Act Contract
          |
          v
Expression Plan
          |
          +-- facts permitted for this act
          +-- hypotheses permitted for this act
          +-- unknowns that must remain silent
          +-- proof references
          +-- prohibited claims
          +-- assumption budget
          +-- CTA contract
          +-- human-approval requirement
          |
          v
Renderer / future language model
          |
          v
Expression candidate
```

## Generation law

Every expression plan carries:

```json
{
  "may_paraphrase": true,
  "may_add_facts": false,
  "may_promote_inference_to_fact": false,
  "may_fill_unknowns": false,
  "must_preserve_claim_status": true,
  "must_preserve_source_refs": true,
  "human_approval_required": true
}
```

A future LLM writer is therefore an expression engine, not a truth engine and not an authority engine.

## Cold permission request

The cold-contact contract has an assumption budget of zero.

It may use public organisation identity, public route identity and configured product identity. It may not use a target buyer-unit hypothesis as if it were a known person, and it may not repeat a campaign pain hypothesis as if the prospect had confirmed that pain.

The live Wave 4 prospect route is now:

```text
buyer_unit_targets.csv
       |
       v
commerce.prospect_bridge
       |
       v
dio.commercial_semantic_object.v1
       |
       v
cold_permission_request
       |
       v
scripts.prospect_outreach_copy
       |
       v
scripts.dio_mail_branding
       |
       v
Outlook draft
```

The old `manage_prospect_outreach.message_for()` entry point remains for compatibility, but delegates to the C3 engine. The product card is presentation. The communicative act chooses the rhetoric.

## Prospect-target authority

`commerce.prospect_bridge.commercial_semantic_object_from_prospect_target()` converts a Wave 4 target into a conservative target-level CSO.

It may verify:

- target ID;
- organisation identity recorded in the registry;
- configured product line;
- public route state;
- public contact route; and
- whether the route is eligible for one permission request.

It may infer, but never verify as customer truth:

- buyer unit;
- segment;
- candidate offer.

It leaves unknown:

- actual customer job-to-be-done;
- workflow pain;
- urgency;
- budget; and
- agreed scope.

A do-not-contact target receives `authority_state=research_only` and cannot render a cold permission request.

## Verified expression context

Some acts require transaction facts that are deliberately not part of the base CSO schema yet, for example an operator-approved quote amount or invoice reference.

C3 accepts those only through `verified_context`:

```json
{
  "verified_context": {
    "scope": {
      "value": "one bounded reporting-period evidence pack",
      "source_refs": ["quote:Q-1"]
    },
    "price": {
      "value": "ZAR 2,500",
      "source_refs": ["quote:Q-1"]
    }
  }
}
```

A naked `price="2500"` is not accepted. The context must carry source references.

## Deterministic fallback

`render_expression()` provides a deterministic renderer for all supported acts.

This is not intended to freeze DIO into robotic prose. It establishes a safe operational fallback and, more importantly, a reference implementation of the rhetorical contract. A future probabilistic writer may improve style, cadence and phrasing while consuming the same plan.

## C3 gate

C3 is satisfied when:

1. every outward commercial expression declares a communicative act;
2. cold outreach cannot use inferred customer pain;
3. DNC/research-only authority blocks direct cold expression;
4. quotes and invoice notices cannot invent price, scope or transaction references;
5. public ads do not personalise to named organisations;
6. source references survive into the expression candidate;
7. the same CSO produces materially different rhetoric under different acts;
8. every act carries a human-approval rule and word/assumption budget; and
9. the live prospect email path delegates copy selection to the act engine.

C3 does not yet grant send authority. Metatron/Loki/BEAST remain responsible for the later governance layer.
