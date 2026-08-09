# DIO Triune Semantic Judgement v1

## Status

C5 inserts a proof-carrying semantic judgement wall between DIO expression and external execution.

It does not replace the existing commercial planning Triune in `commerce/triune.py`. The planning Triune decides how a commercial transaction should progress. The C5 semantic Triune judges whether one concrete expression, bound to one concrete Commercial Semantic Object, may proceed toward one concrete execution.

The constitutional law is:

> **A perfect sentence can still be forbidden. An approved sentence can still be stale. An allowed sentence still does not send itself.**

## Position in the DIO stack

```text
Evidence / source state
        |
        v
Commercial Semantic Object
        |
        v
Communicative Act
        |
        v
Expression
        |
        v
+---------------------------------------+
|      C5 TRIUNE SEMANTIC JUDGEMENT     |
|                                       |
| Metatron   jurisdiction / authority   |
| Loki       adversarial challenge      |
| BEAST      evidence / uncertainty     |
+---------------------------------------+
        |
        v
proof-carrying judgement receipt
        |
        v
human approval lease
        |
        v
provider execution
```

Metatron, Loki and BEAST do **not** write the message. The expression engine remains responsible for expression. The Triune only judges the meaning, evidence, authority and execution relationship.

## Metatron

Metatron answers:

- Is the Commercial Semantic Object valid?
- Is the expression bound to that exact object?
- Does the expression plan agree on the communicative act?
- Is the communicative act valid for the requested execution channel?
- Does the current authority state permit this class of external action?
- Does the execution conversation match semantic lineage?
- Are sensitive execution values backed by an authoritative source class?
- Does the expression preserve the C3 human-approval contract?

Metatron returns `ALLOW` or `BLOCK`.

Metatron never grants the provider permission itself.

## Loki

Loki attempts to break the expression before execution.

It checks:

- generation policy relaxation;
- fact invention permission;
- inference-to-fact promotion;
- unknown-field filling;
- loss of claim-source provenance;
- dependency-manifest tampering;
- inference used by an act that does not permit inference;
- explicit asserted claims that are prohibited by the CSO;
- asserted claims not bound to the governed plan;
- Conversation Context attempting to acquire truth or execution authority; and
- unbound expression.

Loki returns:

- `CLEAR`
- `CHALLENGE`
- `VETO`

A challenge does not silently disappear. It becomes an execution-review obligation.

### Dependency manifest versus asserted claims

C3 currently provides a conservative `claim_sources` dependency manifest. That manifest says which semantic values the renderer depended on; it is intentionally broader than the exact sentence-level claims that appear in the final prose.

C5 therefore distinguishes:

```text
semantic dependency != asserted claim
```

BEAST uses broad semantic dependencies to judge evidence coverage.

Loki uses `asserted_claims`, when present, for precise claim-policy enforcement.

Until every renderer emits sentence-level `asserted_claims`, Loki records `PRECISE_ASSERTED_CLAIM_MANIFEST_ABSENT` as a challenge rather than pretending every dependency was explicitly asserted.

This is intentionally conservative. The judge is not allowed to hallucinate violations either.

## BEAST

C5 loads the real EdgeK-BEAST `EvidenceScorer` from the vendored BEAST source or an explicitly configured `DIO_BEAST_ROOT`.

BEAST scores the expression's declared semantic dependencies using:

- relevance;
- confidence;
- severity;
- freshness;
- repeat count;
- verification strength; and
- blast radius.

C5 additionally blocks when:

- no semantic dependency manifest exists;
- a dependency has no source reference;
- an epistemic status is invalid;
- the expression is bound to another CSO; or
- an active matching BEAST negative capability is supplied.

BEAST returns:

- `PASS`
- `CAUTION`
- `BLOCK`

Explicit unknowns and inferred dependencies remain visible as cautions rather than being erased for rhetorical convenience.

## Overall verdict

```text
Metatron BLOCK
        or
Loki VETO
        or
BEAST BLOCK
        => BLOCK

otherwise, if obligations remain
        => ALLOW_WITH_OBLIGATIONS

otherwise
        => ALLOW
```

Every judgement permanently records:

```json
{
  "execution_authority_granted": false
}
```

A semantic judgement is therefore not an execution token.

## Proof-carrying receipt

`dio.semantic_judgement.v1` binds:

- canonical Commercial Semantic Object hash;
- canonical expression hash;
- exact execution-binding hash;
- bound source-state file hashes;
- Metatron result;
- Loki result;
- BEAST assessment;
- execution obligations; and
- constitutional flags.

Receipts live under:

```text
state/semantic_judgements/JUDGE-*.json
```

The same evidence, expression and execution resolve to the same judgement identity. A later clock tick does not create a conflicting receipt.

## Source-state quarantine

The receipt binds the exact source state used during judgement.

For example, a conversation reply can bind:

```text
state/leads/<lead>.json
state/conversation_context/<context>.json
state/mail_ingress/<message>.json
```

If one of those files changes after judgement, the judgement becomes stale.

The same applies to other rails:

- prospect outreach binds the Wave 4 prospect source archive;
- HOMS/Evidex notifications bind workflow, source job, processing receipt, output approval where applicable, and delivery artifacts;
- agency RFQs bind the generated media brief and durable campaign/vendor evidence.

This implements the BEAST design law that source change invalidates previously earned reuse authority.

## Execution binding

For Outlook mail the execution digest covers the semantically relevant send object:

- mail intent ID;
- purpose;
- recipient;
- subject;
- body / HTML body / body path;
- attachments;
- conversation ID;
- source message ID;
- communicative act;
- Commercial Semantic Object ID; and
- Conversation Context ID.

Provider draft ID and human approval-token state are deliberately not part of the semantic expression hash. Creating a provider draft or granting a separate human lease must not rewrite the meaning that was judged.

Changing the recipient, body, subject, attachment set or semantic binding after judgement invalidates the receipt.

## Human approval is necessary but insufficient

External mail requires two independent things:

```text
current semantic judgement
        +
valid human approval lease
        =
eligible for provider send
```

Human approval cannot repair:

- `BLOCK`;
- Loki `VETO`;
- BEAST `BLOCK`;
- stale source state; or
- tampered execution content.

Likewise, a Triune `ALLOW` does not generate a human approval lease.

## Outlook enforcement

Semantically bound Outlook mail is checked:

1. before a provider draft is created; and
2. again immediately before provider send.

Tampered or stale mail is refused before a Microsoft Graph execution call.

### True conversation replies

C5 exposed a physical-lineage mismatch in the earlier reply path. A generic new-message draft is not a sufficiently strong implementation of a reply that is semantically bound to an existing Outlook conversation.

A C5 `conversation_reply` therefore carries the actual provider message ID from the latest bound Outlook ingress record.

The provider draft rail then:

1. creates a reply draft from that exact source message;
2. verifies the returned conversation ID matches judged lineage;
3. verifies the recipient matches the judged recipient;
4. patches the exact judged subject/body into the reply draft;
5. deletes and refuses a mismatched provider draft; and
6. leaves the judged lead evidence unchanged during draft preparation.

This makes semantic lineage and physical provider lineage coincide.

## Semantic mail construction rule

C5 hardens the mail-intent constructor:

```text
communicative_act present + semantic_binding absent
    => REFUSE

semantic_binding present + communicative_act absent
    => REFUSE
```

Legacy compatibility exists only for mail that declares neither field.

This prevents a future C3-generated message from accidentally falling through the pre-semantic mail route simply because one producer forgot to attach its CSO binding.

## Producers under C5

The C5 rail now governs the primary C3-generated external-mail producers:

### Conversation replies

```text
Lead
 -> C4 Conversation Context
 -> CSO
 -> inbound/qualified reply expression
 -> Triune judgement
 -> Outlook reply draft
 -> human approval
 -> send
```

### Prospect outreach

```text
Wave 4 prospect target
 -> prospect CSO
 -> cold_permission_request
 -> Triune judgement
 -> Outlook draft
 -> human approval
 -> send
```

Creative upgrades must be re-judged before the provider draft can be patched.

### HOMS / Evidex

```text
Product workflow state
 -> workflow CSO
 -> intake_request or delivery
 -> Triune judgement
 -> Outlook draft
 -> human approval
 -> send
```

Evidex judgement also binds reviewed delivery evidence and the delivery artifact.

### Agency RFQ

```text
Campaign + qualified vendor route + media brief
 -> vendor RFQ CSO
 -> request_for_quotation
 -> Triune judgement
 -> mail intent
 -> human approval
 -> send
```

The RFQ remains a request for quotation only. Judgement cannot turn it into booking or spend authority.

## Negative capability

C5 accepts active BEAST negative-capability records as an explicit veto input.

A repeated proven failure pattern can therefore block the same capability/execution route even if the current prose looks acceptable.

This is intentionally asymmetric:

```text
success does not automatically grant wider authority
failure can narrow future capability
```

## Validation

The semantic regression suite covers:

- inherited C1 Commercial Semantic Object rules;
- C2 NicheFoundry evidence/provenance rules;
- C3 communicative-act contracts;
- C4 Conversation Context authority boundaries;
- normal Triune judgement;
- relaxed generation policy;
- prohibited asserted claims;
- active BEAST negative capability;
- CSO mismatch;
- execution tampering;
- source-state mutation;
- human-approval obligation;
- missing judgement;
- judgement idempotence;
- true Outlook reply drafting;
- wrong-thread refusal;
- wrong-recipient refusal;
- refusal before Graph call when mail is stale;
- dual semantic + human approval before send; and
- semantic mail binding construction rules.

The CI workflow also compiles the actual outbound producer paths and the vendored BEAST scorer.

## C5 gate

C5 is satisfied when:

1. semantic judgement is independent of prose generation;
2. Metatron, Loki and BEAST retain separate responsibilities;
3. every judgement binds exact semantic, expression, execution and source state;
4. a BLOCK or VETO cannot be repaired by human send approval;
5. an ALLOW cannot create execution authority;
6. source mutation invalidates earned judgement;
7. semantically bound Outlook mail cannot reach draft/send without a current receipt;
8. true Outlook replies preserve physical conversation lineage;
9. C3 mail cannot declare an act without a CSO binding; and
10. the full C1-C5 semantic regression stack passes together.
