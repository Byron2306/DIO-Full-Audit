# DIO Cinematic Product Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DIO product explainers render inside the approved DIO cinematic brand world with product-specific scene grammar and a governed product score derived from the DIO sonic identity.

**Architecture:** Keep the semantic explainer script pure. Resolve a global media style profile plus a product media profile into a `brand_render_brief`, then enrich a deep renderer-facing copy inside Premium Media Federation. Generate a local 48 kHz stereo product score from the bound DIO sonic motif and pass it through the existing imported-music rights path.

**Tech Stack:** Python 3, JSON registries, pytest, ffmpeg/ffprobe, existing NicheFoundry/Gamma and Document Studio seams.

**Spec:** `docs/superpowers/specs/2026-08-29-dio-cinematic-product-rendering-design.md`

## Global Constraints

- Product truth and claim authority remain unchanged.
- Renderer enrichment must not mutate semantic narration, claim IDs, source IDs, story beat, or timing.
- Generated visual metaphor may never be classified as observed proof.
- Real product evidence outranks generated imagery.
- `DIO_CINEMATIC_BRAND_V1` is the global visual/sonic parent profile.
- HOMS is the first product media profile.
- Local autonomous render remains `ALLOW`; external publication remains `NEEDS_YOU` / `REFUSE`; media spend remains `REFUSE`.
- No generic/procedural music fallback is permitted when a DIO product score is requested.
- Do not stage or overwrite the approved local dirty files `config/vesper_voice_profiles.json` and `presence_core/voice.py` unless a separate voice defect is proven.

---

### Task 1: Product Media Profile Registry and Brand Compiler

**Files:**
- Create: `config/product_media_profiles.json`
- Create: `products/product_explainer_branding.py`
- Create: `tests/test_product_explainer_branding.py`

**Interfaces:**
- Consumes: `config/media_style_profiles.json`, product ID, root path.
- Produces: `load_product_media_profile(product_id, root=ROOT)` and `compile_brand_render_brief(style_profile, product_profile, product_id=...)`.

- [ ] **Step 1: Write failing registry/compiler tests**

```python
from products.product_explainer_branding import (
    compile_brand_render_brief,
    load_product_media_profile,
)
from products.product_explainer_compiler import load_media_style_profile


def test_homs_media_profile_and_dio_brand_compile(root):
    style, _ = load_media_style_profile("DIO_CINEMATIC_BRAND_V1", root=root, require_assets=False)
    product, product_sha = load_product_media_profile("homs", root=root)
    brief = compile_brand_render_brief(style, product, product_id="HOMS")
    assert product_sha.startswith("sha256:")
    assert brief["profile_id"] == "DIO_CINEMATIC_BRAND_V1"
    assert brief["product_id"] == "HOMS"
    assert "black glass" in brief["visual_direction"].lower()
    assert "generic blue ai glow" in [x.lower() for x in brief["forbidden_motifs"]]
    assert brief["scene_grammar"]["proof"]["visual_mode"] == "proof"
    assert brief["scene_grammar"]["mechanism"]["visual_mode"] == "hybrid"
    assert brief["music_direction"]["inherits"] == "DIO_SONIC_IDENTITY_V1"
```

- [ ] **Step 2: Run RED**

Run:

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_branding.py
```

Expected: import/file failure because the registry and branding module do not yet exist.

- [ ] **Step 3: Add HOMS profile and minimal compiler**

`config/product_media_profiles.json` must define `HOMS` scene grammar for `problem`, `product_definition`, `mechanism`, `proof`, `differentiation`, `result`, and `call_to_action`, plus the HOMS score recipe.

`products/product_explainer_branding.py` must:

```python
def load_product_media_profile(product_id: str, *, root: Path = ROOT) -> tuple[dict[str, Any], str]: ...

def compile_brand_render_brief(
    style_profile: dict[str, Any],
    product_profile: dict[str, Any],
    *,
    product_id: str,
) -> dict[str, Any]: ...
```

Hash the exact selected product profile with canonical JSON and return `sha256:<hex>`.

- [ ] **Step 4: Run GREEN**

Run the same focused test. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/product_media_profiles.json products/product_explainer_branding.py tests/test_product_explainer_branding.py
git commit -m "feat: compile cinematic product brand briefs"
```

---

### Task 2: Bind Brand Brief into MediaProductionRequest v2

**Files:**
- Modify: `products/product_explainer_pipeline.py`
- Modify: `tests/test_product_explainer_branding.py`
- Modify: `tests/test_product_explainer_graduation.py`

**Interfaces:**
- Consumes: Task 1 profile loader/compiler.
- Produces: `MEDIA_PRODUCTION_REQUEST.json` containing `brand_render_brief`, product profile hash and DIO score request.

- [ ] **Step 1: Write failing request tests**

```python
def test_media_request_carries_resolved_brand_and_product_score(compiled_homs, root):
    request = build_media_production_request(compiled_homs, root=root)
    assert request["brand_render_brief"]["profile_id"] == "DIO_CINEMATIC_BRAND_V1"
    assert request["product_media_profile"]["id"] == "HOMS"
    assert request["product_media_profile"]["sha256"].startswith("sha256:")
    assert request["sound"]["music_origin"] == "dio_product_score"
    assert request["sound"]["sonic_identity"] == "DIO_SONIC_IDENTITY_V1"
    assert request["release"]["external_publication"] == "NEEDS_YOU"
    assert request["release"]["media_spend"] == "REFUSE"
```

- [ ] **Step 2: Run RED**

Run branding + graduation tests. Expected: missing request keys.

- [ ] **Step 3: Implement request binding**

Inside `build_media_production_request()`:

1. resolve `DIO_CINEMATIC_BRAND_V1` as today;
2. load `HOMS` from product media registry using manifest product ID;
3. compile the brand render brief;
4. add:

```python
"product_media_profile": {"id": manifest["product_id"], "sha256": product_profile_sha},
"brand_render_brief": brand_brief,
"sound": {
    "music_origin": "dio_product_score",
    "sonic_identity": "DIO_SONIC_IDENTITY_V1",
    "music_direction": brand_brief["music_direction"],
    "score_recipe": product_profile["score"]["recipe"],
    "source_path": product_profile["score"]["source_path"],
},
```

Do not change release authority.

- [ ] **Step 4: Run GREEN**

Expected focused tests PASS.

- [ ] **Step 5: Commit**

```bash
git add products/product_explainer_pipeline.py tests/test_product_explainer_branding.py tests/test_product_explainer_graduation.py
git commit -m "feat: bind cinematic brand brief to media request"
```

---

### Task 3: Enrich Renderer Script Without Mutating Semantic Script

**Files:**
- Modify: `products/product_explainer_branding.py`
- Modify: `products/premium_media_federation.py`
- Modify: `tests/test_product_explainer_branding.py`
- Modify: `tests/test_premium_media_explainer_integration.py`

**Interfaces:**
- Consumes: semantic script package + `brand_render_brief`.
- Produces: renderer-facing deep copy carrying NicheFoundry `visual_requirements` and DIO motion/end-card data.

- [ ] **Step 1: Write failing immutability/visual tests**

```python
def test_renderer_enrichment_is_brand_bound_and_semantically_immutable(script, request):
    before = json.loads(json.dumps(script))
    rendered = enrich_renderer_script(script, request)
    assert script == before
    for source, scene in zip(script["scenes"], rendered["scenes"]):
        assert scene["narration"] == source["narration"]
        assert scene["claim_ids"] == source["claim_ids"]
        assert scene["source_ids"] == source["source_ids"]
        assert scene["story_beat"] == source["story_beat"]
        assert scene["target_duration_seconds"] == source["target_duration_seconds"]
        assert scene["brand_profile_id"] == "DIO_CINEMATIC_BRAND_V1"
        assert scene["visual_requirements"]
    proof = next(x for x in rendered["scenes"] if x["story_beat"] == "proof")
    assert proof["visual_mode"] == "proof"
```

Integration must also assert `_prepare_episode()` writes the enriched script to the episode while the caller-owned semantic script remains unchanged.

- [ ] **Step 2: Run RED**

Expected: missing `enrich_renderer_script` and/or missing scene keys.

- [ ] **Step 3: Implement enrichment**

`enrich_renderer_script()` must deep-copy with JSON serialization, prepend global DIO visual direction and forbidden motifs to each scene's product-specific requirements, and set motion from the style profile. CTA gets `visual_mode="brand_end_card"` and end-card requirements.

`_prepare_episode()` must call it when `production_request["brand_render_brief"]` exists and write `brief["brand_render_brief"]`, `brief["music_direction"]`, and the enriched `script_package.json`.

- [ ] **Step 4: Replace hardcoded explainer motion cue**

In `_prepare_native_render_contract()`, use the enriched scene's `motion_cue` before falling back to the legacy documentary cue.

- [ ] **Step 5: Run GREEN and existing integration suite**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_branding.py tests/test_premium_media_explainer_integration.py
```

- [ ] **Step 6: Commit**

```bash
git add products/product_explainer_branding.py products/premium_media_federation.py tests/test_product_explainer_branding.py tests/test_premium_media_explainer_integration.py
git commit -m "feat: drive renderer with DIO scene grammar"
```

---

### Task 4: Build Governed HOMS Product Score from DIO Sonic Identity

**Files:**
- Modify: `products/premium_media_federation.py`
- Create: `tests/test_premium_media_product_score.py`

**Interfaces:**
- Consumes: `production_request["sound"]`, bound DIO sonic WAV, target duration.
- Produces: `imports/music_bed.wav` and `DIO_PRODUCT_SCORE_RECEIPT.json`.

- [ ] **Step 1: Write failing score-builder test**

Create a short temporary 48 kHz stereo WAV motif, request `music_origin="dio_product_score"`, and call the score preparation helper. Assert:

```python
assert receipt["schema"] == "dio.media.product_score.v1"
assert receipt["sonic_identity"] == "DIO_SONIC_IDENTITY_V1"
assert receipt["product_id"] == "HOMS"
assert receipt["duration_seconds"] == pytest.approx(5.0, abs=0.05)
assert receipt["sample_rate"] == 48000
assert receipt["channels"] == 2
assert receipt["source_sha256"]
assert receipt["output_sha256"]
assert (episode_dir / "imports/music_bed.wav").is_file()
```

- [ ] **Step 2: Run RED**

Expected: helper missing.

- [ ] **Step 3: Implement deterministic ffmpeg score recipe**

Add `_prepare_dio_product_score(episode_dir, production_request, target_seconds)`.

For the HOMS `institutional_glass` recipe, invoke ffmpeg with the bound sonic identity as the only musical source, loop to target duration, convert to 48 kHz stereo, keep motif gain low, add a delayed/filtered shadow copy, high-pass subsonic rumble, low-pass excessive brightness, and deterministic fades. Do not fetch external music.

The filter graph is assembled from numeric recipe values stored in the product profile. The receipt records recipe + hashes, not authority.

- [ ] **Step 4: Refuse generic fallback**

When `music_origin == "dio_product_score"`, missing source/ffmpeg/invalid output must raise `PremiumMediaError`; do not continue into procedural or generic music.

- [ ] **Step 5: Integrate into `_prepare_episode()`**

Call the product score builder before NicheFoundry audio performance. Return its receipt as the episode's music import so the existing imported music path consumes `imports/music_bed.wav`.

- [ ] **Step 6: Run GREEN**

Run score + integration + music contract tests.

- [ ] **Step 7: Commit**

```bash
git add products/premium_media_federation.py tests/test_premium_media_product_score.py
git commit -m "feat: derive product score from DIO sonic identity"
```

---

### Task 5: Contract Verification and HOMS Cinematic Render

**Files:**
- Modify only if a failing contract reveals a proven defect.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: a local HOMS premium explainer candidate for human visual/audio review.

- [ ] **Step 1: Run focused contracts**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 -m pytest -q \
tests/test_product_explainer_branding.py \
tests/test_premium_media_product_score.py \
tests/test_premium_media_voice_timing.py \
tests/test_premium_media_explainer_integration.py \
tests/test_premium_media_gauntlet_contract.py \
tests/test_premium_media_runner_contract.py \
tests/test_product_explainer_family_resolution.py \
tests/test_product_explainer_semantic_hydration.py \
tests/test_product_explainer_copy_quality.py \
tests/test_product_explainer_compiler.py \
tests/test_product_explainer_graduation.py
```

Expected: all selected tests PASS.

- [ ] **Step 2: Run HOMS cinematic render**

```bash
DIO_VENV=/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv
export PATH="$DIO_VENV/bin:$PATH"
rm -rf /tmp/dio-homs-cinematic
python3 scripts/run_product_explainer_graduation.py \
  --product homs \
  --root /home/byron/DIO-Full-Audit \
  --output /tmp/dio-homs-cinematic \
  --render \
  --nichefoundry-root /home/byron/Downloads/NicheFoundry_Phase11 \
  --provider imported
```

Expected: `render_state=PASS`, semantic graduation PASS, authority boundaries unchanged.

- [ ] **Step 3: Inspect custody**

Inspect `MEDIA_PRODUCTION_REQUEST.json`, episode `script_package.json`, `DIO_PRODUCT_SCORE_RECEIPT.json`, Gamma execution receipt, audio performance report, and final premium video.

- [ ] **Step 4: Human quality gate**

Play `/tmp/dio-homs-cinematic/premium_media/media/youtube/FINAL_VIDEO_PREMIUM.mp4`.

Acceptance requires explicit human confirmation that visual language and music now meet the DIO brand bar. Technical PASS alone is insufficient.

- [ ] **Step 5: Freeze final media binding only after human approval**

After approval, add the separate `FINAL_MEDIA_BINDING.json` custody task with final path/hash and human approval receipt. Do not freeze a rejected candidate.

## Self-review

- Spec coverage: global brand, HOMS scene grammar, semantic immutability, proof/metaphor boundary, motion, end card, sonic genome, refusal behavior and human quality gate are all mapped to tasks.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: branding module outputs feed MediaProductionRequest, which feeds renderer enrichment and product score preparation.
