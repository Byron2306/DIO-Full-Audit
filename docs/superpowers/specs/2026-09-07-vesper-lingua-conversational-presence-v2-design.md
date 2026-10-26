# Vesper Lingua Conversational Presence v2 Design

## Status

Approved architecture for implementation planning.

## Goal

Turn Vesper from a deterministic intake router with optional wording polish into a responsive, multi-turn, DIO-domain conversational guide. Lingua becomes the semantic conversation layer, while existing deterministic routing, policy and authority gates remain the only path into consequential actions.

The public transport contract remains unchanged:

```text
browser
  -> Cloudflare Presence Gateway
  -> DIO Presence Core
  -> reply queue
  -> browser polling
```

This design changes the cognition behind `presence_core.process_envelope`, not the public `/api/vesper/web/session`, `/api/vesper/web/message` or `/api/vesper/web/replies` contract.

## Problem

The current Presence flow resolves routing before conversational meaning:

```text
incoming message
  -> observe interaction style
  -> deterministic route_message()
  -> policy authorization
  -> optional deterministic side effect such as intake creation
  -> fixed fallback reply
  -> optional Ollama rewrite of that already-selected reply
  -> Lingua communication registration
```

That architecture is safe but conversationally weak. The model is currently allowed to rewrite a reply after the route is already fixed. It cannot carry the conversation, resolve references across turns, compare products intelligently, or ask a useful clarification before the router falls into `unknown`.

A greeting such as `Hi` therefore behaves like a routing event rather than a conversation event. A vague need such as `I have 80 essays and need consistent marking` is forced too early into keyword classification or an unresolved fallback.

## Existing Assets To Reuse

The implementation must extend the current DIO organs rather than create a standalone chatbot subsystem.

Existing assets on the current 68-product backend branch include:

- `presence_core/engine.py`
  - current orchestration owner for public and operator Presence messages;
  - calls deterministic routing, policy, state, Lingua communication registration, persona assignment, interaction regulation and LLM drafting.
- `presence_core/router.py`
  - deterministic product and intent router;
  - bounded Ollama classifier fallback;
  - remains authoritative for consequential route transitions.
- `presence_core/llm.py`
  - current Ollama client;
  - supports bounded classification and reply rewriting;
  - becomes the provider adapter used only when Lingua cannot resolve a good conversational answer locally.
- `presence_core/state.py`
  - persists Presence conversation identity and lightweight last-intent / last-product state;
  - becomes the persistence owner for a bounded conversational state object.
- `adapters/lingua/communicator.py`
  - records Vesper communication meaning with semantic lineage and explicit no-authority boundary.
- `adapters/lingua/interaction_regulator.py`
  - records observable linguistic cues and delivery policy without emotion/personality diagnosis.
- `adapters/lingua/persona_lab.py`
  - assigns a stable Vesper presentation package per conversation.
- BEAST operator-language semantic crystal machinery
  - supports reusable conversational answer frames, semantic generalisation, recurrence evidence and provider-call displacement.

## Core Principle

```text
LANGUAGE != AUTHORITY
```

Vesper may understand, explain, compare, infer, clarify, remember conversational context and suggest a next step.

Vesper conversation may never, by language alone:

- send mail;
- publish content;
- spend money;
- take or confirm payment;
- release fulfilment;
- approve professional judgment;
- expose private order data;
- process an untrusted attachment;
- create legal, commercial or operational authority.

Consequential actions continue to require the existing deterministic route, policy and human/authority gates.

## Intended Behaviour

### Greeting

Input:

```text
Hi
```

Expected response class:

```text
Hi. I’m Vesper, DIO’s guide. What are you trying to get done?
```

A greeting is a conversational primitive, not a failed product classification.

### Product explanation

Input:

```text
What is HOMS?
```

Expected behaviour:

- answer directly from governed DIO product knowledge;
- explain the relevant HOMS family in plain language;
- invite the user to describe the problem rather than forcing a product menu;
- do not create an intake.

### Problem-to-product guidance

Input:

```text
I have 80 student papers and need consistent marking plus evidence if marks are challenged.
```

Expected behaviour:

- infer HOMS Assess as a strong candidate;
- explain why the need aligns with that route;
- optionally mention HOMS Moderate only when materially relevant;
- ask at most one useful follow-up if required;
- offer explanation, comparison or intake as choices;
- do not create an intake until the user explicitly chooses an action.

### Action transition

Input sequence:

```text
User: I have 80 student papers and need consistent marking.
Vesper: ... HOMS Assess appears to fit ... I can explain it or help you begin an intake.
User: Yes, start that for me.
```

Expected behaviour:

- conversational state resolves `that` to the previously discussed HOMS Assess candidate;
- a typed action-intent proposal is produced;
- deterministic routing and policy validate the transition;
- only then may existing `create_intake()` run;
- the model itself never calls or authorizes `create_intake()`.

## Architecture

```text
PUBLIC MESSAGE
     |
     v
Presence identity + conversation custody
     |
     v
Interaction observation + stable persona
     |
     v
Vesper Conversation State
     |
     v
Lingua Conversational Resolver
     |-----------------------------------|
     |                                   |
     | known primitive / crystal         | unresolved or novel
     v                                   v
local answer frame                provider synthesis
     |                                   |
     |                                   v
     |                            typed draft result
     |                                   |
     |-------------------|---------------|
                         v
               response validation
                         |
                         v
                conversational reply
                         |
                         +---- if action proposed ---->
                              deterministic router
                                      |
                                      v
                                  authorize()
                                      |
                                      v
                         existing DIO side-effect path
```

## New Unit: Vesper Conversation State

Add a bounded conversation-state object owned by Presence. It is not a raw transcript dump and is not model memory.

Schema name:

```text
dio.vesper.conversation_state.v1
```

Minimum fields:

```json
{
  "schema": "dio.vesper.conversation_state.v1",
  "conversation_id": "CONV-...",
  "turn_count": 0,
  "current_need": null,
  "current_topic": null,
  "candidate_products": [],
  "selected_product": null,
  "last_user_act": null,
  "last_vesper_act": null,
  "open_question": null,
  "known_constraints": [],
  "action_proposal": null,
  "last_route_intent": null,
  "updated_at": "..."
}
```

Rules:

- persist under the existing Presence state root;
- update atomically after each successful conversational turn;
- store compact semantic facts, not unlimited message history;
- never store secrets or arbitrary attachment contents;
- keep at most the bounded recent-turn window required by synthesis separately from the semantic state;
- conversation state has no authority fields that can be interpreted as approval.

## New Unit: Lingua Conversational Resolver

Create a focused Lingua component responsible for conversational meaning resolution. It must be separate from translation approval logic.

Recommended module:

```text
adapters/lingua/conversation.py
```

Responsibilities:

1. Resolve deterministic conversational primitives.
2. Consult reusable operator-language semantic crystals / answer frames.
3. Retrieve relevant governed DIO product knowledge.
4. Construct provider context when local meaning resolution is insufficient.
5. Normalize provider output into a typed conversational result.
6. Never execute a product route or external action.

Typed result schema:

```text
dio.vesper.conversation_resolution.v1
```

Minimum fields:

```json
{
  "schema": "dio.vesper.conversation_resolution.v1",
  "reply": "...",
  "conversation_act": "answer",
  "interpreted_need": null,
  "candidate_products": [],
  "confidence": 0.0,
  "clarification_needed": false,
  "clarification_question": null,
  "action_intent": "none",
  "action_product": null,
  "source": "primitive|lingua_crystal|provider|fallback",
  "authority_created": false
}
```

Allowed `conversation_act` values for v1:

```text
greeting
answer
explain
compare
clarify
acknowledge
confirm
correct
handoff_offer
unknown
```

Allowed `action_intent` values for v1:

```text
none
begin_intake
status_lookup
operator_summary
```

An action intent is only a proposal. Existing routing/policy must independently validate it.

## Resolution Hierarchy

The conversational resolver must attempt answers in this order:

```text
1. deterministic conversational primitives
2. high-confidence Lingua semantic crystal / answer-frame reuse
3. governed DIO semantic retrieval
4. fast provider synthesis
5. safe deterministic fallback
```

### Layer 1: primitives

V1 primitives include:

- greeting;
- thanks;
- goodbye;
- yes / confirmation;
- no / correction;
- simple identity question;
- `what can you do?`.

These require no model call.

### Layer 2: Lingua semantic crystals

Use operator-language semantic crystal machinery for recurring conversational answer frames where applicability is verified.

Examples:

- what DIO is;
- what Vesper is;
- common HOMS / Evidex / Sophia / VAMP / Document Studio explanations;
- common product comparisons;
- standard trust / proof boundary questions;
- common clarification patterns.

A crystal may generate language but may not contain executable authority.

### Layer 3: governed semantic retrieval

Build provider context from canonical, public-safe product semantics. Do not let the model invent portfolio facts from its pretrained memory.

The retrieval result should include only what is needed for the current question:

- product names and descriptions;
- public-safe capabilities;
- maturity / proof boundaries where relevant;
- candidate route hints;
- current conversation state;
- interaction delivery policy;
- stable Vesper persona instructions.

### Layer 4: provider synthesis

The provider is a subordinate synthesis engine, not the source of truth.

V1 should reuse the existing Ollama-compatible transport in `presence_core/llm.py` so a fast Qwen-class or equivalent model can be selected by configuration without changing application code.

Required provider behaviour:

- `think: false`;
- low latency target;
- JSON typed output for resolution;
- no tool execution;
- no direct file access;
- no direct DIO state mutation;
- no authority creation;
- no invented product capability;
- no invented pricing or delivery promises;
- preserve Vesper AI disclosure;
- obey interaction regulator and stable persona constraints.

The model receives:

```text
Vesper role and identity
public-safe DIO facts
compact conversation state
bounded recent turns
relevant product semantics
candidate route hints
interaction delivery policy
stable persona instruction
user current message
```

The model does not receive unrestricted repository state.

### Layer 5: fallback

Provider failure, malformed output, timeout, low confidence or validation failure must degrade to a useful deterministic reply. It must not collapse back to the current product-menu refusal unless there is genuinely no safer response.

Example generic fallback:

```text
I can help you work out the right DIO path. Tell me what you’re trying to achieve or what is currently getting in your way, and I’ll narrow it down with you.
```

## Deterministic Router Relationship

`presence_core/router.py` remains the authority transition router.

The new sequence is:

```text
conversation resolution
  -> ordinary conversation: reply only
  -> action proposal: route + policy validation
  -> validated consequential intent: existing side-effect branch
```

Do not use the provider to bypass `route_message()` or `authorize()`.

For action-bearing turns, add a deterministic bridge that converts an approved typed conversation proposal plus state into an explicit routing candidate. The router must still reject unsupported or ambiguous actions.

Examples:

```text
conversation action_intent=begin_intake, action_product=homs
  -> deterministic validation
  -> intake_request/homs only if policy and state permit

conversation action_intent=none
  -> no side effect even if reply text contains words such as "start", "send" or "buy"
```

## Conversation Continuity

Vesper must resolve bounded references across turns:

- `that`;
- `the first one`;
- `the other product`;
- `yes, do that`;
- `no, I meant moderation`.

Resolution uses the compact conversation state, not free-form model guessing.

When a reference cannot be resolved confidently, ask one clarification rather than selecting a product silently.

## Product Knowledge

V1 is DIO-domain intelligence with natural small talk, not a general-purpose web assistant.

Primary knowledge domain:

- DIO identity and architecture at a public-safe level;
- the canonical product portfolio available to the public surface;
- product-family differences;
- common customer problems and likely product candidates;
- proof / authority boundaries;
- intake and status processes;
- translation / formatting capabilities;
- public-safe evidence and maturity labels.

Allowed small talk:

- greetings;
- thanks;
- brief social acknowledgement;
- conversational transitions.

Out-of-domain questions should receive a short boundary response and offer to return to DIO-relevant help. Vesper should not become a general ChatGPT clone.

## Interaction Regulation And Persona

The existing interaction regulator remains presentation-only.

It may alter:

- sentence count;
- jargon level;
- humour ceiling;
- proof priority;
- voice cadence;
- sales pressure.

It may not alter:

- product truth;
- route selection authority;
- payment state;
- fulfilment state;
- identity;
- legal/commercial authority.

The existing persona assignment remains stable for the conversation. Provider synthesis must combine the persona instruction with the live interaction regulator, with the safer/lower-pressure interaction rule winning on conflict.

## Lingua Communication Registration

Continue registering final Vesper responses through `register_communication()`.

The final reply, whether sourced from a primitive, semantic crystal or provider, must create a Lingua communication receipt with:

- conversation id;
- source message id where available;
- target language;
- product context where known;
- interaction observation id;
- persona assignment id;
- conversation-resolution source;
- explicit no-authority boundary.

Translation authority remains separate. Approved target-language lanes may render the final response, but conversational semantics do not auto-approve translation quality.

## Semantic Crystal Learning

The system may collect recurrence evidence for successful provider-assisted conversational patterns.

Promotion requirements:

- repeated meaning pattern;
- verified correct applicability;
- no observed authority violation;
- held-out verification;
- measurable provider-call displacement;
- human approval for promotion when required by existing BEAST policy.

Automatic promotion from a single successful provider answer is forbidden.

A promoted crystal must preserve:

- meaning fingerprint;
- answer frame;
- applicability conditions;
- authority boundary;
- provenance / verifier receipts;
- revocation path.

## Failure Modes

### Provider unavailable

- do not fail the public conversation rail;
- use primitives, semantic crystals and deterministic fallback;
- emit a provider-unavailable event;
- no authority change.

### Provider timeout

- bounded timeout;
- return deterministic fallback within the public reply window;
- record timeout telemetry;
- no retry storm.

### Malformed provider JSON

- reject the draft;
- do not parse prose heuristically into an action;
- return deterministic fallback;
- record validation failure.

### Low-confidence product inference

- answer the known part of the question;
- ask one focused clarification;
- keep `action_intent=none`.

### Contradiction with governed product facts

- governed facts win;
- reject provider claim;
- fall back to fact-bound response.

### Consequential wording without typed action intent

- no action occurs.

### Typed action intent without deterministic authorization

- no action occurs;
- reply may explain that human or identity authorization is required.

## Observability

Add explicit events for the conversational layer:

```text
presence.conversation_resolved
presence.conversation_provider_called
presence.conversation_provider_failed
presence.conversation_clarification_requested
presence.conversation_action_proposed
presence.conversation_action_accepted
presence.conversation_action_refused
presence.conversation_crystal_reused
presence.conversation_state_updated
```

Each event should include only bounded, non-secret metadata such as:

- conversation id;
- conversation act;
- source;
- confidence;
- candidate product ids;
- action intent;
- latency;
- provider call used yes/no;
- crystal id where applicable;
- authority-created=false for conversation events.

Do not emit full private message contents into general telemetry.

## Performance Targets

For public web text conversation:

- deterministic primitive target: under 100 ms on the Presence host;
- semantic crystal target: under 250 ms on the Presence host;
- provider-assisted target: first completed reply ideally under 3 seconds and hard bounded by configured timeout;
- provider failure must still return a useful fallback within the existing public polling window;
- no model call for greetings, thanks, goodbye or high-confidence reusable crystals.

These are engineering targets, not public service-level guarantees.

## Configuration

Reuse existing provider variables where practical:

```text
OLLAMA_URL
OLLAMA_MODEL
OLLAMA_TIMEOUT
```

Introduce explicit conversation feature gates rather than overloading the old draft flag:

```text
DIO_VESPER_CONVERSATION_V2=0|1
DIO_VESPER_CONVERSATION_PROVIDER=0|1
DIO_VESPER_CONVERSATION_CRYSTALS=0|1
DIO_VESPER_CONVERSATION_RECENT_TURNS=<bounded integer>
```

Defaults must fail safely to the current deterministic Presence behaviour until the v2 acceptance gauntlet passes.

## Public API Compatibility

No public browser contract change is required for v1 of this upgrade.

Keep:

```text
POST /api/vesper/web/session
POST /api/vesper/web/message
GET  /api/vesper/web/replies
X-Vesper-Session-Token
```

The reply JSON may gain non-authoritative internal metadata behind the gateway, but the current website must continue to work without a frontend migration.

## Security And Privacy

- no arbitrary public `?api=` origin expansion as part of this work;
- session custody remains enforced by the Presence gateway;
- provider context excludes secrets, raw payment data and unrestricted operator state;
- private order status remains identity-bound;
- attachments remain quarantined and unprocessed by the conversational model;
- recent-turn context is bounded;
- semantic state stores compact meaning, not an unlimited transcript archive;
- conversation learning must not infer sensitive personal attributes;
- interaction regulation remains based on observable linguistic cues only.

## Files Expected To Change

Primary implementation surface:

```text
Create: adapters/lingua/conversation.py
Create: tests/test_vesper_conversation_resolver.py
Create: tests/test_vesper_conversation_continuity.py
Create: tests/test_vesper_conversation_authority.py
Create: tests/test_vesper_conversation_provider.py
Create: tests/test_vesper_conversation_gauntlet.py
Modify: presence_core/engine.py
Modify: presence_core/llm.py
Modify: presence_core/router.py
Modify: presence_core/state.py
Modify: adapters/lingua/communicator.py
Modify: config/presence.json
Modify: README_PRESENCE.md
```

If BEAST semantic-crystal integration requires a dedicated narrow adapter, prefer a focused new file under `adapters/lingua/` rather than importing the entire BEAST compute plane into Presence.

## Test Strategy

Implementation must be test-driven.

### Resolver unit tests

Verify:

- greeting primitive;
- identity question;
- thanks / goodbye;
- product explanation;
- product comparison;
- vague problem inference;
- useful clarification;
- no provider call for primitives;
- typed provider output validation;
- malformed provider output rejection.

### Continuity tests

Verify:

- `yes, do that` resolves only when a prior unambiguous action candidate exists;
- `the other one` resolves against known candidates;
- correction updates selected product;
- unresolved pronouns trigger clarification;
- state persists across separate `process_envelope()` calls.

### Authority tests

Verify:

- ordinary conversation cannot create an intake;
- provider prose containing `start the order` cannot create an intake without typed and authorized action intent;
- action proposal cannot bypass `authorize()`;
- attachment contents are never passed to the provider;
- payment, fulfilment, publication and spend remain false unless existing dedicated authority systems change them.

### Provider tests

Verify:

- fast-model request has `think=false`;
- provider timeout returns deterministic fallback;
- provider error returns deterministic fallback;
- invalid JSON returns deterministic fallback;
- unsupported product ids are removed / rejected;
- provider output cannot invent authority fields.

### End-to-end acceptance gauntlet

The following conversations must pass before enabling v2 publicly:

```text
Hi
Who are you?
What is DIO?
What can HOMS do?
HOMS or Evidex?
I don't know what I need.
I teach Grade 8 history and have 90 exams.
I need evidence for an audit.
Can you make a website?
What did I tell you two messages ago?
Yes, let's do that.
No, I meant the other one.
```

Required acceptance states:

```text
natural_greeting                     PASS
multi_turn_continuity                PASS
problem_to_product_inference         PASS
clarification_without_interrogation  PASS
portfolio_knowledge                  PASS
unknown_question_handling            PASS
no_invented_product_capability       PASS
no_accidental_execution_authority    PASS
no_spend_authority                   PASS
no_fulfilment_release                PASS
provider_unavailable_fallback        PASS
lingua_crystal_reuse                 PASS
```

## Rollout

1. Land behind `DIO_VESPER_CONVERSATION_V2=0`.
2. Run unit, continuity, authority and provider tests.
3. Run the acceptance gauntlet against an isolated Presence state root.
4. Enable v2 locally for operator testing.
5. Run public-web synthetic conversations through the same Cloudflare Presence transport used by production.
6. Confirm no change to session/message/reply custody behaviour.
7. Enable v2 for public conversation.
8. Keep provider fallback independently disableable so Lingua primitives and crystals remain available during provider outages.

## Non-Goals

This work does not:

- turn Vesper into a general-purpose internet assistant;
- give an LLM direct DIO tool access;
- replace deterministic routing or authority policy;
- auto-process public attachments;
- auto-send mail;
- auto-publish;
- auto-spend;
- auto-release fulfilment;
- collapse translation approval into conversational semantics;
- change the public web transport contract;
- create a new independent `vesper_chatbot` subsystem.

## Success Definition

Vesper v2 is successful when a public visitor can have a natural multi-turn conversation about their problem, receive accurate DIO-domain guidance, correct Vesper when necessary, and move deliberately from conversation into a governed DIO action without the language model ever acquiring execution authority.

The desired mental model is:

```text
Vesper = identity + presence
Lingua = conversational meaning
fast model = bounded synthesis fallback
DIO router/policy = action transition
DIO authority plane = consequential permission
```
