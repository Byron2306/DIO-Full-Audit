# Sophia C10 Live and Stress Proof Protocol

## Purpose

C10 has two different proof thresholds on purpose.

The first asks whether the longitudinal machinery is real and receipt-bearing.

The second asks whether Sophia was exercised on a sufficiently difficult scholarly revision and whether a human academic found the resulting integrity judgments materially useful.

A passing CI suite is not a live scholarly proof. A passing live proof is not yet a broad accuracy claim.

## Proof Tier 1: C10 longitudinal live proof

A real case must demonstrate all of the following:

1. the initial manuscript completed the grounded C9 integrity lane;
2. at least one author-owned revision completed the grounded C9 lane;
3. at least two manuscript versions are bound to one C10 project;
4. at least one scholarly claim is observed across versions;
5. native Sophia ProjectStore preserves version-scoped claim occurrences rather than overwriting them;
6. ambiguous lineage has been explicitly resolved by a human;
7. at least one explicit human author decision is present;
8. that decision reaches Sophia's native final-decision ledger;
9. the C10 and native integrity records carry stable hashes;
10. the scholarly topology audit and decision queue are receipt-bearing;
11. the blocking scholarly decision queue is zero; and
12. the non-forensic authorship/misconduct boundary remains intact.

Run:

```bash
python scripts/prove_sophia_c10_live.py \
  --job-dir state/sophia_jobs/SOPHIA-JOB-ID
```

A successful receipt states:

```text
C10_LONGITUDINAL_PROOF_PASSED
```

Anything else remains:

```text
C10_LONGITUDINAL_PROOF_NOT_YET_ESTABLISHED
```

The receipt is written under:

```text
state/sophia_jobs/SOPHIA-JOB-ID/C10_LONGITUDINAL_SPECULUM/
```

as `C10_LIVE_PROOF_RECEIPT.json` and `C10_LIVE_PROOF_RECEIPT.md`.

## Proof Tier 2: C10 stress proof

The stress proof deliberately refuses a tame demonstration in which two drafts differ only cosmetically.

In addition to the Tier 1 live proof, the case must exercise at least two meaningful longitudinal change classes and at least one human interpretive event.

Recognised change classes include:

- support state movement;
- epistemic-burden mutation;
- a split/merge/material topology question;
- a human-resolved topology question;
- ambiguous lineage requiring human resolution; and
- claim reintroduction after absence.

The case must also contain at least two explicit human scholarly decisions and finish with a zero blocking decision queue.

### Recommended adversarial manuscript revision

Do not engineer the manuscript merely to make Sophia pass. Use a real academic section where possible. If a controlled demonstration is needed first, include several genuinely different revision phenomena:

- retain one substantive claim but strengthen its evidence;
- narrow one causal claim to an associational claim because the source cannot carry causality;
- split one composite scholarly proposition into two claims;
- change one number or percentage and verify why;
- intentionally remove one unsupported high-risk claim and record that author decision;
- introduce one genuinely new high-risk claim and make the author decide how it will be handled;
- include one paraphrase ambiguous enough that Sophia must ask whether it is continuity or a new claim; and
- verify at least one candidate source against the full publication.

The goal is not to manufacture failures. The goal is to force the system to confront different forms of scholarly change.

## Human validation is mandatory for the stress proof

C10 does not get to validate itself.

After the live case is complete, a human academic reviewer samples Sophia's output and records:

- number of claims checked;
- number of claim-to-source mappings judged correct;
- number of review flags inspected;
- false-positive flags;
- full-source verifications completed;
- topology questions reviewed;
- topology questions found useful;
- material issues the human believes Sophia missed;
- decisions Sophia materially helped the reviewer or author make;
- whether the authorship boundary was respected; and
- whether the reviewer would use the workflow again.

The current controlled validation gate requires:

- at least 5 claims manually checked;
- claim-to-source mapping accuracy of at least 0.80 in that sample;
- review false-positive rate no greater than 0.20;
- at least one source verified against its full publication;
- zero material issues known to have been missed in the reviewed sample;
- preserved authorship boundary;
- at least one material decision helped; and
- if topology questions were present, at least 0.60 of reviewed topology questions judged useful.

These thresholds are engineering pilot gates, not published psychometric properties or universal accuracy estimates.

Record the validation sample:

```bash
python scripts/record_sophia_c10_human_validation.py \
  --job-dir state/sophia_jobs/SOPHIA-JOB-ID \
  --reviewer-alias "Reviewer A" \
  --reviewer-role supervisor \
  --claims-checked 10 \
  --support-mappings-correct 9 \
  --review-flags-checked 10 \
  --false-positive-flags 1 \
  --source-verifications-completed 3 \
  --topology-questions-reviewed 2 \
  --topology-questions-useful 2 \
  --missed-material-issues 0 \
  --decisions-materially-helped 3 \
  --authorship-boundary-respected yes \
  --would-use-again yes \
  --notes "Short human evaluation note."
```

If the reviewer was genuinely independent of the build, add:

```text
--independent-of-build
```

Do not set that flag for Byron or another person materially involved in constructing the workflow merely to make the receipt look stronger.

The validation output is written as:

- `C10_HUMAN_VALIDATION.json`
- `C10_HUMAN_VALIDATION.md`

## Run the final stress proof

After the base live proof and human validation receipt exist:

```bash
python scripts/prove_sophia_c10_stress.py \
  --job-dir state/sophia_jobs/SOPHIA-JOB-ID
```

The stress proof requires:

- Tier 1 proof passed;
- human validation passed;
- at least two meaningful change classes;
- at least one human interpretive event;
- at least two explicit author decisions;
- zero blocking scholarly decision obligations;
- topology, decision-queue and human-validation hashes present.

A successful result states:

```text
C10_STRESS_PROOF_PASSED
```

Otherwise it remains:

```text
C10_STRESS_PROOF_NOT_YET_ESTABLISHED
```

## Full Valinor sequence

### 1. Initial review

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py run SOPHIA-JOB-ID
```

Inspect the initial C9/C10 pack. The initial diagnostic pack may contain open scholarly decision obligations because its purpose is to show the author what requires attention.

### 2. Human review and initial delivery

Once the initial pack is grounded and its lineage is coherent:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py approve SOPHIA-JOB-ID \
  --reviewer "Reviewer name"
```

Use the existing governed delivery path for the initial pack.

### 3. Author-owned revision

The human author revises the manuscript in their own words and makes their own source and argument decisions.

Run the revision:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py revision SOPHIA-JOB-ID \
  --document /path/to/revised_section.docx
```

### 4. Inspect the living Speculum

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py export SOPHIA-JOB-ID
```

Also inspect:

- `LONGITUDINAL_SPECULUM.md`
- `SUPERVISOR_SPECULUM.html`
- `SCHOLARLY_TOPOLOGY_AUDIT.md`
- `SCHOLARLY_DECISION_QUEUE.md`
- `SUPERVISOR_COMMAND_BRIEF.html`

### 5. Resolve ambiguous claim continuity

If a paraphrase is a continuity candidate:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py resolve-lineage SOPHIA-JOB-ID \
  --lineage provisional-lineage-id \
  --accept-parent \
  --actor "Human reviewer" \
  --rationale "Why this is genuinely the same scholarly commitment."
```

Or use `--confirm-new` if it is genuinely a new claim.

### 6. Record author decisions

For material claim decisions:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py record-decision SOPHIA-JOB-ID \
  --lineage lineage-id \
  --decision narrow \
  --actor "Author" \
  --rationale "The available evidence supports association but not causation."
```

Other valid author decisions are documented by the C10 operator and include retaining with limitation, strengthening evidence, removing, deferring or disputing a claim.

### 7. Resolve scholarly topology questions

For a split, merge or material claim-surface change:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py record-topology-decision SOPHIA-JOB-ID \
  --issue TI-... \
  --decision confirm_split \
  --actor "Human reviewer" \
  --rationale "The composite proposition was intentionally separated into two independently supportable claims."
```

A `defer` or `needs_revision` action is recorded but does not close the obligation. A later resolving decision is required before revision release.

### 8. Approve the revised pack

The revised pack is fail-closed until both lineage and the scholarly decision queue are clear:

```bash
python scripts/run_sophia_longitudinal_speculum_c10.py approve-revision SOPHIA-JOB-ID \
  --round 1 \
  --reviewer "Reviewer name"
```

### 9. Run Tier 1 proof

```bash
python scripts/prove_sophia_c10_live.py \
  --job-dir state/sophia_jobs/SOPHIA-JOB-ID
```

### 10. Record human validation

Use `record_sophia_c10_human_validation.py` with the actual observed counts. Never improve the numbers merely to clear the gate.

### 11. Run Tier 2 stress proof

```bash
python scripts/prove_sophia_c10_stress.py \
  --job-dir state/sophia_jobs/SOPHIA-JOB-ID
```

## Public-release rule

`SOPHIA_PROJECT_SPECULUM` remains `proof_ready_not_public` until the stress proof has passed on a real case.

Even after a first pass, public claims should remain bounded to what the receipt establishes. A single strong case is evidence of system behavior, not a universal benchmark.

## Authority boundary

C10 tracks visible scholarly change and asks humans to own material decisions. It does not infer plagiarism, AI authorship, fabrication, misconduct, factual truth or author intent from similarity alone.

The principle remains:

> Sophia records the trail. Humans retain scholarly authority.
