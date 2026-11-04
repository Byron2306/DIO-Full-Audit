# Sonoris genre research and seed catalog

This is a structural listening map, not an attempt to imitate a performer or recording. Artist names are study landmarks. The compiler uses original motifs and makes MIDI candidates that need listening review before production use.

| Genre | Groove / harmony | Tempo bands, meters | Study landmarks | Song candidates |
|---|---|---|---|---|
| Alternative metal | syncopated; minor_pedal | 75–190 BPM; 4/4, 7/8 | Faith No More, System of a Down, Tool | angular groove, atmospheric weight, dissonant hook |
| Black metal | ; pedal_tone | 150–170 / 220–240 BPM; 4/4, 6/8, 3/4 | prior black metal genome | Frost assault, Lament and winter, War ascent |
| Death metal | blast; chromatic_minor | 125–250 BPM; 4/4, 6/8 | Death, Morbid Angel, Cannibal Corpse | technical assault, melodic descent, cavernous crush |
| Doom metal | doom; minor_drone | 45–125 BPM; 4/4, 6/8 | Black Sabbath, Candlemass, Electric Wizard | funeral crawl, traditional lament, stoner hypnosis |
| Folk metal | dance; modal_minor | 95–205 BPM; 4/4, 6/8, 3/4 | Korpiklaani, Eluveitie, Ensiferum | festival dance, epic march, acoustic rite |
| Folk rock | folk; modal_major | 70–160 BPM; 4/4, 3/4, 6/8 | The Byrds, Fairport Convention, Jethro Tull | acoustic narrative, electric folk, waltz refrain |
| Glam metal | arena; major_minor_hook | 85–180 BPM; 4/4, 6/8 | Def Leppard, Mötley Crüe, Poison | arena anthem, power ballad, shuffle strut |
| Grunge | quiet_loud; minor_pedal | 70–175 BPM; 4/4, 6/8 | Nirvana, Soundgarden, Alice in Chains | quiet loud, sludge weight, punk surge |
| Hard rock | backbeat; blues_rock | 90–190 BPM; 4/4, 6/8 | Led Zeppelin, AC/DC, Deep Purple | blues riff, arena drive, slow burn |
| Indie rock | jangle; major_minor_hook | 85–185 BPM; 4/4, 6/8 | Pavement, The Strokes, Arctic Monkeys | jangle hook, lofi push, wide chorus |
| Industrial metal | machine; chromatic_minor | 85–180 BPM; 4/4 | Ministry, Nine Inch Nails, Rammstein | machine march, dystopian pulse, noise collapse |
| Jazz | swing; ii_v_i | 65–225 BPM; 4/4, 3/4, 5/4 | Duke Ellington, Miles Davis, John Coltrane | swing head, modal conversation, late night ballad |
| Jazz synth fusion | ; extended_chords | 70–190 BPM; 4/4, 5/4, 7/8, 6/8 | prior black metal genome | Electric pocket, Modal glide, Odd meter exchange |
| Math rock | odd; modal_shift | 75–205 BPM; 5/4, 7/8, 4/4 | Don Caballero, Battles, American Football | angular interlock, clean tapping, stop start |
| Nu metal | syncopated; minor_pedal | 75–155 BPM; 4/4 | Korn, Deftones, Slipknot | low groove, quiet impact, percussive bounce |
| Post-rock | crescendo; modal_drone | 55–155 BPM; 4/4, 6/8 | Mogwai, Godspeed You! Black Emperor, Explosions in the Sky | slow crescendo, ambient drift, rhythmic swell |
| Power metal | gallop; minor_major_lift | 115–225 BPM; 4/4, 6/8 | Helloween, Blind Guardian, DragonForce | heroic gallop, anthemic ascent, neoclassical chase |
| Progressive metal | odd; modal_shift | 75–220 BPM; 4/4, 5/4, 7/8 | Dream Theater, Opeth, Tool | polymetric engine, atmospheric suite, technical dialogue |
| Progressive rock | odd; modal_shift | 75–195 BPM; 4/4, 5/4, 7/8, 6/8 | King Crimson, Yes, Genesis | miniature suite, organ dialogue, pastoral arc |
| Rock | ; riff pedal | 80–180 BPM; 4/4, 6/8, 3/4 | prior black metal genome | Riff drive, Open road, Bridge break |
| Synthwave | ; minor_progression | 75–130 BPM; 4/4 | Tangerine Dream, Vangelis, The Midnight | Outrun pursuit, Dreamwave nocturne, Darkwave descent |
| Thrash metal | thrash; chromatic_minor | 140–260 BPM; 4/4, 5/4 | Metallica, Slayer, Megadeth | speed assault, midtempo stomp, crossover sprint |

## Sources and implementation notes

- [Berklee: electronic music genres](https://www.berklee.edu/berklee-now/news/electronic-music-genres-a-guide-to-the-most-influential-styles) informs synthwave tempo, analog timbre and drum-machine structure.
- [Berklee: jazz composition](https://online.berklee.edu/courses/jazz-composition) and [modal harmony](https://online.berklee.edu/takenote/harmonic-considerations-modal-harmony/) inform swing, walking bass, comping and harmonic alternatives.
- [Oxford: metal drumming](https://academic.oup.com/book/62310/chapter/552774426) and [Bradford College metal genre taxonomy](https://digitalspace.bradfordcollege.ac.uk/10633466/wp-content/uploads/sites/568/2025/01/ConsideringGenreinMetalMusicFINAL.pdf) inform blast, gallop, odd-meter and stylistic divisions.
- [Oxford: rock rhythm](https://academic.oup.com/book/6294/chapter-abstract/149978188), [Oxford: progressive rock](https://academic.oup.com/book/49450/chapter-abstract/422323295) and [Rock Hall: Soundgarden](https://rockhall.com/inductees/soundgarden/) inform backbeat, progressive form and grunge reference points.

The catalog is `config/sonoris/genre_grammars_v1.json`. `products/sonoris_genre_compiler.py` compiles form and behavior; `products/sonoris_song_engine.py` realizes role events and MIDI. Black metal additionally uses its existing governed genome and physical performance compiler. The library manifest is `media/sonoris/genre_seed_library_v1/LIBRARY_MANIFEST.json`.

Preview audio is a local FluidSynth/SFZ arrangement sketch. It has no vocal performance, genre-master certification or rights clearance. The dashboard keeps release held for human listening and production review.
