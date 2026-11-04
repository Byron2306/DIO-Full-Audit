# VESPER Performance Compiler: first canonical handoff

## What is now real

- `products/vesper_performance_compiler.py` compiles supplied, timed ARPAbet phonemes into deterministic 30 fps face-control frames.
- `config/vesper/viseme_contract_v1.json` defines ten visual visemes, the initial phoneme grouping, ARKit-compatible mouth-control profiles, Vera's canonical voice profile ID, and known limits.
- `media/product_asset_packs/homs_corpo_cult_v1/vesper/visemes/VESPER_VISEME_10GRID_CONCEPT.png` is a visual exploration sheet generated with the current VESPER artwork as reference. It is **not** a runtime sprite sheet, canonical identity approval, or proof of animation quality.

## Why this fits the local ComfyUI work

The local ComfyUI runtime is available at `http://127.0.0.1:8188`. Its built-in MediaPipe path contains `LoadMediaPipeFaceLandmarker`, `MediaPipeFaceLandmarker`, and `MediaPipeFaceMask`. The source returns a 478-point mesh and ARKit-52 blendshape values; the mask node can isolate the `lips` region. That gives the VESPER renderer a real geometry/mask handoff instead of treating each generated mouth as an unrelated picture.

The compatible Comfy-Org weight bundle is now installed at `runtime/ComfyUI/models/detection/mediapipe_face_fp32.safetensors`; its SHA-256 matches the published file. A MediaPipe `.task` file is not a drop-in substitute for the state-dict layout this Comfy loader expects.

The initial runtime path is:

```text
canonical Vera audio (hashed)
        +
phoneme alignments (start/end seconds)
        |
        v
products/vesper_performance_compiler.py
        |
        +--> frame-indexed ARKit-52 mouth controls
        +--> deterministic coarticulation and silence handling
        |
        v
ComfyUI MediaPipe landmarks + lips mask
        |
        v
mouth renderer / constrained lip-region edit
```

Vera remains the source of speech. This compiler never synthesizes, edits, or re-times the audio. A repeated input produces the same performance timeline. The current implementation accepts upstream phoneme alignments; automatic forced alignment and video encoding are not included yet.

## Ten-shape starter vocabulary

| Viseme | ARPAbet families | Intended mouth action |
| --- | --- | --- |
| REST | SIL, SP, PAUSE | relaxed neutral |
| MBP | M, B, P | closed bilabial contact |
| FV | F, V | lower lip meets upper teeth |
| EE | IY, IH, EY, Y | wide/front spread |
| EH | EH, AE | mid front opening |
| AH | AA, AH, AX, ER, AW | open jaw |
| OH | AO, OW, OY | rounded opening |
| OO | UW, UH, W | close pucker/funnel |
| TH | TH, DH | interdental gesture approximation |
| SH | SH, ZH, CH, JH, S, Z | narrow sibilant/affricate shape |

The class grouping is a practical starter contract, not a claim of perfect phonetic coverage. ARKit-52 has no tongue-out control, so TH/DH cannot yet describe tongue placement precisely. Unmapped consonants use a stated EE fallback pending a language-aware phoneme map. Afrikaans should receive its own reviewed map rather than silently inheriting the English fallback.

## Next ComfyUI pass

1. Feed the approved Vera source portrait into MediaPipe and persist its face landmarks, face box, and `lips` mask with a source-image hash.
2. Use the mouth landmark contour as the fixed local coordinate system. Generate or edit only inside the lip mask; keep the rest of Vera's face, hair, pose, lighting, and gold/black design fixed.
3. Render the ten target poses from one canonical source using controlled seeds and the appropriate local image/edit model. Score each result for identity drift, contour stability, and semantic distinction.
4. Bind the accepted artwork/mesh to the ten contract IDs and render short Vera phrases with the compiler's coarticulation output.
5. Store a receipt that binds audio hash, alignment hash, contract version, source-image hash, Comfy workflow/model IDs, seed, outputs, and human review.

The local MediaPipe node path has now run in ComfyUI on Vera's existing vertical artwork. The full-range detector produced a 478-point face mesh, ARKit-52 controls, a lip-only mask, and a visual mesh overlay. The mask and overlay are saved under `media/product_asset_packs/homs_corpo_cult_v1/vesper/visemes/geometry/`; their receipt binds them to the source artwork and workflow. The generated contact sheet is still an exploration board only; it is not a runtime sprite sheet.

A first closed M/B/P portrait candidate now exists at `media/product_asset_packs/homs_corpo_cult_v1/vesper/visemes/poses/VERA_MBP_CLOSED_CANDIDATE.png`. Krea2 generated a reference-conditioned mouth crop; ComfyUI composited only a tight, feathered lip mask back over the canonical portrait and restored the original alpha. This candidate is not approved for release. SD inpainting and a wider Krea2 mask both produced unacceptable artifacts for the open-AH pose, so the 10-pose raster set is **not complete**. The geometry, timing contract, and closed-mouth candidate are real; open-jaw rendering still needs a different mouth-interior/teeth strategy or a mesh renderer.

The Comfy-Org MediaPipe weight bundle installed for the face path is published under Apache-2.0 at [Comfy-Org/mediapipe](https://huggingface.co/Comfy-Org/mediapipe/resolve/main/detection/mediapipe_face_fp32.safetensors). Its local SHA-256 is recorded in the geometry receipt.
