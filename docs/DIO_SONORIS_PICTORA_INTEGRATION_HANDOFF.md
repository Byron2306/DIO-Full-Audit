# DIO Sonoris and Pictora integration handoff

## Current studio upgrade — 2026-10-31

The always-on local studios are now available at `http://127.0.0.1:42154/` (Sonoris) and `http://127.0.0.1:42153/` (Pictora). Sonoris has editable genre/song controls, instrument and stem mix controls, measured section audits, a compiled seed library, persistent named session recipes, and a held media-review handoff. Pictora has persistent render workflows, generate/image-to-image/inpaint/reshape controls, model-compatible pose/identity/face/composition references, saved render history, and a finishing editor.

Pictora capability discovery exposes the live ComfyUI runtime, VRAM, installed checkpoint weight size and per-model terms state. Five checkpoints now match exact upstream version/file hashes; the Krea 2 fine-tune is locally hash-pinned, with its Krea Turbo base and merged adapter identified from safetensors metadata but the adapter's author/version still unknown. All six are marked `IDENTIFIED_RESTRICTED` and commercial use remains `NOT_CLEARED`. Model source/credit/usage constraints now appear at selection and in new render receipts. The Pictora systemd service was restarted after the provenance change and returned healthy at port 42153. The current machine reports a 5.72 GiB GPU and its Krea 2 weight file is 11.94 GiB, which triggers an in-product capacity warning when selected.

The live Pictora studio has now completed three key workflow classes against local ComfyUI 0.42.0: prompt generation, masked inpainting, and a combined pose + FaceID appearance + composition reference render. The inpaint candidate adds a distinct gold medallion within its painted mask. The combined-control receipt binds the input image hashes and local ControlNet, FaceID, IP-Adapter Plus and CLIP Vision file hashes. Exact face identity is not guaranteed; all outputs remain human-review candidates and release-held. Details and job IDs are in `docs/PICTORA_IMAGE_EDITOR_PRODUCT.md`.

Sonoris' Black Metal Lab has been consolidated into the composer form. Its genre preset, atmospheric layer, movement, register, density and level now use the normal compile path and saved recipes; the post-page inline fragments and global fetch interception were removed. The live studio serves the controls inside the composition form.

The Dicere debut explainer typography and layout were revised in V32: card headlines have more deliberate leading, captions use a clearly visible warm gold (`#FFC237`) with improved line spacing and contrast, Vesper has more breathing room inside the frame, and scene markers no longer sit behind the portrait. The 45-second 1920×1080 render and hash-bound receipt are `media/dicere/debut/DICERE_DEBUT_EXPLAINER_V32.mp4` and `.receipt.json`; V32 remains a local review candidate.

The Sonoris seed renderer has now completed the 45 previously unrendered candidates. A live `/api/jobs` inventory reports 82 seed entries with `audio_state=RENDERED`; all 82 have a valid seed receipt and WAV output. The sampled bundles include the stereo mute/sustain guitar parts, bass, drums, lead where configured, MIDI, stereo mix WAV and MP3. This verifies local generation only; listening review and source-pack commercial clearance remain outstanding.

The current genre catalog exposed four stale Folk Metal / Prog Metal seed meters. Those four candidates were recompiled and rerendered to match the catalog (Folk Metal 6/8, Prog Metal 7/8); their prior song directories are retained under `media/sonoris/genre_seed_library_v2/_catalog_revisions/`. The manifest now reports 82 rendered entries across 23 genres.

Both dashboards now expose their ATLAS candidate-domain map from `/api/atlas/domains`: Sonoris has 18 domains (17 shared, 1 Sonoris-specific), Pictora has 22 (17 shared, 5 Pictora-specific), and the union is 23. The current crosswalk reports zero execution-grade signatures for either organ; these are analogical exploration candidates and grant no capability or release authority.

Sonoris review handoffs now flow through the shared campaign music resolver. For an explicit local preview, set `DIO_SONORIS_REVIEW_JOB=<rendered-job-id>` and `DIO_SONORIS_REVIEW_LANE=jobs|seeds`; cleared music selected with `DIO_CAMPAIGN_MUSIC` remains higher priority. A real campaign-media render completed in both vertical and landscape formats at `deliverables/sonoris_studio/media_pipeline_proof_20261031T180417Z/`, using the Pictora site-matched banner, Sonoris' `Machine Without Strings` synthwave render, local Vera narration, and the DIO gilded pack. Its receipt binds audio and video hashes, and marks commercial use unverified, publication held, and release unauthorized. This is integration evidence, not music or creative approval.

When the Vera service restarts and the observed PID changes, refresh its local process evidence before a campaign render:

```bash
.venv/bin/python scripts/refresh_vera_runtime_inventory.py
```

The command checks the systemd user-service PID, exact local Pocket TTS command, loopback health endpoint, process start ticks, and all six recorded model/source file hashes before atomically updating the runtime inventory.

## What is wired now

Two local creative-engine adapters are callable from DIO workflows through `products.sonoris_organ` and `products.pictora_organ`, with a small operator CLI at `scripts/run_dio_creative_organs.py` and registry metadata in `config/creative_organs.json`.

The Sonoris thesis is now captured as a versioned genre-grammar prototype in `config/sonoris/embodied_music_grammar_jazz_synth_fusion_v1.json`; its evidence-led gap map is `docs/SONORIS_COMPUTATIONAL_MUSICAL_MORPHOLOGY_GAP_MAP.md`. Polly already models riff signatures/families, a small gesture vocabulary, section contrast, and a deterministic thrash gesture schedule. Its main limitation is that these ideas remain guitar/bar-centric, with fixed rock/metal roles and largely statistical genre profiles. The new grammar separates genre laws, embodied arrangement gestures, motif morphology, instrument capabilities, realization, and evaluation.

**Glass Meridian** is the first 44-bar Jazz Synth Fusion arrangement authored against that plan. It has a rendered MIDI, PCM listening render, normalized audition MP3, hash-bearing composition receipt, and section-by-section listening guide under `/data/byron/sonoris/rendered/glass-meridian-v002/`. Its explicit GLIDE → LOCK → FRACTURE → ORBIT → HANDOFF → LIFT → RELEASE arc gives jazz a different structural behavior from the existing thrash composition. The MIDI uses electric piano, electric bass, drum kit, synth lead, tenor saxophone, and flute programs from FluidR3 GM. This is an authored prototype, not a general prompt-to-composition product. The sample soundfont is MIT-licensed; keep its notice if redistributing the soundfont. Sonic approval remains pending.

Pictora has generated two local candidate art packs from the DIO Workflows visual direction. The reviewed source assets were the site's `dio-hero-product-2026.webp` and `dio-gilded-card-frame.webp`; they were inspected locally and not uploaded. V1 and V2 prompts, seeds, local ComfyUI receipts, hashes, and generated images are preserved under `media/product_asset_packs/dio_creative_organs_v1/` and `..._v2/`. Both sets are review diagnostics, not approved storefront art: the realism model chose portrait subjects, while the generic checkpoint produced gold textures without recognizable product subjects. See `VISUAL_REVIEW_NOTES.md` in the V2 pack.

A third Pictora pass used the current DIO Workflows `assets/premium/dio-hero-product-2026.webp` as a local image-to-image style anchor, then inpainted clear subject areas and upscaled the results to 1280×720. The preferred Sonoris art now reads as a piano in the gold orbital stage; the preferred Pictora art reads as a landscape canvas in a gold image portal. The selected candidates, uploaded source hash, masks, workflows, prompts, seeds, outputs, and local job receipts are in `media/product_asset_packs/dio_creative_organs_site_matched_v1/`. They still need owner review before storefront use; nothing was published or pushed.

The owner also identified `/home/byron/Downloads/grok-group.zip` as a Vesper mouth-pose source. It contains 19 consistent 1408×1408 face images, including closed/pursed, rounded, parted, wide-open, and smile shapes. A hash-bound inventory and mouth contact sheet are stored at `media/product_asset_packs/homs_corpo_cult_v1/vesper/visemes/grok_group_review/`. The original ZIP remains untouched, and the poses are not yet mapped to phonemes or substituted into the canonical VESPER contract.

The owner reports that the V004 Glass Meridian render slaps. The V004 directory contains two alternatives (`NO_SAX` and `SAX_SUPPORT`); both measure about −20.5 LUFS integrated, 3.2 LU LRA, and −1.5 dB peak. Their sample-level difference is small (0.345% RMS relative to the sax-support mix), so keep both until the preferred variant is explicit.

### Sonoris

The adapter inventories and hashes the existing Variant F MIDI source, verifies the local renderer, FluidR3 GM soundfont, `fluidsynth`, and audio dependencies, then builds an explicit job packet for the Chimera reconstruction. A job is staged without rendering by default. A local render requires `owner_authorized=true` at stage and run, checks that source hashes have not drifted, and refuses populated output directories.

The currently recovered renderer does deterministic general-MIDI stem rendering and two DSP treatments. It is an excellent experimental compositional/audition substrate, but it is not yet a natural-language-to-composition engine. Its own receipts say the instruments are GM substitutions, the historical chain is not reconstructed, sonic acceptance is pending, and commercial clearance is not established. The Bass Gauntlet is documented as a separate isolated experiment; its existing outputs and CC0 Growlybass source-license file are not a blanket clearance for other samples or customer material.

The original Polly compiler has now been connected through an explicit DIO entrypoint. It builds the existing Chainsaw Diplomacy composition, creates deterministic role MIDI, routes each role through pinned SFZ profiles using `sfizz_render`, and emits an instrument/tone/output manifest. `dio-sonoris-acoustic-iron-v001` is the first source-safe palette experiment: steel-string guitar L, nylon guitar R, clean Growlybass, Gogodze Phu II kit, and upright piano lead. It was rendered at 192 BPM, 4/4, 64 bars. The source composition stayed fixed while instrument palette/tone changed.

Four new sample libraries were downloaded to `/data/byron/sonoris/instruments/open-licensed-experiments`: Meta Piano (352 samples), Meta Nylon Guitar (348), Meta Steel Guitar (375), and Gogodze Phu Vol II (1,701). The three Meta archives passed all 1,081 published SHA-256 file entries; the Gogodze archive includes a CC0 license but no upstream checksum manifest, so its archive SHA-256 is recorded locally. Asset receipts and archive hashes are in `DIO_SONORIS_INSTRUMENT_ASSET_RECEIPT.json`. The Meta libraries are documented as full sampled ranges with discrete velocity layers, and the piano's full 88-key range makes it suitable for the experimental lead role. [Meta Open Sound’s repository](https://github.com/facebookincubator/Meta-open-sound) identifies its three instruments as CC0; [Gogodze's author page](https://shop.karoryfer.com/pages/free-gogodze-phu-vol-ii) and included license identify its sample library as royalty-free/CC0.

The acoustic instrument maps do not contain palm-muted guitar samples. The compiler retains the existing semantic articulation labels in MIDI, but these new SFZ maps render sustained sampled notes; they do not magically acquire metal palm-muting technique. That mismatch is intentional in this “acoustic iron” experiment and must remain explicit in the receipt/review. The canonical mix measures about -25.6 LUFS integrated and -10 dBFS true peak, so it needs substantial mix/master work before delivery. A separate loudness-normalized [audition copy](</data/byron/sonoris/rendered/dio-acoustic-iron-v001/LISTENING_PREVIEW.mp3>) is provided for review; it is explicitly not a release master. Structural signatures and file hashes passed the manifest consistency check; actual musical acceptance remains with Byron.

### Pictora

The adapter discovers the local ComfyUI system and available node types, accepts an explicit ComfyUI API-format workflow, queues it at local ComfyUI, polls its history, downloads image outputs into a chosen job directory, and hashes the workflow and artifacts. A custom endpoint must be HTTP loopback; hosted/remote ComfyUI endpoints are refused. The adapter does not choose models, rewrite prompts, infer rights, or publish results.

The local ComfyUI runtime was reachable at `127.0.0.1:8188` during integration. It reported ComfyUI 0.42.0 and an NVIDIA RTX 3050 Laptop GPU with 6GB VRAM. This is enough for local model-driven image work, while workflow size and resolution must stay within that memory budget. The live workflow remains caller-supplied so the user can select their installed Krea2, LoRA, depth/pose, inpaint, or upscale graph deliberately.

## DIO pathways to build on

- **HOMS Exam Builder → Pictora → Learning Studio:** have the exam knowledge spine specify the required concept, grade, source and pedagogical purpose for a diagram/map; render a visual candidate; attach source/claim and model provenance; require factual and age-appropriateness review; pass the approved image and explanation into the learner pack/video workflow. Pictora provides the visual instrument; the exam builder remains the authority for subject and grade alignment.
- **DIO Media → Sonoris:** request short, brief-specific stems or mixes from owned/licensed source material; keep stems and mix variants linked to the campaign/media receipt; require a sonic check and rights check before Vera/VESPER media uses them. Do not replace the current music catalog or Vera canonical voice contract with unreviewed renders.
- **New sellable discovery:** Pictora can become a local visual design studio for image editing, upscaling, inpainting, character/world bibles and branded asset variants. Sonoris can become a music-learning/composition studio linked to Sophia/HOMS, with the user's cross-genre fusion method as the differentiator. These are discovery directions, not launch-ready claims: each still needs a customer intake, repeatable brief-to-delivery workflow, revision loop, rights ledger, pricing and external quality validation.

## Invocation

Read-only capability checks:

```bash
python3 scripts/run_dio_creative_organs.py --catalog
python3 scripts/run_dio_creative_organs.py --sonoris-preflight
python3 scripts/run_dio_creative_organs.py --sonoris-polly-preflight
python3 scripts/run_dio_creative_organs.py --pictora-discover
```

Stage Sonoris without execution, then explicitly run only after reviewing the command and source inventory:

```bash
python3 scripts/run_dio_creative_organs.py --sonoris-stage --out /data/byron/sonoris/rendered/dio-job-name --owner-authorized
python3 scripts/run_dio_creative_organs.py --sonoris-run /data/byron/sonoris/rendered/dio-job-name/DIO_SONORIS_JOB_SPEC.json --owner-authorized
```

Render the pinned acoustic-iron palette through Polly's original compiler, or bind its receipt to the already-rendered v001 experiment:

```bash
python3 scripts/run_dio_creative_organs.py --sonoris-acoustic-iron --out /data/byron/sonoris/rendered/dio-acoustic-iron-v002 --owner-authorized
python3 scripts/run_dio_creative_organs.py --sonoris-polly-receipt --out /data/byron/sonoris/rendered/dio-acoustic-iron-v001
```

Render the current authored Jazz Synth Fusion prototype into a fresh directory under `/data/byron/sonoris/rendered`:

```bash
python3 scripts/run_dio_creative_organs.py --sonoris-glass-meridian --out /data/byron/sonoris/rendered/glass-meridian-v003 --owner-authorized
```

The runner refuses non-empty output directories so it cannot overwrite an existing review artifact.

Submit a caller-prepared ComfyUI API-format workflow (`class_type` nodes, not the UI workflow export), then collect outputs:

```bash
python3 scripts/run_dio_creative_organs.py --pictora-discover
python3 scripts/run_dio_creative_organs.py --pictora-submit /path/to/workflow-api.json --out /data/byron/lilith-local/pictora/job-id --owner-authorized
python3 scripts/run_dio_creative_organs.py --pictora-collect JOB_ID --out /data/byron/lilith-local/pictora/job-id
```

When ComfyUI is not listening on the default local endpoint, set `DIO_COMFYUI_URL` to an HTTP loopback URL or pass `--endpoint http://127.0.0.1:8188`. The adapter intentionally refuses non-loopback endpoints.

## Release boundary and next engineering steps

Both organ receipts preserve the workflow/source hashes, local execution boundary, human-review requirement, unproved commercial validation and `release_authorized=false`. No public upload, campaign publication, provider call, or customer-facing claim is performed by these integrations.

To make them production products, next add customer brief schemas and review/revision UX, durable job-state storage, model/LoRA/license manifests, output-policy checks, and a governed release action. For Sonoris, add a real composition/MIDI-generation layer around harmony, section, instrumentation, genre-role and arrangement constraints, then connect it to the current renderer. For Pictora, build a curated workflow catalogue for generation, inpaint, upscale, depth/pose conditioning and reproducible character/world sheets, with rights-aware model manifests. Keep each engine local and opt-in until those controls and the actual delivery quality are proven.
