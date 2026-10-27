# Vesper canonical Vera voice verification — 27 October 2026

Vesper's live engine now selects the promoted public voice registry default (`vera_pocket_public`, Pocket TTS `voice_url=vera`). Historical Persona Lab assignments and `DIO_VESPER_VOICE_PROFILE` cannot replace the public speech identity. Explicit internal auditions remain available through `build_voice_plan(requested_profile=...)`. Missing or unapproved public defaults cannot render.

The local website voice path previously discarded the engine's voice plan and returned only text. It now renders eligible voice replies, stores their audio alongside the canonical assistant message, and exposes the audio through the existing session-token reply protocol. Canonical text remains intact when rendering is unavailable. Replay remains idempotent. No send, spend, release, translation, or identity authority is created.

## Verification

- Before the fix, two engine regressions selected Piper/OpenVoice instead of Vera under stale environment/persona settings. They now pass.
- Before the website fix, the actual website transport regression failed because `reply.audio` was absent. It now verifies ready Vera audio, text preservation during renderer failure, and single-turn replay.
- Final focused run: `.venv/bin/python -m pytest tests/test_vesper*.py tests/test_presence_vesper.py tests/test_canonical_vesper_web_launcher.py tests/test_r4e_actual_website_transport.py tests/test_r4f_public_api.py -q` — **152 passed**.
- `git diff --check` for the changed source/tests passed. `.venv/bin/python -m pip check` reported no broken requirements.
- The root agent separately ran the repository suite and is reporting its unrelated failures; this focused run is not a claim that the whole repository passes.

## Actual local audio and provenance

Evidence is retained under `state/presence/voice_verification/` (the existing external runtime state root). No existing state was removed.

`vera_runtime_inventory.json` has SHA-256 `340ff989cd8f3fa465694d353a75fa68e6ce8b5559a37285d60b52856d69693b`. Its evidence class is **LOCAL_VERIFIED_RUNTIME_INVENTORY**. It records the observed Pocket TTS process command, installed source/config hashes, cached model/voice hashes, and a real engine-to-render receipt. This is local observational evidence. It is not HTTP service, hardware, remote, or process-memory attestation. Model selection is explicitly an inference from the observed language configuration/fallback and local cache.

- Observed renderer: Pocket TTS 3.3.0, PID 2132, `serve --host 127.0.0.1 --port 8000 --language english --default-voice vera`.
- Model: `kyutai/pocket-tts-without-voice-cloning`, revision `e7205b6ee50e654a5ea19f0e9df2b0813b05e921`, actual cached model SHA-256 `916ccd2686e9311cb40054893a3c4284393d658825ffc714a276f3e9b152344f`.
- Vera embedding revision: `4e1e0a3e611c51c0b4ed8174fc10f32a54644303`, actual cached embedding SHA-256 `3a9d4a9237d8615b5c3d10610b16a3037edb163cc18df42f138bfbc1f2beb7a3`.
- `vesper-vera-canonical.wav`: real engine-selected Vera under deliberately stale Piper environment settings and enabled Persona Lab; 23.32 seconds, 1,119,404 bytes; SHA-256 `2478ea4aece99dc7157264ea55cc30d9635769a1e1590c9d8d77876a1fff8320`.

`verified_vera_runtime_inventory(root)` rechecks the inventory endpoint, observed live process command, model/voice/source/config file hashes, and model/voice hash correspondence. Marketing receipts can bind its inventory path/hash and model provenance to each generated audio hash. This optional helper creates no rendering or external authority.

## Reloaded local website round trips

The existing `dio-presence-local.service`, `dio-vesper-public-api.service`, and `dio-vesper-web-repair.service` were reloaded after confirming their source paths resolve to this checkout. Health checks returned HTTP 200. Pocket TTS was not restarted.

The website services lacked local ASR dependencies and a cached-model setting. The existing cached model at `/home/byron/.local/share/lu-labs/voice/models/stt/faster-whisper-base.en` was reused. Only `DIO_PRESENCE_LOCAL_ASR_MODEL` was set in their existing environment files; credentials and authority switches were preserved. The owned checkout environment received `faster-whisper==1.2.1` and compatible `av==16.1.0`. PyAV 19 failed because its `av.open` no longer accepts the `metadata_errors` argument used by this faster-whisper version. Reproducible pins are in `requirements-vesper-voice.txt`.

Actual input was locally generated WAV speech saying “Hello. What can you help me with?”, then processed through HTTP voice ingress, cached local Whisper, the canonical engine, Pocket TTS Vera, and HTTP reply retrieval. No ASR, engine, renderer, or HTTP mocks were used for these checks. Session tokens were neither printed nor persisted in the proof.

| Service | Reloaded PID | Voice/reply HTTP | Actual returned audio |
| --- | --- | --- | --- |
| Public API, port 8772 | 145602 | 200 / 200 | `live-public-8772-vera.wav`, 23.64 s, SHA-256 `1fb7087992603b1e549d9ddc2f0f3ed4774020d91f4ad33f24e21d3c9fd24416` |
| Website server, port 8770 | 145604 | 200 / 200 | `live-public-8770-vera.wav`, 22.76 s, SHA-256 `2e7b3a4b6378f940dd369a6687737ccc7087ab2b7c23b20d71d6a88a8d61205b` |

Both replies identify `vera_pocket_public` / `pocket_tts`, carry the actual audio hash, and preserve `authority_created=false`, `external_send=REFUSE`, and `external_release=REFUSE`. Detailed evidence is in `live_public_voice_roundtrip.json`.

The separate signed bridge/cloud-edge lane remains blocked by a missing `DIO_PRESENCE_PUBLIC_SHARED_SECRET` in the bridge's existing process environment. No replacement secret was minted. The local in-process website engine round trips do not require that signing identity. Local verification does not establish that a deployed public hostname routes to these reloaded services.

## Primary licensing references and attribution

The [Kyutai model card](https://huggingface.co/kyutai/pocket-tts-without-voice-cloning) labels the weights CC BY 4.0. The installed Pocket TTS source maps Vera to `hf://kyutai/tts-voices/vctk/p229_023_enhanced.wav`; [Kyutai's voice repository](https://huggingface.co/kyutai/tts-voices#vctk) identifies VCTK recordings as CC BY 4.0. The [Pocket TTS README](https://github.com/kyutai-labs/pocket-tts/blob/main/README.md) links to the individual voice licenses, and the [source code license](https://github.com/kyutai-labs/pocket-tts/blob/main/LICENSE) is MIT. These are source references, not a blanket legal clearance.

Suggested provenance credit: “Speech generated with Pocket TTS by Kyutai; Vera voice source from VCTK, CC BY 4.0.” Retain the model/voice source links and the [CC BY 4.0 license link](https://creativecommons.org/licenses/by/4.0/) with distributed attribution material.
