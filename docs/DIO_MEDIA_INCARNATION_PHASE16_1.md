# DIO Media Incarnation — Phase 16.1

Phase 16.1 closes the difference between a media plan and produced media.

## Execution chain

```text
Phase 16 product incarnation
        ↓
native NicheFoundry campaign functions
        ↓
full six-scene production script
        ↓
CPU-local branded image renderer
        ↓
FFmpeg/Flite narration + timed captions
        ↓
FFmpeg H.264/AAC composition
        ↓
Sophia media claim review
        ↓
Evidex hash-bound media proof
        ↓
human publication gate
```

## Material outputs

The reference run produces:

- two rendered PNG advertisements
- five rendered 1080×1080 carousel slides
- a rendered 1280×720 YouTube thumbnail
- six rendered 1920×1080 video scenes
- a complete production script and shot list
- offline spoken WAV narration
- six timed SRT caption blocks
- YouTube title, description, chapters, tags and pinned-comment package
- a playable 1080p H.264/AAC MP4
- Sophia review and a hash-bound Evidex media manifest

## Native execution truth

The existing NicheFoundry adapter is invoked through its real campaign functions. Its receipt states `NATIVE_FUNCTION_EXECUTION` and `live_adapter_invoked: true`. Rendering is performed by the Phase 16.1 media provider using Pillow and FFmpeg. No cloud service, network request or API key is used.

This does not claim that the separate historical `/home/byron/Downloads/NicheFoundry_Phase11` workspace was invoked. That absolute-path project remains outside the repository and is not treated as available evidence.

## Authority boundary

Material production is allowed. Publication, sending and media spend remain refused. A rendered MP4 is not a published video. A rendered advertisement is not a booked placement.

## Acceptance

```bash
python -m pytest -q tests/test_media_incarnation_phase16_1.py
python scripts/run_media_incarnation_phase16_1.py \
  --output /tmp/dio-phase16-1-media-incarnation
```

Expected token:

```text
DIO_MEDIA_INCARNATION_READY
```
