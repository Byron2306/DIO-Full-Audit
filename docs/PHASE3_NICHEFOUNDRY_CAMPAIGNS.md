# Phase 3: NicheFoundry Campaign Engine

Status: working. Evidex has passed the first push into a NicheFoundry lightweight episode package and a polished no-paid-token MP4 preview.

Phase 3 turns the product layers into NicheFoundry-ready campaign and storyboard packs.

## Command

```bash
python3 scripts/build_phase3_campaigns.py --out campaigns/phase3
python3 scripts/build_operator_dashboard.py
```

## Product Layers

Configured in:

```text
config/product_layers.json
```

Generated layers:

- Evidex Evidence Pack.
- HOMS Marking Relief Pack.
- KnowEdge Inbox Desk.
- VAMP Performance Evidence Desk.
- Sophia Academic Review Desk.

## Outputs Per Layer

Each layer gets:

- `CAMPAIGN_PACK.md`
- `foundry_opportunity.json`
- `storyboard.json`
- `visual_plan.json`
- `metadata_package.json`
- `editorial_review.json`
- `PHASE3_RECEIPT.json`

Index:

```text
campaigns/phase3/PHASE3_CAMPAIGN_INDEX.md
```

## Gate Before Video Rendering

Do not start full media generation until:

- campaign copy is reviewed,
- product claims are verified,
- no private data is present,
- offer is fulfilment-ready,
- editorial review has no blockers.

## Why This Phase Is Lightweight

NicheFoundry has heavy media, voice, render, and publishing machinery. Phase 3 intentionally stops at campaign/storyboard approval so disk, time, and API usage stay controlled.

The next step is to pick one approved campaign and graduate it into NicheFoundry's real storyboard/render path.

## Evidex Push

Evidex is the first approved campaign because it already has the strongest chain:

```text
route -> review pack -> real Evidex ZIP -> service wrapper -> campaign pack -> foundry import kit
```

Commands:

```bash
python3 scripts/approve_campaign.py --campaign campaigns/phase3/evidex --state approved --reviewer codex
python3 scripts/promote_campaign_to_episode.py --campaign campaigns/phase3/evidex --force
node /home/byron/Downloads/NicheFoundry_Phase11/scripts/build_cards.js /home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6
node /home/byron/Downloads/NicheFoundry_Phase11/scripts/prepare_imports.js /home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6
python3 scripts/build_free_media_preview.py --episode /home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6 --provider edge --transition 0.55
```

Current pushed outputs:

- `PHASE3_APPROVAL.json`
- `PHASE3_PUSH_RECEIPT.json`
- 6 generated SVG cards.
- Canva storyboard and export CSV.
- Adobe storyboard and export CSV.
- ElevenLabs narration CSV.
- NicheFoundry-compatible `script_manifest.json`, `render_manifest.json`, `visual_manifest.json`, `narration_manifest.json`, and `audio_manifest.json`.
- `free_preview.mp4` generated with `edge-tts` and 0.275s applied scene fades.
- `FREE_MEDIA_RECEIPT.json`.
- `imports/music_search_plan.md` and `imports/music_search_plan.json`.

The preview lane can run fully offline with:

```bash
python3 scripts/build_free_media_preview.py --episode <episode-dir> --provider espeak
```

To replace the placeholder music, drop a cleared file at:

```text
imports/music_bed.mp3
```
