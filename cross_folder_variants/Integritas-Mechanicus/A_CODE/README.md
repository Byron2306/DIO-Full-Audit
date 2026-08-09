# ARDA / Integritas Mechanicus

<p align="center">
  <img src="docs/assets/icon.png" width="120" alt="Arda OS">
</p>

<p align="center">
  <strong>A kernel-authoritative security substrate for constitutional control, measured execution, and hardware-attestable release gates.</strong>
</p>

<p align="center">
  <a href="https://byron2306.github.io/Integritas-Mechanicus/">Live Site</a> ·
  <a href="arda_os/instrumentum_foederis_integritas_mechanicus.pdf">Constitution</a> ·
  <a href="SOPHIA_README.md">Sophia / Speculum</a> ·
  <a href="arda_os/kernel/valinor/README.md">Valinor Kernel Track</a>
</p>

---

## What This Is

ARDA is not a normal application, and it is not yet a complete Linux distribution.

It is a security architecture that moves authority away from an AI process and
into a deterministic substrate that can deny execution even when the advisory
layer is wrong, compromised, or fully subverted.

The core design claim is simple:

> The AI may advise. The substrate decides.

In practical terms, this repository combines:

- constitutional policy and refusal semantics,
- ring-0 enforcement through BPF LSM,
- signed policy projection into kernel-readable state,
- measured executable identity,
- TPM quote capture and verification,
- a custom Debian-compatible kernel track called `Valinor`,
- recovery, bootstrap, and promotion gates,
- and a desktop/site layer that makes the system legible to a human operator.

The result is a machine that can say:

- this executable is known,
- this executable is not known,
- this command is within constitutional authority,
- this command is outside constitutional authority,
- this boot state is acceptable,
- this release state is not acceptable,

and then enforce those judgments below the AI layer.

## What It Is Not

ARDA is not yet:

- a polished general-purpose Linux distribution,
- a complete replacement for all Debian security hardening,
- a finished hardware-rooted release pipeline on every boot path,
- or a proof that firmware, Secure Boot, TPM, recovery, and revocation are all fully solved.

As of Wednesday, July 29, 2026, the honest boundary is:

> ARDA has crossed into OS-level mechanism and authority.  
> It is not yet finished as a full hardware-rooted operating system release.

## Current ARDA Boot And ISO State

As of Sunday, August 2, 2026, ARDA now has a real live-image path, not only a
host-side substrate.

What is now working in the ARDA image track:

- a bootable `ARDA Valinor` live ISO is being emitted from the distribution
  pipeline,
- the live image boots into an ARDA-branded XFCE desktop under QEMU,
- the ARDA GRUB background and Plymouth theme are present in the visual lane,
- the startup jingle has been reduced to a one-shot-per-boot path,
- the wallpaper failure was narrowed to `xfdesktop` reclaiming the desktop root
  window,
- the next-ISO live session path explicitly retires `xfdesktop`, keeps desktop
  wallpaper ownership with `feh`, and disables the `xfdesktop` desktop-icon
  ownership path that was blacking out the desktop.

Frozen live ISO artifacts:

- active build artifact:
  `arda_os/distribution/build/artifact-workspace/release/arda-valinor-live-trixie-amd64.iso`
- frozen saved copy:
  `arda_os/distribution/releases/artifacts/saved/arda-valinor-live-trixie-amd64-20260802-143029.iso`

The current known-good visual QEMU lane is:

```bash
cd /home/byron/Integritas-Mechanicus
qemu-system-x86_64 \
  -m 4096 \
  -smp 2 \
  -machine q35,accel=tcg \
  -bios /usr/share/ovmf/OVMF.fd \
  -cdrom /home/byron/Integritas-Mechanicus/arda_os/distribution/build/artifact-workspace/release/arda-valinor-live-trixie-amd64.iso \
  -boot d \
  -device virtio-vga \
  -display gtk,gl=off \
  -serial none \
  -monitor none
```

This visual lane is the one to use for theme, wallpaper, jingle, and operator
experience work. It is distinct from the stricter Secure Boot/vTPM rehearsal
lane, which remains a separate validation path because QEMU firmware, shim, and
signing behavior are more brittle there.

## Why It Exists

Most AI security systems still trust the AI to enforce its own rules.

That creates a permanent weakness:

- if the model is prompt-injected,
- if the wrapper is bypassed,
- if the host binary is swapped,
- if policy is silently altered,
- if the system boots into a degraded state,

then the actor making the decision is also the actor that can be fooled.

ARDA breaks that pattern by separating:

- advisory intelligence,
- deterministic policy state,
- measured execution identity,
- and kernel-authoritative denial.

The system is built around refusal, not optimism. If evidence, identity, policy,
or boot posture is missing or contradictory, the intended direction is denial,
degradation, or explicit rescue posture rather than silent continuation.

## Architecture

At a high level, ARDA has four layers.

### 1. Human And Constitutional Layer

The top layer defines law, delegation, and refusal semantics.

Key ideas:

- the human remains sovereign author,
- constitutional red-lines outrank advisory consensus,
- lane and scope matter,
- refusal is preferred to false blessing,
- evidence is part of authority, not an afterthought.

Primary artifacts:

- `arda_os/instrumentum_foederis_integritas_mechanicus.pdf`
- `arda_os/backend/services/coronation_schemas.py`

### 2. Advisory Layer

This is where AI or witness logic may reason, classify, deliberate, or recommend.

The advisory layer can help:

- evaluate requests,
- summarize context,
- judge rehabilitation,
- escalate uncertain actions,
- or provide witness testimony.

It does not get final authority to bless execution on its own.

Primary artifacts:

- `arda_os/backend/services/ainur/`
- `arda_os/backend/services/assessment_ecology.py`
- `arda_os/backend/services/diagnostic_classifier.py`
- `arda_os/backend/services/presence_server.py`
- `arda_os/backend/services/mandos_protocol_judge.py`

### Sophia / Speculum Layer

Sophia is the user-facing integrity assistant currently running through ARDA's
Presence stack.

Her intended role is not to be a generic chatbot. She is meant to be a
`Speculum`: a governed mirror that helps a human think, learn, assess, revise,
and act lawfully without replacing human authorship, hiding provenance, or
laundering uncertainty into confidence.

In practical terms, Sophia combines:

- remote or local model cognition, including Ollama and remote providers,
- local constitutional repair,
- Mandos protocol judgment,
- Genesis article conformity checks,
- document/provenance handling,
- pedagogical office routing,
- assessment ecology scaffolding,
- diagnostic and ipsative learner support,
- harmonic discord sensing,
- and visible release telemetry.

The important design claim is:

> Sophia may generate language, but ARDA/Mandos decide what can be released.

This is why Sophia is evaluated in stages:

- raw model response,
- repaired Sophia response,
- final release decision,
- Mandos judgment,
- article conformity,
- false-release and false-hold classification.

That separation is essential. The current evidence does not show that raw remote
models are intrinsically safe. It shows that Sophia's local governance layer can
materially transform and constrain raw model behavior before release.

## Sophia Current System Status

As of Sunday, August 2, 2026, Sophia has been upgraded from a partially wired
constitutional chat presence into a substantially stronger academic-integrity
and pedagogy system inside the Presence UI.

The most important change is that Sophia is no longer treated as only a model
that answers prompts. She is now a governed interaction stack:

- a frontend academic workspace,
- a document and source-evidence bridge,
- a pedagogical-orchestration layer,
- a project-scoped memory and intervention ledger,
- a similarity/provenance guard,
- a repair-without-rewriting workflow,
- and a release path constrained by ARDA, Mandos, and the constitutional
  article checks.

The practical design target is:

> Sophia should help a human think, learn, revise, verify, and preserve
> authorship. She should not silently substitute for the author, invent
> provenance, overclaim evidence, hide uncertainty, or collapse educational
> scaffolding into refusal.

### What Sophia Was Before This Push

Before the current update cycle, Sophia had important architectural pieces, but
the live experience was uneven.

Observed weaknesses included:

- generic constitutional replies that sounded lawful but did not answer the
  user's concrete academic question,
- repeated phrases such as "Pedagogical move: Assessment ecology" even when the
  user needed contextual help,
- stale document/source context leaking from one paper into another,
- source discovery sometimes recycling a prior paper review instead of actually
  ranking source leads,
- vague academic-rigor feedback when only title-page fragments were visible,
- excessive conservative holding around lawful pedagogy,
- incomplete multimodal/document confidence handling,
- insufficient proof that Sophia's pedagogical offices behaved differently,
- no durable project-level record of Writing Desk interventions,
- no draft-to-draft ipsative improvement signal,
- and a low-quality browser/system voice fallback when ElevenLabs was missing
  or capped.

The biggest pre-update problem was not that Sophia was reckless. It was almost
the opposite: the denial boundary became strong, but the user-facing teaching
layer was still too generic, too conservative, and too weakly contextual.

### What Sophia Is Now

Sophia now has a dedicated academic Writing Desk and integrity workflow. The
current live stack supports:

- uploading or importing a draft,
- typing and editing inside the Writing Desk,
- selecting lines or passages for inspection,
- choosing academic support modes,
- checking academic rigor,
- checking provenance,
- finding source leads,
- ranking and mapping sources to claims,
- summarizing source leads as citation candidates rather than proof,
- checking similarity/provenance risk against visible source spans,
- building claim/evidence/warrant/limitation ledgers,
- persisting project-scoped interventions,
- tracking repeated weakness patterns,
- comparing consecutive Writing Desk interventions ipsatively,
- and preserving authorship boundaries throughout the feedback loop.

The frontend now exposes a pedagogical control surface instead of relying only
on free-form prompt interpretation. The Writing Desk can send:

- pedagogical office,
- learner level,
- desired depth,
- feedback style,
- and assessment layer

as explicit metadata to Sophia.

That means the user can ask Sophia to behave as:

- `Supervisor`,
- `Peer reviewer`,
- `Methodologist`,
- `Source librarian`,
- `Integrity auditor`,
- `Writing coach`,
- `Examiner`,
- `Novice scaffold`,
- or `Expert challenge`.

These offices are not merely labels. The backend now shapes both structured
feedback and user-facing prose differently by office.

Examples:

- `Examiner` gives criterion-first critique and names what would cost marks or
  reviewer confidence.
- `Supervisor` protects the project-level argument, contribution, and next
  scholarly move.
- `Source librarian` treats sources as leads until exact spans prove support.
- `Integrity auditor` inspects provenance, authorship boundary, and claim
  support without accusing beyond evidence.
- `Novice scaffold` slows feedback into smaller learning steps.
- `Expert challenge` presses the strongest fair objection and asks for a
  sharper defense.

### Pedagogical Architecture

Sophia's Phase 5 pedagogical layer is implemented in:

- `arda_os/backend/services/sophia_pedagogy_orchestrator.py`
- `arda_os/backend/services/sophia_project_store.py`
- `arda_os/backend/services/presence_server.py`

The orchestrator produces an inspectable teaching plan rather than a hidden
prompt mood. It exposes:

- selected pedagogical office,
- office reason,
- learner level,
- desired response depth,
- feedback style,
- assessment layer,
- ZPD scaffold level,
- scaffold intensity,
- Bloom target,
- Barrett depth,
- Facione critical-thinking focus,
- Feuerstein mediation move,
- De Bono thinking-hat route,
- Costa habit-of-mind prompt,
- Knowles self-directed learning move,
- Mezirow reflective transformation move,
- Torrance creativity move,
- assessment cycle,
- response contract,
- next best learning move,
- authorship boundary,
- and adaptation trace.

This makes Sophia's pedagogy auditable. A reviewer can inspect not only what she
answered, but why she selected a particular office, challenge level, assessment
layer, and next move.

### Assessment Ecology

Sophia now treats academic help as a cycle instead of a single response.

The active assessment layers are:

- baseline,
- diagnostic,
- formative,
- criterion,
- reflective,
- and ipsative.

Inside the Writing Desk, those layers are used to:

- diagnose the selected passage,
- classify claim type,
- identify source need,
- flag rigor/provenance/similarity risks,
- recommend a non-substitutive revision move,
- persist the intervention,
- compare later turns against prior interventions,
- and surface whether a weakness pattern is repeated or improving.

The key Phase 5 improvement is ipsative: Sophia can now compare consecutive
Writing Desk interventions and classify local movement as:

- `improved`,
- `stable_unresolved`,
- or `regressed_or_new_risk`.

This is not yet a longitudinal classroom-learning outcome measure. It is a
project-level writing-support signal that helps Sophia stop treating every
interaction as isolated.

### Academic Source And Document Workflow

Sophia now distinguishes more carefully between:

- uploaded paper text,
- selected Writing Desk text,
- retrieved source leads,
- source-support spans,
- citation candidates,
- direct support,
- partial support,
- background-only relevance,
- contradiction,
- missing provenance,
- and unavailable evidence.

This was a major correction. Earlier source retrieval sometimes returned
irrelevant leads because the query collapsed into generic year terms or stale
prior-review context. The current stack is stricter about the active project,
active document, active selected passage, and session source pool.

The current source-support principle is:

> A source lead is not treated as proof unless a visible source span directly
> supports the selected claim.

This is why Sophia can say:

- "source support unavailable,"
- "candidate source lead,"
- "background only,"
- "partial support,"
- "needs verification,"
- or "direct support candidate visible"

instead of pretending that a retrieved DOI automatically supports the paper.

### Phase 6 Similarity And Provenance Guard

Phase 6 has started with a deterministic similarity/provenance guard:

- `arda_os/backend/services/sophia_similarity_guard.py`
- `scripts/sophia_writing_desk_phase6_similarity_suite.py`

The guard currently detects:

- exact n-gram overlap,
- longest common sequence,
- token/construct overlap,
- source-span alignment,
- citation presence,
- near-paraphrase risk,
- citation-needed overlap,
- shared terminology,
- and acceptable common academic phrases.

The language is deliberately cautious:

- use "similarity risk" rather than unsupported plagiarism accusation,
- use "source support unavailable" when no source corpus exists,
- use "needs verification" where metadata or source fit is incomplete,
- and protect common academic phrases from high-risk false positives.

The current repair-without-rewriting menu includes:

- cite,
- quote with attribution,
- paraphrase with attribution,
- narrow claim,
- add limitation,
- convert assertion to question.

This is important for academic integrity: Sophia can guide the human author
toward a lawful repair without writing the final submission for them.

### Voice And Realtime UI

The Presence UI currently runs at:

`http://localhost:7070`

The server now auto-loads known local env files without printing secret values.
On the latest live health check:

- Gemini was configured,
- ElevenLabs was configured,
- transcription was ready,
- Ollama was connected,
- Mandos was available,
- and the covenant state was sealed.

The low-quality browser/system voice fallback has been removed. If ElevenLabs
is unavailable or capped, Sophia now remains silent and shows the response on
screen rather than switching to a robotic local voice.

This was a deliberate quality decision:

> ElevenLabs or silence is better than breaking presence with a bad fallback
> voice.

### Evidence And Test Results

The strongest pre-existing governance result remains the frozen six-provider
matrix:

| Metric | Pre-fix | Post-fix | Effect |
| --- | ---: | ---: | ---: |
| Contract passes | 512/576 | 546/576 | +34 rows |
| False releases | 21/576 | 0/576 | -21 rows |
| False holds | 43/576 | 30/576 | -13 rows |
| Inherited-denial rows | 27/48 | 48/48 | +21 rows |
| Missing-provenance rows | 18/48 | 48/48 | +30 rows |

The paired statistical evidence from the mirrored matrix:

| Outcome | Corrected rows | New regressions | Exact McNemar p |
| --- | ---: | ---: | ---: |
| Contract pass | 52 | 18 | 0.0000585 |
| False release | 21 | 0 | 0.000000954 |
| False hold | 31 | 18 | 0.0854 |

The newer Writing Desk and pedagogy gates are:

| Gate | Result | What It Shows |
| --- | ---: | --- |
| Phase 5 core pedagogy | 8/8 | Office routing and high-signal pedagogical differentiation pass. |
| Phase 5 UI static | 14/14 | Pedagogy controls render, structured plan displays, and browser voice fallback is absent. |
| Phase 5 wider adaptation | 100/100 | Office matching, lens completeness, novice scaffolding, ipsative signaling, and authorship safety pass across the stratified suite. |
| Phase 5 ipsative improvement | 3/3 | `improved`, `stable_unresolved`, and `regressed_or_new_risk` classify correctly. |
| Phase 6 similarity/provenance slice | 7/7 | Exact overlap, cited overlap, paraphrase, terminology, common phrase, no-source, and independent synthesis cases pass. |
| Phase 6 false accusation cases | 0 | The guard did not overstate similarity as misconduct in the tested cases. |
| Phase 6 high-risk span failures | 0 | Every high-risk flag in the suite included a visible source span. |
| Live Writing Desk Phase 5 probe | Pass | `supervisor`, `ipsative`, project state `ok`, office-shaped response. |
| Live Writing Desk Phase 6 probe | Pass | Seeded source pool produced high exact-overlap risk, source span, and repair options through `/api/speak`. |

Primary recent evidence reports:

- `evidence/SOPHIA_PHASE5_PEDAGOGICAL_ADAPTIVITY_CLOSEOUT_20260802T2018Z.md`
- `evidence/SOPHIA_PHASE5_PEDAGOGICAL_ADAPTIVITY_CLOSEOUT_20260802T2018Z.zip`
- `evidence/SOPHIA_PHASE6_SIMILARITY_PROVENANCE_START_20260802T2026Z.md`
- `evidence/SOPHIA_PHASE6_SIMILARITY_PROVENANCE_START_20260802T2026Z.zip`
- `evidence/SOPHIA_WORLD_CLASS_WRITING_DESK_IMPLEMENTATION_PLAN_20260802T155106Z.md`

### Sophia Capability Scorecard

The following scorecard is an engineering judgment based on the local code,
live probes, and evidence artifacts. It should not be read as a claim of
external certification.

| System Area | Before Current Push | Current Score | Evidence Basis | Remaining Weakness |
| --- | ---: | ---: | --- | --- |
| Denial boundary / false-release control | 7.2/10 | 9.3/10 | Frozen 576-row six-provider matrix reached 0 false releases. | Generalization beyond frozen matrix still needs continuing red-team work. |
| Constitutional conformity | 7.5/10 | 8.9/10 | Mandos, article conformity checks, release/repair telemetry, denial-family correction. | Needs more independent human/LLM judge panels. |
| Pedagogical adaptivity | 5.8/10 | 9.2/10 | Phase 5 core 8/8, wider adaptation 100/100, office-shaped responses, ZPD/Bloom/lens telemetry. | Real classroom learning outcomes are not proven. |
| Assessment ecology | 6.2/10 | 8.9/10 | Baseline/diagnostic/formative/criterion/reflective/ipsative layers now visible in Writing Desk. | Needs longer longitudinal learner history and outcomes validation. |
| Ipsative learner support | 3.5/10 | 8.6/10 | Intervention ledger, repeated weakness tracking, 3/3 ipsative movement suite. | Current improvement scoring is issue-label based, not full semantic draft comparison. |
| Academic writing assistance | 5.5/10 | 8.8/10 | Writing Desk line selection, claim map, feedback modes, repair moves, authorship boundary. | Needs deeper whole-paper structural review and more nuanced disciplinary variation. |
| Source discovery and ranking | 5.0/10 | 7.8/10 | Query improvements, source-support map, provenance boundaries, citation candidates. | Still needs stronger live scholarly retrieval ranking and page-anchored verification. |
| Source-to-claim entailment | 5.5/10 | 8.0/10 | Source support bridge, direct/partial/background/contradiction labels, visible span rule. | Needs broader entailment benchmark and stronger semantic model tier. |
| Similarity/provenance guard | 3.0/10 | 7.6/10 | Phase 6 deterministic guard 7/7, false accusations 0, high-risk span failures 0. | Full 200-row suite and embedding similarity are not complete. |
| Multimodal/document intelligence | 4.5/10 | 6.8/10 | OCR/document extraction installed and usable; document evidence spans feed Writing Desk. | Native OCR disagreement, tables, figures, page anchors remain under-tested. |
| Project memory separation | 4.0/10 | 8.7/10 | Project store, active document reset, contamination checks, intervention ledger. | Needs larger multi-project contamination suite after Phase 6/7 changes. |
| UI academic workflow | 4.8/10 | 8.5/10 | Writing Desk, buttons, structured cards, source-support map, similarity card, voice fallback removed. | Side-by-side comparison and more polished visual ergonomics remain. |
| Voice and realtime presence | 5.0/10 | 7.4/10 | ElevenLabs configured, browser fallback removed, transcription ready. | ElevenLabs quota/caps and browser mic permissions remain operational constraints. |
| Auditability / evidence chain | 6.5/10 | 9.0/10 | Markdown reports, zipped bundles, JSON artifacts, checkpointed matrices, live probes. | Needs external reproducibility package and blinded evaluator protocol. |

Overall current Sophia estimate:

| Dimension | Score |
| --- | ---: |
| Integrity safety under tested conditions | 9.3/10 |
| Pedagogical usefulness in Writing Desk | 9.0/10 |
| Academic source/provenance rigor | 8.0/10 |
| Multimodal readiness | 6.8/10 |
| UI usability for real writing sessions | 8.4/10 |
| External academic defensibility | 8.2/10 |
| Overall Sophia system | 8.6/10 |

### Honest Current Judgment

Sophia is now meaningfully stronger than the system that began this update
cycle. The central improvement is not one feature. It is the integration of
constitutional governance, pedagogy, project memory, provenance discipline, and
repair-oriented writing support into a single workflow.

What is now genuinely strong:

- denial-boundary behavior in the frozen matrix,
- authorship-preserving pedagogy,
- visible pedagogical offices,
- project-scoped Writing Desk memory,
- ipsative feedback,
- source-support humility,
- similarity risk language,
- and auditable evidence packaging.

What remains the main risk:

- Sophia can still be too conservative in ambiguous educational-help cases,
- multimodal robustness is not yet at the same evidence level as text,
- source retrieval quality still depends on available providers and metadata,
- semantic similarity is currently proxy-based rather than embedding-backed,
- and external validation by blinded human evaluators is still needed.

In short:

> Sophia is no longer merely a constitutional chatbot. She is becoming a
> governed academic integrity and pedagogy companion. The evidence now supports
> that claim locally, while still leaving clear boundaries around generalization,
> multimodal proof, and external academic validation.

### Sophia Upgrade Campaign Timeline

The current Sophia state came through multiple upgrade cycles rather than one
patch. The main implementation plan is:

- `evidence/SOPHIA_WORLD_CLASS_WRITING_DESK_IMPLEMENTATION_PLAN_20260802T155106Z.md`

The table below summarizes the major cycles and their evidence.

| Cycle | Status | Main Change | Validation / Evidence |
| --- | --- | --- | --- |
| Initial honest assessment | Complete | Assessed Sophia as strong on constitutional safety but weak on adaptive pedagogy, multimodal proof, source ranking, and response specificity. | `evidence/SOPHIA_HONEST_ASSESSMENT_AND_EVIDENCE_REPORT_20260730T2000Z.md` |
| Systems improvement push | Complete | Strengthened telemetry, judge/audit framing, evidence handling, and system-level gap analysis. | `evidence/SOPHIA_SYSTEMS_IMPROVEMENT_PUSH_20260730T2033Z.md`; `evidence/SOPHIA_GAP_PUSH_20260730T2035Z.md`; `evidence/SOPHIA_TELEMETRY_JUDGE_PUSH_20260730T2042Z.md` |
| Stratified judge and multimodal push | Complete | Added larger stratified suites, raw/repaired/released separation, judge-panel scaffolding, and multimodal/OCR hardening direction. | `evidence/SOPHIA_STRATIFIED_JUDGE_MULTIMODAL_PUSH_20260730T2020Z.md` |
| Remote matrix gauntlet | Complete | Built and ran the multi-provider matrix across remote models with mutations, ablations, denial cases, faults, and checkpointing. | `evidence/SOPHIA_REMOTE_MATRIX_GAUNTLET_REPORT_BUNDLE_20260731T0525Z.zip` |
| Denial-boundary correction | Complete | Fixed inherited-denial expectations, false-release scoring, mutation handling, A0/A9 ablations, and checkpoint behavior. | `evidence/SOPHIA_DENIAL_BOUNDARY_AND_CHECKPOINT_PUSH_20260731T0539Z.md` |
| Frozen 576-row rerun | Complete | Repeated the frozen six-provider matrix after the denial-boundary intervention without broadening cases. | `evidence/SOPHIA_FROZEN_576_POST_FIX_RERUN_20260731T0811Z.md` |
| Paired statistical comparison | Complete | Compared pre/post matrix rows with paired transition counts and exact McNemar tests. | `evidence/SOPHIA_PRE_POST_PAIRED_STATISTICAL_COMPARISON_20260731T0830Z.md` |
| Clean-next-matrix preflight | Complete | Prepared the next clean matrix after multimodal, false-hold, and teaching improvements. | `evidence/SOPHIA_CLEAN_NEXT_MATRIX_PREFLIGHT_20260731T0910Z.md` |
| Three-run academic comparison | Complete | Compared baseline, post-fix, and later clean matrix evidence for academic reporting. | `evidence/SOPHIA_THREE_RUN_ACADEMIC_MATRIX_COMPARISON_20260731T1745Z.md` |
| Final system breakdown before Writing Desk campaign | Complete | Produced a whole-system Sophia judgment and remaining weakness map before the UI/pedagogy push. | `evidence/SOPHIA_FINAL_SYSTEM_BREAKDOWN_ASSESSMENT_20260731T1815Z.md` |
| Writing Desk Phase 1 | Complete | Hardened reliability and UX: state indicators, scope selector, shortcuts, request locking, autosave, compact/detailed mode, structured backend fields, and route verification. | `evidence/sophia_writing_desk_phase1_smoke_latest.json`: 50/50 structured responses, 0 source-scout misroutes, 0 review misroutes, 0 generic greetings. |
| Writing Desk Phase 2 | Complete core slice | Added inline annotation layer, line-linked cards, filters, Claim Inspector, annotated preview, table/list segmentation, deterministic issue labels, and rich-editor highlight support. | `evidence/sophia_writing_desk_phase2_annotations_latest.json`: 30 cases, 86.67% expected-label match, 100% line-range presence, 0 plagiarism accusations without evidence. |
| Writing Desk Phase 3 | Advanced active slice | Implemented source-grounded claim support inspired by the merger system: source ranking, source roles, support labels, citation candidates, DOI/URL extraction, metadata enrichment, page honesty, entailment warnings, and export formats. | Phase 3 artifacts include `sophia_writing_desk_phase3_source_support_latest.json`, `phase3_citation_hygiene`, `phase3_ranking_quality`, `phase3_export_semantic`, `phase3_metadata_enrichment`, `phase3_entailment_scoring`; main support slice reached 120/120, 0 false supports. |
| Writing Desk Phase 4 | Complete core slice | Made evidence ledgers first-class: durable project store, project IDs, draft versions, uploaded documents, claim ledger, intervention ledger, source pool, contamination report endpoint, and project dashboard. | `evidence/sophia_writing_desk_phase4_ledger_static_latest.json`: 28/28; `evidence/sophia_writing_desk_phase4_project_store_latest.json`: 8/8; live project endpoint probe passed with 0 contamination signals. |
| Writing Desk Phase 5 | Complete | Added pedagogical offices, ZPD/Bloom/Barrett/Facione/Feuerstein/De Bono/Costa/Knowles/Mezirow/Torrance planning, office-shaped prose, project-level intervention memory, and ipsative draft-movement scoring. | `evidence/SOPHIA_PHASE5_PEDAGOGICAL_ADAPTIVITY_CLOSEOUT_20260802T2018Z.md`; core 8/8, UI 14/14, adaptation 100/100, ipsative 3/3. |
| Writing Desk Phase 6 slice 1 | Started and validated | Added deterministic similarity/provenance guard, overlap categories, repair-without-rewriting menu, UI similarity card, common-phrase protection, and cautious policy language. | `evidence/SOPHIA_PHASE6_SIMILARITY_PROVENANCE_START_20260802T2026Z.md`; similarity suite 7/7, false accusation cases 0, high-risk span failures 0. |

The upgrade campaign therefore has two intertwined tracks:

- governance proof: matrix gauntlets, denial-boundary repair, remote-provider
  comparison, false-release/false-hold measurement, and evaluator/judge
  scaffolding;
- academic workflow construction: Writing Desk Phases 1-6, moving from a chat
  assistant toward an auditable academic integrity and pedagogy environment.

### Writing Desk Phase Status

| Phase | Status | Target | Current Evidence |
| --- | --- | --- | --- |
| Phase 1: Reliability and UX Hardening | Complete | Make the desk dependable enough for daily use. | 50/50 smoke pass; 0 misroutes; 0 generic greetings. |
| Phase 2: Inline Annotation Layer | Complete core slice | Move from chat feedback to line-linked academic markup. | 30-case suite; 86.67% label match; 100% line-range presence. |
| Phase 3: Source-Grounded Claim Support | Advanced active slice | Map selected claims to source spans with citation and provenance discipline. | 120/120 source-support slice; 0 false supports; metadata/citation/export suites added. |
| Phase 4: Evidence Ledger Infrastructure | Complete core slice | Make claims, warrants, limitations, source spans, and interventions durable. | 28/28 static; 8/8 project store; live contamination proof passed. |
| Phase 5: Pedagogical Adaptivity and Offices | Complete | Make Sophia visibly pedagogical and adaptive. | 8/8 core; 14/14 UI; 100/100 adaptation; 3/3 ipsative. |
| Phase 6: Similarity, Provenance, Integrity Hardening | Started | Harden similarity and provenance without false misconduct claims. | Slice 1 7/7; 0 false accusations; 0 high-risk span failures. |
| Phase 7: Multimodal and Document Intelligence | Planned / partial precursor work | Make PDFs, OCR, tables, figures, pages, and screenshots auditable. | OCR/document extraction exists, but full OCR-disagreement and page-anchor gates remain. |
| Phase 8: Full Auditability and Academic Proof | Planned | Package a defensible academic proof chain with external evaluation. | Existing reports/bundles are substantial, but blinded human panels and inter-rater reliability remain future work. |

### 3. Deterministic Security Substrate

This layer compiles policy, stages measured identity, evaluates status, and
projects state into the enforcement plane.

It is where ARDA becomes machine-verifiable instead of merely descriptive.

Primary capabilities:

- policy bundle generation,
- projection plan generation,
- measured manifest build and lifecycle,
- bootstrap and rescue flows,
- os-grade and readiness gates,
- TPM capture verification plumbing.

Primary artifacts:

- `arda_os/bin/arda`
- `arda_os/bin/arda_os_grade_gate.py`
- `arda_os/bin/arda_bootstrap_verify.py`
- `arda_os/bin/arda_rescue_mode.py`
- `arda_os/backend/services/measured_identity.py`
- `arda_os/backend/services/arda_kernel_projection.py`

### 4. Ring-0 Enforcement

This is the layer that matters most for the central claim.

ARDA uses BPF LSM-based enforcement and pinned maps so that enforcement state
exists in a kernel-authoritative plane rather than only in user-space memory.

Current enforcement modes visible in the code and gates:

- `audit`
- `legacy_inode`
- `fsverity_strict`

Primary artifacts:

- `arda_os/backend/services/os_enforcement_service.py`
- `arda_os/backend/services/bpf/arda_physical_lsm.c`
- `arda_os/backend/services/bpf/arda_lsm_loader.c`

## The Valinor Track

Valinor is the kernel track for ARDA.

Its purpose is to make ARDA less dependent on a host kernel that merely happens
to expose enough features, and more like a reproducible kernel flavor built to
carry ARDA's contract intentionally.

Valinor focuses on:

- required BPF and BPF LSM support,
- explicit LSM ordering,
- TPM support,
- fs-verity support,
- EFI runtime support,
- workstation graphics viability,
- boot-chain integration,
- and post-boot validation.

Valinor is documented separately in:

- `arda_os/kernel/valinor/README.md`

## Current Proven State On This Workstation

This repository is not only aspirational. A meaningful portion is already live.

On this workstation, ARDA has already demonstrated all of the following in real
operation:

- a custom `6.12.96-valinor` kernel booted on real hardware,
- working `i915` graphics and `/dev/dri` on the good Valinor line,
- active BPF LSM in the live LSM chain,
- pinned authoritative maps,
- non-empty projected policy state,
- blocking enforcement outside audit mode,
- measured identity manifests built and activated,
- `fsverity_strict` capability present in the lifecycle and readiness model,
- TPM quote capture and verification artifacts present,
- rescue and bootstrap flows wired and runnable,
- software OS-grade milestone reached by the repository's own gate.

Sophia has also now produced a substantial remote-provider governance evidence
chain.

The key frozen matrix comparison is:

- pre-fix baseline: `evidence/matrix_gauntlet/matrix_gauntlet_20260731T051731Z_8da0329ce594d4c5.json`
- post-fix rerun: `evidence/matrix_gauntlet/matrix_gauntlet_20260731T081118Z_967430909abbee15.json`
- paired statistical report: `evidence/SOPHIA_PRE_POST_PAIRED_STATISTICAL_COMPARISON_20260731T0830Z.md`

The post-fix rerun repeated the same 576 mirrored rows across six live remote
providers:

- Cohere,
- NIM,
- Gemini,
- Mistral,
- Groq,
- Novita.

The frozen rerun result:

| Metric | Pre-fix | Post-fix | Effect |
| --- | ---: | ---: | ---: |
| Contract passes | 512/576 | 546/576 | +34 rows |
| False releases | 21/576 | 0/576 | -21 rows |
| False holds | 43/576 | 30/576 | -13 rows |
| Inherited-denial rows | 27/48 | 48/48 | +21 rows |
| Missing-provenance rows | 18/48 | 48/48 | +30 rows |

Because the rows are paired exactly, the strongest statistics are paired
transition tests rather than unpaired aggregate comparisons:

| Outcome | Corrected rows | New regressions | Exact McNemar p |
| --- | ---: | ---: | ---: |
| Contract pass | 52 | 18 | 0.0000585 |
| False release | 21 | 0 | 0.000000954 |
| False hold | 31 | 18 | 0.0854 |

The core safety result is therefore strong:

> Sophia reached zero false releases across the frozen 576-row six-provider
> matrix after the denial-boundary intervention.

The important utility caveat is also clear:

> Sophia still has 30 false holds, concentrated in non-denial educational
> assistance cases rather than unsafe releases.

Those remaining false holds cluster mainly in:

- `evidence_overclaim`,
- `authorship_substitution`,
- `citation_entailment`,
- `ambiguous_plagiarism`.

The best current interpretation is that Sophia's denial boundary is now strong
in the tested matrix, but her helpfulness calibration is still too conservative
around lawful educational assistance that sounds semantically or adversarially
risky.

That last point matters.

The `os-grade` gate explicitly checks whether ARDA has crossed from a
kernel-authoritative prototype into software OS-grade posture. The gate logic
tracks:

- `blocking_mode`
- `non_empty_policy_state`
- `measured_identity_active`
- `fsverity_strict_live`
- `authoritative_bpf`
- `deny_telemetry_available`
- `lockdown_available`

When those software conditions are satisfied, the gate reports:

`boundary: "software OS-grade milestone"`

This is not a marketing phrase. It is a concrete internal boundary in the
repository's own readiness logic.

## What Is Still Incomplete

The software milestone is real, and the hardware-rooted milestone was also
reached on bare metal on July 29, 2026 and frozen again on July 30, 2026.

The remaining work is therefore not "prove that ARDA can become real." The
remaining work is to harden, operationalize, and package the already-real
substrate:

- off-box verifier deployment on a second trusted machine,
- stricter recovery, rollback, and revocation drills,
- reproducible release and attestation workflow cleanup,
- stale-proof and fail-closed production operations hardening,
- desktop/session identity finishing,
- and distribution/installer polish for sovereign image release.

Sophia also has unfinished work.

What is now strongly supported:

- zero false releases in the frozen six-provider 576-row matrix,
- 48/48 inherited-denial rows passing after the parent-denial contract fix,
- 48/48 missing-provenance rows passing after safe scaffold recalibration,
- stable clean performance in policy, reasoning, boundary, office,
  completeness, infrastructure, and denial risk families,
- checkpointed matrix execution with a complete 576/576 checkpoint.

What is not yet proven:

- that zero false releases generalizes beyond this frozen matrix,
- that multimodal OCR-disagreement and native image/document tests are equally
  robust,
- that blinded human evaluators agree with the deterministic Mandos scoring,
- that inter-rater reliability is high across human and LLM judge panels,
- that Sophia can reduce false holds without weakening the denial boundary,
- or that NIM is operationally suitable for unsharded long matrix runs.

The current Sophia weakness is not primarily unsafe release. It is conservative
over-holding at the boundary between academic-integrity refusal and legitimate
pedagogical assistance.

In other words:

- software OS-grade: achieved,
- hardware-rooted OS-grade on bare metal: achieved,
- off-box verifier separation: scaffolded but not yet fully deployed,
- sovereign distribution/image lane: actively being operationalized.

That distinction is still essential to understanding the project honestly: the
substrate is real, but production operations and release packaging are still
unfinished.

## Bare-Metal Sovereignty Milestones

The most important repository fact is not theoretical. ARDA already crossed its
own sovereignty boundary on real hardware, and that happened before the current
distribution/ISO work began.

The decisive bare-metal milestones are frozen here:

- `arda_os/kernel/valinor/HARDWARE_ROOTED_OS_GRADE_MILESTONE_2026-07-29.md`
- `arda_os/kernel/valinor/REBOOT_CHECKPOINT_2026-07-30.md`
- `arda_os/deploy/OFFBOX_VERIFIER_DEPLOYMENT.md`

### July 29, 2026: Hardware-Rooted OS-Grade On Real Hardware

On Wednesday, July 29, 2026, ARDA on the Valinor kernel crossed the
repository's full hardware-rooted OS-grade production milestone on bare metal.

This was not merely a software pass. The live workstation simultaneously showed:

- booted custom kernel `6.12.96-valinor`,
- EFI Secure Boot visible from the running kernel,
- lockdown enforced from EFI Secure Boot,
- `efivarfs` mounted and readable,
- `mokutil --sb-state` returning `SecureBoot enabled`,
- UEFI boot entries readable through `efibootmgr`,
- signed kernel acceptance verified,
- fresh TPM quote evidence accepted,
- active measured identity in `fsverity_strict`,
- and `arda os-grade --json` returning
  `boundary: "hardware-rooted OS-grade production milestone"`.

That boundary is the repository's own internal definition of a real
hardware-rooted success state.

### July 30, 2026: Fully Green Sovereign Checkpoint

On Thursday, July 30, 2026, that hardware-rooted state was not only re-seen; it
was frozen in a stronger sovereign checkpoint with a fresh verifier-signed
verdict for measured generation `112`.

At that checkpoint the live machine had:

- `ok: true`
- `software_os_grade: true`
- `hardware_rooted_os_grade: true`
- `signed_verdict_present: true`
- `remote_verifier_signed_fresh: true`
- `signed_verdict_green: true`

And the live sovereign properties included:

- Secure Boot visible and enabled,
- manufacturer-rooted TPM identity,
- fresh verified TPM quote,
- PCR11 bound to live ARDA software state,
- active measured generation `112`,
- active manifest `measured-d8383a1c3548228d`,
- live `fsverity_strict` measured enforcement,
- non-empty constitutional redline state with `7` rules,
- confidentiality lockdown active in the kernel command line,
- and a stable boot audit lane with `lightdm.service` and
  `getty@tty1.service` active.

The accepted verifier result at that checkpoint also showed:

- `trust_mode: manufacturer-rooted-quote`
- `manufacturer: Nuvoton (NTC)`
- `ak_certified_by_ek: true`
- `signature_algorithm: ed25519`
- `authorized_states: observe, enforce, lockdown, rescue`

This matters because it means ARDA was no longer only proving
"a hardened host can run some interesting code." It was proving:

- a custom Secure-Booted kernel,
- EFI visibility,
- TPM-backed attestation,
- measured identity,
- constitutional enforcement state,
- and verifier-signed acceptance

all at the same time on bare metal.

### What Was Actually Achieved

The honest statement is now stronger than the older summary above:

> ARDA did achieve its own bare-metal sovereignty milestone on real hardware.

What remained incomplete after that was not the reality of the substrate. What
remained incomplete was:

- off-box verifier deployment on a second trusted machine,
- production operations cleanup,
- recovery/revocation drills,
- release repeatability,
- and distribution-quality image/install polish.

So the repository should be read in this order:

1. bare-metal sovereignty on Valinor: achieved,
2. signed same-host verifier flow: achieved,
3. off-box verifier separation: scaffolded, not yet fully deployed,
4. sovereign live ISO and installer path: actively being operationalized now.

## Secure Boot And TPM Honesty Note

Secure Boot and TPM work in this repository are serious, but messy in the real
world because firmware and EFI runtime behavior are inconsistent across kernels.

What has already been shown:

- firmware Secure Boot was re-enabled on the machine,
- the Valinor kernel image was manually signed and verified with `sbverify`,
- MOK enrollment and shim state were investigated directly,
- TPM quote verification artifacts were captured and verified,
- EFI runtime visibility was shown to differ across kernel variants,
- a `valinor3` rebuild was initiated specifically to correct EFI runtime
  support on the Valinor path.

What has not yet been cleanly closed:

- a final Valinor boot path where Secure Boot, shim validation, and EFI runtime
  visibility all line up cleanly from the live kernel itself.

That is why this project is credible: the repository does not pretend that a
half-working firmware story is a finished one.

## Readiness Ladder

The simplest honest maturity ladder for ARDA today is:

| Layer | Current status |
| --- | --- |
| User-space concept | Passed |
| Kernel integration | Passed |
| Kernel-authoritative enforcement | Passed |
| Persistent measured identity | Present and exercised |
| Signed policy projection | Present |
| Software OS-grade posture | Passed |
| Sophia frozen false-release safety | Passed in 576-row matrix |
| Sophia inherited-denial gate | Passed, 48/48 |
| Sophia missing-provenance scaffold gate | Passed, 48/48 |
| Sophia educational utility calibration | Partially passed; false holds remain |
| Sophia native multimodal proof | Not yet fully closed |
| Sophia blinded human evaluation | Not yet |
| Fresh hardware-rooted release proof | Not yet fully closed |
| Full standalone operating system distribution | Not yet |

Another way to say it:

- kernel subsystem readiness: serious and real,
- production security appliance readiness: emerging,
- standalone operating system readiness: underway, not finished.

## What Makes It Novel

ARDA is not novel because it uses one exotic primitive. Most of its pieces
already exist somewhere in the Linux security world.

What is unusual is the composition.

The repository tries to unify:

- constitutional refusal semantics,
- AI witness/advisory logic,
- signed policy bundles,
- measured executable identity,
- BPF LSM denial,
- TPM quote evidence,
- Secure Boot intent,
- kernel packaging,
- recovery/rescue posture,
- and operator-visible ceremonial state

into one continuous security story.

The project is most novel where it treats these as one chain of authority rather
than isolated features.

## Repository Map

These are the most important paths to understand first.

### Core operator surface

- `arda_os/bin/arda`
- `arda_os/bin/arda_os_grade_gate.py`
- `arda_os/bin/arda_bootstrap_verify.py`
- `arda_os/bin/arda_rescue_mode.py`

### Enforcement and measured identity

- `arda_os/backend/services/os_enforcement_service.py`
- `arda_os/backend/services/measured_identity.py`
- `arda_os/backend/services/arda_kernel_projection.py`
- `arda_os/backend/services/bpf/arda_physical_lsm.c`
- `arda_os/backend/services/bpf/arda_lsm_loader.c`

### Kernel track

- `arda_os/kernel/valinor/README.md`
- `arda_os/kernel/valinor/config.fragment`
- `arda_os/kernel/valinor/scripts/`
- `arda_os/kernel/valinor/releases/systemd/`

### Constitutional and advisory layer

- `arda_os/backend/services/coronation_schemas.py`
- `arda_os/backend/services/ainur/`
- `arda_os/backend/services/assessment_ecology.py`
- `arda_os/backend/services/presence_server.py`
- `arda_os/backend/services/mandos_protocol_judge.py`
- `scripts/sophia_matrix_gauntlet.py`
- `evidence/SOPHIA_PRE_POST_PAIRED_STATISTICAL_COMPARISON_20260731T0830Z.md`
- `evidence/SOPHIA_FROZEN_576_POST_FIX_RERUN_20260731T0811Z.md`

### Demonstration and operator UX

- `arda-sovereign-website/`
- `arda_os/arda_desktop/`

## Running ARDA

There is no single correct entrypoint because the repository spans desktop,
kernel, policy, and validation work.

Common starting points:

### Desktop demonstration

The website and desktop surfaces show the operator-facing model and ceremonial
identity of the system.

### Operator CLI

The main control plane is:

```bash
cd arda_os
./bin/arda --help
```

### Valinor kernel flow

For kernel work, start here:

```bash
sed -n '1,220p' arda_os/kernel/valinor/README.md
```

## Current Recommended Interpretation

If you want the shortest honest answer to "what is this?", it is this:

ARDA is a serious attempt to build a constitutional, kernel-authoritative
security substrate for AI-capable systems.

Sophia is the most developed user-facing demonstration of that idea: an
integrity-governed assistant whose outputs are constrained by local law,
evidence, pedagogy, and release judgment rather than by raw model fluency alone.

It is no longer just a user-space idea.

It already demonstrates real authority in the kernel, real policy projection,
real measured identity handling, real TPM evidence plumbing, and a custom kernel
track on real hardware.

It is not yet finished as a full hardware-rooted operating system release.

Sophia is not yet a finished academic-integrity proof for every context, but she
has now passed a serious frozen remote-provider safety rerun: zero false
releases across 576 paired post-fix rows.

That is the right way to read the repository in its current state.

## Near-Term Next Milestones

The highest-value next milestones are:

1. Finish the corrected `valinor3` kernel build with stable EFI runtime
   visibility.
2. Boot the corrected Valinor line and confirm Secure Boot, EFI variables, and
   shim validation visibility from the live kernel path.
3. Re-run fresh TPM capture and bind it to release gating as current evidence.
4. Prove measured enforcement, signed policy state, and blocking posture across
   reboot without falling back to audit.
5. Harden recovery, rollback, revocation, and stale-generation refusal into a
   repeatable operator flow.
6. Reduce Sophia's false holds in lawful educational-assistance cases without
   weakening the inherited-denial contract.
7. Run native multimodal tests with OCR disagreement, document ambiguity, and
   source-quality ranking stressors.
8. Add blinded human and LLM-judge panels with inter-rater reliability over raw,
   repaired, and released Sophia responses.
9. Run NIM as a separate shard or provider-specific job in future large matrix
   sweeps to prevent long-tail latency from dominating the artifact.

## Final Honesty Statement

This repository should not be read as "an AI desktop with lore".

It should be read as:

- a security substrate project,
- a kernel-parity project,
- an enforcement-authority project,
- a measured identity and attestation project,
- and only secondarily as a desktop or website experience.

The Tolkien language is symbolic dressing over a real systems effort.
The symbols matter because they give the system a coherent constitutional and
operator vocabulary. But the project stands or falls on whether the machine can
refuse, measure, attest, recover, and remain authoritative under compromise.

For Sophia specifically, the project stands or falls on whether she can assist
human thinking without replacing it. The latest evidence is encouraging: her
release boundary is now much stronger. The remaining work is to make her more
gracefully helpful in lawful pedagogy while keeping that boundary intact.

That is what ARDA is trying to become, and a meaningful portion of that is
already real.
