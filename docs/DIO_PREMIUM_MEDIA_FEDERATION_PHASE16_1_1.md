# DIO Phase 16.1.1 — Premium Media Federation

Phase 16.1.1 replaces inferred engine use with receipt-backed execution states.

## What the gate proves

- DIO invokes the real `Byron2306/NicheFoundry` audio-performance pipeline.
- Production narration uses an approved provider: imported, Voicebox, Kokoro, Piper, ElevenLabs, or OpenVoice.
- eSpeak and Flite are refused as production voices.
- NicheFoundry emits its native performance, sound-design, asset-hash, rights, and loudness evidence.
- The programme master is 48 kHz stereo and includes a rights-evidenced music plan.
- DIO combines that master with the Phase 16.1 video and hash-binds the premium result.
- Publication, sending, media spend, and release remain human-gated.

## The corpus truth correction

`CORPUS_EXECUTION_CENSUS.json` distinguishes four states:

- `NATIVE_EXECUTED`: the engine's own runtime ran and emitted its own evidence.
- `PROJECTION_ONLY`: DIO locally produced an engine-shaped result; the engine did not run.
- `SOURCE_BOUND_ONLY`: source code or a contract is referenced, but its runtime was bypassed.
- `NOT_INVOKED` / `NOT_BOUND`: the engine was outside this execution.

For this gate NicheFoundry is native. Document Studio, Lingua, HOMS, Evidex, VAMP, and Sophia are reported at their actual state. The aggregate `full_corpus_native_execution` claim therefore remains `REFUSE`. That refusal is a correctness result, not a failed premium-media build.

## Local execution

Clone NicheFoundry beside the DIO checkout or set its location explicitly:

```bash
export DIO_NICHEFOUNDRY_ROOT="$HOME/NicheFoundry"

python -m pytest -q tests/test_premium_media_phase16_1_1.py

python scripts/run_premium_media_phase16_1_1.py \
  --nichefoundry-root "$DIO_NICHEFOUNDRY_ROOT" \
  --provider auto \
  --output /tmp/dio-phase16-1-1-premium-media
```

`auto` uses NicheFoundry's provider order. Configure the provider selected by that runtime. You may also request `imported`, `voicebox`, `kokoro`, `piper`, `elevenlabs`, or `openvoice` explicitly. The gate will not silently fall back to eSpeak or Flite.

## Review evidence

The final run directory contains:

- `media/youtube/FINAL_VIDEO_PREMIUM.mp4`
- `premium/NICHEFOUNDRY_NATIVE_EXECUTION.json`
- `premium/CORPUS_EXECUTION_CENSUS.json`
- `premium/nichefoundry_episode/` with native NicheFoundry audio evidence
- `PREMIUM_MEDIA_PROOF.json`
- `PREMIUM_MEDIA_RECEIPT.json`

Success ends with `DIO_PREMIUM_MEDIA_INCARNATION_READY`.

## Next native boundaries

Later gates must invoke, and accept native receipts from, Document Studio, Lingua, HOMS, Evidex, VAMP, and Sophia independently. No source import, local projection, adapter call, or registry entry may be promoted to native execution.
