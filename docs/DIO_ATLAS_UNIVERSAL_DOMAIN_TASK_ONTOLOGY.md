# DIO ATLAS — Universal Domain & Task Ontology

**Status:** M4 foundation candidate  
**Branch:** `agent/dio-atlas-m4-universal-pivot`  
**Purpose:** give DIO a source-bound map of human work so that metamorphic and commercial learning can generate governed cross-domain pivot hypotheses without inventing capabilities, evidence, market truth, or authority.

## 1. Why ATLAS exists

M1 proved that DIO can preserve identity while composing existing capabilities into a new metamorphic unit. M2 proved that DIO can observe commercial outcomes, settle evidence, crystallise market truth, and produce held projection-adaptation candidates without overclaiming commercial success.

Those proofs create a new question:

> If a commercial context weakens, where can the organism look next?

The execution-grade Metamorphic Registry answers **what DIO has earned the right to execute**. It does not answer **what kinds of work exist in the world**, **which tasks are mechanically similar across domains**, or **which adjacent jobs may be candidates for a governed pivot**.

DIO ATLAS is that second layer.

ATLAS is not a product registry and is not an authority registry. It is a source-bound semantic map of domains, actors, jobs, work patterns, task primitives, artifacts, constraints, and relationships.

## 2. Constitutional separation

The existing Metamorphic Registry remains the execution-truth registry.

```text
DIO ATLAS                         METAMORPHIC REGISTRY
what work exists                 what DIO has proved it can do
what resembles what              exact executable capability identities
source/crosswalk knowledge       executor/evidence/quality contracts
analogical candidates            earned capability truth
        |                                  |
        +--------------+-------------------+
                       |
                       v
                ANALOGICAL RESOLVER
                       |
          COMPOSABLE / PARTIALLY_COMPOSABLE /
                    UNSUPPORTED
```

The following laws are frozen for ATLAS:

1. `knowledge_never_implies_capability`
2. `similarity_never_implies_equivalence`
3. `analogy_never_implies_evidence`
4. `domain_adjacency_never_implies_market_demand`
5. `task_match_never_implies_execution_proof`
6. `taxonomy_membership_never_mints_authority`
7. `commercial_negative_learning_never_globally_invalidates_a_product`
8. `negative_learning_may_generate_a_pivot_hypothesis_but_never_execute_it`
9. `verified_capability_identity_must_be_preserved_across_domain_projection`
10. `capability_gaps_must_remain_explicit`
11. `external_taxonomy_nodes_are_knowledge_only_until_separately_proved`
12. `all_cross_domain_relations_require_provenance_and_relation_state`
13. `human_or_governed_review_is_required_before_analogical_candidates_become_semantic_policy`
14. `authority_ceiling_cannot_widen_during_pivot`
15. `commercial_truth_remains_context_bound`
16. `unknown_domain_names_must_not_block_task_morphology_reasoning`

## 3. Mapping to the existing DIO META Portfolio Atlas

The existing portfolio workbook defines:

```text
DIO organism
  × META primitives
  × reusable work patterns
  × profile libraries
  × commercial incarnations
```

and the product equation:

```text
DIO Product =
    Work Pattern
  × META Composition
  × Domain Profile
  × Framework Profile
  × Authority Profile
  × Connector Pack
  × Output Profile
  × Commercial Policy
```

ATLAS does not replace that architecture. It expands the **semantic search space beneath and around it**.

The canonical twelve existing DIO META work patterns remain:

- WP01 Evidence work
- WP02 Integrity work
- WP03 Achievement work
- WP04 Quality work
- WP05 Obligation work
- WP06 Assessment work
- WP07 Assurance work
- WP08 Intake work
- WP09 Authority work
- WP10 Document work
- WP11 Proof work
- WP12 Market work

The portfolio workbook also uses the label `Learning` in several incarnation rows even though `Learning` is not one of the twelve canonical patterns. ATLAS records this as **WP13 Learning work — CANDIDATE_EXTENSION**, not as silently established canon.

Every portfolio incarnation is crosswalked in `config/atlas/dio_meta_incarnation_crosswalk.csv`. `Capability Cost` is first-class and is derived from the original Build Burden and Validation Burden while preserving both source values.

## 4. The six orthogonal ATLAS axes

Every ATLAS job or domain node may be described independently across six axes.

| Axis | Question |
|---|---|
| Domain | Where does this work occur? |
| Actor | Who performs, owns, reviews, or buys it? |
| Job / outcome | What is the actor trying to accomplish? |
| Work morphology | Which reusable work patterns and task primitives constitute the job? |
| Artifact | What information/object is consumed, transformed, and produced? |
| Constraint | Which evidence, safety, legal, quality, privacy, freshness, and authority conditions govern it? |

This separation is necessary because two remote domains can share the same work morphology while using completely different vocabulary.

## 5. Universal work primitives

`config/atlas/dio_atlas_work_primitives.csv` defines domain-independent task primitives such as:

```text
extract requirements
map evidence
assess sufficiency
reconcile
calculate
detect contradiction
detect drift
track obligation
assess eligibility
synthesise narrative
assemble dossier
generate correspondence
observe response
attribute outcome
settle truth
learn/update
authorise bounded action
preserve receipt
package proof
crosswalk taxonomy
resolve similarity
plan composition
```

A work pattern is therefore a reusable grammar over primitives rather than a domain name.

## 6. Source federation, not synthetic omniscience

No static CSV can truthfully claim to contain every future field of human knowledge. ATLAS therefore defines a **federation envelope** over authoritative classification families and keeps source/version/provenance explicit.

The initial federation registry is `config/atlas/dio_atlas_source_federation.csv` and includes:

- United Nations ISIC Rev. 5 — economic activities
- United Nations CPC Ver. 3.0 — goods and services
- ILO ISCO-08 — occupations defined by tasks and duties
- European Commission ESCO v1.2.1 — occupations, skills, knowledge, and relationships
- UNESCO ISCED-F 2013 — fields of education and training
- OECD Frascati / FORD — fields of research and development
- WIPO IPC 2026.01 — technology fields
- WHO ICD-11 — health and disease classification surface
- FAO AGROVOC — agriculture and food controlled vocabulary
- UN COFOG — functions of government
- DIO META Portfolio Atlas — DIO-local product/work/profile vocabulary

The source states are deliberately different from capability states. A source can be `REFERENCED_NOT_INGESTED`, `PINNED_REFERENCE`, or later `INGESTED_VERSIONED`. Ingestion alone never creates a DIO capability.

## 7. Relation states

ATLAS relations are typed and stateful:

| State | Meaning |
|---|---|
| SOURCE_ASSERTED | Relationship is asserted by a pinned external or DIO source. |
| CROSSWALKED | Deterministic mapping exists between source vocabularies. |
| DIO_DERIVED | Relationship follows from a deterministic DIO rule. |
| ANALOGICAL_CANDIDATE | Similarity is plausible but not yet verified as equivalent or executable. |
| HUMAN_APPROVED | A human has accepted the semantic relationship for bounded use. |
| EXECUTION_CORROBORATED | A controlled DIO composition executed and settled successfully. |
| MARKET_CORROBORATED | Real source-bound commercial evidence supports the relationship in the exact commercial context. |

No transition in this table creates authority.

## 8. Capability signatures

Every **verified** DIO capability can be projected into ATLAS as a mechanical signature without changing its Metamorphic Registry identity.

A capability signature records:

- exact registry capability ID and unit digest
- verbs / transformations
- input artifact classes
- output artifact classes
- primitive IDs
- work-pattern IDs
- evidence modes
- quality requirements
- authority ceiling
- source proof / receipt identity
- current execution truth class

The first execution-grade signatures are deliberately small:

- `professional_correspondence`
- `finance_readiness`
- `article_publication`
- `funding_proposal_pack`

The fourth is the M1 composite and requires the first three. ATLAS may use the portfolio's other 53 incarnations as semantic/product hypotheses, but they must not be laundered into M1 execution-grade capability truth.

## 9. Capability Cost

The older portfolio atlas already carries Build Burden and Validation Burden. ATLAS adds the requested `Capability Cost` explicitly.

For the initial deterministic crosswalk:

```text
capability_cost_score = (build_burden + validation_burden) / 2

< 1.5       LOW
< 2.5       LOW_MEDIUM
< 3.5       MEDIUM
< 4.5       HIGH
otherwise   VERY_HIGH
```

This is a planning cost proxy, not an observed financial cost and not an ROI claim.

Later ATLAS phases may add evidence-bound observed engineering time, validation effort, compute, connector burden, legal/professional validation burden, and commercial proof cost as separately typed measurements.

## 10. Pivot hypothesis

A market-learning event may generate a `PivotHypothesis` only after its commercial truth is settled and scoped.

```text
negative / weak commercial context
        |
        v
identify failed dimension
buyer / offer / price / channel / job / domain
        |
        v
preserve verified mechanical capability signature
        |
        v
search ATLAS by work morphology
        |
        v
exclude failed context neighbourhood
        |
        v
rank remote domain/jobs by primitive compatibility
        |
        v
COMPOSABLE / PARTIALLY_COMPOSABLE / UNSUPPORTED
        |
        v
held pivot hypothesis
```

A pivot hypothesis records:

- source market-crystal / negative-learning evidence
- exact failed commercial context
- preserved capability signatures
- target domain/job
- work-pattern overlap
- primitive overlap
- missing primitives
- artifact compatibility
- constraint/authority mismatches
- capability cost
- analogy state
- execution truth state
- commercial truth state

It cannot publish, spend, send, purchase, deploy, deliver, promote a capability, or claim market demand.

## 11. Analogical resolver output states

ATLAS permits only three top-level mechanical verdicts:

### COMPOSABLE
All required primitives for the target job are covered by execution-corroborated capability signatures and the authority intersection remains valid.

### PARTIALLY_COMPOSABLE
Some verified mechanisms fit, but one or more required primitives, artifacts, constraints, or authority conditions remain explicit gaps.

### UNSUPPORTED
The verified DIO capability set does not provide enough mechanical coverage to justify a candidate composition.

These are mechanical compatibility states. They are not product-market-fit states.

## 12. Unknown-domain proof

ATLAS must pass a proof in which the domain label has no registered meaning.

Example input:

```text
domain = "ZXQ-unknown-field"
job = ingest structured and unstructured evidence; compare it against a rule set;
      identify gaps and contradictions; produce an evidence-bound narrative and
      formal response pack.
```

The resolver must reason from the task morphology, not the meaningless domain label. It must identify compatible verified primitives, explicit gaps, and a bounded analogy state.

A successful unknown-domain test proves **morphological transfer**, not universal domain expertise.

## 13. False-analogy adversary

ATLAS must also reject seductive similarities.

Examples:

- `medical diagnosis` and `quality gap assessment` both compare observations to criteria, but diagnosis requires medical knowledge, clinical evidence, safety rules, and professional authority not supplied by generic evidence mapping.
- `legal adjudication` and `policy compliance mapping` both reason over rules and evidence, but adjudication carries legal authority and professional constraints that a generic DIO evidence capability does not possess.
- `aircraft maintenance release` and `document QA` both involve checklists and sign-off, but release-to-service authority and safety evidence are non-transferable.

Domain-name similarity or primitive overlap can therefore produce `PARTIALLY_COMPOSABLE` or `UNSUPPORTED`, never automatic equivalence.

## 14. M4 programme

M1 and M2 remain frozen verified properties. M3 remains reserved for literal substantive content lineage. ATLAS is the proposed M4 programme:

| Phase | Purpose |
|---|---|
| M4-0 | Atlas Constitution + DIO META crosswalk |
| M4-1 | Federated Human-Domain Atlas |
| M4-2 | Universal Work-Pattern Vocabulary |
| M4-3 | Artifact & Transformation Ontology |
| M4-4 | DIO Capability Signature Projection |
| M4-5 | Analogical Resolver |
| M4-6 | Negative-Learning Pivot Compiler |
| M4-7 | Cross-Domain Fusion Gauntlet |
| M4-8 | False-Analogy Adversary |
| M4-9 | Universal Pivot Verification |

Proposed final M4 token:

```text
DIO_ATLAS_UNIVERSAL_PIVOT_VERIFIED
```

That token may mean only:

> DIO can search a broad, source-bound map of human work and generate mechanically justified cross-domain pivot hypotheses from verified capabilities while preserving explicit gaps, evidence boundaries, world state, and authority.

It must never mean:

> DIO knows every fact in every domain, is professionally competent in every field, or may autonomously act in every domain.

## 15. Central sentence

> **ATLAS gives DIO an imagination without giving it delusions.**

The Metamorphic Registry remains the ledger of what DIO has earned. ATLAS becomes the map of where those earned mechanisms might fit next.