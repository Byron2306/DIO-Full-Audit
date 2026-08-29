# HOMS CORPO CULT Asset Pack Design

## Purpose

The first Round 2 HOMS cinematic render achieved semantic, audio, rights, render and authority correctness. Human review accepted the film as good but identified one remaining visual gap: it still reads as a premium academic explainer rather than an unmistakable DIO institution.

This extension turns the approved black-glass/gold HOMS concept into a reusable, hash-bound visual asset pack and scene compositor. It intensifies HOMS without changing product truth, claim authority, proof classification, narration, Vesper, the governed DIO product score, or publication authority.

`CORPO CULT` is an internal creative nickname only. It must never appear in customer-facing copy, captions, product claims, filenames exposed to customers, or publication metadata.

## Locked visual doctrine

HOMS becomes a governed academic command institution inside the DIO cinematic world.

The visual hierarchy is:

1. monumental near-black architectural space;
2. black glass, obsidian, graphite and reflective dark stone;
3. subdued bronze/gold architectural detailing as persistent brand texture;
4. luminous warm gold reserved for verified, active, governed, approved or human-authorized state;
5. real HOMS evidence and outputs inserted into controlled glass surfaces when proof is available;
6. restrained cream typography and canonical DIO/HOMS branding;
7. negative space, symmetry, depth, haze and deliberate motion.

The target feeling is not luxury decoration. It is institutional gravity: a machine built by people who distrust unchecked machines.

## Forbidden visual shortcuts

The following remain forbidden:

- generic blue AI glow;
- humanoid robots;
- glowing brains;
- Matrix-style code rain;
- stock classroom, office or teacher photography as the dominant scene language;
- fake product interfaces;
- generated documents presented as real HOMS outputs;
- decorative HUD clutter;
- random gold bloom with no semantic purpose;
- literal religious symbols or public-facing cult language;
- generated imagery classified as observed proof.

## Asset-pack architecture

The pack lives at:

```text
media/product_asset_packs/homs_corpo_cult_v1/
```

with this tracked structure:

```text
pack.json
reference/
  HOMS_CORPO_CULT_REFERENCE_V1.png
plates/
  HOMS_BG_COMMAND_HALL_4K.png
  HOMS_BG_REACTOR_CHAMBER_4K.png
  HOMS_BG_GOVERNANCE_WALL_4K.png
  HOMS_BG_ACADEMIC_DESK_4K.png
  HOMS_ENDCARD_BG_4K.png
overlays/
  HOMS_GOLD_FRAME.png
  HOMS_GOLD_PATHWAYS.png
  HOMS_REACTOR_RING.png
  HOMS_GLASS_PANEL.png
  HOMS_ATMOSPHERE.png
```

The reference board is inspiration only and may never be used directly as a scene background because its text/UI/person elements are baked into the pixels.

Production plates contain no baked product claims, no people, no fake UI, and no customer-facing text. All plates are 16:9 and normalized to 3840x2160. Transparent overlays are normalized to 3840x2160 RGBA.

## Asset manifest

`pack.json` uses schema `dio.media.visual_asset_pack.v1` and records:

- `pack_id = HOMS_CORPO_CULT_V1`;
- `product_id = HOMS`;
- pack version;
- representation-only authority statement;
- each asset ID, role, relative path, SHA-256, pixel dimensions, alpha state and source class;
- rights state `INTERNAL_ORIGINAL`;
- `commercial_use = true`;
- `remote_runtime_fetch = REFUSE`;
- `generated_as_proof = REFUSE`.

The pack is fail-closed. Missing files, hash mismatches, wrong dimensions, wrong alpha mode, path traversal, or an invalid rights state refuse resolution.

## Deterministic overlay builder

Raster architectural plates are human-approved creative inputs. Reusable overlays should be deterministic rather than repeatedly image-generated.

Add `scripts/build_homs_corpo_cult_asset_pack.py` using Pillow, already present in the repository runtime, to normalize approved plates and generate transparent overlays from numeric parameters.

The builder must generate:

- a restrained gold frame;
- controlled routing/pathway geometry;
- a concentric reactor ring;
- black-glass panel treatment;
- subtle atmospheric particles/haze.

The builder records hashes into `pack.json`. It does not create semantic authority.

## Product media profile binding

The existing `HOMS` entry in `config/product_media_profiles.json` gains:

```json
"visual_asset_pack": {
  "pack_id": "HOMS_CORPO_CULT_V1",
  "scene_bindings": {}
}
```

Every canonical story beat receives a scene recipe with:

- background asset ID;
- ordered overlay asset IDs;
- ambient gold intensity;
- luminous gold state rule;
- optional proof slot;
- motion cue remains inherited from the existing scene grammar.

Canonical HOMS mapping:

1. `problem` -> command hall, subdued pathways, fragmented academic objects only as abstraction;
2. `product_definition` -> reactor chamber, reactor ring illuminated as product identity;
3. `mechanism` -> academic desk / command hall hybrid, pathways visibly route assessment inputs through governed stages;
4. `proof` -> governance wall plus real bound HOMS proof inserted into a glass proof slot; if no proof exists, no generated substitute is allowed;
5. `differentiation` -> governance wall with visibly separate automated and human-authority regions;
6. `result` -> command hall resolving into ordered outputs with controlled active gold;
7. `call_to_action` -> clean end-card plate with canonical DIO sigil/wordmark and website supplied by the existing brand layer.

## Resolver

Add `products/product_visual_asset_pack.py` exposing:

```python
load_visual_asset_pack(pack_id: str, *, root: Path = ROOT) -> tuple[dict[str, Any], str]
resolve_scene_asset_recipe(pack: dict[str, Any], product_profile: dict[str, Any], story_beat: str) -> dict[str, Any]
```

The first function validates the manifest and exact file hashes. The second resolves only representation instructions. Neither may read or modify claims, commercial truth, evidence classifications, release authority, or spend authority.

## Brand brief and media request

`compile_brand_render_brief()` adds the selected asset-pack ID and scene recipes to the renderer-facing brief.

`build_media_production_request()` adds:

```json
"visual_asset_pack": {
  "id": "HOMS_CORPO_CULT_V1",
  "sha256": "sha256:...",
  "fallback": "REFUSE"
}
```

The semantic explainer manifest remains unchanged.

`enrich_renderer_script()` adds `visual_asset_recipe` to the renderer-facing deep copy only. Narration, story beat, claim IDs, source IDs and semantic timing remain unchanged.

## Scene compositor

Add `products/product_explainer_scene_compositor.py` exposing:

```python
compose_product_explainer_scenes(
    episode_dir: Path,
    script_package: dict[str, Any],
    production_request: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]
```

The compositor uses Pillow to create deterministic 1920x1080 PNG scene plates from the 4K pack assets.

For each scene it:

1. resolves the configured 4K background;
2. applies ordered transparent overlays;
3. applies scene-specific ambient/luminous gold treatment without changing semantic content;
4. if the scene is `proof`, inserts only a bound real proof asset into the configured proof slot;
5. writes a final scene image under `premium_visuals/dio_asset_pack/`;
6. records every input/output hash in `DIO_VISUAL_ASSET_PACK_RECEIPT.json`.

The compositor does not bake narration or marketing claims into generated visuals. The existing renderer remains responsible for captions/text treatment.

## Proof behavior

For `visual_mode = proof`:

- a real bound proof asset may be composited;
- a generated image may frame the proof but may not replace it;
- if no proof asset exists, the compositor emits a neutral governed background with `proof_asset_state = MISSING` and no fake document/UI;
- it must never label a generated placeholder as proof.

The receipt carries the proof state explicitly.

## NicheFoundry integration

The existing NicheFoundry execution remains intact for audio, timing, Gamma execution evidence and final rendering.

After `build_premium_assets.js` runs and before `_prepare_native_render_contract()` freezes `visual_plan.json`, Premium Media Federation invokes the DIO scene compositor when a `visual_asset_pack` is requested.

`_prepare_native_render_contract()` gains an optional composed-scene receipt. When present:

- each scene `preview_path` points to the DIO-composited image;
- provider becomes `dio_asset_pack`;
- composition becomes `dio_asset_pack_bound`;
- `visual_report.json` records `composition_authority = dio_asset_pack`;
- Gamma execution remains recorded as supporting generation evidence but is not the final visual authority.

If HOMS requests `HOMS_CORPO_CULT_V1` and any required scene composition is missing or invalid, the render raises `PremiumMediaError`. It must not silently fall back to generic Gamma imagery.

## Thumbnail and end card

The compositor produces a candidate thumbnail from the HOMS product-definition or CTA composition. The canonical DIO wordmark and sigil remain source-bound through the existing style profile.

No font file is copied into the pack. Existing system font resolution continues to apply.

## Receipt and custody

`DIO_VISUAL_ASSET_PACK_RECEIPT.json` records:

- schema `dio.media.visual_asset_pack_receipt.v1`;
- pack ID and manifest hash;
- source asset hashes;
- per-scene recipe fingerprint;
- proof insertion state;
- output scene paths/hashes/dimensions;
- composition authority `dio_asset_pack`;
- generic visual fallback `REFUSE`;
- external publication authority created `false`.

The final premium proof/receipt adds:

- `visual_asset_pack_binding = PASS`;
- `visual_asset_pack_fallback = REFUSE`;
- `visual_composition_authority = dio_asset_pack`.

## Authority invariants

- Product Registry / ATLAS / manifests continue to define what HOMS is.
- Evidence / Commercial Truth continue to define what may be claimed.
- The asset pack is representation only.
- No generated visual becomes evidence by being placed in the pack.
- Local render remains `ALLOW`.
- External publication remains `NEEDS_YOU` / renderer `REFUSE` until explicit human action.
- Media spend remains `REFUSE`.
- Existing Vesper voice and DIO product-score behavior remain unchanged.
- The approved dirty local voice files remain untouched unless a separate voice defect is proven.

## Acceptance criteria

The HOMS CORPO CULT pass is accepted only when:

1. the pack resolves from a local manifest with exact hashes;
2. all production plates are 3840x2160 and all overlays meet alpha/dimension requirements;
3. every canonical HOMS story beat resolves to one explicit scene recipe;
4. the media request contains the pack ID/hash and `fallback = REFUSE`;
5. renderer enrichment does not mutate semantic narration, timing, claim IDs or source IDs;
6. the compositor produces seven deterministic 1920x1080 scene images and a custody receipt;
7. proof scenes insert only real bound proof assets or explicitly record `MISSING` without fabrication;
8. HOMS pack requests cannot silently fall back to Gamma visuals;
9. `visual_plan.json` points to the DIO-composited scene images and records `dio_asset_pack` as composition authority;
10. Vesper, governed HOMS score, music-rights and authority gates remain green;
11. existing Round 2 contract tests plus new asset-pack tests pass;
12. a full HOMS render completes locally;
13. human review explicitly confirms the result reaches the intended gilded DIO institutional bar;
14. only after human approval are the pack hash and final candidate hash frozen into final media custody.
