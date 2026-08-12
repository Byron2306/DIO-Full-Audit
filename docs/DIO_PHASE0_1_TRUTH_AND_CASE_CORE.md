# DIO Portfolio Convergence: Phase 0 + Phase 1

Date: 2026-08-11  
Status: implementation wave, validation required before merge

## Executive decision

The new DIO product portfolio must not be built on an audit snapshot that is older than the systems it claims to represent.

Phase 0 therefore establishes **cross-system source truth** before stronger convergence claims are made. Phase 1 then establishes **one governed case grammar** for every evidence, requirement, assurance, procurement, research, agent-authority and investor workflow.

The ordering is deliberate:

```text
source truth
    ↓
reproducible system snapshot
    ↓
canonical governed case
    ↓
frameworks / claims / evidence / challenges / deadlines
    ↓
authority gates
    ↓
actions
    ↓
receipts
```

No product executor is created by these phases.

---

# Phase 0: Snapshot convergence and truth reset

## Problem

The `DIO-Full-Audit` main branch is an August 9 convergence snapshot. Several systems have newer known local work.

In particular:

- the published `Integritas-Mechanicus` main head is pinned at `cdecaa3009021e819ad787ce18305967eafa4b83` from August 3;
- the Sophia Production Wave 2 Valinor gauntlet observed on August 11 is therefore newer local production evidence, not evidence contained in that published head;
- DIO Legalis Wave 1 is known as current local work but no authoritative GitHub repository or local path has yet been resolved in this audit;
- the Hivenance Phoenix Phase 7.1 material used by DIO is newer than the published `Hivenance` main head;
- older published ARDA and Seraph heads must not be silently treated as proof of later local convergence work.

Phase 0 converts those facts into typed state instead of prose caveats.

## Source registry

`config/dio_system_sources.json`

Each system receives:

- a stable source ID;
- system role;
- published GitHub repository/ref/SHA when available;
- observed publication time;
- local path hints when known;
- a capture policy;
- explicit source state;
- optional evidence markers that should be visible in the local repository.

Capture policies distinguish:

- `published_reference_only`;
- `published_plus_local_if_newer`;
- `local_required_when_newer`;
- `source_path_required`;
- `self_dynamic`.

## Read-only capture

Run:

```bash
python3 scripts/capture_system_snapshot.py
```

When a source path is unresolved, supply it explicitly rather than teaching the audit to guess:

```bash
python3 scripts/capture_system_snapshot.py \
  --source dio_legalis=/ACTUAL/PATH/TO/LEGALIS
```

For a hard acceptance gate:

```bash
python3 scripts/capture_system_snapshot.py \
  --source dio_legalis=/ACTUAL/PATH/TO/LEGALIS \
  --require-ready
```

The script is read-only with respect to source repositories. It records:

- local git HEAD;
- branch;
- origin;
- clean/dirty state;
- content hashes for dirty files;
- a deterministic dirty-tree fingerprint;
- whether local HEAD equals the published pin;
- expected marker presence;
- source claim authority;
- blockers.

Output defaults to:

```text
state/system_snapshots/latest.json
```

The snapshot itself receives a SHA-256 over its canonical payload.

## Phase 0 states

### READY

Every source whose policy requires local capture has been resolved and fingerprinted.

### NEEDS_LOCAL_CAPTURE

No hard required source is missing, but one or more useful local sources remain unresolved.

### BLOCKED

A source required for an implementation claim is unresolved or failed capture.

The initial expected state is **BLOCKED until DIO Legalis is resolved**, because the product architecture now cites Legalis as a shared organ in Assurance, VendorProof, TenderProof and RegOps.

That is intentional.

## Phase 0 acceptance gate

Phase 0 passes only when:

1. the source registry contains every system used by current product claims;
2. all known newer local work is captured with git/worktree identity;
3. Legalis has an authoritative source path and capture receipt;
4. Sophia Wave 2 artifacts are present in the captured local Integritas state or a newer published commit;
5. dirty sources are fingerprinted rather than silently treated as published commits;
6. snapshot schema validation passes;
7. the resulting snapshot state is `READY`.

A READY snapshot does not mean every DIO organ is production-ready. It means the audit knows **what exact source state it is talking about**.

---

# Phase 1: Governed Case Core v2

## Design principle

A DIO case is the universal unit of consequential work.

A tender, AI assurance review, accreditation criterion, grant obligation, vendor questionnaire, research claim or agent action should not require a new evidence/governance skeleton.

They should be domain profiles over the same semantic object.

## Canonical case

Schema:

```text
schemas/dio_governed_case_v2.schema.json
```

Runtime:

```text
products/governed_case.py
```

New product jobs now bind to:

```text
state/product_jobs/<JOB-ID>/JOB.json
state/product_jobs/<JOB-ID>/CASE.json
```

`CASE.json` is now `dio.governed_case.v2`.

## Case anatomy

```text
scope
  frameworks
  jurisdictions
  subject
  world state

lineage
  campaign
  lead
  conversation
  job
  transaction
  parent/revision case

actors
  identity
  role
  authority scope

requirements
  framework/control/contract/obligation/policy/request
  dependencies
  owner
  due/expiry state

claims
  stable epistemic lineage
  deterministic fingerprint
  parent revision
  UNVERIFIED / SUPPORTED / CONTESTED / REFUTED

evidence
  provenance
  hash
  authority grade
  trust state
  freshness/expiry
  supports / contradicts links

challenges
  contradiction
  missing evidence
  staleness
  authority
  scope
  alternative hypothesis
  duplication
  world-state mismatch

exceptions
  bounded waiver/exception lifecycle

deadlines
  submission
  renewal
  review
  expiry
  response

gates
  ALLOW
  REFUSE
  NEEDS_YOU
  NEEDS_EVIDENCE

actions
  risk tier
  reversibility
  required gates
  capability lease
  execution receipt

decisions
  explicit actor
  verdict
  evidence references
  reasoning summary

outputs
  planned → generated → reviewed → approved → released
```

## The most important separation

DIO now distinguishes **epistemic support** from **institutional authority**.

Evidence may make a claim `SUPPORTED`.

Evidence may make a requirement `supported`.

Neither fact automatically grants authority to execute, submit, certify, approve, pay, publish or release anything.

That authority remains in gates and decisions.

This prevents a dangerous collapse:

```text
model believes requirement is satisfied
        ≠
human/authority has declared requirement satisfied
        ≠
external action is authorised
```

## Claim lineage

A revised claim receives:

- a new claim record;
- a new deterministic fingerprint;
- a parent claim ID;
- the same epistemic lineage ID.

The old state remains historically meaningful.

This mirrors the production Sophia principle already demonstrated in later local work and generalises it across every DIO product.

## Evidence truth

Evidence has independent dimensions:

### Authority grade

- `self_asserted`
- `source_backed`
- `independent`
- `authoritative`

### Trust state

- `captured_untrusted`
- `trusted_for_review`
- `quarantined`
- `rejected`

### Freshness

- `unknown`
- `current`
- `stale`
- `expired`

A gate cannot be `ALLOW` when its required evidence is untrusted, stale or expired.

A `SUPPORTED` claim must retain at least one current trusted supporting evidence item.

When that evidence expires, the support disappears rather than becoming immortal historical truth.

## Challenge lifecycle

Challenges are first-class records rather than comments.

A material or blocking open challenge against a claim moves it to `CONTESTED`.

A resolved/dismissed challenge allows the epistemic state to be recomputed from current evidence.

This gives Seraph/Loki-style dissent a product-neutral home.

## Execution boundary

The generic product platform still contains:

```text
generic_executor = REFUSE
external_release = NEEDS_YOU
```

A registered product can therefore:

- accept and classify intake;
- create a canonical case;
- model requirements;
- attach evidence;
- maintain claim lineage;
- raise challenges;
- track deadlines;
- prepare decisions and actions.

It cannot claim that a product-specific executor exists.

## v1 migration

`products/case_migration.py` migrates scaffold-only `dio.governed_case.v1` cases.

Migration is deliberately loss-aware.

It refuses automatic migration if the old scaffold unexpectedly contains:

- claims;
- decisions;
- progressed/released outputs.

Those cases require human review instead of lossy flattening.

For ordinary scaffold-only cases it preserves:

- deterministic case identity;
- lineage;
- source-evidence trust/freshness;
- gate states;
- scaffold requirement state.

A `CASE_MIGRATION.json` receipt is written beside the migrated case.

## Phase 1 acceptance gate

Phase 1 passes when:

1. all new portfolio workflows create valid `dio.governed_case.v2` cases;
2. scaffold v1 migration is idempotent and loss-aware;
3. claim revision preserves lineage but creates a new fingerprint and record;
4. trusted current evidence can move `UNVERIFIED → SUPPORTED`;
5. material challenge can move `SUPPORTED → CONTESTED`;
6. challenge resolution recomputes support correctly;
7. evidence expiry can remove support;
8. untrusted/stale evidence cannot authorise a gate;
9. generic executor refusal continues to block product execution;
10. external release remains explicit authority;
11. the new Phase 0 and Phase 1 tests pass in CI/local validation.

## What Phase 1 deliberately does not do

It does not yet implement:

- framework importers;
- legal interpretation;
- autonomous requirement satisfaction;
- product-specific executors;
- generic external action execution;
- automatic waivers;
- autonomous institutional sign-off.

Those belong to later phases.

---

# Result

After Phase 0 and Phase 1, DIO should be able to say two much stronger things:

1. **We know exactly which source state each system claim refers to.**
2. **Every new product can express consequential work through the same evidence, challenge, authority and lineage object.**

That is the foundation required before the Framework Engine in Phase 2.
