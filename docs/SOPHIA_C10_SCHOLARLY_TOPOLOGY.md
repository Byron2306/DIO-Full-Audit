# Sophia C10: Scholarly Topology and Human Decision Queue

## Why this layer exists

The Longitudinal Speculum can preserve a claim across revisions, but scholarly change is not always a one-to-one sentence rewrite.

A revision can:

- split one composite proposition into two claims;
- merge two earlier propositions into one synthesis;
- change a number, percentage, negation, modality or quantifier;
- swap the evidence source while retaining similar wording;
- strengthen an associational proposition into a causal one;
- introduce a new high-risk claim;
- or make a high-risk claim disappear without telling us whether the author deliberately removed it.

C10 therefore adds a second layer above claim continuity:

`Longitudinal Speculum -> Scholarly Topology Audit -> Human Decision Queue -> Revision Release Gate`

The topology layer does not determine what the author meant. It tells the human where scholarly structure or burden changed enough that silence would be unsafe to interpret as intent.

## Scholarly topology audit

The audit writes:

- `SCHOLARLY_TOPOLOGY_AUDIT.json`
- `SCHOLARLY_TOPOLOGY_AUDIT.md`
- `SCHOLARLY_DECISION_QUEUE.json`
- `SCHOLARLY_DECISION_QUEUE.md`
- `SUPERVISOR_COMMAND_BRIEF.html`

The currently bound review pack receives copies of the same artifacts and its ZIP is rebuilt.

### Split candidates

A split candidate occurs when one earlier claim is materially similar to multiple claims in the next reviewed version.

Example:

`Structured feedback improves academic writing and revision quality.`

may become:

`Structured feedback improves academic writing.`

and

`Structured feedback improves revision quality.`

Sophia records this as a structural hypothesis. A human reviewer can confirm that the author intentionally decomposed the proposition, reject the split interpretation, or defer the question.

### Merge candidates

A merge candidate is the inverse: one current claim is materially similar to multiple earlier claims.

Sophia does not silently choose the highest-scoring parent and erase the alternative ancestry question. The topology audit preserves the ambiguity for human interpretation.

### Factual surface mutation

Within a continuing lineage, C10 checks visible changes that can materially alter scholarly meaning:

- numeric and percentage changes;
- negation changes;
- modality changes;
- quantifier changes;
- citation-surface changes;
- evidence-source identity changes;
- causal-scope changes; and
- universal-scope changes.

These signals are not findings that the new wording is wrong. They are prompts to verify that the change was deliberate and adequately supported.

## Human scholarly decision queue

The decision queue creates explicit obligations when material scholarly ownership is still missing.

Current obligations include:

1. ambiguous claim lineage that still needs continuity confirmation;
2. a burden mutation without an author decision on the revised occurrence;
3. a high-risk claim that disappears without an explicit author `remove` or `defer` decision;
4. a newly surfaced high-risk claim without an author decision;
5. unresolved split or merge topology questions; and
6. material factual-surface mutations without an author decision or human topology interpretation.

The governing rule is:

> Silence is not scholarly intent.

A claim disappearing is therefore not automatically interpreted as withdrawal or successful resolution. A stronger claim is not treated as accepted merely because it survived into the latest draft.

## Two release gates

C10 deliberately distinguishes the first diagnostic delivery from the revision release.

### Initial diagnostic pack

The initial pack may contain open scholarly decisions. That is expected: the pack exists to show the author and reviewer what needs attention.

Initial approval therefore requires:

- the grounded C9 pack;
- a ready Longitudinal Speculum;
- no unresolved claim-continuity ambiguity that would make the initial lineage itself incoherent; and
- valid C10/native integrity hashes.

It does **not** require a zero decision queue.

### Revision release

The revision round is different. Before the revised pack is approved, C10 requires:

- at least two bound manuscript versions;
- resolved claim-lineage ambiguity;
- valid Longitudinal Speculum and native Sophia integrity hashes;
- a ready topology audit;
- valid topology and decision-queue hashes; and
- **zero unresolved scholarly decision obligations**.

The final gate is implemented in `require_scholarly_release_clear_summary()`.

This makes the revision round meaningful: it is not merely a second AI pass. It is a governed scholarly handback in which material changes have been surfaced and explicitly owned by a human.

## Operator commands

The canonical C10 job workflow remains:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py run SOPHIA-JOB-ID
```

After an author-owned revision:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py revision SOPHIA-JOB-ID \
  --document /path/to/revised_section.docx
```

Record an author decision on a claim lineage:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py record-decision SOPHIA-JOB-ID \
  --lineage lineage-... \
  --decision strengthen_evidence \
  --rationale "The causal wording will be retained only if evidence meeting the stronger burden is added." \
  --actor "Author name"
```

Record a human topology interpretation:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py record-topology-decision SOPHIA-JOB-ID \
  --issue TI-... \
  --decision confirm_split \
  --actor "Human reviewer" \
  --rationale "The author intentionally separated the composite proposition into two independently supportable claims."
```

Approve the initial diagnostic pack:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py approve SOPHIA-JOB-ID \
  --reviewer "Reviewer name"
```

Approve the revised pack only after the scholarly decision queue is clear:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py approve-revision SOPHIA-JOB-ID \
  --round 1 \
  --reviewer "Reviewer name"
```

A dependency-light topology tool is also available for direct state inspection:

```bash
python scripts/run_sophia_c10_topology.py \
  --state-root state/sophia_jobs/SOPHIA-JOB-ID/C10_LONGITUDINAL_SPECULUM \
  --project-id SOPHIA-JOB-ID \
  audit
```

## Supervisor command brief

`SUPERVISOR_COMMAND_BRIEF.html` is intentionally decision-first.

It answers:

- What now needs a human decision?
- Which claim structures may have split or merged?
- Which material factual surfaces changed?
- Which scholarly obligations still block revision release?

It does not ask the supervisor to understand ProjectStore internals, similarity metrics or DIO orchestration before acting.

## Authority boundary

C10 topology signals are **scholarly continuity and revision hypotheses**, not findings of:

- author intent;
- factual falsity;
- plagiarism;
- AI authorship;
- fabrication;
- misconduct; or
- institutional non-compliance.

The machinery is deliberately asymmetric toward caution. It may ask a human to inspect a change. It may not convert textual similarity into an accusation or convert human silence into scholarly consent.

## Proof target

The live proof should deliberately include a difficult revision, not merely cosmetic rewriting.

A useful test manuscript should include at least some of the following between versions:

- one retained claim with stronger evidence;
- one claim narrowed from causal to associational scope;
- one composite claim split into two;
- one changed numerical statement;
- one high-risk claim removed intentionally;
- one genuinely new high-risk claim; and
- one ambiguous paraphrase requiring human continuity confirmation.

C10 succeeds if Sophia preserves enough scholarly history to help a supervisor make better decisions while clearly exposing the places where machine continuity inference ends and human scholarly authority begins.
