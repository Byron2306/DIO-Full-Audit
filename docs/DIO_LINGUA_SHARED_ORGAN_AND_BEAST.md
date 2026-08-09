# DIO Lingua Shared Organ And BEAST Audit

## Working Architecture

```text
HOMS / Sophia / Evidex / VAMP / NicheFoundry / Market / Lilith / Document Studio
  -> versioned source artifact
  -> typed semantic units and source hashes
  -> optional language lane
  -> provider draft and deterministic QA
  -> unit corrections and flag dispositions
  -> proficient reviewer approval
  -> BEAST semantic credits
  -> DIO Format Core profile projection
  -> downstream document, email, slide, caption, transcript or video projection
```

`config/lingua_product_routes.json` is the route matrix. It defines supported artifacts, required context, channels and authority boundaries. `scripts/register_product_lingua_object.py` registers an existing product artifact without translating it. A later target-language job adds a lane to the same object instead of creating a disconnected document.

The current proof registers real artifacts from:

- HOMS learner guide;
- Sophia reviewer commentary;
- Evidex evidence narrative;
- VAMP review snapshot;
- NicheFoundry narration/campaign copy;
- Document Studio multilingual procedure.

Public HOMS, Sophia, Evidex and VAMP intake forms now carry source language, requested output language and the proficient-review requirement. NicheFoundry and Market consume approved meaning internally for captions, narration, ads and campaign copy.

Format Core consumes the same versioned meaning rather than translating a finished document. It applies style, language and delivery profiles to typed blocks, then generates DOCX, PDF, PPTX, accessible HTML and VTT outputs. Exact-unit source hashes stop stale translated blocks before rendering. See `docs/DIO_FORMAT_CORE.md`.

## Operator Approval

The Control Deck **Lingua QA** tab is the authority surface. Each language lane opens one workspace containing:

- source and reviewed target text side by side;
- an editable target unit;
- every provider or deterministic QA flag;
- required `accepted_as_is`, `corrected`, or `not_applicable` disposition;
- a reviewer note per flag;
- one meaning-approved checkbox per unit;
- reviewer name and proficient role;
- separate save and final crystallisation actions.

Final approval fails closed when a source hash changes, a unit is missing, target text is empty, any unit is unchecked, or any material flag remains unresolved. The four controlled water-procedure lanes have passed this route and created 28 reviewer-bound translation-unit credits.

Semantic approval updates Lingua QA to `semantic_approved`. It does not collapse other authorities. Document Studio remains `linguistic_approved_pending_remaining_review` until its technical-editor, client and delivery gates are separately satisfied.

## BEAST Audit

Before this change the DIO bridge used only two EdgeK-BEAST organs:

- `DurableInferenceStorage` for semantic credits;
- `CrystalChainLedger` for tamper-evident events.

That preserved data but did not exercise BEAST as a learning system. The active bridge now also uses:

| BEAST organ | DIO Lingua use |
|---|---|
| EvidenceScorer | Explainable severity, repetition, verification and blast-radius scores |
| EvidenceChronicleWriter | Durable high-value quality observations |
| NegativeCapabilityStore | A failure pattern activates only after three repeated observations and can recover after clean outcomes |
| CapabilityLearningLedger | Tracks fresh work, exact reuse, provider calls avoided and authority state |
| MemoryHull | Human-readable, sealed decision residue with verification |
| PRECLifecycleStore | Perceive, reason, economise and crystallise trace for each bridge operation |
| DurableInferenceStorage reuse/stale APIs | Exact approved-unit reuse accounting and source-hash quarantine |

Current operational evidence after replaying the controlled packs:

- 22 capability-learning events;
- 13 quality observations still in `observing`, with zero falsely active negative capabilities;
- 13 verified Memory Hull sidecars and zero failed seals;
- 13 completed PREC lifecycles;
- 28 human-authorised translation-unit credits;
- one exact approved Setswana replay that reused seven units and displaced a provider call;
- a valid crystal chain.

The shared SQLite base store also leaked handles because Python's SQLite context manager commits without closing. EdgeK-BEAST now returns a closing connection type; 47 focused BEAST tests pass and DIO's integration test passes with `ResourceWarning` treated as an error.

## Deliberate Non-Use

BEAST contains broader agent planning, source-plan promotion, code capability generation, distributed compute, Forge KV and operator-language semantic-crystal machinery. Those are not automatically appropriate here.

In particular, the operator-language crystal route encodes reusable conversational answer frames, not translation authority. Reusing it for target-language units would blur evidence type and authority. DIO instead integrates the general storage, evidence, lifecycle and failure-learning organs directly.

The next justified BEAST expansion is narrow:

1. Use semantic search for approved terminology suggestions, never silent replacement.
2. Attach policy, audience, curriculum and privacy fingerprints to reuse applicability.
3. Measure provider calls and tokens actually displaced by exact approved reuse.
4. Add cross-artifact consistency reports when one approved term appears in a document, slide, caption and email.
5. Promote recurring deterministic repair procedures only after held-out verification; do not promote translated meaning without reviewer authority.

## Commands

Register an artifact:

```bash
./.venv/bin/python scripts/register_product_lingua_object.py \
  --product homs \
  --artifact-type learner_guide \
  --artifact-id HOMS-G10-T3-MOTION-LEARNER-GUIDE \
  --semantic-object-id HOMS-G10-T3-MOTION-GUIDE \
  --source deliverables/homs_learning_studio/grade_10_physical_sciences_term_3_motion/documents/HOMS_G10_T3_MOTION_LEARNER_GUIDE.docx \
  --subject "Physical Sciences" --grade 10 --curriculum-concept "Motion in One Dimension"
```

Inspect BEAST organ state:

```bash
printf '{"operation":"status"}\n' | ./.venv/bin/python scripts/lingua_beast_bridge.py | jq
```

Use the Control Deck for review and approval:

```text
http://127.0.0.1:8765/ -> Lingua QA -> Review and approve / Inspect approval
```
