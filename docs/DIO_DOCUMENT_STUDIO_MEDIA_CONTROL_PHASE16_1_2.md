# DIO Phase 16.1.2 — Document Studio Media Control

Phase 16.1.2 extends Document Studio's existing semantic-first formatting model into governed video-frame and thumbnail composition.

## Authority split

- Gamma supplies generated visual source material.
- The canonical script supplies authoritative wording.
- Document Studio selects the image-dominant region, applies Format Core styling, fits canonical titles, enforces safe zones, and renders the controlled frame.
- NicheFoundry supplies narration, cleared music, sound design and mastering.
- DIO binds the controlled frames and mastered audio into the final proof.

Gamma-rendered typography is never treated as authoritative content.

## Native receipt

`premium/document_studio_media/DOCUMENT_STUDIO_MEDIA_RECEIPT.json` records:

- native Document Studio execution;
- Format Core profile and profile hash;
- crop decision for each Gamma source;
- canonical title, line count and font size;
- typography safe-zone result;
- scene and thumbnail hashes;
- release refusal and human gate.

## Acceptance additions

- `native_document_studio_execution: PASS`
- `document_studio_format_core_binding: PASS`
- `document_studio_safe_zone_qa: PASS`
- `document_studio_motion_composition: PASS`

The corpus census promotes Document Studio from `SOURCE_BOUND_ONLY` to `NATIVE_EXECUTED`. Lingua, HOMS, Evidex, VAMP and Sophia retain their truthful non-native states, so the aggregate full-corpus claim remains refused.

## Run

```bash
python scripts/run_premium_media_phase16_1_1.py \
  --nichefoundry-root "$DIO_NICHEFOUNDRY_ROOT" \
  --provider auto \
  --output /tmp/dio-phase16-1-2-document-studio-media
```
