# Sonoris: computational musical morphology gap map

## Thesis translated into an implementation model

Sonoris should plan a piece as a set of genre-specific structural laws, embodied gestures, motif identities, instrument interactions, and production intentions. A renderer then realizes that plan in playable notes and supported articulations. Tempo, scale, density, and timbre remain useful constraints and measurements; they are not the musical plan itself.

The new experimental profile at `config/sonoris/embodied_music_grammar_jazz_synth_fusion_v1.json` makes that separation concrete and contains the plan for **Glass Meridian**, a 44-bar jazz synth fusion prototype.

## What already exists in Polly

| Thesis area | Existing evidence | Current boundary |
|---|---|---|
| Gesture vocabulary | `fusion_lab/music_dna/riff_morphology.py` defines STOMP, SPRINT, PANIC, HOOK, TRANSITION, and TRANCE | Gesture analysis is riff/bar-centric and strongly shaped by metal note-event features |
| Riff identity and recurrence | `RiffSignature`, `RiffFamily`, family recurrence, longest run, and section contrast are modeled | Identity is inferred from a rhythm-guitar event stream rather than general phrase/ensemble behavior |
| Gesture scheduling | `chainsaw_diplomacy.py` assigns distinct riff families and gestures by section and bar | The schedule is authored into a fixed five-role thrash composition |
| Genre-specific profile data | `music_dna/genre_profiles.py` loads genre-specific ranges, categorical meters, components, and hard constraints | The profile is primarily statistical; its structural laws and interaction grammar are not general first-class data |
| Instrument rendering | SFZ profiles, articulation maps, MIDI generation, tone chains, stems, and manifests exist | Renderer roles and production path are fixed around two rhythm guitars, bass, drums, and lead guitar |
| Determinism and evidence | Seeds, hashes, structural signatures, profile manifests, and source receipts are available | They document a render well but do not represent the reasons a gesture was chosen or its intended interaction |

## The main architectural gap

Polly already has important pieces of your idea, especially riff morphology and an explicit thrash gesture schedule. The gap is not “add gestures”; it is to lift them above guitar-bar analysis and make a genre grammar govern a whole arrangement. The new planning layer should be instrument-neutral. It should express what a part does, what it interacts with, and how it changes over time; the selected instrument profile then declares which gestures and articulations it can realize.

### Recommended layers

1. **Genre grammar** — structural laws, allowed/required behaviors, contrast expectations, transition logic, and ensemble interaction rules. It can permit a chorus, through-composition, long trance, missing lead, or unusual meter when the genre profile allows it.
2. **Embodied arrangement plan** — sections and gesture arcs, with explicit energy, density, register, tension, duration, and arrival behavior.
3. **Motif morphology** — identities, phrase boundaries, transformations, callbacks, handoffs, and deliberate breaks. Similarity should use rhythm, contour, articulation, rests, and role behavior rather than a single note pattern.
4. **Instrument capabilities** — ranges, supported articulations, polyphony, attack/release behavior, expressive controls, and provenance. Instruments fulfill roles; roles do not dictate one instrument.
5. **Realization and production** — convert the plan to notes/events, route to the chosen renderer, apply instrument-valid articulation and production behavior, and emit stems plus provenance.
6. **Evaluation and review** — evaluate the result against its own genre grammar, inspect gesture and motif realization, then retain human sonic review as the final quality judgment.

## Evidence-led prototype plan

The jazz synth fusion profile gives a deliberately different structural law from thrash: no mandatory verse/chorus, a groove that may stay grounded through a contrasting section, and foreground handoffs between synth, saxophone, and flute. Its gesture arc is GLIDE → LOCK → FRACTURE → ORBIT → HANDOFF → LIFT → RELEASE. The 44-bar prototype uses separate motif identities and assigns bass, drums, and comping distinct ways to lock, push, interrupt, or leave space.

### V004 realization update

The owner has now rendered two V004 variants from the same V002 composition: `GLASS_MERIDIAN_V4_NO_SAX.wav` and `GLASS_MERIDIAN_V4_SAX_SUPPORT.wav`, and reports that V4 “slaps.” The V004 realization adds a sampled Rhodes with velocity asymmetry, chord rake, and phrase-timing drift; a tenor sax with expression, delayed vibrato, and legato controls; and a Virtuosity kit with instrument-specific microtiming, dynamic variation, and cymbal breath. Both candidate mixes measure about −20.5 LUFS integrated, 3.2 LU LRA, and −1.5 dBFS peak. The variants differ subtly at the sample level, so keep both pending the owner's final variant choice. The remaining electric bass, synth lead, and flute are still rendered through the temporary FluidR3 bridge in the next V005/V006 receipts. These new performances advance the instrument-capability thesis, while the fixed role bridge and still-unverified source-license receipts remain gaps.

The first rendered version is an authored prototype using the local FluidR3 General MIDI soundfont. It demonstrates the arrangement and interaction plan. It does not yet prove a reusable natural-language-to-composition engine, a high-fidelity acoustic instrument library, or a commercially cleared release. Those require a generalized composer/renderer bridge and listening review.

### V005 realization update — grunge quiet/loud contrast

The shared non-metal realizer now interprets grunge's `QUIET_VERSE`, `HEAVY_HOOK`, and `BREAKDOWN` gestures as distinct performance states. The quiet verse reduces guitar and bass density, sustains the harmony, removes the lead answer, thins hats to quarter notes, and uses a side-stick; hook and breakdown sections restore the full backbeat and higher energy. The Sonoris Studio API compiled and rendered the `Quiet Verse / Heavy Hook · Section Audited` candidate (`20261031T172416Z-e59b1cd4`) with sampled harmony, bass, lead, and drum stems. `/api/jobs/{job_id}/audit` exposes per-section event density, mean velocity, MIDI pitch counts, and authored articulations for both new jobs and older library entries. The measured event plan confirms section-level velocity and density differences. It remains a review candidate; the receipt's human listening review requirement is still in force.

### V006 realization update — gesture-aware dynamics and visible section audit

The shared realization path now maps form gestures such as `INTRODUCE`, `HOOK`, `DROP`, and `RELEASE` to measurable intensity changes, so the plan's section arc carries into part velocities. The Sonoris listening bench displays those measurements in a per-section table and retains the detailed JSON audit link. A live API compile and render produced `Verse / Hook Dynamic Arc` (`20261031T172742Z-28601c5e`): its hook harmony averages velocity 89 versus 80 in the verse, with the intro and release lower still. The same audit-generation path was compiled across all 23 genre profiles, with every generated event assigned to a section. This is arrangement evidence; it does not replace listening review or certify genre authenticity.

### V007 realization update — metal subgenre time-feel separation

The metal realization now gives several styles distinct performance behavior before note rendering: doom leaves a full bar for a sustained arrival; power metal gallops on its designated gallop gesture; folk metal defaults to compound 6/8 and a six-cell dance contour; industrial metal uses a quarter-note machine motor; nu metal leaves syncopated gaps around a half-time center; and glam metal uses a broad chord bed with an original pentatonic lead-answer vocabulary. Prog metal now defaults to 7/8, while its catalog still permits 4/4 and 5/4. The abstract study references remain provenance for genre behaviors, not source material for notes or melodies. These are code-level realization laws awaiting rendered-stem comparison and human listening review; the output should still be treated as a candidate until that review.

The live composition panel now shows each selected genre's default meter and preferred BPM alongside its allowed tempo bands. This makes the selected defaults legible before compile, including compound and asymmetric meters, while leaving the empty tempo/meter fields to resolve to the grammar's actual defaults.

### V008 realization update — resolved song-type defaults and live contrast candidates

The catalog now exposes resolved tempo, meter, and bar defaults for each genre and song type, and the live studio renders those values before compile. Two candidates were compiled and rendered through the persistent service: `Lanterns at the Longhouse` (`20261031T174346Z-13231a43`, folk metal, 6/8, sampled bagpipes) and `Sevenfold Tectonic` (`20261031T174346Z-0021b727`, prog metal, 7/8, sampled Rhodes). Their receipts and WAV/MP3 hashes are under `media/sonoris/studio_jobs/`; these confirm actual module routing and meter realization, not stylistic success.

### V009 realization update — folk/reed role handoff

Folk metal now gives the bagpipe or selected folk module a generated six-eighth-note phrase in 6/8 during `FOLK_THEME` and `DANCE_RETURN`; `HEAVY_RIFF` transfers the guitar answer to the foreground and keeps the reed to a section drone. The revised `Lanterns at the Longhouse · Reed Lead v2` candidate (`20261031T174555Z-78b2d2f2`) rendered with the bagpipe stem. Its section audit records folk/lead events as 25/0 in the 4-bar folk theme, 2/6 in the 8-bar heavy riff, 50/0 in the 8-bar dance return, and 1/0 in the 4-bar coda. This verifies the intended role handoff in the event plan; human listening review is still required.

## Next integration moves

- Introduce a versioned, validated genre-grammar contract based on the jazz profile, while keeping the current thrash path working as a legacy adapter.
- Replace fixed musical role assumptions with role-capability declarations that can select synths, saxophones, flutes, violins, guitars, keys, or combinations.
- Make composer output preserve gesture, motif, section, and interaction provenance through MIDI and stems.
- Add genre-specific evaluators; do not apply a rock/chorus rubric to black metal or a metal riff-family metric to jazz.
- Extend instrument acquisition with license receipts and patch capability checks before a source can enter a commercial palette.
- Keep the authored prototype and listening notes separate from claims that the general engine is complete.
