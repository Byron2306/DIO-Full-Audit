# DIO Cinematic Product Rendering Layer

## Purpose

Round 2 upgrades the Product Explainer Media Compiler from technically valid rendering to recognizable DIO brand execution.

The first HOMS autonomous render proved semantic compilation, Vesper narration, measured timing reconciliation, audio QA, NicheFoundry execution and authority boundaries. Human review rejected the visual and music quality: the imagery read as generic editorial/education material and the music did not carry the DIO identity.

This design makes the existing DIO cinematic style profile executable. It does not change canonical product truth, evidence authority, or publication authority.

## Locked creative direction

DIO product explainers share one cinematic world and one sonic genome, but each product receives its own visual choreography and score treatment.

The invariant DIO visual world is:

- near-black architectural space;
- black glass, obsidian metal and polished dark surfaces;
- monumental technological scale;
- restrained cream typography;
- controlled warm gold for verified, active, governed or released states;
- symmetry, negative space, depth, haze and deliberate motion;
- real product evidence before generated metaphor.

The following remain forbidden:

- generic blue AI glow;
- humanoid robots;
- glowing brains;
- Matrix-style code rain;
- stock-office imagery;
- decorative HUD clutter;
- fake product interfaces or generated scenes presented as proof.

The sonic rule is: **same musical language, different composition**. The DIO sonic identity remains the source motif. Each product receives a deterministic arrangement profile around that motif. The flagship trailer score remains special and is not copied wholesale into every product explainer.

## Authority invariants

- Product Registry / ATLAS / manifests define what the product is.
- Evidence and Commercial Truth define what may be claimed.
- Lingua controls expression.
- Market intelligence may change emphasis only.
- Media style and product media profiles control representation only.
- Generated visual metaphor may never be classified as observed proof.
- Real product output, real UI and real evidence outrank generated imagery.
- Local autonomous media rendering remains `ALLOW`.
- External publication remains `NEEDS_YOU` / `REFUSE` until explicit human action.
- Media spend remains `REFUSE`.
- Learning or creative iteration may not silently mutate canonical product truth.

## Architecture

```text
Product Explainer Manifest
        +
DIO_CINEMATIC_BRAND_V1
        +
Product Media Profile (HOMS first)
        |
        v
Brand Render Brief Compiler
        |
        +--> visual grammar + forbidden motifs + motion + typography + end card
        +--> product scene grammar
        +--> product score recipe derived from DIO sonic identity
        |
        v
MediaProductionRequest v2
        |
        v
Premium Media Federation
        |
        +--> renderer-facing script copy enriched with visual_requirements
        +--> governed product score WAV
        +--> NicheFoundry / Gamma
        +--> Document Studio control surface
        |
        v
Local canonical product explainer master
        |
        v
Human visual/audio release gate
```

The semantic script remains a truth-bearing object. Renderer-specific visual instructions are applied to a deep copy inside the media federation. This prevents creative styling from contaminating semantic challenge or claim custody.

## Product media profile registry

Create `config/product_media_profiles.json` with schema `dio.product_media_profile_registry.v1`.

The first profile is `HOMS`. It contains only representation data:

- scene grammar keyed by canonical story beat;
- visual mode (`metaphor`, `hybrid`, `proof`);
- focal subject;
- product-specific visual requirements;
- overlay guidance;
- music tone;
- deterministic score recipe.

The HOMS scene grammar is:

1. `problem`: fragmented assessment work represented as disordered academic artifacts within a monumental dark archive, not stressed-teacher stock photography.
2. `product_definition`: HOMS represented as a governed academic production desk within the DIO architectural world.
3. `mechanism`: briefs, rubrics, memoranda and grade constraints moving through explicit governed stages and human gates.
4. `proof`: real bound HOMS outputs or evidence are preferred. Generated imagery may frame them but may not impersonate them.
5. `differentiation`: grade-aware assistance and explicit educator authority represented as separate machine and human decision chambers.
6. `result`: review-ready academic outputs emerging from governed flow, with no unsupported time-saving or outcome claims.
7. `call_to_action`: canonical DIO/HOMS brand end card.

## Brand render brief

Add a focused module `products/product_explainer_branding.py`.

It exposes:

```python
load_product_media_profile(product_id: str, *, root: Path) -> tuple[dict[str, Any], str]
compile_brand_render_brief(style_profile: dict[str, Any], product_profile: dict[str, Any], *, product_id: str) -> dict[str, Any]
enrich_renderer_script(script_package: dict[str, Any], production_request: dict[str, Any]) -> dict[str, Any]
```

`compile_brand_render_brief` returns renderer-facing data, including:

- `profile_id`;
- `visual_direction`;
- `palette`;
- `forbidden_motifs`;
- `typography`;
- `motion`;
- `end_card`;
- `scene_grammar`;
- `music_direction`.

`enrich_renderer_script` deep-copies the semantic script and adds, per scene:

- `visual_mode`;
- `focal_subject`;
- `visual_requirements`;
- `overlay_text`;
- `motion_cue`;
- `brand_profile_id`.

It must not alter narration, claim IDs, source IDs, story beat or semantic timing.

## NicheFoundry compatibility seam

The harvested Phase 11 NicheFoundry implementation constructs Gamma illustration prompts from `scene.visual_requirements`. Its `sceneIllustrationPrompt` function also has a generic `practical_open_source` fallback, which explains the current generic software/editorial aesthetic.

Round 2 therefore injects strong DIO and HOMS instructions into `visual_requirements` before NicheFoundry receives the renderer-facing script. No NicheFoundry source modification is required for the first pass.

`Premium Media Federation._prepare_episode()` also writes the compiled brand brief into `brief.json` for custody and future renderer compatibility.

If the current local NicheFoundry checkout is later proven to ignore `visual_requirements`, that is a typed compatibility failure and a separate NicheFoundry patch cycle. DIO must not silently assume brand execution occurred.

## Motion and end card

The existing hardcoded `restrained documentary push` cue is removed from the explainer path. The render contract consumes the style profile motion default.

The CTA scene receives a locked end-card representation containing:

- canonical DIO sigil path;
- canonical DIO wordmark path;
- product name;
- `DIO WORKFLOWS`;
- `dioworkflows.co.za`;
- black background / cream type / controlled gold accent rules.

Brand files remain source-bound assets. No font files are copied or redistributed.

## Product score builder

The current generic or selected music bed is not sufficient as the default DIO product identity.

Round 2 adds a governed local score builder to the media federation. It consumes:

- the project-owned DIO sonic identity WAV;
- the product score recipe from `product_media_profiles.json`;
- the explainer target duration.

For HOMS the arrangement is intentionally restrained and institutional:

- the DIO motif remains audible but subordinate to narration;
- low-pass filtering softens brightness;
- a delayed filtered shadow creates depth;
- no stock-corporate uplift;
- no EDM or trailer-braam behavior;
- fade-in and fade-out are deterministic;
- output is 48 kHz stereo PCM WAV;
- the generated product score is treated as project-owned local audio and passes through the existing imported-music rights path.

The score builder uses `ffmpeg`, already required by the premium media pipeline. It records source hash, recipe, command-independent recipe fingerprint, output hash and duration in `DIO_PRODUCT_SCORE_RECEIPT.json`.

If the bound sonic identity is missing or invalid, the render refuses with a typed premium-media error. It does not fall back to generic music.

## Media production request

`build_media_production_request()` resolves both the style profile and product media profile and writes their hashes into the request.

The request gains:

```json
{
  "brand_render_brief": {},
  "product_media_profile": {"id": "HOMS", "sha256": "..."},
  "sound": {
    "music_origin": "dio_product_score",
    "sonic_identity": "DIO_SONIC_IDENTITY_V1",
    "music_direction": {},
    "score_recipe": {}
  }
}
```

The media request remains representation authority only.

## Proof versus metaphor

Scene modes are enforced as follows:

- `metaphor`: generated cinematic imagery is permitted.
- `hybrid`: generated DIO environment may frame or contextualize real product artifacts.
- `proof`: real bound assets are required for any representation labeled as proof; generated imagery may not replace the evidence.

For HOMS, the canonical proof scene is `proof`. Mechanism is `hybrid`. Other scenes default to `metaphor` except CTA, which is `brand_end_card`.

The current semantic challenge rule against generated evidence remains in force.

## Verification

Round 2 is accepted only when all of the following are demonstrated:

1. brand profile and HOMS product media profile resolve with source hashes;
2. media production request contains the full renderer-facing brand brief;
3. renderer-facing script contains DIO visual requirements and product-specific scene grammar;
4. semantic narration/claims/source IDs remain unchanged after renderer enrichment;
5. forbidden DIO motifs are propagated to every generated scene instruction;
6. proof scene remains proof-first and cannot be silently downgraded to metaphor;
7. motion cue derives from `DIO_CINEMATIC_BRAND_V1`, not the previous documentary hardcode;
8. local HOMS product score is 48 kHz stereo, source-bound and hash-receipted;
9. generic/procedural music fallback is refused when `dio_product_score` is requested;
10. existing explainer/media contract tests remain green;
11. HOMS full autonomous render completes locally;
12. human review confirms visual and music quality before a final media binding is frozen.

Technical PASS does not imply human visual approval. Final media custody is frozen only after the human quality gate accepts the artifact.
