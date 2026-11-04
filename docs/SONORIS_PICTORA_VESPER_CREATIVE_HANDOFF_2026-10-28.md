# Sonoris, Pictora and Vesper creative handoff — 2026-10-28

## Organ identity

`media/product_asset_packs/dio_creative_organs_site_matched_v2/` contains current-site-derived Sonoris and Pictora banners (1920×1080), badges (1024px) and three 512px icons per organ. The set uses the existing DIO organ heroes, dark obsidian artboards, restrained gold, orbital motifs and locally typeset text. Generated text was not relied on. Human review and publication remain pending. See `CREATIVE_ORGAN_IDENTITY_PACK.json`.

## Sonoris explainer

`video/SONORIS_GOLDEN_ORGAN_EXPLAINER_REVIEW.mp4` is a 45-second 1920×1080 review asset with canonical local Pocket TTS Vera narration and an original 45-second procedural ambient synth composition. The bed is newly synthesized with F-minor harmonic color, low pulses and sparse bell tones; no catalog track or external sample is used. Narration and voice model provenance are in `receipts/POCKET_TTS_NARRATION_RECEIPT.json`; media manifest and hashes are in `receipts/SONORIS_EXPLAINER_MEDIA_RECEIPT.json`. Ad claims describe the experimental organ; do not imply a released customer product.

## Black-metal composition

`media/sonoris/releases/black_metal_where_pines_forget_v1/` contains the original 52-bar, 168 BPM through-composed track **Where the Pines Forget**, MIDI, a FluidR3 complete preview, separate sfizz-rendered Metal-GTX, Growlybass and Salamander review stems, and a rough ensemble mix. The composition reads `BLACK_METAL_CLASSIC` as gesture-based grammar: trance, sprint, panic, stomp, collapse, transformed hook and release, with chromatic half-step tension and blast/double-kick motion. The full Metal-GTX program wrappers were empty in the supplied directory, so the guitar review render uses the individual `Sus_Up` articulation. The Metal-GTX had no local license file, so its guitar sample render stays private review-only pending rights confirmation. Growlybass readme declares royalty-free commercial and non-commercial use. Salamander’s misspelled `REAMDE` declares CC BY-SA 3.0, with attribution and share-alike conditions. FluidR3 clearance is unverified. See `SONORIS_BLACK_METAL_RELEASE_RECEIPT.json`.

## Vesper animation experiment

`media/product_asset_packs/homs_corpo_cult_v1/vesper/visemes/welcome_v2/` contains a silent 30fps V2, contact sheet and receipt. It uses the owner-provided Grok group mouth pose atlas and provisional editorial timings in `welcome_to_dio_storyboard_v1.json`. Face/hair remain fixed while a feathered lower-face patch selects nearest viseme poses. There is no speech audio, therefore this is not aligned lip sync. The original clip is unchanged.

## Reproduction scripts

- `scripts/build_sonoris_black_metal_candidate.py`
- `scripts/build_sonoris_organ_identity_and_explainer.py`
- `scripts/generate_sonoris_ambient_synth.js`
- `scripts/animate_vesper_welcome_v2.py`

All outputs are local review candidates; nothing was pushed or published.

## Updated black-metal pass and genre compiler

The user's feedback prompted a new v2 render. `media/sonoris/releases/black_metal_where_pines_forget_v2/WHERE_THE_PINES_FORGET_METAL_GTX_GROWLYBASS_SALAMANDER_V2.mp3` is now rendered through Metal-GTX's up/down sustain and mute articulations, with two independent humanized guitar performances, amp saturation, Growlybass Dirty/Vicious patches, and Salamander drums. The MIDI follows the compiler's 52-bar D-minor/168 BPM plan with chromatic motion and diminished/augmented fifth voicings. Metal-GTX's license remains unverified, so that render is held for private audition pending rights review. See the updated v2 receipt.

The ad's v2 review file is `media/product_asset_packs/dio_creative_organs_site_matched_v2/video/SONORIS_GOLDEN_ORGAN_EXPLAINER_REVIEW_V2.mp4`. V1's score was too quiet, and a later score draft had a buffer-delay NaN that produced silence. Both issues are corrected in V2: the generated F-minor darksynth arpeggio begins alone, ducks under Vera, and remains audible through the end. New score generation and voice receipts are in `receipts/SONORIS_EXPLAINER_MEDIA_RECEIPT_V2.json` and `receipts/POCKET_TTS_NARRATION_RECEIPT_V2.json`.

`config/sonoris/genre_grammars_v1.json` and `products/sonoris_genre_compiler.py` implement the behavior-first genre plan/compiler. The catalog covers black metal, synthwave, jazz fusion, rock and ambient. Primary grammar owns form and hard constraints; a bounded secondary grammar can contribute timbre and counter-gestures without averaging contradictory laws. The first compiled plans are in `media/sonoris/composition_plans/genre_examples_v1/`.
