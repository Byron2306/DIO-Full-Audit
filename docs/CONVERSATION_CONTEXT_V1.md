# DIO Conversation Context v1

## Purpose

C4 makes DIO conversation-aware without allowing conversation text to silently become commercial truth or execution authority.

The governing separation is:

> **Commercial Semantic Object = what DIO may treat as meaning/truth.**
>
> **Conversation Context = what happened in the interaction and how the next expression may adapt.**

Conversation Context is therefore downstream of captured messages but below the Commercial Semantic Object in authority.

## Authority hierarchy

```text
Commercial Semantic Object
truth / epistemic state / authority
            |
            v
Communicative Act Contract
relationship + rhetorical boundary
            |
            +----------------------+
            |                      |
            v                      v
Conversation Context         Verified execution context
thread / tone / requests     quote / invoice / workflow refs
            |                      |
            +----------+-----------+
                       v
                Expression Plan
                       |
                       v
             deterministic or LLM
                    expression
                       |
                       v
                  human gate
```

Conversation Context can shape wording and response order. It cannot modify the CSO.

## Canonical object

`dio.conversation_context.v1` contains:

- conversation ID and channel;
- bounded turn history;
- received inbound count;
- actually-sent outbound count;
- prepared-but-unsent outbound count;
- thread state;
- observed questions;
- open questions;
- observed request-like statements;
- latest requested action;
- latest inbound excerpt;
- derived tone labels;
- bounded style hints; and
- explicit authority prohibitions.

## Hard authority boundary

Every context object records:

```json
{
  "may_shape_expression": true,
  "may_select_response_order": true,
  "may_surface_message_questions": true,
  "may_establish_commercial_fact": false,
  "may_grant_consent": false,
  "may_set_scope": false,
  "may_set_budget": false,
  "may_set_payment_state": false,
  "may_confirm_identity": false,
  "may_grant_execution_authority": false
}
```

Examples:

- `"URGENT, please quote us today"` may produce an `urgent` tone observation and a recorded request for a quote. It does **not** establish urgency as a commercial fact and does not grant quote authority.
- `"We definitely have budget"` is message text. Conversation Context does not turn it into a verified budget field.
- `"Sounds good"` does not become consent, agreed scope or payment authority.
- a Telegram user ID does not become verified customer identity merely because a conversation exists.

## Outlook evidence

`conversation_core.outlook.build_outlook_conversation_context()` consumes:

- Microsoft Graph mail ingress records as `received` inbound turns; and
- outbound mail intents only when `send_state=sent`.

An Outlook draft is **not** conversation history.

An approved-but-unsent message is **not** conversation history.

This prevents DIO from later saying or inferring that a customer was told something merely because a draft existed.

## Presence / Vesper evidence

DIO Presence now uses the same context species for Telegram, WhatsApp and web chat.

The public/operator persona is now **Vesper**. `Lilith` remains the internal/legacy deployment codename and an accepted command alias so existing HF Space names, secrets and operator habits do not break.

For the live core Telegram path:

- provider ingress becomes an inbound `received` turn;
- a reply becomes outbound `sent` only after the Telegram API reports success;
- a generated reply that is not externally confirmed remains `prepared`;
- provider message IDs deduplicate retries;
- the resulting context is written into the shared `state/conversation_context` store.

Older Presence intakes can seed conversation context when no live turn journal exists, preserving value from pre-C4 state without duplicating newly journalled turns.

## Expression integration

`commerce.expression_guarded` accepts Conversation Context separately from the CSO.

For conversation-aware acts (`inbound_reply`, `qualified_lead_reply`, `pilot_invitation`, `follow_up`) it may surface:

- the latest recorded request;
- an unanswered question;
- bounded style hints; and
- thread state.

Conversation fields do not enter `facts[]` or `hypotheses[]` in the expression plan.

The plan explicitly carries:

```json
{
  "conversation_context_may_shape_expression": true,
  "conversation_context_may_establish_fact": false,
  "conversation_context_may_grant_consent": false,
  "conversation_context_may_set_scope": false,
  "conversation_context_may_set_budget": false,
  "conversation_context_may_grant_execution_authority": false
}
```

A context object whose `conversation_id` does not match the CSO lineage is rejected. This prevents cross-thread context injection.

## Reconciliation

Run:

```bash
python scripts/reconcile_conversation_context.py
```

The reconciler writes:

```text
state/conversation_context/CTX-*.json
state/conversation_context/INDEX.json
```

The normal commercial orchestrator now runs this reconciliation before each commercial projection.

## Governed Outlook reply preparation

Run:

```bash
python scripts/prepare_conversation_reply.py <LEAD_ID>
```

The preparer:

1. loads the canonical lead;
2. requires a bound Outlook conversation and recipient;
3. loads the exact registered Conversation Context;
4. requires `thread.state=awaiting_dio_response`;
5. derives a CSO from the lead;
6. chooses `inbound_reply` or `qualified_lead_reply` from the verified relationship/qualification state;
7. renders through C3 + C4 context policy;
8. creates a normal DIO mail intent with approval pending; and
9. writes a reply candidate receipt carrying CSO/context lineage.

It does not create send authority.

## Why Vesper matters

The old Lilith Presence work looked, on the surface, like a Telegram concierge. Architecturally it already contained several valuable DIO properties:

- separate public/operator trust domains;
- signed ingress;
- bounded intent routing;
- quarantine-first attachments;
- identity-bound status disclosure;
- held intake creation;
- read-only operational summaries;
- Needs You escalation; and
- refusal to spend, publish, approve or release autonomously.

C4 promotes that work from a channel-specific interface into a **cross-channel Presence organ**. Vesper is the persona. Conversation Context is the reusable substrate underneath it.

## C4 gate

C4 is satisfied when:

1. Outlook and Presence project into one conversation-context schema;
2. drafts/prepared replies are not treated as sent;
3. message requests and questions preserve their source references;
4. tone remains derived rather than factual;
5. conversation context cannot set truth, consent, scope, budget, payment, identity or execution authority;
6. cross-thread context injection is rejected;
7. context can materially alter a conversation-aware expression without altering CSO fact/hypothesis sets;
8. a real Outlook reply-preparation path consumes the context and stops at the existing approval gate;
9. live Telegram turns can be journalled with provider-confirmed send state; and
10. the Vesper rename does not break Lilith legacy invocation or deployment identifiers.
