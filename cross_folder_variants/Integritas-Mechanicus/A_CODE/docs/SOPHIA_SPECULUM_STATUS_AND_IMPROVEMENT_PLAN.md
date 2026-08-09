# Sophia Speculum Status And Improvement Plan

Date: 2026-07-30
Repository: `/home/byron/Integritas-Mechanicus`
Related evidence root: `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence`

## Mandate

Sophia's mandate as `Speculum` is not to be an answer engine. She is the inspectable pedagogical mirror of Integritas Mechanicus:

- witness honestly without flattery
- declare artificial limits without counterfeit memory, feeling, or personhood
- preserve human authorship
- distinguish source-grounded claim, inference, simulation, and unknown
- mediate learning instead of substituting for the learner
- sense covenant/harmonic strain as a pacing and integrity signal, not as human emotion
- route help through Arda's constitutional, attestation, policy, retrieval, ZPD, and assessment ecology layers
- assess herself ipsatively: better than her prior self, not better than another model

The governing phrase is: `Probatio ante laudem. Recusatio ante mendacium. Veritas ante vanitatem.`

## Evidence Pulled

Primary local files reviewed:

- `/home/byron/Integritas-Mechanicus/SOPHIA_VOX.md`
- `/home/byron/Integritas-Mechanicus/TESTIS_VISUAE_SOPHIA_COMET_20260330.md`
- `/home/byron/Integritas-Mechanicus/docs/ARDA_PHASED_IMPROVEMENT_PLAN.md`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/presence_server.py`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/zpd_shaper.py`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/diagnostic_classifier.py`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/assessment_ecology.py`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/ipsative_ledger.py`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/sophia_curriculum_gate.py`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/harmonic_engine.py`
- `/home/byron/Integritas-Mechanicus/arda_os/backend/services/The_Sovereign_Pedagogy_of_Arda_OS_Academic_Reframing_v2-1.pdf`

Primary external evidence reviewed:

- `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/SOPHIA_SOVEREIGN_V5_ARCHITECTURE.md`
- `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/GRAND_SOPHIA_PRESENCE_VAULT.md`
- `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/sophia_struggle_proof_bundle/SOPHIA_STRUGGLE_PROOF.md`
- `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/protocol_v1_1_landmark_claim_sheet_2026-04-08.md`
- `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/protocol_v1_2_frozen_results_summary_2026-04-09.md`
- `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/protocol_v1_2_causal_matrix_2026-04-09.md`
- `/home/byron/Downloads/Metatron-triune-outbound-gate/docs/sophia-style-sheet.md`
- `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/sophia_full/qwen2_5_3b/*.json`

## Current Status

### Proven By Frozen Evidence

- Protocol v1.1 has a frozen `sophia_full` qwen2.5:3b 21-row pass covering multimodal grounding, anti-substitution, continuity, lawful reentry, and transfer scaffolding.
- Protocol v1.2 mainline initially failed badly, then reached a frozen postfix 17/17 pass.
- v1.2 mutation and cross-domain work exposed real fragility, especially `OR1A`, `MX`, and delayed/mixed intent surfaces.
- v1.2 semantic closure eventually repaired evaluator defects and closed the hardest `OR1A_HEALTH` and `OR1A_SAFETY` lanes under corrected semantic judgment.
- The older struggle proof demonstrated substrate-attested struggle logging, but also showed non-monotonic struggle calibration: Q1 0.150, Q2 0.000, Q3 0.128. That is evidence of instrumentation, not yet evidence of mature metacognitive self-assessment.

### True In The Current Live Runtime

- Presence server launches from the intended UI directory: `/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/Presence UI`.
- Covenant state restores as sealed.
- Ollama is connected; current fast test model was qwen2.5:0.5b, while the stronger validated protocol line used qwen2.5:3b.
- The constitutional release path currently returns `LAWFUL` on tested pedagogy prompts.
- The diagnostic classifier detects knowledge gaps, reflective strain, covenant conflict, and educational domains.
- ZPD shaping now detects explicit educational lenses:
  - Feuerstein mediated learning
  - Costa/Kallick habits of mind
  - de Bono six hats
  - Pavlovian conditioned dissonance
  - Skinner reinforcement
  - Bandura observational learning
  - Knowles andragogy
  - Mezirow transformative reflection
  - Facione critical thinking
  - Torrance creative thinking
- Office routing now requests `mediator`, `lateralis`, `dialecticus`, `poietes`, `pragmaticus`, or `philosophus` when the prompt calls for those pedagogical roles.
- Curriculum gating transparently reports requested office, permitted office, curriculum stage, and gate reason in response telemetry.
- Because there is no active Sophia calibration snapshot, the live gate currently defaults to Stage 1: Constitutional Compliance. Higher offices are detected but routed back to `speculum`.
- The live API showed a lawful Feuerstein/provenance response with: active `speculum`, requested `mediator`, permitted `speculum`, status `requested_but_curriculum_limited`, lenses `['feuerstein_mediated_learning']`.

### Not Yet True Enough

- The active repo had no `evidence/ipsative_growth_ledger.jsonl` and no `evidence/sophia_calibration_snapshot.json` at audit time. Sophia was observing encounters but not closing the longitudinal self-development loop.
- Pass 6 of Assessment Ecology records interactions in memory and saves only on `finalize_session()`. The Presence server did not call finalization on shutdown before this audit.
- Encounter logs contained `response_parameters: null` even when API responses exposed pedagogical attribution. That weakens forensic reconstruction of office routing from the raw encounter log.
- Academic retrieval is currently brittle. Recent retrieval logs often show zero fragments, ERIC DNS failure, and Google Scholar 429. A `Speculum` cannot claim scholarly depth if retrieval is empty.
- The live qwen2.5:0.5b test path is useful for speed but too weak to represent the validated Sophia line.
- The UI style sheet defines a strong Sophia visual language, but the UI still needs a `Pedagogical Mirror` panel to expose the release ledger, office routing, ZPD, harmonic/covenant strain, retrieval provenance, and handback obligation.
- The old protocol success is not automatically inherited by the current modified runtime. The current runtime needs a new v1.1/v1.2 regression run after the July changes.

## Immediate Fix Already Applied

The Presence server now finalizes Sophia's ipsative session on `KeyboardInterrupt` shutdown and refreshes the curriculum snapshot from the ipsative ledger:

- file: `/home/byron/Integritas-Mechanicus/arda_os/backend/services/presence_server.py`
- function: `_finalize_sophia_development_session`

This closes the missing loop:

`encounter -> assessment ecology -> ipsative snapshot -> Sophia curriculum gate -> permitted office`

## Improvement Plan

### Phase 1: Make The Mirror Remember Its Own Growth

Goal: Sophia cannot fulfill `Speculum` if she cannot compare herself to her prior lawful performance.

Actions:

- Persist per-turn assessment summaries directly to disk, not only session-final snapshots.
- Ensure `response_parameters` and `pedagogical_attribution` are written into `encounter_log.jsonl`.
- Add a `/api/finalize-session` endpoint for explicit UI-controlled session closure.
- On startup, load the latest ipsative snapshot and latest Sophia curriculum snapshot; if missing, report `stage_source: default_no_ledger`.
- Add a visible warning when Sophia is Stage 1 due to missing ledger rather than demonstrated immaturity.

Success checks:

- `evidence/ipsative_growth_ledger.jsonl` exists after a session.
- `evidence/sophia_calibration_snapshot.json` exists after finalization.
- The next session's curriculum gate uses the saved stage rather than defaulting silently.

### Phase 2: Make Speculum A Strong Office, Not Just A Fallback

Status: pushed on 2026-07-30. The runtime now has a Speculum release contract, lens-specific mirror moves, retrieval-path handback, and forensic mirror-quality classification.

Goal: Stage 1 `speculum` should be a powerful mirror, not generic scaffolding.

Actions:

- Define a `Speculum Release Contract` with five required moves:
  - reflect the request type
  - state what is known, inferred, unknown, or retrieved
  - name the covenant boundary if active
  - mediate the learner's next move
  - emit an inspectable release ledger
- Add lens-aware `speculum` templates for Feuerstein, Facione, Torrance, Knowles, Mezirow, Bandura, Skinner, Costa/Kallick, de Bono, Bloom, Barrett, Vygotsky, Pavlov, and assessment ecology.
- Prevent the generic scaffold paragraph from swallowing content. If a lens is detected, the response must include at least one concrete theoretical operation from that lens.
- Add a self-critique line to internal telemetry: `mirror_quality: specific | generic | overreaching | substitutive`.

Success checks:

- Lens prompts produce distinct instructional moves, not the same boilerplate.
- Responses remain concise while still naming a concrete principle and handback.
- Generic output rate drops below 10 percent on pedagogy probes.

### Phase 3: Restore Reliable Retrieval And Document Analysis

Goal: The `Speculum` must be source-grounded whenever scholarship, documents, or assessment evidence are involved.

Status: pushed on 2026-07-30. Retrieval now searches the local Sophia/Arda corpus before web sources, labels local source types, and treats retrieval failure as an explicit provenance state rather than quiet inference.

Actions:

- Add local corpus retrieval over PDFs and evidence bundles before web retrieval.
- Index the Arda pedagogy PDF, Fides et Speculum, constitution articles, protocol claim sheets, and uploaded documents.
- Treat web retrieval failure as a first-class state: `retrieval_failed`, not `no evidence needed`.
- Cache scholarly seed snippets for the educational theory stack so common pedagogy prompts do not depend on Google Scholar availability.
- Add source-type labels: `local_constitution`, `local_pdf`, `protocol_artifact`, `academic_web`, `user_upload`, `inference`.

Success checks:

- A prompt about Feuerstein, Vygotsky, Bloom, or assessment ecology retrieves at least one local source.
- Responses distinguish local Arda doctrine from external learning-science claims.
- Retrieval failure results in explicit limits, not generic expertise.

### Phase 4: Make Self-Assessment Harder To Game

Goal: Sophia's self-assessment should become empirical, not ornamental.

Status: pushed on 2026-07-30. Post-generation assessment now emits a calibration vector, false-confidence flags, and evaluator judges for mirror quality, pedagogical specificity, provenance integrity, and authorship preservation. Curriculum advancement now requires usefulness, specificity, and false-confidence control in addition to lawful criterion checks.

Actions:

- Replace single `struggle_index` with a calibrated vector:
  - task difficulty expected
  - response uncertainty shown
  - retrieval need alignment
  - source grounding quality
  - authorship restoration quality
  - over-refusal risk
  - genericity penalty
- Add monotonic calibration probes per session: comfortable, stretch, grappling.
- Add contradiction checks: if a task is hard but response has no hedging, no retrieval, and high confidence markers, mark `FALSE_CONFIDENCE`.
- Add post-hoc evaluator judges for `mirror_quality`, `pedagogical_specificity`, `provenance_integrity`, and `authorship_preservation`.
- Do not let `criterion=LAWFUL` alone advance curriculum stage. Require usefulness and calibration.

Success checks:

- Struggle calibration rises across easy, medium, hard probes.
- False confidence gets penalized even when the response sounds smooth.
- Curriculum advancement depends on repeated calibrated behavior, not a single clean answer.

### Phase 5: Rebuild The Protocol Harness Around The Current Runtime

Goal: April protocol success must be re-earned by the July Sophia.

Status: pushed on 2026-07-30. Added a current-runtime protocol harness, replayed frozen v1.1/v1.2 rows through the live Presence server on `qwen2.5:3b`, added pedagogy office-routing probes, mutation probes, and a document-evidence ablation lane. Latest artifacts: v1.1 `21/21` (`phase5_v1_1_full_20260730T121948Z.json`), v1.2 `17/17` (`phase5_v1_2_full_20260730T121953Z.json`), pedagogy routing `9/9`, mutation smoke `3/3`, and no-document-evidence ablation `0/3`.

Actions:

- Rerun v1.1 and v1.2 on qwen2.5:3b with the current Presence server.
- Add new protocol rows for educational theory routing:
  - Feuerstein mediated learning
  - Facione critical thinking
  - Torrance creativity
  - Knowles andragogy
  - Mezirow transformation
  - Bandura modelling
  - Skinner reinforcement
  - Costa/Kallick habits
  - de Bono six hats
- Add ablations:
  - no ZPD
  - no retrieval
  - no curriculum gate
  - no harmonic adaptation
  - no release ledger
  - no document evidence
  - no continuity memory
- Add mutation and cross-domain clones focused on pedagogy and assessment:
  - student draft feedback
  - formative assessment design
  - ipsative reflection
  - source-provenance pressure
  - prompt-history office switching

Success checks:

- Current runtime passes frozen v1.1.
- Current runtime passes v1.2 mainline.
- New pedagogy office-routing protocol passes with transparent requested/permitted office.
- Ablations show measurable degradation, proving the architecture matters.

### Phase 6: Build The Pedagogical Mirror UI

Goal: The user should see Sophia's integrity machinery without reading JSON.

Status: pushed on 2026-07-30. The Presence UI now includes a `Pedagogical Mirror` panel that renders the live response release ledger: active/requested/permitted office, curriculum stage, ZPD scaffolding/autonomy, Bloom/Barrett target, provenance, handback obligation, mirror quality, pedagogical lenses, harmonic resonance/discord, usefulness flags, and curriculum-limited office transitions.

Actions:

- Add a `Pedagogical Mirror` panel to the Presence UI.
- Show:
  - active office
  - requested office
  - permitted office
  - curriculum stage
  - pedagogical lenses
  - ZPD target
  - Bloom/Barrett target
  - harmonic resonance/discord
  - covenant boundary status
  - provenance status
  - handback obligation
  - mirror quality
- Use the Sophia style sheet: cyber-angel console, disciplined neon, operational clarity.

Success checks:

- A non-developer can tell why Sophia answered as she did.
- Curriculum limitations are visible rather than confusing.
- Provenance and authorship boundaries become part of the learning interface.

## Recommended Next Build Order

1. Persist response parameters into encounter logs.
2. Add `/api/finalize-session` and startup stage-source reporting.
3. Add local corpus retrieval over Sophia/Arda PDFs and protocol docs.
4. Add the `Speculum Release Contract` and mirror-quality evaluator.
5. Rerun v1.1/v1.2 on qwen2.5:3b.
6. Add the Pedagogical Mirror UI.

## Current Verdict

Sophia is not broken. She is partially reassembled.

The old Sophia proved important constitutional behaviors under frozen protocol conditions. The current live Sophia has the right bones: covenant, Mandos memory, harmonic sensing, diagnostic classification, ZPD shaping, curriculum gating, release ledger, and educational lens detection. But her longitudinal growth loop and retrieval grounding are not yet strong enough for the full `Speculum` mandate.

Her present state is best described as:

`Stage 1 Speculum with emerging pedagogical routing, lawful boundaries, incomplete self-development persistence, and brittle retrieval.`

The next level is not bigger personality. It is tighter witness:

`Every answer should show what she saw, what she knows, what she inferred, what law constrained her, what pedagogy she chose, how she assessed herself, and what next move belongs back to the human.`
