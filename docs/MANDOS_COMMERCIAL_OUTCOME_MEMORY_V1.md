# Mandos Commercial Outcome Memory v1

## Law

> **Mandos does not forget.**

C6 closes the DIO commercial semantic loop by turning real outcomes back into governed evidence.

The memory law is deliberately asymmetric:

```text
success may suggest
repetition may corroborate
adversarial validation may qualify
human confirmation may promote

failure may narrow capability earlier
```

No outcome, pattern, crystal or model may create execution authority.

## Position in DIO

```text
Evidence
  -> Commercial Semantic Object
  -> Communicative Act
  -> Expression
  -> C5 Triune Judgement
  -> Human Approval
  -> Execution
  -> REAL OUTCOME
  -> MANDOS
       |-> Hivenance hypothesis evidence
       |-> NicheFoundry audience/opportunity evidence
       |-> BEAST negative capability
       `-> promoted reusable strategy, only after earned gates
```

C1-C5 govern what DIO means, says and does.

C6 governs what DIO is allowed to learn from what happened next.

## Outcome object

The canonical outcome is:

```text
dio.commercial_outcome.v1
```

Supported outcome classes include:

- outbound sent;
- reply received;
- explicitly closed no-reply observation window;
- objection recorded;
- qualification changed;
- revision requested;
- approval recorded;
- paid order;
- payment failure;
- delivery sent;
- delivery acknowledged;
- correction received;
- refund or cancellation;
- manual time;
- cost;
- revenue;
- transaction closeout; and
- campaign measurement.

Every outcome binds:

- commercial lineage;
- strategy signature;
- epistemic evidence state;
- source references;
- source classes;
- source file hashes where available;
- economics; and
- exact detail.

The authority contract is permanent:

```json
{
  "may_expand_execution_authority": false,
  "may_become_reusable_strategy": false
}
```

An outcome is evidence. It is not strategy authority.

## Immutable journal

Outcomes live under:

```text
state/mandos/outcomes/OUT-*.json
```

Mandos also appends every first-seen outcome to:

```text
state/mandos/JOURNAL.jsonl
```

The journal is hash chained:

```text
entry[n].previous_entry_sha256 == entry[n-1].entry_sha256
```

Each entry also binds the hash of its immutable outcome file.

Reconciliation is idempotent. Seeing the same exact outcome again does not create a second memory.

Interpretation may change later. The original outcome does not.

## Silence is not automatically evidence

DIO must never infer `no reply` merely because no new message is visible at one instant.

A silence outcome exists only after an explicit bounded observation window is closed:

```text
sent mail
  + explicit window start
  + explicit window end
  + end is in the past
  + no inbound in the bound conversation during that window
  + operator confirmation
  = no_reply_window_closed
```

The outcome explicitly records that absence is operator-confirmed, not a provider fact.

This prevents cron timing or connector lag from becoming fabricated rejection evidence.

## Independent cases

Repeated events inside one commercial case do not count as repeated independent validation.

Mandos chooses a case identity from durable commercial lineage, preferring transaction, lead, campaign, order, conversation or job identity.

Therefore:

```text
reply + qualification + payment
from the same lead
!= three independent cases
```

This prevents one successful transaction from voting for itself three times.

## Promotion ladder

The automatic evidence ladder stops before strategy authority:

```text
1 verified independent case
  -> observation

2 verified independent cases
  -> repeated_observation

3+ verified independent cases
+ 2+ evidence source classes
  -> corroborated_pattern
```

Nothing above `corroborated_pattern` happens automatically.

### Candidate strategy

A corroborated pattern requires explicit nomination:

```text
corroborated_pattern
  + human nomination with rationale
  -> candidate_strategy
```

### Adversarial validation

A candidate requires explicit validation receipts:

```text
candidate_strategy
  + adversarial validation PASSED
  + evidence receipt references
  -> adversarial_validated
```

If positive and negative cases coexist, promotion also requires an explicit contradiction resolution.

### Reusable crystal

Only then can a human explicitly promote:

```text
adversarial_validated
  + explicit human confirmation
  + rationale
  -> reusable_crystal
```

A reusable crystal is still limited to:

```text
scope = strategy_hypothesis_only
may_expand_execution_authority = false
```

It can influence what DIO tries or proposes. It cannot authorize execution.

## Revocation without forgetting

A reusable crystal can be revoked when new evidence contradicts it.

Revocation changes current reuse authority but does not delete:

- original outcomes;
- journal history;
- the fact that the pattern was once promoted; or
- its historical maximum stage.

This distinction is central:

```text
memory != current belief
```

Mandos preserves both.

## Economics

Outcomes may carry:

- revenue in minor currency units;
- cost in minor currency units;
- manual minutes; and
- derived gross margin.

Market Command measurements therefore flow into Mandos as real observations rather than disappearing into dashboard aggregates.

A market campaign's own `promote` settlement does **not** equal Mandos reusable strategy. Market optimization and semantic strategy authority remain separate systems.

## Hivenance feedback

Hivenance receives Mandos campaign outcomes in a dedicated context lane:

```text
mandos_outcomes
```

It includes:

- outcome identity/type/polarity;
- independent case identity;
- economics;
- source references/classes;
- pattern stage; and
- explicit reuse-authority state.

Hivenance may use this as hypothesis evidence.

It may not treat the evidence as live execution authority.

## NicheFoundry feedback

NicheFoundry receives the same verified outcome envelope separately from its scoring system.

Mandos outcome evidence is not converted into a synthetic `0.x` score.

When enriching a Commercial Semantic Object, Mandos can add verified outcome facts and evidence references using the existing C1 schema. It does not overwrite:

- buyer identity;
- workflow pain;
- customer scope;
- consent;
- NicheFoundry opportunity scores; or
- authority state.

The live NicheFoundry request packet also carries Mandos feedback when campaign lineage is available and explicitly prohibits generating synthetic market scores from it.

## BEAST negative capability

Mandos creates a typed registry:

```text
state/mandos/beast/NEGATIVE_CAPABILITIES.json
```

A negative capability becomes `active` when the same bounded strategy has at least two independent verified negative cases and no verified positive contradiction.

A positive contradiction changes the failure pattern to `contested`, which removes its automatic veto authority.

The C5 BEAST semantic evidence layer reads active Mandos failure memory automatically.

Thus:

```text
repeated verified failure
  -> active negative capability
  -> matching future C5 execution can BLOCK
```

But:

```text
repeated verified success
  != automatic execution permission
```

The organism may learn caution faster than confidence.

## Automatic reconciliation

The main commercial orchestrator now performs:

```text
Conversation Context reconciliation
  -> Commercial transaction reconstruction
  -> Triune commercial assessment
  -> Mandos outcome reconciliation
```

Mandos reconstructs outcomes from existing canonical receipts where the evidence supports them, including:

- governed sent mail;
- later inbound replies;
- operator lead qualification;
- provider-backed paid orders;
- delivery acknowledgement;
- transaction closeout; and
- Market Command measurement rows.

Unsupported meaning is not invented. For example, an inbound email is not automatically classified as an objection or correction without a separate governed classification/confirmation step.

## What Mandos deliberately does not do

Mandos does not:

- infer objection semantics from arbitrary prose;
- infer no-reply without a closed observation window;
- turn campaign settlement into semantic truth;
- overwrite C1 customer truth;
- promote strategy automatically;
- erase contradicted history;
- treat positive evidence as execution permission; or
- bypass C5 or human approval.

## C6 gate

C6 is satisfied when:

1. real commercial outcomes have a canonical immutable object;
2. the journal detects mutation or missing outcomes;
3. repeated events from one case do not masquerade as independent evidence;
4. silence requires an explicit bounded observation window;
5. economics survive the feedback loop;
6. Hivenance receives outcome evidence without execution authority;
7. NicheFoundry receives outcome evidence without fake precision;
8. repeated verified failure can produce a BEAST negative capability;
9. positive contradiction can contest that capability;
10. successful patterns cannot crystallize automatically;
11. adversarial validation and explicit human promotion are required for reuse;
12. revocation preserves historical evidence; and
13. the full C1-C6 semantic regression stack passes together.

## Final loop

```text
Evidence enters.
Meaning is resolved.
Uncertainty remains explicit.
Authority is earned.
Expression may vary.
Execution does not exceed its proof.
Reality answers.
Mandos records.
Patterns must earn reuse.
Failure narrows before success expands.
Nothing true is erased.
```
