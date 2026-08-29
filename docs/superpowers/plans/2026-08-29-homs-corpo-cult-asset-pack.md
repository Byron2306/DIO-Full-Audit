# HOMS CORPO CULT Asset Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved gilded HOMS visual language into a reusable, hash-bound asset pack that deterministically composes all seven HOMS explainer scenes and becomes the final visual authority for HOMS renders.

**Architecture:** Add a generic local visual-asset-pack registry/resolver, a deterministic HOMS pack builder, HOMS scene bindings, and a Pillow compositor that emits renderer-ready 1920x1080 scene images. Premium Media Federation will keep NicheFoundry/Gamma execution intact but replace HOMS final scene preview paths with DIO-composited assets; when the pack is requested, silent fallback to generic Gamma is refused.

**Tech Stack:** Python 3, JSON registries, Pillow, hashlib, pytest, existing Product Explainer Compiler, Premium Media Federation, NicheFoundry/Gamma, ffmpeg/ffprobe for existing media pipeline.

**Spec:** `docs/superpowers/specs/2026-08-29-homs-corpo-cult-asset-pack-design.md`

## Global Constraints

- `CORPO CULT` is an internal creative nickname only and must never appear in customer-facing narration, captions, claims or publication metadata.
- Product truth, claim authority, evidence classification and semantic timing remain unchanged.
- Generated pack imagery is representation only and may never become observed proof.
- Real bound HOMS proof outranks generated imagery.
- Ambient bronze/gold may provide brand texture; luminous warm gold is reserved for verified, active, governed, approved or human-authorized state.
- Production plates are 3840x2160 RGB/RGBA; compositor outputs are 1920x1080 RGBA/RGB PNG.
- Pack files are local and hash-bound; remote runtime fetch is `REFUSE`.
- A requested HOMS asset pack may not silently fall back to generic Gamma imagery.
- Existing Vesper voice and DIO product-score behavior remain unchanged.
- Local autonomous render remains `ALLOW`; external publication remains `NEEDS_YOU` / renderer `REFUSE`; media spend remains `REFUSE`.
- Do not stage or overwrite `config/vesper_voice_profiles.json` or `presence_core/voice.py` unless a separate voice defect is proven.

---

### Task 1: Add the Generic Visual Asset Pack Registry and Resolver

**Files:**
- Create: `config/visual_asset_packs.json`
- Create: `products/product_visual_asset_pack.py`
- Create: `tests/test_product_visual_asset_pack.py`

**Interfaces:**
- Consumes: pack ID and repository root.
- Produces: `load_visual_asset_pack(pack_id: str, *, root: Path = ROOT) -> tuple[dict[str, Any], str]`.
- Produces: `resolve_scene_asset_recipe(pack: dict[str, Any], product_profile: dict[str, Any], story_beat: str) -> dict[str, Any]`.

- [ ] **Step 1: Write the failing resolver tests**

Create a temporary repository root containing a registry, pack manifest and synthetic 3840x2160 PNG assets. The focused test must prove schema validation, file hashing, dimensions, alpha requirements and path containment.

```python
from pathlib import Path
from PIL import Image
import hashlib
import json
import pytest

from products.product_visual_asset_pack import (
    load_visual_asset_pack,
    resolve_scene_asset_recipe,
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_png(path: Path, *, alpha: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "RGBA" if alpha else "RGB"
    fill = (0, 0, 0, 0) if alpha else (5, 6, 7)
    Image.new(mode, (3840, 2160), fill).save(path, format="PNG")


def test_visual_asset_pack_is_local_hash_bound_and_scene_resolvable(tmp_path: Path):
    pack_root = tmp_path / "media/product_asset_packs/homs_corpo_cult_v1"
    background = pack_root / "plates/HOMS_BG_COMMAND_HALL_4K.png"
    overlay = pack_root / "overlays/HOMS_GOLD_FRAME.png"
    _write_png(background, alpha=False)
    _write_png(overlay, alpha=True)

    manifest = {
        "schema": "dio.media.visual_asset_pack.v1",
        "pack_id": "HOMS_CORPO_CULT_V1",
        "product_id": "HOMS",
        "rights": {"status": "INTERNAL_ORIGINAL", "commercial_use": True},
        "remote_runtime_fetch": "REFUSE",
        "generated_as_proof": "REFUSE",
        "assets": [
            {"asset_id": "HOMS_COMMAND_HALL", "kind": "background", "path": "plates/HOMS_BG_COMMAND_HALL_4K.png", "sha256": _sha(background), "width": 3840, "height": 2160, "alpha": False},
            {"asset_id": "HOMS_GOLD_FRAME", "kind": "overlay", "path": "overlays/HOMS_GOLD_FRAME.png", "sha256": _sha(overlay), "width": 3840, "height": 2160, "alpha": True},
        ],
    }
    (pack_root / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/visual_asset_packs.json").write_text(json.dumps({
        "schema": "dio.media.visual_asset_pack_registry.v1",
        "packs": {"HOMS_CORPO_CULT_V1": "media/product_asset_packs/homs_corpo_cult_v1/pack.json"},
    }), encoding="utf-8")

    pack, fingerprint = load_visual_asset_pack("HOMS_CORPO_CULT_V1", root=tmp_path)
    assert fingerprint.startswith("sha256:")
    assert pack["pack_id"] == "HOMS_CORPO_CULT_V1"
    assert pack["remote_runtime_fetch"] == "REFUSE"
```

Also add tests that mutate one asset after the manifest is written, use `../` path traversal, or declare an opaque overlay. Each must raise `ProductExplainerError` with code `VISUAL_ASSET_PACK_INVALID`.

- [ ] **Step 2: Run RED**

Run:

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_visual_asset_pack.py
```

Expected: import failure because `products.product_visual_asset_pack` does not exist.

- [ ] **Step 3: Implement the minimal registry/resolver**

`config/visual_asset_packs.json` initially contains:

```json
{
  "schema": "dio.media.visual_asset_pack_registry.v1",
  "packs": {
    "HOMS_CORPO_CULT_V1": "media/product_asset_packs/homs_corpo_cult_v1/pack.json"
  }
}
```

`products/product_visual_asset_pack.py` must:

```python
REGISTRY_SCHEMA = "dio.media.visual_asset_pack_registry.v1"
PACK_SCHEMA = "dio.media.visual_asset_pack.v1"


def load_visual_asset_pack(pack_id: str, *, root: Path = ROOT) -> tuple[dict[str, Any], str]:
    ...


def resolve_scene_asset_recipe(
    pack: dict[str, Any],
    product_profile: dict[str, Any],
    story_beat: str,
) -> dict[str, Any]:
    ...
```

Validation rules are exact: registry schema match; selected manifest remains inside repository root; manifest schema/ID match; rights status `INTERNAL_ORIGINAL`; commercial use true; remote fetch `REFUSE`; generated-as-proof `REFUSE`; every asset remains under the selected pack directory; every asset file exists; SHA-256 matches; actual dimensions are 3840x2160; overlays must have alpha; asset IDs are unique.

- [ ] **Step 4: Run GREEN**

Run the same focused test. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/visual_asset_packs.json products/product_visual_asset_pack.py tests/test_product_visual_asset_pack.py
git commit -m "feat: resolve governed visual asset packs"
```

---

### Task 2: Build the HOMS Production Asset Pack Deterministically

**Files:**
- Create: `scripts/build_homs_corpo_cult_asset_pack.py`
- Create: `tests/test_homs_corpo_cult_asset_builder.py`
- Create at execution time: `media/product_asset_packs/homs_corpo_cult_v1/pack.json`
- Add approved binary assets under: `media/product_asset_packs/homs_corpo_cult_v1/plates/`, `overlays/`, and `reference/`.

**Interfaces:**
- Consumes approved source plates from `incoming/homs_corpo_cult_v1/`.
- Produces normalized 3840x2160 plate/overlay assets plus `pack.json` with exact hashes.
- CLI: `python3 scripts/build_homs_corpo_cult_asset_pack.py --source-dir <dir> --output-dir <dir>`.

- [ ] **Step 1: Write a failing builder test**

The test supplies five synthetic source plates and calls `build_pack(source_dir, output_dir)`. Assert the exact production filenames and manifest properties:

```python
EXPECTED_PLATES = {
    "HOMS_COMMAND_HALL": "plates/HOMS_BG_COMMAND_HALL_4K.png",
    "HOMS_REACTOR_CHAMBER": "plates/HOMS_BG_REACTOR_CHAMBER_4K.png",
    "HOMS_GOVERNANCE_WALL": "plates/HOMS_BG_GOVERNANCE_WALL_4K.png",
    "HOMS_ACADEMIC_DESK": "plates/HOMS_BG_ACADEMIC_DESK_4K.png",
    "HOMS_ENDCARD": "plates/HOMS_ENDCARD_BG_4K.png",
}
EXPECTED_OVERLAYS = {
    "HOMS_GOLD_FRAME": "overlays/HOMS_GOLD_FRAME.png",
    "HOMS_GOLD_PATHWAYS": "overlays/HOMS_GOLD_PATHWAYS.png",
    "HOMS_REACTOR_RING": "overlays/HOMS_REACTOR_RING.png",
    "HOMS_GLASS_PANEL": "overlays/HOMS_GLASS_PANEL.png",
    "HOMS_ATMOSPHERE": "overlays/HOMS_ATMOSPHERE.png",
}

assert manifest["pack_id"] == "HOMS_CORPO_CULT_V1"
assert len(manifest["assets"]) == 10
assert manifest["rights"] == {"status": "INTERNAL_ORIGINAL", "commercial_use": True}
assert manifest["remote_runtime_fetch"] == "REFUSE"
assert manifest["generated_as_proof"] == "REFUSE"
```

- [ ] **Step 2: Run RED**

Expected: missing builder module/script.

- [ ] **Step 3: Implement `build_pack()` and overlay generation**

The script must expose:

```python
def build_pack(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    ...
```

Required source names are exactly:

```text
command_hall.png
reactor_chamber.png
governance_wall.png
academic_desk.png
endcard.png
```

For each source plate: convert to RGB, crop-to-fill 16:9 without stretching, resize with `Image.Resampling.LANCZOS` to 3840x2160, save PNG.

Generate overlays with Pillow RGBA drawing primitives. Use the DIO palette already defined by `DIO_CINEMATIC_BRAND_V1`: near-black transparent background; `#d9b66f` and `#f1d79b` for lines/highlights; no baked words or claims. Overlay opacity must remain restrained: frame max alpha 150; pathways max alpha 165; ring max alpha 170; atmosphere max alpha 80.

Write `pack.json` only after all files exist and hashes/dimensions have been measured from the written bytes.

- [ ] **Step 4: Run GREEN**

Run:

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_homs_corpo_cult_asset_builder.py tests/test_product_visual_asset_pack.py
```

Expected: PASS.

- [ ] **Step 5: Generate and human-approve the five real clean source plates**

Create the five raster inputs using the already approved HOMS black-glass/gold doctrine. Every source plate must contain no baked product claims, no person, no fake UI, no customer-facing text and no literal cult/religious symbolism. Save them under:

```text
incoming/homs_corpo_cult_v1/command_hall.png
incoming/homs_corpo_cult_v1/reactor_chamber.png
incoming/homs_corpo_cult_v1/governance_wall.png
incoming/homs_corpo_cult_v1/academic_desk.png
incoming/homs_corpo_cult_v1/endcard.png
```

- [ ] **Step 6: Build the real pack**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/build_homs_corpo_cult_asset_pack.py \
  --source-dir incoming/homs_corpo_cult_v1 \
  --output-dir media/product_asset_packs/homs_corpo_cult_v1
```

Then load the pack with `load_visual_asset_pack("HOMS_CORPO_CULT_V1")`. Expected: success with `sha256:` fingerprint.

- [ ] **Step 7: Commit only the approved production pack**

Do not commit `incoming/`. Commit the normalized pack, reference image if approved, builder and tests:

```bash
git add scripts/build_homs_corpo_cult_asset_pack.py tests/test_homs_corpo_cult_asset_builder.py media/product_asset_packs/homs_corpo_cult_v1
git commit -m "feat: add HOMS gilded visual asset pack"
```

---

### Task 3: Bind the HOMS Asset Pack into the Brand Brief and Media Request

**Files:**
- Modify: `config/product_media_profiles.json`
- Modify: `products/product_explainer_branding.py`
- Modify: `products/product_explainer_pipeline.py`
- Create: `tests/test_product_explainer_corpo_cult_binding.py`

**Interfaces:**
- Consumes: `HOMS_CORPO_CULT_V1` pack fingerprint and HOMS seven-beat product profile.
- Produces: `brand_render_brief.visual_asset_pack` and `MEDIA_PRODUCTION_REQUEST.visual_asset_pack`.
- Produces per renderer scene: `visual_asset_recipe`.

- [ ] **Step 1: Write failing binding tests**

```python
def test_homs_brand_brief_binds_gilded_asset_pack(compiled_homs, root):
    request = build_media_production_request(compiled_homs, root=root)
    pack = request["visual_asset_pack"]
    assert pack["id"] == "HOMS_CORPO_CULT_V1"
    assert pack["sha256"].startswith("sha256:")
    assert pack["fallback"] == "REFUSE"

    rendered = enrich_renderer_script(
        build_explainer_script_package(compiled_homs["manifest"]),
        request,
    )
    assert len(rendered["scenes"]) == 7
    for scene in rendered["scenes"]:
        assert scene["visual_asset_recipe"]["background_asset_id"]
        assert scene["visual_asset_recipe"]["overlay_asset_ids"]
```

Add a semantic immutability assertion comparing narration, claim IDs, source IDs, story beat and target duration before/after enrichment.

- [ ] **Step 2: Run RED**

Expected: missing `visual_asset_pack` keys.

- [ ] **Step 3: Add the exact HOMS scene bindings**

Under `profiles.HOMS.visual_asset_pack` add:

```json
{
  "pack_id": "HOMS_CORPO_CULT_V1",
  "scene_bindings": {
    "problem": {
      "background_asset_id": "HOMS_COMMAND_HALL",
      "overlay_asset_ids": ["HOMS_GOLD_FRAME", "HOMS_ATMOSPHERE", "HOMS_GOLD_PATHWAYS"],
      "overlay_opacity": {"HOMS_GOLD_FRAME": 0.52, "HOMS_ATMOSPHERE": 0.30, "HOMS_GOLD_PATHWAYS": 0.22},
      "gold_state": "ambient"
    },
    "product_definition": {
      "background_asset_id": "HOMS_REACTOR_CHAMBER",
      "overlay_asset_ids": ["HOMS_ATMOSPHERE", "HOMS_REACTOR_RING", "HOMS_GOLD_FRAME"],
      "overlay_opacity": {"HOMS_ATMOSPHERE": 0.28, "HOMS_REACTOR_RING": 0.72, "HOMS_GOLD_FRAME": 0.50},
      "gold_state": "active"
    },
    "mechanism": {
      "background_asset_id": "HOMS_ACADEMIC_DESK",
      "overlay_asset_ids": ["HOMS_GLASS_PANEL", "HOMS_GOLD_PATHWAYS", "HOMS_GOLD_FRAME"],
      "overlay_opacity": {"HOMS_GLASS_PANEL": 0.66, "HOMS_GOLD_PATHWAYS": 0.60, "HOMS_GOLD_FRAME": 0.48},
      "gold_state": "active"
    },
    "proof": {
      "background_asset_id": "HOMS_GOVERNANCE_WALL",
      "overlay_asset_ids": ["HOMS_GLASS_PANEL", "HOMS_GOLD_FRAME", "HOMS_ATMOSPHERE"],
      "overlay_opacity": {"HOMS_GLASS_PANEL": 0.72, "HOMS_GOLD_FRAME": 0.50, "HOMS_ATMOSPHERE": 0.22},
      "gold_state": "governed",
      "proof_slot": [0.18, 0.18, 0.64, 0.64]
    },
    "differentiation": {
      "background_asset_id": "HOMS_GOVERNANCE_WALL",
      "overlay_asset_ids": ["HOMS_GOLD_PATHWAYS", "HOMS_GLASS_PANEL", "HOMS_GOLD_FRAME"],
      "overlay_opacity": {"HOMS_GOLD_PATHWAYS": 0.48, "HOMS_GLASS_PANEL": 0.56, "HOMS_GOLD_FRAME": 0.48},
      "gold_state": "governed"
    },
    "result": {
      "background_asset_id": "HOMS_COMMAND_HALL",
      "overlay_asset_ids": ["HOMS_ATMOSPHERE", "HOMS_GOLD_PATHWAYS", "HOMS_REACTOR_RING", "HOMS_GOLD_FRAME"],
      "overlay_opacity": {"HOMS_ATMOSPHERE": 0.28, "HOMS_GOLD_PATHWAYS": 0.68, "HOMS_REACTOR_RING": 0.42, "HOMS_GOLD_FRAME": 0.52},
      "gold_state": "active"
    },
    "call_to_action": {
      "background_asset_id": "HOMS_ENDCARD",
      "overlay_asset_ids": ["HOMS_GOLD_FRAME", "HOMS_ATMOSPHERE"],
      "overlay_opacity": {"HOMS_GOLD_FRAME": 0.56, "HOMS_ATMOSPHERE": 0.20},
      "gold_state": "brand_end_card"
    }
  }
}
```

- [ ] **Step 4: Bind pack fingerprint into request and renderer copy**

`build_media_production_request()` loads the selected pack, adds:

```python
"visual_asset_pack": {
    "id": pack["pack_id"],
    "sha256": pack_sha,
    "fallback": "REFUSE",
},
```

`compile_brand_render_brief()` copies `visual_asset_pack` from the product profile into the brief.

`enrich_renderer_script()` resolves the recipe for each beat and writes it only to the deep renderer-facing copy as `visual_asset_recipe`.

- [ ] **Step 5: Run GREEN and existing branding tests**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
tests/test_product_explainer_corpo_cult_binding.py \
tests/test_product_explainer_branding.py \
tests/test_product_explainer_media_request_branding.py \
tests/test_product_explainer_renderer_branding.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add config/product_media_profiles.json products/product_explainer_branding.py products/product_explainer_pipeline.py tests/test_product_explainer_corpo_cult_binding.py
git commit -m "feat: bind HOMS visual asset pack to explainer"
```

---

### Task 4: Compose Deterministic HOMS Scene Plates

**Files:**
- Create: `products/product_explainer_scene_compositor.py`
- Create: `tests/test_product_explainer_scene_compositor.py`

**Interfaces:**
- Consumes: enriched renderer script, `MediaProductionRequest v2`, hash-validated asset pack.
- Produces: seven 1920x1080 scene PNGs under `premium_visuals/dio_asset_pack/`.
- Produces: `DIO_VISUAL_ASSET_PACK_RECEIPT.json`.

- [ ] **Step 1: Write failing compositor tests**

Use a temporary pack fixture with solid-color backgrounds and transparent overlays. Assert deterministic output dimensions, hashes and scene count.

```python
def test_compositor_creates_seven_hash_bound_scene_plates(tmp_path, script, request):
    receipt = compose_product_explainer_scenes(
        tmp_path / "episode",
        script,
        request,
        root=tmp_path,
    )
    assert receipt["schema"] == "dio.media.visual_asset_pack_receipt.v1"
    assert receipt["pack_id"] == "HOMS_CORPO_CULT_V1"
    assert receipt["composition_authority"] == "dio_asset_pack"
    assert receipt["generic_visual_fallback"] == "REFUSE"
    assert len(receipt["scenes"]) == 7
    for scene in receipt["scenes"]:
        assert scene["width"] == 1920
        assert scene["height"] == 1080
        assert scene["sha256"].startswith("sha256:")
```

Add a proof-scene test with no proof asset asserting `proof_asset_state == "MISSING"` and no fabricated proof path. Add a raster proof test using a real temporary PNG and assert `proof_asset_state == "BOUND_RENDERED"` and the source hash is recorded.

- [ ] **Step 2: Run RED**

Expected: missing compositor module.

- [ ] **Step 3: Implement deterministic composition**

Expose:

```python
def compose_product_explainer_scenes(
    episode_dir: Path,
    script_package: dict[str, Any],
    production_request: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    ...
```

For each scene: load validated background; center-crop to 16:9; resize to 1920x1080; apply overlays in declared order using their per-scene opacity; write `scene_<NN>_<story_beat>.png`.

For `proof_slot = [x, y, w, h]`, interpret values as normalized fractions of the 1920x1080 canvas. Only PNG/JPEG/WebP bound proof assets may be inserted in v1. A bound non-raster proof records `BOUND_NONRASTER_UNRENDERED`; absence records `MISSING`; neither case creates a fake document.

The receipt must include pack fingerprint, source hashes, recipe fingerprint, output hashes, dimensions, proof state, composition authority, fallback refusal and `publication_authority_created = false`.

- [ ] **Step 4: Prove determinism**

Run the compositor twice into two empty episode directories with identical inputs. Assert corresponding scene SHA-256 values are identical.

- [ ] **Step 5: Run GREEN**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_scene_compositor.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add products/product_explainer_scene_compositor.py tests/test_product_explainer_scene_compositor.py
git commit -m "feat: compose governed HOMS scene plates"
```

---

### Task 5: Make the DIO Asset Pack the HOMS Final Visual Authority

**Files:**
- Modify: `products/premium_media_federation.py`
- Create: `tests/test_premium_media_corpo_cult_integration.py`
- Modify only when assertions require it: `tests/test_premium_media_gauntlet_contract.py`

**Interfaces:**
- Consumes: compositor receipt from Task 4.
- Produces: NicheFoundry `visual_plan.json` whose HOMS scene `preview_path` values point to `premium_visuals/dio_asset_pack/*.png`.
- Produces final receipt fields `visual_asset_pack_binding`, `visual_asset_pack_fallback`, `visual_composition_authority`.

- [ ] **Step 1: Write failing federation handoff test**

Mock only the external NicheFoundry command execution boundary. Feed a valid HOMS production request and composed-scene receipt into `_prepare_native_render_contract()`.

```python
def test_native_render_contract_prefers_bound_homs_asset_pack(tmp_path):
    _prepare_native_render_contract(
        tmp_path,
        gamma_receipt,
        script_package=script,
        composed_visuals=composed_receipt,
    )
    plan = json.loads((tmp_path / "visual_plan.json").read_text())
    assert {row["composition"] for row in plan["scene_plans"]} == {"dio_asset_pack_bound"}
    assert all("premium_visuals/dio_asset_pack/" in row["preview_path"] for row in plan["scene_plans"])
    report = json.loads((tmp_path / "visual_report.json").read_text())
    assert report["composition_authority"] == "dio_asset_pack"
```

Add a fail-closed test where HOMS requests the pack but the compositor receipt omits one scene. Expected: `PremiumMediaError`; Gamma paths must not be substituted.

- [ ] **Step 2: Run RED**

Expected: `_prepare_native_render_contract()` does not accept `composed_visuals` and still writes Gamma preview paths.

- [ ] **Step 3: Invoke compositor in `_run_nichefoundry()`**

After `build_premium_assets.js` and after loading `gamma_execution_receipt.json`, but before `_prepare_native_render_contract()`, call `compose_product_explainer_scenes()` when `production_request.visual_asset_pack` exists.

Keep Gamma execution evidence intact. Do not delete `gamma_execution_receipt.json` or its scene-coverage checks.

- [ ] **Step 4: Make `_prepare_native_render_contract()` composition-aware**

Change signature to:

```python
def _prepare_native_render_contract(
    episode_dir: Path,
    gamma: dict[str, Any],
    *,
    script_package: dict[str, Any] | None = None,
    composed_visuals: dict[str, Any] | None = None,
) -> None:
    ...
```

When `composed_visuals` is present, require exact scene coverage and verified output files/hashes, then write each visual-plan row with provider `dio_asset_pack`, composition `dio_asset_pack_bound`, and the DIO-composited relative path. When no pack is requested, preserve existing Gamma behavior exactly.

- [ ] **Step 5: Extend premium proof/receipt**

For a pack-bound render add:

```python
"visual_asset_pack_binding": "PASS",
"visual_asset_pack_fallback": "REFUSE",
"visual_composition_authority": "dio_asset_pack",
```

Do not change `human_visual_release`, `external_publication`, `external_send`, `media_spend` or `human_gate`.

- [ ] **Step 6: Run GREEN and regression cluster**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
tests/test_premium_media_corpo_cult_integration.py \
tests/test_product_explainer_scene_compositor.py \
tests/test_product_explainer_corpo_cult_binding.py \
tests/test_premium_media_brand_handoff.py \
tests/test_premium_media_brand_execution.py \
tests/test_premium_media_explainer_integration.py \
tests/test_premium_media_product_score.py \
tests/test_premium_media_gauntlet_contract.py \
tests/test_premium_media_runner_contract.py
```

Expected: all selected tests PASS.

- [ ] **Step 7: Commit**

```bash
git add products/premium_media_federation.py tests/test_premium_media_corpo_cult_integration.py tests/test_premium_media_gauntlet_contract.py
git commit -m "feat: render HOMS from governed visual asset pack"
```

---

### Task 6: Full HOMS Gilded Graduation and Final Custody

**Files:**
- Create after human acceptance: `media/golden_references/homs_corpo_cult_v1/FINAL_MEDIA_BINDING.json`
- Create after human acceptance: `media/golden_references/homs_corpo_cult_v1/HUMAN_VISUAL_APPROVAL.json`
- Copy after human acceptance: final approved MP4 and thumbnail into the same golden-reference directory.

**Interfaces:**
- Consumes Tasks 1-5 and the existing governed HOMS score/Vesper path.
- Produces one local candidate, human approval receipt and immutable final media binding.

- [ ] **Step 1: Run the full Round 2 + asset-pack contract gate**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 -m pytest -q \
tests/test_product_visual_asset_pack.py \
tests/test_homs_corpo_cult_asset_builder.py \
tests/test_product_explainer_corpo_cult_binding.py \
tests/test_product_explainer_scene_compositor.py \
tests/test_premium_media_corpo_cult_integration.py \
tests/test_product_explainer_branding.py \
tests/test_product_explainer_media_request_branding.py \
tests/test_product_explainer_renderer_branding.py \
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

- [ ] **Step 2: Render the HOMS candidate**

```bash
DIO_VENV=/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv
NICHEFOUNDRY=/home/byron/Downloads/NicheFoundry_Phase11
OUT=/tmp/dio-homs-corpo-cult-v1
rm -rf "$OUT"
PATH="$DIO_VENV/bin:$PATH" PYTHONNOUSERSITE=1 "$DIO_VENV/bin/python3" \
scripts/run_product_explainer_graduation.py \
  --product homs \
  --root /home/byron/DIO-Full-Audit \
  --output "$OUT" \
  --render \
  --nichefoundry-root "$NICHEFOUNDRY" \
  --provider imported
```

Expected technical receipt: semantic graduation PASS; render PASS; premium voice PASS; governed score PASS; `visual_asset_pack_binding = PASS`; `visual_asset_pack_fallback = REFUSE`; visual composition authority `dio_asset_pack`; human visual release `NEEDS_YOU`; external publication not authorized.

- [ ] **Step 3: Inspect visual custody before watching**

Verify `DIO_VISUAL_ASSET_PACK_RECEIPT.json`, `visual_plan.json`, `DIO_PRODUCT_SCORE_RECEIPT.json`, `PREMIUM_MEDIA_PROOF.json`, `PREMIUM_MEDIA_RECEIPT.json` and final MP4 hashes. Every HOMS visual-plan scene must resolve to a DIO asset-pack image.

- [ ] **Step 4: Human visual/audio gate**

Play the final candidate. Acceptance questions are exact:

1. Does every scene unmistakably inhabit the same black-glass/gold DIO institution?
2. Does the film feel monumental and governed rather than brochure-like?
3. Is ambient gold restrained while active/governed states receive brighter gold?
4. Are there no stock-office/classroom scenes, fake UI or fake proof?
5. Does real proof remain visually distinct from generated framing?
6. Does Vesper remain intelligible over the institutional-glass score?
7. Does the CTA feel like canonical DIO/HOMS rather than a generic ad end card?

Any `NO` means the candidate remains unfrozen and the failing scene/asset is revised.

- [ ] **Step 5: Freeze only after explicit human acceptance**

Copy the accepted MP4 and thumbnail to:

```text
media/golden_references/homs_corpo_cult_v1/HOMS_PRODUCT_EXPLAINER_MASTER_V1.mp4
media/golden_references/homs_corpo_cult_v1/HOMS_PRODUCT_EXPLAINER_THUMBNAIL_V1.png
```

Write `HUMAN_VISUAL_APPROVAL.json` with schema `dio.media.human_visual_approval.v1`, product `HOMS`, pack ID/hash, final-video hash, decision `APPROVED`, and `publication_authority_created = false`.

Write `FINAL_MEDIA_BINDING.json` with schema `dio.media.final_binding.v1`, exact paths/hashes for pack manifest, final MP4, thumbnail, score receipt, visual asset-pack receipt and human approval receipt. Keep `external_publication = NEEDS_YOU` and `media_spend = REFUSE`.

- [ ] **Step 6: Run final integrity verification and commit custody**

Re-hash every bound file and compare against `FINAL_MEDIA_BINDING.json`. Then:

```bash
git add media/golden_references/homs_corpo_cult_v1
git commit -m "feat: freeze approved HOMS cinematic master"
```

Do not include unrelated working-tree changes.

---

## Self-review

- Spec coverage: asset manifest, local hashing, production plates, deterministic overlays, HOMS scene mapping, proof behavior, renderer deep-copy boundary, scene compositor, NicheFoundry handoff, no silent Gamma fallback, premium receipts, authority invariants, human review and final custody are each assigned to a concrete task.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, generic error-handling instruction or undefined task dependency remains.
- Type consistency: pack loader returns `(dict[str, Any], str)`; scene resolver returns `dict[str, Any]`; compositor returns `dict[str, Any]`; federation receives that receipt as `composed_visuals`; request key is consistently `visual_asset_pack`; scene key is consistently `visual_asset_recipe`.
- Scope control: no NicheFoundry source modification is planned for v1. DIO owns the visual composition and hands NicheFoundry ordinary local preview paths through its existing `visual_plan.json` contract.
