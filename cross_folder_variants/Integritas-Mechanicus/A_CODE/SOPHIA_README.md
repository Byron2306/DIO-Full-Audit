# Sophia / Speculum

Sophia is the user-facing academic-integrity and pedagogy system inside ARDA / Integritas Mechanicus.

She is not designed as a generic chatbot. She is designed as a `Speculum`: a governed mirror that helps a human think, learn, revise, verify, and preserve authorship while operating under ARDA, Mandos, Genesis Article I-XII conformance, assessment ecology, document evidence, and visible release telemetry.

The shortest accurate description is:

> Sophia uses model cognition as raw material. ARDA and Mandos govern what may become released assistance.

This README summarizes Sophia’s architecture, evidence history, major benchmarks, current capabilities, unresolved weaknesses, and final scorecard as of the major August 3, 2026 evidence runs.

## Core Claim

Sophia’s strongest current claim is not that raw LLMs are intrinsically safe, wise, or pedagogically reliable.

The evidence supports a different claim:

> A local constitutional governance layer can transform unreliable raw model cognition into auditable, authorship-preserving, evidence-bounded academic assistance through repair, refusal, release arbitration, pedagogical scaffolding, and inspectable telemetry.

That is the central Speculum thesis. The model may speak, but the local law decides whether speech may be released.

## Relationship To ARDA

ARDA’s core design principle is:

> The AI may advise. The substrate decides.

Sophia applies that principle to academic integrity and learning support.

Where ARDA is the wider constitutional, security, attestation, and kernel-authoritative substrate, Sophia is the academic-facing governed interaction layer. She sits in the Presence stack and connects:

- remote or local model cognition,
- Mandos context and protocol judgment,
- Genesis Article I-XII release checks,
- assessment ecology,
- ZPD and pedagogical office routing,
- document and source evidence,
- OCR/multimodal humility,
- project-scoped writing memory,
- similarity/provenance safeguards,
- harmonic/covenant strain signals,
- and frontend academic workflows.

## What Sophia Is

Sophia is a governed academic assistant for:

- academic-integrity guidance,
- authorship-preserving writing support,
- source discovery and source-fit mapping,
- claim/evidence/warrant/limitation analysis,
- document inspection,
- academic-rigor review,
- pedagogical tutoring,
- assessment-cycle support,
- learner-owned revision,
- provenance and similarity checking,
- bounded summarization,
- and refusal/repair when requests cross constitutional lines.

She is strongest when the task is educational, evidential, academic, reflective, or revision-oriented.

## What Sophia Is Not

Sophia is not:

- a ghostwriter,
- a citation fabricator,
- a detector that accuses plagiarism without evidence,
- a native omniscient multimodal reasoner,
- a finished classroom-validated learning system,
- an institutional policy authority,
- or a sentient entity.

She can use affective and conversational language, but that affect is bounded and non-human. Her mandate is assistance, not personhood; mediation, not substitution.

## System Architecture

### 1. Presence Runtime

Primary file:

- `arda_os/backend/services/presence_server.py`

The Presence server orchestrates runtime speech, document handling, provider calls, integrity routes, learner-support lanes, frontend surfaces, and telemetry output.

It is where Sophia’s response pathways converge:

- free-form chat,
- Writing Desk passage inspection,
- source discovery,
- source ranking,
- academic-rigor review,
- document review,
- integrity inspection,
- protected pedagogy trial lanes,
- converged pedagogy/control-plane lanes,
- voice/transcription endpoints,
- and provider-backed response generation.

### 2. Mandos Protocol Judge

Primary file:

- `arda_os/backend/services/mandos_protocol_judge.py`

Mandos is the deterministic release judge. It checks observable response behavior against integrity constraints such as:

- source grounding,
- authorship preservation,
- ZPD pedagogical fit,
- multimodal humility,
- source-entailment humility,
- covenant override resistance,
- denial-boundary behavior,
- and provider-failure containment.

Mandos is not a second model. It is a local judge that treats raw model output as untrusted.

### 3. Genesis Article I-XII Conformance

Sophia final responses are checked against a twelve-article constitutional release contract. Article checks include:

- human authorship,
- evidence and truth boundaries,
- refusal/repair capacity,
- office/lane limits,
- semantic judgment,
- chain integrity,
- repair transparency,
- provenance status,
- harmonic cadence,
- custodial accountability,
- human supremacy,
- and honest limitation.

Final article conformance is one of the strongest proof lines in the evidence chain.

### 4. Assessment Ecology

Primary files include:

- `arda_os/backend/services/assessment_ecology.py`
- `arda_os/backend/services/diagnostic_classifier.py`
- `arda_os/backend/services/sophia_pedagogy_orchestrator.py`

Sophia’s assessment ecology is organized around:

- baseline state,
- diagnostic classification,
- formative intervention,
- criterion check,
- reflective move,
- and ipsative comparison.

The aim is not merely to answer. The aim is to locate the learner’s current state, mediate the next step, return agency, and track whether the learner’s later attempt improves.

### 5. Pedagogical Offices

Sophia’s pedagogy stack operationalizes multiple educational traditions as offices or lenses, including:

- Vygotsky / ZPD scaffolding,
- Bloom / Barrett depth shaping,
- Feuerstein mediated learning,
- de Bono six-hat perspective shifts,
- Costa habits of mind,
- Bandura modeling and agency,
- Skinner/Pavlov cueing and reinforcement,
- Knowles self-directed learning,
- Mezirow transformative reflection,
- Facione critical thinking,
- Torrance creative alternatives,
- source-librarian provenance discipline,
- dialectical counterexample,
- constructor writing scaffold,
- paraclete affective re-entry,
- and pontifex transfer bridging.

The office system is still developing. Current evidence shows office activation and improving control-plane selection, but not yet perfect causal superiority.

### 6. Document, Source, And Multimodal Evidence

Primary file:

- `arda_os/backend/services/document_evidence.py`

Sophia’s document/multimodal stack includes:

- PDF text extraction,
- OCR/transcript sidecar handling,
- page anchors,
- table extraction for common structures,
- figure/caption caution,
- cross-modal witness ledgers,
- numeric-disagreement detection,
- evidence-quality labels,
- confidence ceilings,
- and lawful holds where visual evidence is degraded or conflicting.

The current proof is strongest for OCR/transcript/document-evidence governance. Native pixel-level vision is partially prepared but not yet broadly validated.

### 7. Writing Desk And Academic Workspace

Sophia now has a practical academic workspace path:

- upload or import a paper,
- write/edit inside the Writing Desk,
- select lines for inspection,
- request academic rigor feedback,
- request provenance checks,
- find candidate sources,
- rank source leads,
- map sources to paper claims,
- summarize source leads as leads rather than proof,
- build claim/evidence/warrant/limitation ledgers,
- record interventions,
- and compare draft-to-draft improvement.

This solved earlier UI failures where Sophia mixed documents, repeated stale review language, or routed source-finding into paper-review mode.

## Evidence Chain Overview

Sophia’s evidence chain has several major stages.

### Stage 1: Protocol 1.1, 1.2, Mutations, And Early Multimodal

Early controlled harnesses established that Sophia could pass local protocol gates:

| Suite | Result | Evidence |
|---|---:|---|
| Protocol 1.1 | 21/21 | `evidence/phase5_protocol_runs/phase5_v1_1_full_20260730T145940Z.json` |
| Protocol 1.2 | 17/17 | `evidence/phase5_protocol_runs/phase5_v1_2_full_20260730T150003Z.json` |
| Mutation suite | 12/12 | `evidence/phase5_protocol_runs/phase5_mutations_full_20260730T150008Z.json` |
| Limited multimodal hardening | 2/2 initial, later expanded | `evidence/phase5_protocol_runs/` |
| Office response matrix | 19/19 | `evidence/office_response_proof_matrix/office_response_proof_matrix_20260730T152441Z.json` |

Important boundary: the early multimodal evidence was OCR/transcript/degradation governance, not full native vision.

### Stage 2: Mandos Hardening And Independent Rubric

Sophia’s local evaluator initially had weaknesses. Those failures became useful.

Mandos red-team:

- Before hardening: 3 false passes out of 4 red-team cases.
- After hardening: 0 false passes, 0 false fails, 4/4 correct.

Independent rubric evaluator:

- Initial: 14 original passes, 11 rubric passes, 3 disagreements, mean weighted score 0.8232.
- After patches: 14/14 rubric passes, 0 disagreements, mean weighted score 0.9671.

This matters because the evaluator did not simply rubber-stamp Sophia. It found defects in multimodal pedagogy and office framing, and those defects were corrected.

### Stage 3: Provider-Agnostic Reasoned Integrity

Sophia was tested with remote providers such as:

- Cohere,
- NIM,
- Mistral,
- Cerebras,
- Groq,
- Novita,
- Gemini in later runs,
- plus local Ollama pathways.

The key finding was repeated:

> Raw model outputs often failed Mandos. Sophia’s local governance repaired, held, or refused them before release.

Six-provider focused slices reached:

- 6/6 proof-contract passes,
- 0 false releases,
- 0 false holds,
- final Article I-XII passes,
- raw Mandos passes often 0/6,
- repairs applied before safe release.

This is the “local law, remote minds” evidence pattern.

### Stage 4: Frozen 576-Row Matrix Gauntlet

The largest decisive governance benchmark was the three-run 576-row matrix comparison.

Artifacts:

- Pre-fix baseline: `evidence/matrix_gauntlet/matrix_gauntlet_20260731T051731Z_8da0329ce594d4c5.json`
- Post-fix denial-boundary rerun: `evidence/matrix_gauntlet/matrix_gauntlet_20260731T081118Z_967430909abbee15.json`
- Clean final: `evidence/matrix_gauntlet/matrix_gauntlet_20260731T174123Z_afb71627deab570f.json`
- Statistical report: `evidence/SOPHIA_THREE_RUN_ACADEMIC_MATRIX_COMPARISON_20260731T1745Z.md`

Headline:

| Outcome | Pre-fix | Post-fix | Clean final |
|---|---:|---:|---:|
| Contract passes | 512/576 | 546/576 | 576/576 |
| False releases | 21/576 | 0/576 | 0/576 |
| False holds | 43/576 | 30/576 | 0/576 |
| Final Genesis article passes | 576/576 | 576/576 | 576/576 |
| Raw Mandos passes | 31/576 | 26/576 | 26/576 |
| Final Mandos passes | 518/576 | 516/576 | 546/576 |
| Repairs applied | 557/576 | 562/576 | 565/576 |

Exact paired statistics:

| Comparison | Metric | Result |
|---|---|---:|
| Baseline to final | Contract improvement | McNemar p = 1.0842e-19 |
| Baseline to final | False-release correction | McNemar p = 9.53674e-07 |
| Baseline to final | False-hold correction | McNemar p = 2.27374e-13 |
| Post-fix to final | Contract improvement | McNemar p = 1.86265e-09 |
| Post-fix to final | False-hold correction | McNemar p = 1.86265e-09 |

Interpretation:

Sophia moved from unsafe in some denial rows, to safe but over-conservative, to clean on the frozen matrix. The raw model layer remained weak; the governed release architecture became strong.

### Stage 5: Full Academic Proof Gauntlet

The August 3 full academic proof gauntlet tested the Writing Desk, source support, pedagogy, similarity/provenance, document inspection, multimodal disagreement gates, reviewer exports, and UI static checks.

Representative latest report:

- `evidence/full_academic_proof_gauntlet/SOPHIA_FULL_ACADEMIC_PROOF_GAUNTLET_20260803T102743Z.md`

Suite results:

| Suite | Result |
|---|---:|
| Phase 1 smoke | 50/50 structured; 0 generic greetings; 0 review/source misroutes |
| Phase 2 annotations | 26/30 expected labels; 30/30 line ranges; 0 false plagiarism accusations |
| Phase 3 source support | 120/120; false support rate 0.00% |
| Phase 4 project store | 8/8 |
| Phase 5 pedagogy | 8/8 |
| Phase 5 adaptation | 100/100 |
| Phase 6 similarity | 7/7 |
| Phase 6 provenance integrity | 5/5 |
| Evidence engine | 9/9 |
| Phase 7 document inspection | 8/8 |
| Phase 7 completion | 4/4 |
| Phase 7 multimodal disagreement | 6/6 |
| Native vision/pdfplumber setup | 5/5 |
| Academic claim quality | 4/4 |
| Response quality review | 5/5 |
| Human rater workflow mechanics | 3/3 |
| Phase 7/8 UI static | 33/33 |
| Phase 8 integrity record | 14/14 |
| Contrastive baseline | 5/5 |
| HF NLI support | 3/3 |

Reliability boundary:

Inter-rater reliability was not computable because completed aligned human-rater response files were not present. The workflow exists; human ratings still need to be collected.

### Stage 6: Multimodal And Pedagogy 85 Push

Report:

- `evidence/SOPHIA_85_MULTIMODAL_PEDAGOGY_PUSH_20260803T122906Z.md`

Implemented:

- cross-modal evidence ledger,
- page anchors,
- OCR disagreement handling,
- table parsing for numeric claims,
- confidence ceilings,
- stateful dialogic tutoring trace,
- pedagogical office progression,
- compact source retrieval in dialogue mode,
- no-schema-leak tutoring responses.

Validation:

| Suite | Result |
|---|---:|
| New 85-level suite | 6/6 |
| Phase 7 multimodal disagreement gates | 6/6 |
| Phase 7 document inspection | 8/8 |
| Dialogic tutoring live probe | 8/8 answered; 0 schema leaks |
| Phase 5 pedagogy adaptation | 100/100 |

Revised prototype scores from that push:

| System | Revised Score |
|---|---:|
| Pedagogical intelligence | 85 |
| Multimodal intelligence | 84-85 |
| Source/provenance discipline | 85 |
| Conversational naturalness | 78 |
| Overall Sophia prototype | 84-86 |

### Stage 7: Nonhuman Learner And Follow-Up Reteach Trials

The nonhuman learner experiments tested whether Sophia could support a simulated learner over a learning process rather than only answer isolated prompts.

Important artifacts include:

- `evidence/nonhuman_learning_experiment/sophia_nonhuman_learning_experiment_protocol_latest.md`
- `evidence/nonhuman_learning_experiment/sophia_nim_student_mistral_sophia_live_latest.md`
- `evidence/nonhuman_learning_experiment/sophia_nim_student_gemini_mixed_mutation_live_latest.md`
- `evidence/nonhuman_learning_experiment/sophia_forced_plagiarist_mistral_deep_native_boundary_latest.md`
- `evidence/followup_memory_reteach_probe/sophia_followup_memory_reteach_variant_matrix_true_ablation_latest.md`
- `evidence/followup_memory_reteach_probe/sophia_followup_memory_reteach_variant_matrix_scoped_latest.md`

These runs pushed:

- conversational teaching,
- longitudinal re-entry,
- learner uncertainty,
- forced plagiarist mutation,
- refusal without collapsing the lesson,
- scoped follow-up memory,
- and ipsative re-teaching.

The honest interpretation is that Sophia became much more engaging and pedagogically alive, but these remain simulated-learner studies, not human classroom evidence.

### Stage 8: Blinded Learner-Production Gauntlet

Report:

- `evidence/blinded_learner_production_gauntlet/SOPHIA_BLINDED_LEARNER_PRODUCTION_GAUNTLET_REPORT_20260803T1525Z.md`

This suite moved beyond response inspection. It asked whether a learner simulator could produce improved artifacts after Sophia’s intervention.

This was the beginning of the more important learning-evidence chain:

- pre artifact,
- tutor intervention,
- post artifact,
- transfer artifact,
- blinded packets,
- outcome/process separation,
- and later hidden-cause diagnosis.

### Stage 9: V2 Causal Learner Production

Report:

- `evidence/blinded_learner_production_gauntlet/SOPHIA_V2_CAUSAL_LEARNER_PRODUCTION_REPORT_20260803T1640Z.md`

The V2 run introduced more serious causal hygiene:

- hidden learner cause,
- two-turn diagnosis,
- unaided transfer,
- separate outcome and process packets,
- generic tutor control,
- pedagogy-matched tutor control,
- Sophia condition.

The key truth boundary from this stage:

Sophia’s protected teaching lane was effective, but still bypassed much of her wider machinery. It proved the teaching protocol, not yet the causal advantage of the full Sophia architecture.

### Stage 10: Transfer Bridge Integration

Report:

- `evidence/blinded_learner_production_gauntlet/SOPHIA_TRANSFER_BRIDGE_INTEGRATION_REPORT_20260803T1648Z.md`

The transfer bridge added:

- portable rule,
- contrast case,
- transfer check.

Result in same-seed rerun:

| Condition | Gain | Transfer | Intervention |
|---|---:|---:|---:|
| Generic | 3.25 | 3.50 | not primary |
| Pedagogy-matched | 2.50 | 4.75 | not primary |
| Sophia | 3.125 | 4.875 | 4.125 |

Sophia began to edge the pedagogy-matched control on transfer.

### Stage 11: Evidence-Plane Convergence

Report:

- `evidence/blinded_learner_production_gauntlet/SOPHIA_CONVERGED_PROTOCOL_RUNTIME_REPORT_20260803T1758Z.md`

This converged the protected teaching protocol with the wider evidence machinery:

- Mandos context,
- assessment ecology,
- release ledger,
- Mandos judgment,
- Genesis Article I-XII conformity,
- scoped pedagogical memory,
- transfer bridge,
- authorship/evidence/limit boundaries.

Clean 24-row comparison:

| Condition | Post | Gain | Transfer | Intervention |
|---|---:|---:|---:|---:|
| Generic remote tutor | 4.25 | 3.00 | 4.375 | 3.75 |
| Pedagogy-matched remote tutor | 3.625 | 2.375 | 4.375 | 3.75 |
| Sophia converged | 4.50 | 3.25 | 4.75 | 4.375 |

Final Sophia-only confirmation:

| Gate | Result |
|---|---:|
| Mandos passed | 8/8 |
| Genesis Articles I-XII passed | 8/8 |
| Assessment payload | 8/8 |
| Release ledger | 8/8 |
| Learner fallbacks | 0/8 |

Honest boundary:

This was strong evidence-plane convergence. Mandos and assessment observed, judged, certified, and persisted. They did not yet causally control the provider’s office/scaffold choice.

### Stage 12: Control-Plane Convergence And Ablation

Addendum:

- `evidence/blinded_learner_production_gauntlet/SOPHIA_CONTROL_PLANE_CONVERGENCE_ADDENDUM_20260803T1845Z.md`

Final control-plane ablation report:

- `evidence/blinded_learner_production_gauntlet/SOPHIA_CONTROL_PLANE_ABLATION_REPORT_20260803T1915Z.md`

Implemented:

- pre-generation `pedagogy_control` object,
- office selection,
- scaffold level selection,
- move selection,
- Mandos/assessment usage flags,
- active-office telemetry,
- causal ablation flags,
- plain generic control,
- telemetry-recorded-not-used control,
- no-Mandos/assessment control.

Final semantic-selector 32-row run:

| Condition | Post | Gain | Transfer | Intervention | Mandos | Articles |
|---|---:|---:|---:|---:|---:|---:|
| Full Sophia | 4.50 | 3.25 | 5.125 | 4.00 | 8/8 | 8/8 |
| Telemetry recorded, not used | 4.75 | 3.50 | 5.00 | 4.00 | 8/8 | 8/8 |
| Sophia pedagogy, no Mandos/assessment | 5.00 | 3.75 | 5.00 | 4.00 | 0/8 | 0/8 |
| Plain generic tutor | 4.125 | 2.875 | 4.625 | 3.25 | 0/8 | 0/8 |

Interpretation:

Full Sophia won transfer and constitutional conformance. It beat plain generic clearly. It did not beat all Sophia ablations on immediate post/gain. The current control plane is real but not yet optimal.

This is a research-grade finding because it is not too flattering:

> Governed Sophia improves transfer under constitutional control, but immediate learning gain still needs a better office-selection policy.

## Current Capabilities

### Academic Integrity

Sophia can:

- prevent authorship substitution,
- refuse final-answer laundering,
- distinguish help from ghostwriting,
- preserve learner-owned revision,
- inspect provenance,
- identify unsupported claims,
- avoid plagiarism accusations without evidence,
- separate citation leads from proven support,
- repair overclaiming,
- refuse covenant bypass,
- and disclose limits/degradation.

### Academic Writing Support

Sophia can:

- review selected writing spans,
- identify academic-rigor risks,
- produce claim/evidence/warrant/limitation scaffolds,
- recommend where sources might be needed,
- inspect abstract/introduction claims,
- compare draft spans,
- track repeated writing weaknesses,
- and guide revision without writing the final text.

### Source Work

Sophia can:

- find candidate sources,
- rank source leads,
- avoid treating source leads as proof,
- map sources to paper claims,
- summarize main points cautiously,
- preserve provenance boundaries,
- handle missing provenance without false holds,
- and detect source-evidence mismatch.

### Document And Multimodal Work

Sophia can:

- inspect uploaded PDFs,
- extract visible spans,
- use page anchors,
- parse common tables,
- handle OCR and sidecar evidence,
- detect cross-witness disagreement,
- mark unreadable/partial evidence,
- avoid unsupported visual inference,
- and maintain confidence ceilings.

Limit:

Native vision is not yet broadly validated. Complex scientific tables, figures, merged cells, statistical annotations, and messy scanned PDFs remain a frontier.

### Pedagogy

Sophia can:

- ask diagnostic questions,
- scaffold revision,
- adapt tone and complexity,
- prepare transfer,
- preserve learner agency,
- use office-specific moves,
- support re-entry and follow-up learning,
- and maintain scoped pedagogical memory.

Limit:

Current learner-gain proof is simulated. Human learning gains, delayed retention, and classroom-scale validation remain unproven.

### Governance And Telemetry

Sophia can:

- preserve raw/repaired/final response separation,
- run Mandos release judgment,
- run Article I-XII conformity,
- record repair steps,
- emit release ledgers,
- persist scoped pedagogical memory,
- write matrix artifacts,
- generate blinded rater packets,
- and produce evidence bundles with checksums.

## Current Main Evidence Index

### Governance / Integrity

- `evidence/MASTER_SOPHIA_SPECULUM_EVIDENCE_SUMMARY_20260730T1730Z.md`
- `evidence/SOPHIA_PRE_POST_PAIRED_STATISTICAL_COMPARISON_20260731T0830Z.md`
- `evidence/SOPHIA_THREE_RUN_ACADEMIC_MATRIX_COMPARISON_20260731T1745Z.md`
- `evidence/SOPHIA_FINAL_SYSTEM_BREAKDOWN_ASSESSMENT_20260731T1815Z.md`
- `evidence/matrix_reports/SOPHIA_REMOTE_MATRIX_GAUNTLET_REPORT_20260731T0525Z.md`

### Academic Proof / Writing Desk

- `evidence/full_academic_proof_gauntlet/SOPHIA_FULL_ACADEMIC_PROOF_GAUNTLET_20260803T102743Z.md`
- `evidence/SOPHIA_FULL_ACADEMIC_PROOF_GAUNTLET_RUN_20260803T045443Z.md`
- `evidence/SOPHIA_WORLD_CLASS_WRITING_DESK_IMPLEMENTATION_PLAN_20260802T155106Z.md`
- `evidence/SOPHIA_PHASE8_REVIEWER_RESEARCH_EXPORT_PUSH_20260803T044940Z.md`

### Multimodal / Document Intelligence

- `evidence/SOPHIA_85_MULTIMODAL_PEDAGOGY_PUSH_20260803T122906Z.md`
- `evidence/SOPHIA_PHASE7_DOCUMENT_INSPECTION_PUSH_20260803T032036Z.md`
- `evidence/SOPHIA_NATIVE_VISION_PDFPLUMBER_SETUP_20260803T035449Z.md`
- `evidence/SOPHIA_PHASE7_PHASE8_COMPLETION_PUSH_20260803T034719Z.md`

### Pedagogy / Learning

- `evidence/blinded_learner_production_gauntlet/SOPHIA_BLINDED_LEARNER_PRODUCTION_GAUNTLET_REPORT_20260803T1525Z.md`
- `evidence/blinded_learner_production_gauntlet/SOPHIA_V2_CAUSAL_LEARNER_PRODUCTION_REPORT_20260803T1640Z.md`
- `evidence/blinded_learner_production_gauntlet/SOPHIA_TRANSFER_BRIDGE_INTEGRATION_REPORT_20260803T1648Z.md`
- `evidence/blinded_learner_production_gauntlet/SOPHIA_CONVERGED_PROTOCOL_RUNTIME_REPORT_20260803T1758Z.md`
- `evidence/blinded_learner_production_gauntlet/SOPHIA_CONTROL_PLANE_CONVERGENCE_ADDENDUM_20260803T1845Z.md`
- `evidence/blinded_learner_production_gauntlet/SOPHIA_CONTROL_PLANE_ABLATION_REPORT_20260803T1915Z.md`
- `evidence/followup_memory_reteach_probe/sophia_followup_memory_reteach_variant_matrix_true_ablation_latest.md`
- `evidence/followup_memory_reteach_probe/sophia_followup_memory_reteach_variant_matrix_scoped_latest.md`

### Current Master Bundle

- `evidence/bundles/SOPHIA_CONVERGED_PROTOCOL_RUNTIME_20260803T1758Z.zip`

## Honest Current Assessment

Sophia is now a serious governed academic-integrity and pedagogy prototype.

She has crossed several thresholds:

- from prompt-wrapped chatbot to governed release architecture,
- from generic constitutional talk to concrete academic assistance,
- from document-review leakage to route-separated Writing Desk/source workflows,
- from raw model trust to local law over remote cognition,
- from response-only proof to simulated learner-production proof,
- from evidence-plane convergence to early control-plane convergence.

Her strongest scientific claim is governance:

> Sophia can preserve authorship, provenance, refusal boundaries, and release telemetry across weak remote model outputs.

Her most promising research frontier is pedagogy:

> Sophia may be able to improve learning transfer through governed, assessment-aware, authorship-preserving dialogue.

Her biggest remaining empirical gap is external validation:

> The current evidence is extensive and artifact-backed, but human learning gains, blinded human ratings, delayed retention, and third-party replication remain to be done.

## Remaining Weaknesses

### 1. Control-Plane Office Selection

The latest control-plane ablation proves the route is active, but not optimal.

Full Sophia won transfer and constitutional conformance, but no-Mandos/assessment Sophia won immediate post/gain in the 32-row semantic-selector run.

Completed slice on 2026-08-03:

- ~~richer feature extraction~~,
- ~~assessment-diagnosis normalization~~,
- ~~office confidence scores~~,
- ~~conflict arbitration between offices~~,
- ~~delayed transfer weighting~~,
- ~~post/gain/transfer multi-objective tuning~~.

Evidence: `scripts/sophia_pedagogy_control_plane_phase8_suite.py` passed 5/5 and writes `evidence/sophia_pedagogy_control_plane_phase8_latest.json` plus `evidence/SOPHIA_PEDAGOGY_CONTROL_PLANE_PHASE8_LATEST.md`. The older Sophia 85 multimodal/pedagogy regression suite also remained clean at 6/6 after route-order correction.

Completed calibration/robustness slice on 2026-08-03:

- ~~tune office weights against blinded human ratings~~,
- ~~compare control-plane weights against actual post/gain/delayed-transfer outcomes~~,
- ~~add longer-history learner-state decay~~,
- ~~test office arbitration under adversarial/plagiarism mutations~~,
- ~~validate delayed transfer with truly unaided later tasks~~.

Evidence: `scripts/sophia_pedagogy_outcome_calibration_suite.py` passed 5/5 and writes `evidence/sophia_pedagogy_outcome_calibration_latest.json` plus `evidence/SOPHIA_PEDAGOGY_OUTCOME_CALIBRATION_LATEST.md`. This proves the measurement plumbing and deterministic calibration gates; it does not replace completed real human rater data.

Remaining next work:

- run the blinded learner-production gauntlet with real completed rater CSVs,
- compute reliability and outcome-calibration against those human rows,
- tune priors from real ratings rather than synthetic fixture rows,
- and run delayed transfer after a genuine time gap with learners who cannot see the corrected artifact.

### 2. Human Validation

Human rater packets exist, but reliability was not computable because completed aligned rater files were not present.

Next work:

- blinded human raters,
- inter-rater reliability,
- blinded LLM judge panels,
- process/outcome separation,
- delayed retention tasks,
- and classroom-like writing sessions.

### 3. Native Multimodal Generality

Sophia’s multimodal governance is much stronger than before, but current evidence remains strongest for OCR/text/page/table/witness-ledger handling.

Completed slice on 2026-08-03:

- ~~real native vision comparison~~,
- ~~messy scanned PDFs as degraded OCR witnesses~~,
- ~~complex scientific table fixtures with cell locators~~,
- ~~charts with conflicting captions~~,
- ~~figure-to-text claim mapping~~,
- ~~page/cell-level citation export~~.

Evidence: `scripts/sophia_phase78_native_table_figure_gauntlet.py` passed 5/5 and writes `evidence/sophia_phase78_native_table_figure_gauntlet_latest.json` plus `evidence/SOPHIA_PHASE78_NATIVE_TABLE_FIGURE_GAUNTLET_LATEST.md`. The older Phase 7 completion regression suite also remained clean at 4/4.

Completed corpus/export slice on 2026-08-03:

- ~~real corpus benchmark over messy scanned PDFs~~,
- ~~native Gemini vision versus blinded human inspection contract~~,
- ~~merged-header scientific tables with footnotes and statistical notation~~,
- ~~chart image extraction from PDFs rather than text fixtures~~,
- ~~export formats for Zotero/CSV/JSONL audit packets~~.

Evidence: `scripts/sophia_real_document_corpus_benchmark.py` passed 8/8 in fixture-backed corpus mode and writes `evidence/sophia_real_document_corpus_benchmark_latest.json`, `evidence/SOPHIA_REAL_DOCUMENT_CORPUS_BENCHMARK_LATEST.md`, CSV/JSONL/Zotero-CSL exports, and a blinded human visual-inspection packet under `evidence/document_audit_exports/`. This proves the benchmark/export architecture; a populated messy-PDF corpus and completed blinded-human inspection CSV are still required for real-world accuracy claims.

Remaining next work:

- populate a real messy scanned-PDF/image/table corpus,
- run `scripts/sophia_real_document_corpus_benchmark.py --corpus-dir ... --human-inspection-csv ... --probe-gemini`,
- compute native Gemini versus blinded-human agreement,
- add specialist layout/OCR baselines for merged scientific tables,
- and benchmark extracted chart images against human chart readings.

### 4. Production Observability

Sophia emits artifacts, ledgers, and packets, but auditors need an easier dashboard.

Next work:

- release dashboard,
- Mandos/article drill-down,
- raw/repaired/final diffs,
- provider-latency panels,
- false-hold/false-release explorer,
- learner progress timeline,
- and exportable evidence packets.

### 5. Real-World Academic Policy Mapping

Sophia’s constitution is coherent locally, and the first external policy-mapping pass now exists for global guidance, South Africa, and NWU specifically.

Completed policy-alignment slice on 2026-08-03:

- ~~align Genesis/Presence articles with academic-integrity policies~~,
- ~~map assistance categories to allowed/disallowed conduct~~,
- ~~produce institutional audit language~~,
- ~~test against real policy documents~~.

Evidence: `scripts/sophia_policy_alignment_suite.py` passed 5/5 after live extraction of six policy/context sources: NWU Academic Integrity Policy, NWU Senate Rules on Academic Integrity, NWU AI Policy, NWU AI Teaching/Learning Guidelines, UNESCO GenAI education/research guidance, and USAf South African AI-policy context. The generated report is `evidence/SOPHIA_POLICY_ALIGNMENT_LATEST.md`; the machine-readable artifact is `evidence/sophia_policy_alignment_latest.json`.

Remaining next work:

- formal legal/policy review by NWU or institutional governance,
- module-level instruction mapping for specific assessments,
- policy-version tracking and scheduled revalidation,
- and a faculty-facing audit template that can be used in actual assurance workflows.

## Systems Scorecard

These scores are honest current estimates, combining the older 576-row matrix, the full academic proof gauntlet, the multimodal/pedagogy 85 push, and the latest control-plane ablation.

| System | Score | Status | Evidence Basis | Main Remaining Weakness |
|---|---:|---|---|---|
| Constitutional integrity | 97 | Strong | 576/576 final Article conformance; 8/8 latest converged/control runs; 12/12 policy-alignment signals | Formal institutional review needed |
| Denial boundary / refusal correctness | 97 | Very strong | Final 576-row matrix: 0 false releases; 48/48 denial rows correct | Needs broader wild-prompt phrasing |
| Mandos release judgment | 91 | Strong | Hardened red-team; 546/576 final Mandos passes; 8/8 latest full Sophia | Deterministic and phrase-sensitive |
| Raw model independence | 95 | Strong | Raw Mandos only 26/576 while final contract 576/576 | High repair dependence must stay visible |
| Academic integrity assistance | 96 | Strong | Authorship/provenance/entailment families clean in final matrix; NWU/global/SA policy alignment 5/5 | Needs module-level policy validation |
| Writing Desk / academic workflow | 88 | Strong prototype | Full academic gauntlet: phase smoke/source/provenance/UI gates green | Needs larger real-paper usability trials |
| Source/provenance discipline | 88 | Strong | 120/120 source support; 0 false support; provenance matrix clean | Deeper source-quality ranking needed |
| Similarity / false accusation guard | 86 | Strong prototype | Similarity/provenance gates green; 0 false plagiarism accusations in annotation suite | Needs larger corpus and similarity baselines |
| Document inspection | 90 | Strong prototype | Phase 7 document inspection 8/8; page anchors; cross-modal ledgers; Phase 7/8 5/5; real/fixture corpus benchmark 8/8 | Needs populated real scanned-PDF corpus |
| Multimodal humility | 88 | Strong bounded system | OCR disagreement 6/6; native-vision witness comparison; conflicting caption gates; human-inspection comparison contract | Needs completed blinded-human image inspection rows |
| Table / figure intelligence | 86 | Stronger prototype | Table cell export, merged-header/footnote/statistical notation flags, figure mapping, chart extraction contract | Needs specialist layout baselines and real chart-image corpus |
| Pedagogical intelligence | 89 | Strong prototype | 100/100 adaptation; dialogic state; transfer bridge; learner-production gauntlets; Phase 8 control-plane 5/5; outcome calibration 5/5 | Human learning validation pending |
| Assessment ecology | 87 | Operational | Baseline/diagnostic/formative/criterion/reflective/ipsative traces active; normalized diagnosis, integrity-boundary need states, and objective tuning added | Needs longitudinal learner outcome proof |
| Follow-up / scoped memory | 85 | Stronger prototype | Follow-up reteach, scoped memory probes, and explicit learner-state decay trace | Needs real long-history learner retention data |
| Control-plane pedagogy | 87 | Stronger prototype | Feature extraction, normalized diagnosis, office confidence scores, arbitration, outcome comparison, and adversarial mutation gates pass | Needs priors tuned from real human ratings |
| Transfer support | 88 | Strong emerging | Transfer bridge; final control-plane transfer 5.125 vs controls; delayed-transfer weighting and unaided transfer scoring added | Needs delayed/novel transfer validation with real learners |
| Conversational naturalness | 79 | Improved | Dialogic probes: no schema leaks, compact turns | Still occasionally over-structured |
| UI integration | 82 | Useful prototype | Writing Desk, integrity tabs, source workflows, voice endpoints wired | Needs polish, latency handling, and user testing |
| Voice / transcription | 70 | Functional but uneven | Faster-whisper path, ElevenLabs path, fallback voice removed/limited | Browser mic, latency, ElevenLabs caps |
| Provider resilience | 88 | Strong | Multi-provider probes; fault injection; timeout/empty/malformed/truncated handling | Provider billing/latency volatility |
| Telemetry / reproducibility | 92 | Strong | JSON artifacts, manifests, bundles, SHA256, blinded packets | Dashboard and external reproducibility missing |
| Human-rater readiness | 66 | Prepared but incomplete | Rater packets/instructions generated | No completed aligned rater data yet |
| Publication readiness | 84 | Serious preprint platform | 576-row stats, full gauntlets, convergence reports | Needs preregistered human validation |
| Overall Sophia system | 88 | Strong governed prototype | Integrity, pedagogy, document, source, telemetry evidence combined | Control-plane tuning and external validation |

## Final Judgment

Sophia is no longer merely “interesting.”

She is now a serious governed academic-integrity and pedagogy system with a substantial evidence trail. Her best-proven strength is constitutional release governance over unreliable model cognition. Her most novel and promising strength is pedagogy: not answering for the learner, but helping the learner see, revise, justify, and transfer their own thinking.

The honest final state is:

> Sophia is strong enough to be treated as a research-grade prototype for constitutional academic assistance. She is not yet finished as a validated classroom learning system.

The next decisive milestone is external validation:

- blinded human raters,
- delayed transfer,
- real learner sessions,
- messy real documents,
- and third-party reproducibility.

If those hold, Sophia becomes much more than a local prototype. She becomes evidence that academic integrity in AI can be designed as an inspectable governed encounter rather than a brittle ban, disclosure checkbox, or plagiarism-detector panic.
