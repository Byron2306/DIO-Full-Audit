# Production Studio Campaign Story Pipeline

## Purpose

Production Studio marketing media is now a governed campaign pipeline rather than a three-frame caption reel.

```text
canonical incarnation + audience/profile
        |
        v
channel copy + static campaign assets
        |
        v
CAMPAIGN_STORY.json
hook -> pain -> workflow -> proof -> boundary -> CTA
        |
        v
GAMMA_STORY_REQUEST.json
        |
        v
Gamma public API
six 16:9 campaign cards + GAMMA_STORY_RECEIPT.json
        |
        v
local Piper only
scene WAV files + PIPER_NARRATION_RECEIPT.json
        |
        v
FFmpeg + rights-recorded music bed
        |
        +--> reel_1080x1920.mp4
        +--> explainer_1920x1080.mp4
        |
        v
CAMPAIGN_MEDIA_RECEIPT.json
        |
        v
operator review gate
```

## Campaign story

Every creative family receives one master six-scene story:

1. Hook
2. Pain
3. Workflow
4. Proof
5. Human-authority boundary
6. Call to action

The story is written to both `CAMPAIGN_STORY.json` and `CAMPAIGN_STORY.md`. Its stable story hash binds the downstream Gamma request.

This story is the common semantic spine for the channel copy, Gamma deck, Piper narration and final videos. The channels are variants of one campaign rather than unrelated assets.

## Gamma contract

`scripts/run_gamma_story.js` consumes `GAMMA_STORY_REQUEST.json` and uses the existing NicheFoundry `lib/gamma_system.js` integration.

The request is intentionally strict:

- presentation format
- 16:9 cards
- one card per story scene
- explicit input-text card breaks
- PNG export
- supplied claims and story order preserved
- no fabricated customers, testimonials, revenue, certifications or outcomes
- visual review required before publication

Gamma results are cached only when the stored request hash matches and all expected card files still exist.

The generated receipt is `gamma/GAMMA_STORY_RECEIPT.json`.

## Piper contract

Campaign narration is **local Piper only**.

There is no ElevenLabs, Kokoro, eSpeak or remote-TTS fallback in `scripts/build_campaign_media.py`.

Piper binary resolution order:

1. `PIPER_BIN`
2. `$NICHEFOUNDRY_ROOT/.venv-piper/bin/piper`
3. `piper` on `PATH`

Voice model resolution order:

1. `PIPER_MODEL`
2. models under `$NICHEFOUNDRY_ROOT/assets/piper`
3. models under `DIO-Full-Audit/assets/piper`

`PIPER_VOICE` may be used as a case-insensitive model-name/path hint when more than one local model is installed.

Every accepted model must have both:

```text
<voice>.onnx
<voice>.onnx.json
```

If no local Piper runtime or valid local voice model is available, narrated media production fails explicitly. It does not silently route to another provider.

## Media outputs

After Gamma succeeds, `scripts/build_campaign_media.py` synthesizes one WAV per story scene with Piper, then builds two campaign videos from the Gamma cards:

- `assets/reel_1080x1920.mp4`
- `assets/explainer_1920x1080.mp4`

The rights-recorded NicheFoundry music bed is mixed beneath the narration. The media receipt binds:

- Gamma generation and request hash
- Gamma card count
- Piper model and model SHA-256
- every narration WAV SHA-256
- music attribution
- final video hashes and measured durations

## Governance

A successful media build means the campaign assets exist and the required production lineage is present. It does **not** mean:

- publication is authorized
- advertising spend is authorized
- product claims are independently certified
- customer demand has been validated
- market success has been demonstrated

Publication and spend remain held for operator approval.

## Production Studio behavior

The existing `render_reel` operator switch is now the media-execution switch.

When it is false, Production Studio still creates:

- all static creative sizes
- channel copy
- the complete six-scene campaign story
- local story-scene posters
- the Gamma story request
- the NicheFoundry production request with a mandatory local-Piper voice contract

When it is true, the run additionally requires successful Gamma generation and successful local Piper narration before the rendered campaign is considered ready.

## Useful local voice overrides

```bash
export NICHEFOUNDRY_ROOT=/home/byron/Downloads/NicheFoundry_Phase11
export PIPER_BIN="$NICHEFOUNDRY_ROOT/.venv-piper/bin/piper"
export PIPER_VOICE='en_GB'
# or pin one exact model:
export PIPER_MODEL="$NICHEFOUNDRY_ROOT/assets/piper/<voice>/<voice>.onnx"
```

The Gamma API key continues to be read from the NicheFoundry `.env` file or the process environment as `GAMMA_API_KEY`.
