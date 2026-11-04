# Sonoris governed genre compiler — v1

Sonoris should treat genre as a compositional grammar of musical behavior. A genre is not just BPM, key, sounds, or a default verse/chorus template. It defines which gestures are plausible, how forms can evolve, how instruments interact, what articulation performs the gesture, and what production supports the physical effect.

## Compiler stages

1. Select a primary genre grammar and optional bounded secondary influence.
2. Compile a behavior plan: section form, gesture vocabulary, motif identities, harmonic behaviors, instrumental roles, articulation expectations, production behavior, and acceptance gates.
3. Realize the plan as notes, rhythms, instrument-specific articulation events, and interaction patterns.
4. Render the selected source-backed instruments and record provenance, license and processing receipts.
5. Measure the result against the primary grammar, reject missing hard requirements, revise the plan or realization, then request human listening review.

A plan is intent, not evidence. The audit interface returns `UNKNOWN` when measured evidence is missing and never treats successful MIDI rendering as proof that the music sounds or behaves like its genre.

## Governed blends

Every composition has one primary grammar. It owns form, section laws, core gesture distribution, harmonic center and acceptance constraints. A secondary grammar may contribute timbres, counter-gestures, instrument roles and production color up to the configured weight. The compiler does not average conflicting hard rules. It records the owner of each layer or rejects the unresolved conflict.

## Genre-specific laws

The initial catalog contains black metal, synthwave, jazz synth fusion, rock and ambient. These profiles deliberately differ:

- Black metal permits long trance repetition and through-composition without a conventional chorus. It values tremolo, chromatic minor motion, diminished/augmented fifths, blasts, double bass and transformed riff identities.
- Synthwave uses a recognizable pulse motor, bass and kick interaction, arpeggiated motif orbit, pad bloom, a build/drop behavior and production movement through saturation, chorus, delay and filter.
- Jazz fusion values pocket, extended harmony, displaced accents, motif development, improvisational orbit and instrumental handoffs.
- Rock prefers a verse/hook arc and guitar/bass/drum interlock while still permitting through-composition.
- Ambient permits free time and no beat, hook or chorus. Duration, timbral change, register, density and space can carry the form.

## Implementation

- Grammar catalog: `config/sonoris/genre_grammars_v1.json`
- Compiler: `products/sonoris_genre_compiler.py`
- Sonoris organ API wrappers: `products/sonoris_organ.py` (`genre_compiler_snapshot`, `compile_genre_composition`, `audit_genre_composition`)
- The existing Polly Music DNA feature validator remains useful for measurable numeric tendencies. The new compiler adds the missing form, gesture, role, articulation and blend governance layer around it.

This v1 compiles and audits composition plans. It does not yet automatically translate every genre plan into source-specific MIDI articulations; the black-metal renderer demonstrates a profile-specific rendering route, while other genre realizers remain to be bound.

## Concrete plan examples

The executable compiler produced four distinct plans in `media/sonoris/composition_plans/genre_examples_v1/`: synthwave, jazz fusion, rock, and ambient. They intentionally do not share one form: synthwave gets pulse/orbit/ascent/drop behavior, jazz gets pocket/fracture/orbit/handoff, rock gets verse and hook arcs, and ambient gets a slow transformation form with free time and no required beat or hook. These are plans only; their `evidence_state` says the audio has not been realized.

The black-metal track's plan is in `media/sonoris/releases/black_metal_where_pines_forget_v2/SONORIS_GOVERNED_COMPOSITION_PLAN.json`. Its renderer uses the plan's section and gesture schedule, then routes attacks through Metal-GTX's supported up/down sustain and mute patches, plus separate double-tracked performances. Its evidence report still requires human listening review.

CLI example:

```bash
python scripts/compile_sonoris_composition.py \\
  --genre ambient --title "Slow Orbit" --mood "spacious and suspended" \\
  --out /tmp/sonoris-ambient-plan.json
```
