# DIO Media Pipeline Status - 2026-08-16

## Current Finding

The older NicheFoundry media engines are present and executable.

Confirmed local engines:

- `NicheFoundry_Phase11/scripts/build_dio_campaign_reel.js`
- `NicheFoundry_Phase11/scripts/build_premium_assets.js`
- `NicheFoundry_Phase11/scripts/render_episode.js`
- `NicheFoundry_Phase11/scripts/upload_dio_publication_candidate.js`
- local `node`, `ffmpeg`, and `ffprobe`

The missing layer was not the engine itself. The missing layer was a durable DIO bridge that treats NicheFoundry media generation as an operable Market Command production lane.

## What Now Works

`scripts/run_nichefoundry_media_pipeline.py` bridges the DIO creative-family registry into the native NicheFoundry campaign-reel engine.

It now:

- resolves each `NICHEFOUNDRY_PRODUCTION_REQUEST.json`
- verifies the three scene images
- verifies the rights-recorded music bed
- invokes the native NicheFoundry reel renderer when requested
- records per-family `MEDIA_PIPELINE_RECEIPT.json`
- preserves the NicheFoundry `NICHEFOUNDRY_REEL_RECEIPT.json`
- updates both the central registry and each family `FAMILY.json`
- emits `marketing.media_pipeline_ran` events
- keeps publication and spend held

Latest controlled run:

- families selected: 24
- ready: 24
- blocked: 0
- failed: 0
- reel receipts: 24
- media pipeline receipts: 24

## Dashboard Change

The Control Deck Market Command tab now exposes the media engine directly.

Each creative family shows:

- advert/poster links
- vertical reel link
- production request link
- media receipt link
- native reel receipt link
- premium episode status
- `Run media bridge` control
- governed draft creation control

The old dashboard bug where the UI looked for `request_path` while the registry stored `request` has been fixed.

## Remaining Gap

Short-form campaign media is operational.

Premium long-form media is not yet fully fused into the same universal lane.

Reason: the current DIO creative-family requests are lightweight campaign requests. NicheFoundry's premium Gamma/music/voice/render path expects a full episode directory with files such as:

- `brief.json`
- `studio_pack_snapshot.json`
- `script_package.json`
- `script_manifest.json`
- `render_manifest.json`
- `visual_manifest.json`

So every current family is marked:

- `media_pipeline_state`: `ready`
- `native_reel_state`: `ready`
- `premium_episode_state`: `needs_full_episode_promotion`
- `long_form_state`: `needs_episode_promotion`

## Next Build Layer

Build a second bridge:

`creative_family -> full NicheFoundry episode -> premium assets -> voice/music -> long-form render -> publication candidate`

That bridge should use the existing old engines instead of rewriting them:

1. Convert the DIO creative family into a NicheFoundry episode directory.
2. Write the episode manifests expected by NicheFoundry.
3. Invoke premium visual/music generation where credentials are present.
4. Render a long-form explainer using the existing preview/render pipeline.
5. Create a `FINAL_PUBLICATION_CANDIDATE.json`.
6. Surface it in Video Releases for approval and upload.

This is the actual missing media-generation layer.
