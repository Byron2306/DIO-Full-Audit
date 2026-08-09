# DIO Commercial Semantic Object v1

Status: C1 foundation contract

Canonical schema: `schemas/dio.commercial_semantic_object.v1.schema.json`

Python implementation: `commerce/semantic.py`

## Purpose

`dio.commercial_semantic_object.v1` is the shared meaning boundary between DIO's evidence/domain systems and any downstream expression engine.

It exists to stop rich upstream intelligence from being flattened into thin prospect rows, generic offer names, or ungrounded copy-generation prompts.

The contract separates:

- facts DIO can verify;
- hypotheses DIO is still inferring;
- explicit unknowns;
- commercial meaning such as job-to-be-done, workflow pain, trigger and scope;
- proof that may matter to this buyer;
- claims that are permitted or prohibited;
- channel and rhetorical strategy;
- evidence and authority lineage.

The object contains meaning, not finished prose.

## Design law

> Deterministic meaning. Probabilistic expression. Governed execution.

A writer may vary phrasing. It may not silently upgrade an inference to a fact, fill an unknown with invented precision, or claim authority that the semantic object does not possess.

## Epistemic states

Every canonical semantic value uses one of three states:

- `verified`: the value itself is supported and retains one or more evidence references;
- `inferred`: the value remains a hypothesis and retains its basis references;
- `unknown`: the value is explicitly unresolved and is stored as `null` rather than a guessed default.

A numeric score is not evidence merely because it has decimals.

## Thin-lead compatibility adapter

`commercial_semantic_object_from_lead()` provides an intentionally conservative bridge from existing `dio.lead.v1` or similar thin lead rows.

The adapter can establish facts about the lead record itself, for example:

- the captured lead ID;
- contact identity fields present in the record;
- the selected product or offer;
- the captured request subject;
- the recorded consent state;
- attribution/channel metadata.

It does **not** treat free-form request text as proof of:

- buyer role;
- organisation type;
- budget;
- urgency;
- workflow pain;
- job-to-be-done;
- agreed scope;
- processing authority.

Those remain explicit unknowns until a later semantic resolver or authoritative source earns the right to populate them.

## C1 gate

C1 is satisfied when:

1. the CSO schema is canonical and versioned;
2. verified and inferred values cannot pass validation without evidence/basis references;
3. unknowns remain first-class rather than becoming default scores;
4. permitted and prohibited claims cannot overlap;
5. existing thin lead rows can be converted without manufacturing customer facts;
6. the compatibility adapter is covered by regression tests.

C2 will promote NicheFoundry's richer audience and opportunity semantics into this object rather than replacing this contract.
