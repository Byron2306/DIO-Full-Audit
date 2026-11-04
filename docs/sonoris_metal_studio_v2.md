# Sonoris metal pattern and instrument study, v2

The prior metal candidate library reused one generic onset pattern across most metal labels. This revision uses original rhythm and pitch cells for ten metal subgenres, with a distinct drum grid, bass interaction, tonal movement, tuning and tone target. The specific artist tabs and multitrack pages consulted are listed per profile in [`config/sonoris/metal_style_models_v1.json`](../config/sonoris/metal_style_models_v1.json). Those are community notations except for the linked official Metallica tablature book, so song-specific tunings and details may vary. This is a structural style study, not a transcription, artist imitation, or claim that one song represents an entire subgenre.

| Style | Seed behavior | Ensemble and tone |
|---|---|---|
| Thrash | Fast palm-muted pedal and chromatic turnarounds, stop accents, picked bass in lockstep | E standard baseline, tight bright amp, eighth-note drive and double-kick bursts |
| Death | Dense chromatic/diminished cells and tempo-weight contrast | C standard baseline, aggressive amp, blast and breakdown drums, vicious bass |
| Power | Gallop and diatonic lift, harmonized melodic answer | E standard baseline, brighter amp, double kick, organ support |
| Doom | Long minor/tritone weight with large gaps | C standard baseline, fuzz and dark EQ, half-time kit, long bass sustain |
| Glam | Open arena backbeat, hooks and blues-leaning lead answer | E-flat standard baseline, lighter crunch, stereo guitar, organ, clean bass |
| Folk | Dance pulse and modal melody in a separate role | D standard baseline; bagpipe on drive seeds, transverse flute on space seeds, accordion on fracture seeds |
| Progressive | Asymmetric attacks, changing meter, quiet/heavy contrast and counterpoint | Drop D baseline, sampled electric piano, independent bass |
| Industrial | Repeated gated cells, machine-precise timing and synth pulses | Drop D baseline, driven amp, gated/saturated drum stem, aggressive bass |
| Alternative | Quiet/clean and wide heavy contrast, melodic bass and texture | Drop C baseline, sampled guitar with dry clean breaks and synth pad |
| Nu | Detuned, syncopated single-note/chord hits with rests and half-time snare | Drop B baseline, low-focused amp, textured pad, heavy bass |

Tuning, tempo and meter are starting points, not fixed genre laws. Sonoris exposes them in the dashboard. The key and tuning controls change the generated register and riff root; the user can also select the guitar sample pack, lead, bass, drum kit, keys, folk sample, amp tone, drive, attack velocity, drum velocity, each stem's mix level, and master gain. At present the timing generator works at beat and sub-beat resolution, so microtiming from human performances is approximated through velocity and double-track offset; it is not a guitar performance model.

The local studio also supports named session recipes. A recipe stores the current genre/song type, form and tonal controls, tone and velocity settings, active module choices, per-stem mix levels, and Black Metal Lab support-layer settings. The service stores settings only in `deliverables/sonoris_studio/workflows/SONORIS_SESSION_RECIPES.json`; compiled songs and audio remain independent job artifacts. Recipes are available across browser profiles and service restarts on this machine, with a 30-recipe limit. `GET`, `POST`, and `DELETE /api/workflows` (delete uses `/api/workflows/{id}`) provide the local studio interface. The dashboard's **Add genre starter sessions** action explicitly adds 22 original, catalog-derived setups spanning the requested metal and rock families, synthwave, jazz, and jazz fusion. It adds missing names only, preserves custom recipes, and can be used again after deletion; it never runs automatically. The action is backed by `POST /api/workflows/restore-starters`.

The Black Metal Lab now lives inside the composition form and uses the same typed controls, recipe persistence, compile handler, and module selector as the rest of Sonoris. Its atmospheric type routes to a compatible local keys module; presets set the matching genre, title, bar count, seed, and layer. The prior post-page fragment and global `fetch` interception have been removed. The running dashboard serves the consolidated controls; the browser's composition request carries the support-layer settings directly.

### Media-pipeline review handoff

The listening bench can prepare a hash-bound, review-only handoff for any rendered Sonoris candidate. The same resolver is used by the campaign media renderer, multichannel campaign factory, Hustle reel, customer launch preview, and media-incarnation explainer through Sonoris' central music selector. From a pipeline shell, set `DIO_SONORIS_REVIEW_JOB` to the rendered job ID and `DIO_SONORIS_REVIEW_LANE` to `jobs` or `seeds`. The next local render uses that score as its bed and carries the handoff receipt and attribution note into the artifact package. `DIO_CAMPAIGN_MUSIC` remains the explicit override for cleared canonical catalog music.

This route is for internal previews only. The handoff rechecks the Sonoris source receipt and MP3 hash, records the composition receipt hash, sets commercial use to unverified, and keeps publication and release unauthorized. It does not promote a sampled Sonoris track into the commercial music catalog.

## Audio path

- The downloadable MIDI includes all active roles, including sampled SFZ roles. The older path omitted those roles from the candidate MIDI.
- Rhythm guitar is rendered as separate left and right performances, with distinct mute/sustain/clean partitions. The default Metal GTX guitar uses its palm-mute and sustain samples. The alternate FreePats FSBS pack uses recorded distorted guitar samples. Guitarix `gxmetal_head` and `gx_fuzz_` supply local amp/fuzz effects as applicable; EQ, compression and a cabinet-like high-frequency rolloff follow. The amp input is a sampled DI, not a live guitar recording for each song.
- Bass has its own Growlybass sample stem, compressed and octave shifted to the composed low register. Drum modules now vary by style: thrash/glam/hard rock use the power kit; death/power/prog and black metal use Virtuosity; doom/alternative/grunge/post-rock/folk-rock use the room kit; folk metal and math rock use Salamander; industrial uses the electronic kit; nu metal uses the 808 kit; jazz, indie and straight rock use the standard kit; synthwave uses its electronic kit; ambient leaves drums off. Each module remains selectable in the studio, and the selected module is recorded in the composition receipt.
- Keys and folk instruments are independent stems. Local sampled options include bagpipe and drones, wooden recorder, button accordion, VSCO2 flute, jRhodes piano, FreePats rock organ and synth pad. FluidR3 options remain available for comparison.
- Stems are balanced and panned before FFmpeg loudness processing. The studio retains each final stem, WAV, MP3, MIDI, score events and receipt for inspection.

On 2026-10-31 the genre-kit defaults were applied to the saved seed library: all 82 examples across 23 genres have rendered audio, and the displaced seed versions are retained under `media/sonoris/genre_seed_library_v2/_catalog_revisions/`. The 22 original genre starter sessions have also been restored to the persistent local recipe store; custom recipes remain supported up to the 30-recipe limit.

The downloaded FreePats bagpipe, recorder, accordion, alternate guitar, [rock organ](https://freepats.zenvoid.org/Organ/electric-organ.html) and [synth pad](https://freepats.zenvoid.org/Synthesizer/synth-pad.html) pages designate those instruments CC0. VSCO2 Community Edition is [CC0](https://github.com/sgossner/VSCO-2-CE). The local installed Metal GTX, Growlybass, Virtuosity and jRhodes packs have separate source/license records that should be checked before a commercial release. Every Sonoris receipt therefore marks commercial rights unverified and human listening review required. The render is an arrangement and tone preview, not a mastered release.

## ATLAS exploration map

The live dashboard exposes 18 analogical ATLAS domain candidates: 17 shared with Pictora and one Sonoris-specific (`D1406`). The union across both organs is 23 domains. ATLAS reports zero execution-grade signatures for Sonoris; these links are exploration hypotheses, not capability proof, market evidence, or release authority.

## Source entry points

- [Metallica official *Master of Puppets* tablature book](https://www.metallica.com/store/master-of-puppets---guitar-tablature-book/M504.html) and [Songsterr notation guide](https://www.songsterr.com/howtoreadtab.pdf): interpreting palm mute, accent, durations and meter.
- [Suffocation bass multitrack](https://www.songsterr.com/a/wsa/suffocation-liege-of-inveracity-bass-tab-s406723), [Deicide drum tab](https://www.songsterr.com/a/wsa/deicide-dead-by-dawn-drum-tab-s29249): rhythm section contrast beyond guitar only.
- [Eluveitie flute track](https://www.songsterr.com/a/wsa/eluveitie-inis-mona-tab-s33938t0), [Dream Theater keyboard track](https://www.songsterr.com/a/wsa/dream-theater-pull-me-under-tab-s6248t6), [Nine Inch Nails synth bass track](https://www.songsterr.com/a/wsa/nine-inch-nails-head-like-a-hole-bass-tab-s48760t0): non-guitar roles.
- Instrument pages: [FreePats bagpipe](https://freepats.zenvoid.org/Ethnic/bagpipe.html), [recorder](https://freepats.zenvoid.org/Wind/recorder.html), [accordion](https://freepats.zenvoid.org/Organ/accordion.html), [distorted guitar](https://freepats.zenvoid.org/ElectricGuitar/distorted-electric-guitar.html).
