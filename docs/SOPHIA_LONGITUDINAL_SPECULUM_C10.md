# Sophia C10: Longitudinal Speculum

## Purpose

C9 made scholarly integrity inspectable inside one controlled review. C10 asks the next question:

> Can Sophia preserve the history of a scholarly claim across author-owned revisions without confusing changed wording, changed evidence, changed epistemic burden, or machine inference with human intent?

C10 is deliberately a proof-ready research/product layer before public marketing. It does not replace C9. It stacks on C9 and reuses the real Sophia `SophiaProjectStore`.

## Core object

The living record is:

`claim v1 -> evidence v1 -> Sophia intervention -> human decision -> claim v2 -> evidence v2 -> lineage state -> remaining risk`

Every reviewed claim occurrence has a **version-scoped record ID**. Related claim occurrences may share a **claim lineage ID**. This prevents the native project store from overwriting an earlier claim occurrence when a later draft is added.

## What C10 distinguishes

C10 does not treat all textual change as the same event.

It distinguishes:

- `new_claim`
- `continued_claim`
- `continuation_candidate_needs_confirmation`
- `burden_mutation`
- `reintroduced_claim`
- `human_confirmed_continuation`
- `human_confirmed_new_claim`

The longitudinal export then derives higher-level states such as:

- `single_observation`
- `continued`
- `evidence_strengthened`
- `evidence_regressed`
- `burden_mutated`
- `continuity_uncertain`
- `absent_latest_revision`
- `reintroduced`

A claim that is absent from the latest draft is **not** called abandoned unless a human author records a removal decision.

## Lineage matching contract

C10 uses a transparent deterministic matcher over:

- normalized text similarity;
- canonicalized token overlap;
- claim-type agreement;
- causal/universal scope agreement;
- and source identity where visible.

The matcher is intentionally conservative.

A strong unambiguous match may continue automatically. A mid-confidence paraphrase becomes `continuation_candidate_needs_confirmation`. It is not silently treated as new and it is not silently merged with an older claim.

Secondary similarity evidence therefore never gains authority to decide scholarly identity on its own.

## Epistemic burden mutation

C10 separately checks whether a related claim has become harder to justify.

Current burden signals include:

- claim type change;
- evidence-risk increase;
- stronger causal scope;
- stronger universal scope.

A claim may therefore remain in the same conceptual lineage while being marked `burden_mutation`.

Example:

`X is associated with Y` -> `X causes Y`

is not merely an edited sentence. It creates a stronger evidence burden.

## Evidence trajectory

Each lineage keeps the C9 support state for each occurrence:

`does_not_support / unmapped -> background_only -> partial_support -> support_ready`

The longitudinal layer can therefore report evidence strengthening or regression across drafts without treating that movement as proof of authorship or learning gain.

## Human decisions

C10 adds an explicit author-decision operation.

Allowed controlled decisions are:

- `keep`
- `revise`
- `narrow`
- `strengthen_evidence`
- `retain_with_limitation`
- `remove`
- `defer`
- `dispute`

The decision is written into both:

1. the C10 longitudinal registry; and
2. Sophia's native `final_decision_ledger` through `SophiaProjectStore.append_final_decision()`.

The human therefore remains the authority on whether a claim is retained, narrowed, disputed or removed.

## Human continuity resolution

Ambiguous paraphrases are explicit review items.

A reviewer can:

- confirm that the provisional occurrence continues the proposed parent lineage; or
- confirm that it is genuinely a new claim.

The decision updates the version-scoped native claim record and the longitudinal registry.

C10 approval refuses unresolved continuity candidates.

## Outputs

The C10 state root writes:

- `LONGITUDINAL_REGISTRY.json`
- `LONGITUDINAL_SPECULUM.json`
- `LONGITUDINAL_SPECULUM.md`
- `SUPERVISOR_SPECULUM.html`
- native Sophia ProjectStore state under `project_store/`

The currently synced review pack also receives:

- `LONGITUDINAL_SPECULUM.json`
- `LONGITUDINAL_SPECULUM.md`
- `SUPERVISOR_SPECULUM.html`

and its review ZIP is rebuilt so the C10 objects travel with the pack.

## Operator entrypoint

The C10 entrypoint is:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py --help
```

### Run a new initial review through C9 and bind C10

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py run SOPHIA-JOB-ID
```

### Bind existing C9 packs without rerunning Gemini

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py sync SOPHIA-JOB-ID
```

This is useful for an already completed initial review or revision round.

### Inspect the living Speculum

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py export SOPHIA-JOB-ID
```

The easier human view is:

```text
state/sophia_jobs/SOPHIA-JOB-ID/C10_LONGITUDINAL_SPECULUM/SUPERVISOR_SPECULUM.html
```

### Record an author decision

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py record-decision SOPHIA-JOB-ID \
  --lineage lineage-... \
  --decision retain_with_limitation \
  --rationale "Keep the association, but preserve the observational boundary." \
  --actor "Author name"
```

### Run the included author-owned revision round

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py revision SOPHIA-JOB-ID \
  --document /path/to/revised_section.docx
```

### Resolve an ambiguous paraphrase as continuation

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py resolve-lineage SOPHIA-JOB-ID \
  --lineage lineage-PROVISIONAL \
  --accept-parent \
  --actor "Human reviewer" \
  --rationale "Same substantive claim after author paraphrase."
```

### Confirm that an ambiguous paraphrase is actually new

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py resolve-lineage SOPHIA-JOB-ID \
  --lineage lineage-PROVISIONAL \
  --confirm-new \
  --actor "Human reviewer" \
  --rationale "This introduces a distinct proposition rather than revising the earlier claim."
```

### C10-gated approval

Initial review:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py approve SOPHIA-JOB-ID \
  --reviewer "Reviewer name"
```

Revision review:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py approve-revision SOPHIA-JOB-ID \
  --round 1 \
  --reviewer "Reviewer name"
```

The C10 approval gate requires:

- a ready longitudinal Speculum;
- the expected number of bound versions;
- no unresolved continuity candidates;
- a 64-character longitudinal Speculum hash; and
- a 64-character native Sophia integrity-record hash.

## CI proof contract

The C10 workflow first reruns the inherited C9 tests, then tests longitudinal behavior.

The C10 adversarial suite covers:

1. two version-scoped claim occurrences without native overwrite;
2. evidence strengthening in one lineage;
3. stronger epistemic burden as a mutation rather than a cosmetic edit;
4. ambiguous paraphrase held for human continuity confirmation;
5. human continuity confirmation propagated into the native ProjectStore;
6. author decision propagated into the native final-decision ledger;
7. disappearance distinguished from author abandonment;
8. reintroduced claim distinguished from new claim;
9. idempotent re-ingestion of the same draft; and
10. release blocking while continuity remains unresolved.

## What C10 does not claim

C10 does not prove:

- who authored a sentence;
- that two differently worded claims are philosophically identical;
- misconduct;
- plagiarism;
- learning gain;
- truth of the underlying scholarly claim;
- or institutional compliance.

Its lineage matcher is a governed continuity aid. Ambiguity is an output state, not an implementation failure.

## Live proof protocol

The decisive next test should use one real postgraduate manuscript section.

1. Run the initial section through C9+C10.
2. Human-review the highest-risk source mappings.
3. Record at least one explicit author decision on a material claim.
4. Let the author revise the section in their own words.
5. Run the revision through C9+C10.
6. Inspect whether Sophia correctly separates:
   - retained claims;
   - new claims;
   - changed evidence support;
   - burden mutations;
   - disappeared claims;
   - and ambiguous continuity.
7. Resolve any ambiguous lineage manually.
8. Check that the final native Sophia record contains both version-scoped occurrences and the human decision.
9. Inspect `SUPERVISOR_SPECULUM.html` blind to the raw implementation and judge whether it improves a real supervision/research-integrity decision.

The strongest C10 success criterion is not "the matcher got every row automatically." It is:

> Sophia preserves enough scholarly continuity to be useful while refusing to counterfeit certainty about claim identity or human intent.

## Next frontier if C10 survives live proof

A later phase could add a governed semantic witness for harder paraphrases, but only as another evidence source. It must not silently replace the deterministic lineage contract or the human confirmation gate.

That would allow Sophia to ask a richer question:

> These claims look semantically related. Is this the same proposition, a narrowed proposition, an expanded proposition, or a new one?

The answer should remain inspectable and human-resolvable.
