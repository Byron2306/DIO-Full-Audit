# DIO Phase 16.2 — Fusion Closure

Phase 16.2 repairs the media federation boundary exposed by the Phase 16.1.2
evidence review. Fusion means governed invocation of authoritative engines; it
does not mean replacing proven engines with simplified local imitations.

## Corrected authority

- Gamma creates the composed scene and thumbnail assets.
- NicheFoundry's native `lib/render_system.js`, invoked by
  `scripts/render_episode.js`, owns the final video render.
- Document Studio binds editable semantic controls, Format Core identity,
  structural validation, and human approval state.
- Document Studio does not crop completed Gamma cards, repaint raster text, or
  claim native rendering when only its DIO adapter ran.
- DIO binds receipts, hashes, authority states, and release refusal.

## Regression removed

The former adapter selected one half of completed Gamma images and painted a
second typography layer over them. A missing font silently fell back to a
10-pixel bitmap font while the gate still emitted PASS. That implementation and
its authority claim are removed.

## Truth gates

The closure gate now requires:

- `native_nichefoundry_render_execution: PASS`
- `gamma_composition_preserved: PASS`
- `document_studio_control_surface_binding: PASS`
- `document_studio_native_render_execution: REFUSE`
- `destructive_media_recomposition: REFUSE`
- `automated_perceptual_release: REFUSE`
- `human_visual_release: NEEDS_YOU`

The native NicheFoundry render QA and asset-hash manifest must pass. Structural
checks cannot promote a visual asset to human-approved release.

## Run

```bash
git fetch origin agent/dio-phase16-1-2-document-studio-media-control
git switch --detach origin/agent/dio-phase16-1-2-document-studio-media-control

export DIO_NICHEFOUNDRY_ROOT="$HOME/Downloads/NicheFoundry_Phase11"

rm -rf /tmp/dio-phase16-2-fusion-closure

python scripts/run_premium_media_phase16_1_1.py \
  --nichefoundry-root "$DIO_NICHEFOUNDRY_ROOT" \
  --provider auto \
  --output /tmp/dio-phase16-2-fusion-closure
```

The machine acceptance token is `DIO_FUSION_CLOSURE_READY`. Final visual
release remains a human decision after reviewing the generated MP4, thumbnail,
Gamma scenes, Document Studio control manifest, and proof package.
