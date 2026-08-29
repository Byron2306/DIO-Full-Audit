# HOMS Existing Asset Ingestion Addendum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Amend the HOMS CORPO CULT visual-pack build so existing DIO ornaments, icons, Vesper frames and hero imagery are audited, normalized, hash-bound and reused before any equivalent assets are generated from scratch.

**Architecture:** Keep the generic `HOMS_CORPO_CULT_V1` pack resolver from Task 1. Add a deterministic source-ingestion layer that accepts approved local DIO source art, cleans alpha-edge contamination without changing visible opaque artwork, converts production assets to lossless PNG, classifies source versus production state, and writes exact provenance into `pack.json`. HOMS-specific grand architectural plates remain generated/curated inputs; shared DIO ornamentation is reused from the existing DIO visual library.

**Tech Stack:** Python 3, Pillow, hashlib, JSON, pytest, existing visual asset-pack resolver.

**Spec:** `docs/superpowers/specs/2026-08-29-homs-corpo-cult-asset-pack-design.md`

## Global Constraints

- `CORPO CULT` remains an internal creative nickname and must not appear in customer-facing media metadata, narration, captions or claims.
- Existing DIO source artwork is preserved byte-for-byte under source custody; normalized production PNGs are derived outputs.
- Product truth, claim authority, evidence classification and semantic timing remain unchanged.
- Generated or decorative imagery may never be represented as observed proof.
- Real bound HOMS proof outranks all generated/decorative assets.
- Production plates are 3840x2160 RGB/RGBA; reusable overlays/icons retain native aspect ratio unless the pack builder explicitly creates a 3840x2160 composition canvas.
- Production overlays/icons must have meaningful alpha, transparent pixels must not carry severe red/yellow fringe contamination, and output PNGs must be lossless.
- Local source files only; remote runtime fetch remains `REFUSE`.
- No equivalent ornament/icon is regenerated if an approved DIO source asset already exists and can be normalized.
- `config/vesper_voice_profiles.json` and `presence_core/voice.py` remain untouched.

---

### Task A: Deterministic DIO Source Asset Normalizer

**Files:**
- Create: `scripts/build_homs_corpo_cult_asset_pack.py`
- Create: `tests/test_homs_corpo_cult_asset_builder.py`

**Interfaces:**
- Consumes: approved source image path, semantic asset ID, kind, role.
- Produces: normalized PNG and provenance row.
- Function: `normalize_source_asset(source: Path, destination: Path, *, require_alpha: bool) -> dict[str, object]`
- Function: `build_pack(source_dir: Path, output_dir: Path) -> dict[str, object]`

- [ ] **Step 1: Write failing tests**

Create synthetic RGBA WebP/PNG assets containing deliberately contaminated RGB in low-alpha edge pixels and opaque gold artwork. Require normalization to preserve dimensions/aspect, keep opaque pixels materially unchanged, zero/neutralize RGB where alpha is effectively transparent, produce PNG, and emit source/output hashes. Also require `build_pack()` to reuse supplied source ornaments/icons rather than generate placeholders when those source files exist.

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_homs_corpo_cult_asset_builder.py
```

Expected: import failure because `scripts.build_homs_corpo_cult_asset_pack` does not exist.

- [ ] **Step 3: Implement minimal normalizer and pack builder**

`normalize_source_asset()` must open with Pillow, convert to RGBA when alpha is required, reject opaque inputs when `require_alpha=True`, decontaminate pixels with alpha <= 8 by setting RGB to zero while preserving alpha, save lossless PNG, then report `source_sha256`, `output_sha256`, dimensions, mode, alpha state and cleanup counts. Pixels with alpha >= 224 must remain byte-identical in RGB values after normalization.

`build_pack()` must ingest approved source files by explicit manifest mapping. It must never directory-glob arbitrary assets into production. Missing required assets cause refusal. HOMS architectural source plates are crop-to-fill normalized to 3840x2160; shared ornaments/icons keep native aspect ratio and are tagged `composition_asset=true` rather than pretending to be 4K full-scene overlays.

- [ ] **Step 4: Run GREEN**

Run builder tests plus `tests/test_product_visual_asset_pack.py`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_homs_corpo_cult_asset_pack.py tests/test_homs_corpo_cult_asset_builder.py
git commit -m "feat: normalize existing DIO visual assets"
```

---

### Task B: Real HOMS Pack Inventory

**Files:**
- Create at execution time: `media/product_asset_packs/homs_corpo_cult_v1/source_manifest.json`
- Create at execution time: `media/product_asset_packs/homs_corpo_cult_v1/pack.json`
- Add approved production PNGs under `plates/`, `ornaments/`, `icons/`, `vesper/`, `sigils/`, `reference/`.

**Interfaces:**
- Consumes: five approved HOMS architecture plates plus existing DIO source art.
- Produces: hash-bound production pack accepted by `load_visual_asset_pack("HOMS_CORPO_CULT_V1")`.

- [ ] **Step 1: Classify current DIO source art explicitly**

Use these semantic families where available: eye/divider, orbit/frame/ring, panel/card/pill frames, title/banner/trace, Vesper presentation/vertical, premium medallion board, semantic icons for conversation/education/evidence/governance/growth/media/partnership/workflow, and established DIO hero imagery as reference-only unless explicitly promoted to a HOMS scene plate.

- [ ] **Step 2: Normalize approved assets**

Run the builder against the curated source directory. Source originals remain outside committed production paths or under `reference/source_custody/` only if intentionally preserved. Production outputs are PNGs with exact provenance rows.

- [ ] **Step 3: Verify the real pack**

Load with `load_visual_asset_pack("HOMS_CORPO_CULT_V1")`; require fingerprint, source/output hashes, rights state, remote fetch refusal, generated-as-proof refusal, and all referenced assets resolvable.

- [ ] **Step 4: Human visual spot-check**

Inspect representative normalized eye/orbit/frame/icon assets at 100% on black and transparent checkerboard backgrounds. Reject visible red/yellow fringe, clipped ornamentation, or altered opaque gold artwork.

- [ ] **Step 5: Commit only approved production assets**

Do not stage unrelated workspace files or existing dirty Vesper voice files.
