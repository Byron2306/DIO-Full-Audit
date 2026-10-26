# DIO ATLAS — Derived Portfolio Surface

**Status:** M4 foundation candidate, not final verification  
**Canonical branch:** `agent/dio-atlas-m4-universal-pivot`

## The 53-row distinction

The 53 rows in `config/atlas/dio_meta_incarnation_crosswalk.csv` are the preserved historical DIO META portfolio. They are not the ATLAS candidate universe.

ATLAS therefore maintains two different registries:

```text
LEGACY PORTFOLIO CROSSWALK
53 historically enumerated incarnations
preserved exactly for lineage and compatibility

DERIVED ATLAS CANDIDATE REGISTRY
N deterministic candidate incarnations
compiled from domain nodes × reusable job morphologies × verified capability signatures
N is not fixed to 53 and must exceed the legacy portfolio by construction
```

The distinction is constitutional:

- legacy portfolio knowledge does not become execution truth merely because it exists in the old spreadsheet;
- a derived candidate does not become a product merely because ATLAS can describe it;
- similarity does not create capability;
- a mechanically composable candidate does not imply market demand;
- no candidate can widen authority or execute an external effect.

## Candidate compiler

`atlas/incarnations.py` compiles the candidate surface from three truth layers:

1. **ATLAS domains** — broad source-bound human-work nodes from `dio_atlas_universal_domain_registry.csv`;
2. **job morphologies** — reusable buyer-job/task shapes from `dio_atlas_job_morphologies.csv`;
3. **execution-bound capability signatures** — only the M1-earned capability identities projected in `dio_atlas_capability_signatures.csv`.

The compiler does not perform a blind Cartesian product. Each job morphology declares the domain families in which the job shape is plausible. Two deliberately universal controlled-artifact morphologies guarantee that every non-root ATLAS domain node can still be interrogated for mechanical transfer without claiming domain expertise.

The foundation constitution requires:

```text
legacy portfolio rows                    = 53 exactly
job-morphology templates                 >= 20
derived candidate incarnations           >= 500
derived ATLAS domain coverage            = 100%
execution-grade M1 capability signatures = 4 exactly
```

The exact derived count is a deterministic result of the current domain registry and morphology templates. It is intentionally not hard-coded to a vanity number.

## Candidate states

Each generated row is one of:

```text
COMPOSABLE_CANDIDATE
    all required generic mechanics are currently covered by execution-corroborated signatures;
    still UNPROVED as a new product and UNTESTED commercially.

PARTIALLY_COMPOSABLE_CANDIDATE
    meaningful mechanical overlap exists but explicit primitive, specialist, profile, or validation gaps remain.

CAPABILITY_GAP
    the target morphology is known but current execution-grade capability coverage is insufficient.
```

All three remain `ANALOGICAL_CANDIDATE` relation state until separately governed.

## What each candidate records

The generated CSV contains:

- deterministic candidate ID and digest;
- domain ID/name/family/type;
- job-morphology template and buyer job;
- required work patterns;
- required, covered, and missing task primitives;
- verified DIO capability identities contributing mechanical coverage;
- required and missing specialist capabilities;
- primitive-coverage ratio;
- mechanical verdict and candidate state;
- input and output artifact classes;
- professional-authority and safety flags;
- authority ceiling and external-effect intent;
- Build Burden and Validation Burden estimates;
- first-class Capability Cost and its explicit planning-estimate basis;
- legacy-portfolio analogies, if any;
- execution truth = `UNPROVED_CANDIDATE`;
- commercial truth = `UNTESTED`;
- market demand = false;
- capability created = false;
- authority created/widened = false;
- external effects/execution = false.

## Capability Cost

For generated candidates, Capability Cost is a planning proxy rather than observed financial cost.

It combines:

- morphology base build burden;
- uncovered primitive burden;
- missing specialist-capability burden;
- domain safety criticality;
- professional-authority/validation burden.

Every row therefore carries:

```text
capability_cost_basis = ATLAS_PLANNING_ESTIMATE_NOT_OBSERVED_COST
```

Observed engineering time, money, compute, validation cost, or commercial proof cost must be added later as separately sourced evidence.

## Negative-learning pivot over the vast surface

M2-8 already produces context-bound negative-learning records. `rank_candidate_incarnations_from_negative_learning()` now uses those records as the trigger for a search over the entire generated ATLAS candidate surface.

The Funding Proposal reference task is reduced to its work morphology, then every derived candidate is ranked by:

```text
primitive similarity
+ work-pattern similarity
+ artifact similarity
+ current verified primitive coverage
- specialist-capability gaps
```

There is no same-industry bonus and no product-name bonus.

The pivot proof selects 25 held candidates while enforcing cross-family diversity. It excludes the source Funding/Grant domain so that "pivot" cannot simply mean renaming the original product.

Every selected result remains:

```text
relation_state             = ANALOGICAL_CANDIDATE
market_demand_claimed      = false
capability_created         = false
authority_created          = false
external_effects           = false
execution_performed        = false
direct_learning_to_execution = false
```

## Materialized registry

The deterministic CSV can be produced locally with:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/compile_atlas_candidate_registry.py
```

Default output:

```text
state/atlas/dio_atlas_candidate_incarnations.csv
```

This file is a generated semantic opportunity surface, not an execution registry.

## Why this matters

Before this layer, DIO could preserve the old 53-row product portfolio and reason about a small hand-picked pivot gauntlet.

After this layer, the old 53 becomes what it should have been all along: **historical seeds**.

ATLAS can derive a much larger candidate landscape from the mechanics DIO has actually earned, identify which distant jobs are mechanically reachable, expose the gaps where they are not, and let M2 negative learning redirect search through that landscape without manufacturing evidence or authority.

> The registry is no longer a list of products someone thought of. It is a governed generator of places the organism might become useful next.
