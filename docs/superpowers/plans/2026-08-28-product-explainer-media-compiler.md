# DIO Product Explainer Media Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a truth-bound autonomous Product Explainer Compiler that turns a known DIO product into a complete local 45–60 second explainer production package without an operator-written creative brief, while preserving evidence, claim, voice, media-rights, and human-release boundaries.

**Architecture:** Add one semantic compiler in `products/product_explainer_compiler.py` that resolves canonical product truth, binds evidence and approved meaning, constructs a claim envelope, produces `ProductExplainerManifest` plus `MediaProductionRequest v2`, and generates a scene package for the existing Phase 16 premium-media backend. Extend the premium-media federation so it consumes supplied script/production contracts instead of requiring its fixed incident-readiness story. Preserve NicheFoundry native rendering, Document Studio non-destructive controls, premium-media integrity checks, and human publication authority.

**Tech Stack:** Python 3, standard-library JSON/hash/path tooling, existing DIO product portfolio/runtime state, DIO Lingua artifacts, existing NicheFoundry Node renderer, FFmpeg/ffprobe, Pocket TTS through Vesper Presence Core, pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-product-explainer-media-compiler-design.md`

## Global Constraints

- Local semantic compilation may be `ALLOW` only when required source truth is bound and current.
- Local media rendering may be `ALLOW` only after machine-checkable semantic and media gates pass.
- External publication remains `NEEDS_YOU`; no code in this plan may create automatic publication authority.
- Media spend remains `REFUSE`.
- Market/audience information may alter emphasis, sequencing, CTA, or derivative framing; it may not mutate canonical product definition, claim boundaries, or evidence lineage.
- Real product outputs, UI, screenshots, and evidence outrank generated explanatory diagrams and cinematic metaphors.
- Generated imagery must never be represented as observed evidence, a real product screen, or a customer result.
- `DIO_CINEMATIC_BRAND_V1` references canonical DIO assets and installed font family names; do not vendor or copy font files into the repository.
- The approved Vesper public voice is `vera_pocket_public`; synthesis creates no send, identity, translation, publication, or spend authority.
- An original local score is a first-class rights-safe media source, not a low-quality procedural fallback. Existing `procedural_music_fallback = REFUSE` semantics remain valid for fallback behavior.
- The derivative compiler is out of scope until the canonical HOMS explainer graduation proof passes.
- Do not switch branches, reset, stash, or discard the operator's current dirty worktree. Before implementation, inspect and preserve local unpushed Pocket TTS and launch-media changes.

## Execution Preflight

Run this before Task 1. It does not change the worktree.

```bash
cd /home/byron/DIO-Full-Audit
set -euo pipefail

git branch --show-current
git status --short

git diff -- presence_core/voice.py config/vesper_voice_profiles.json \
  products/premium_media_federation.py products/premium_media_gauntlet.py

find state/product_portfolio -maxdepth 1 -type f -name 'DIO_META_PORTFOLIO_ATLAS*.json' -print 2>/dev/null || true

test -f media/golden_references/dio_launch_cinematic_v1/master/DIO_LAUNCH_TRAILER_MASTER_V1.mp4
sha256sum media/golden_references/dio_launch_cinematic_v1/master/DIO_LAUNCH_TRAILER_MASTER_V1.mp4
```

Expected branch: `agent/dio-public-launch-rail`. If local Pocket TTS support is already present, preserve it and make Task 5's tests prove it instead of replacing it.

---

### Task 1: Contract Schemas and DIO Cinematic Brand Profile

**Files:**
- Create: `schemas/product_explainer_manifest.schema.json`
- Create: `schemas/media_production_request_v2.schema.json`
- Create: `config/media_style_profiles.json`
- Create/extend: `products/product_explainer_compiler.py`
- Test: `tests/test_media_style_profiles.py`

**Interfaces:**
- Produces: `load_media_style_profile(profile_id: str, *, root: Path, require_assets: bool = True) -> tuple[dict[str, Any], str]`
- Produces: `ProductExplainerError(code: str, message: str, details: dict[str, Any] | None = None)` with public attributes `code` and `details`.
- Consumers: Tasks 4, 6, and 7.

- [ ] **Step 1: Write the failing profile tests**

```python
from pathlib import Path
import json
import pytest

from products.product_explainer_compiler import ProductExplainerError, load_media_style_profile

ROOT = Path(__file__).resolve().parents[1]


def test_dio_cinematic_brand_profile_is_release_safe():
    profile, digest = load_media_style_profile(
        "DIO_CINEMATIC_BRAND_V1", root=ROOT, require_assets=False
    )
    assert digest.startswith("sha256:")
    assert profile["voice"]["profile"] == "vera_pocket_public"
    assert profile["release"]["automatic_local_render"] is True
    assert profile["release"]["automatic_external_publication"] is False
    assert profile["release"]["automatic_media_spend"] is False
    assert profile["typography"]["silent_font_fallback"] is False


def test_missing_required_brand_asset_fails_closed(tmp_path: Path):
    config = {
        "schema": "dio.media.style_profile_registry.v1",
        "profiles": {
            "BROKEN": {
                "schema": "dio.media.style_profile.v1",
                "profile_id": "BROKEN",
                "golden_reference": {"master": "missing/master.mp4", "sha256": "sha256:x"},
                "visual": {"palette": {"black": "#050607", "gold": "#d9b66f"}},
                "typography": {
                    "brand_face": "Noto Serif Display",
                    "body_face": "Noto Serif",
                    "technical_face": "DejaVu Sans",
                    "wordmark": "missing/dio-wordmark.svg",
                    "sigil": "missing/dio-sigil.webp",
                    "silent_font_fallback": False
                },
                "voice": {"role": "vesper_public", "profile": "vera_pocket_public"},
                "sound": {"sonic_identity": "DIO_SONIC_IDENTITY_V1"},
                "release": {
                    "automatic_local_render": True,
                    "automatic_external_publication": False,
                    "automatic_media_spend": False
                }
            }
        }
    }
    path = tmp_path / "config" / "media_style_profiles.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config))
    with pytest.raises(ProductExplainerError) as exc:
        load_media_style_profile("BROKEN", root=tmp_path, require_assets=True)
    assert exc.value.code == "STYLE_ASSET_MISSING"
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_media_style_profiles.py
```

Expected: import failure because `products.product_explainer_compiler` does not yet expose the required interface.

- [ ] **Step 3: Implement the minimal profile loader and exception**

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class ProductExplainerError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_media_style_profile(
    profile_id: str, *, root: Path = ROOT, require_assets: bool = True
) -> tuple[dict[str, Any], str]:
    registry_path = root / "config" / "media_style_profiles.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    profile = (registry.get("profiles") or {}).get(profile_id)
    if not isinstance(profile, dict):
        raise ProductExplainerError("STYLE_PROFILE_INVALID", f"unknown media style profile: {profile_id}")
    release = profile.get("release") or {}
    if release.get("automatic_external_publication") is not False or release.get("automatic_media_spend") is not False:
        raise ProductExplainerError("STYLE_PROFILE_INVALID", "style profile may not create publication or spend authority")
    if require_assets:
        required = [
            profile["golden_reference"]["master"],
            profile["typography"]["wordmark"],
            profile["typography"]["sigil"],
        ]
        missing = [value for value in required if not (root / value).is_file()]
        if missing:
            raise ProductExplainerError("STYLE_ASSET_MISSING", "required DIO brand assets are missing", {"missing": missing})
    return profile, _fingerprint(profile)
```

Create `config/media_style_profiles.json` with this registry shape:

```json
{
  "schema": "dio.media.style_profile_registry.v1",
  "profiles": {
    "DIO_CINEMATIC_BRAND_V1": {
      "schema": "dio.media.style_profile.v1",
      "profile_id": "DIO_CINEMATIC_BRAND_V1",
      "golden_reference": {
        "master": "media/golden_references/dio_launch_cinematic_v1/master/DIO_LAUNCH_TRAILER_MASTER_V1.mp4",
        "sha256": "bind-at-runtime"
      },
      "visual": {
        "palette": {
          "black": "#050607",
          "gold": "#d9b66f",
          "pale_gold": "#f1d79b",
          "cream": "#f3efe7"
        }
      },
      "typography": {
        "brand_face": "Noto Serif Display",
        "body_face": "Noto Serif",
        "technical_face": "DejaVu Sans",
        "wordmark": "media/golden_references/dio_launch_cinematic_v1/brand/dio-wordmark.svg",
        "sigil": "media/golden_references/dio_launch_cinematic_v1/brand/dio-sigil.webp",
        "silent_font_fallback": false
      },
      "voice": {
        "role": "vesper_public",
        "profile": "vera_pocket_public",
        "render_mode": "presence_core_import"
      },
      "sound": {
        "sonic_identity": "DIO_SONIC_IDENTITY_V1",
        "music_policy": "original_local_or_rights_verified"
      },
      "release": {
        "automatic_local_render": true,
        "automatic_external_publication": false,
        "automatic_media_spend": false
      }
    }
  }
}
```

At load time, replace the sentinel `bind-at-runtime` with the actual SHA-256 of the master before fingerprinting the resolved profile. Do not write that runtime hash back into config unless a separate freeze action is later introduced.

The two JSON Schema files must require the exact top-level fields from the approved design. Set `additionalProperties` to `true` for v1, but require the authority/release fields and their safe enum/boolean values. `media_production_request_v2.schema.json` must require a `voice` object containing `role`, `profile`, and `render_mode`, because Task 6 consumes these resolved voice fields directly.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_media_style_profiles.py
```

Expected: PASS.

- [ ] **Step 5: Commit only Task 1 files**

```bash
git add schemas/product_explainer_manifest.schema.json \
        schemas/media_production_request_v2.schema.json \
        config/media_style_profiles.json \
        products/product_explainer_compiler.py \
        tests/test_media_style_profiles.py
git commit -m "feat: add governed product explainer media contracts"
```

---

### Task 2: Deterministic Product Resolution and Truth Hydration

**Files:**
- Modify: `products/product_explainer_compiler.py`
- Create: `tests/test_product_explainer_compiler.py`

**Interfaces:**
- Produces: `resolve_product_truth(product_id: str, *, root: Path = ROOT) -> dict[str, Any]`
- Returned keys: `product_id`, `canonical_name`, `description`, `identity_source`, `identity_sha256`, `portfolio_rows`, `capabilities`, `outputs`, `proof_assets`, `audience_observations`, `source_bindings`.
- Consumers: Task 3.

- [ ] **Step 1: Write failing resolver tests with isolated fixtures**

```python
from pathlib import Path
import json
import pytest

from products.product_explainer_compiler import ProductExplainerError, resolve_product_truth


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_resolver_uses_portfolio_for_identity_and_marketing_only_as_supplement(tmp_path: Path):
    portfolio = tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json"
    _write_json(portfolio, {
        "schema": "dio.meta_portfolio.runtime.v1",
        "incarnations": [{
            "Incarnation": "HOMS Assess",
            "Suite": "HOMS",
            "Description": "Governed assessment production and review workflows",
            "Capabilities": ["assessment generation", "rubric-bound review"],
            "Outputs": ["assessment paper", "memorandum", "rubric"]
        }]
    })
    marketing = tmp_path / "state/marketing_factory/CREATIVE_FAMILY_REGISTRY.json"
    _write_json(marketing, {
        "schema": "dio.marketing.creative_family_registry.v1",
        "families": [{
            "product": {"id": "HOMS_ASSESS", "name": "HOMS Assess"},
            "audience": {"pain": "Assessment preparation is repetitive.", "outcome": "Reviewable assessment outputs."},
            "proof_asset": "proof/homs.md"
        }]
    })
    (tmp_path / "proof").mkdir()
    (tmp_path / "proof/homs.md").write_text("controlled HOMS proof", encoding="utf-8")

    truth = resolve_product_truth("homs", root=tmp_path)

    assert truth["canonical_name"] == "HOMS"
    assert truth["description"] == "Governed assessment production and review workflows"
    assert truth["identity_source"].endswith("DIO_META_PORTFOLIO_ATLAS_RUNTIME.json")
    assert truth["audience_observations"][0]["pain"] == "Assessment preparation is repetitive."
    assert truth["proof_assets"][0]["path"] == "proof/homs.md"


def test_conflicting_canonical_sources_refuse(tmp_path: Path):
    base = tmp_path / "state/product_portfolio"
    row_a = {
        "Incarnation": "HOMS Assess",
        "Suite": "HOMS",
        "Description": "Governed assessment production",
        "Capabilities": ["assessment generation"],
        "Outputs": ["assessment paper"]
    }
    row_b = {
        "Incarnation": "HOMS Assess",
        "Suite": "HOMS",
        "Description": "Automatic guaranteed assessment compliance",
        "Capabilities": ["assessment generation"],
        "Outputs": ["assessment paper"]
    }
    _write_json(base / "DIO_META_PORTFOLIO_ATLAS_RUNTIME.json", {"incarnations": [row_a]})
    _write_json(base / "DIO_META_PORTFOLIO_ATLAS.json", {"incarnations": [row_b]})

    with pytest.raises(ProductExplainerError) as exc:
        resolve_product_truth("homs", root=tmp_path)

    assert exc.value.code == "PRODUCT_IDENTITY_AMBIGUOUS"
```

- [ ] **Step 2: Run targeted tests and verify RED**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py -k 'resolver or conflicting'
```

Expected: FAIL because `resolve_product_truth` is absent.

- [ ] **Step 3: Implement deterministic source discovery and projection**

Use this authority order inside the compiler:

```python
PORTFOLIO_EXACT_NAMES = (
    "DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
    "DIO_META_PORTFOLIO_ATLAS.json",
)


def _portfolio_candidates(root: Path) -> list[Path]:
    base = root / "state" / "product_portfolio"
    exact = [base / name for name in PORTFOLIO_EXACT_NAMES if (base / name).is_file()]
    if exact:
        return exact
    return sorted(base.glob("DIO_META_PORTFOLIO_ATLAS*.json")) if base.is_dir() else []
```

Normalize candidate product IDs by lowercasing and removing punctuation. Match `homs` against `Suite`, `Incarnation`, `product_id`, `id`, and `name`. If multiple rows match and share one non-empty suite name, resolve to that suite. If authoritative candidates disagree on canonical name or non-empty canonical description for the same normalized product, raise `PRODUCT_IDENTITY_AMBIGUOUS`.

Read `state/marketing_factory/CREATIVE_FAMILY_REGISTRY.json` only after canonical identity is established. Extract audience pain/outcome and proof paths only for rows whose normalized product identity begins with or belongs to the resolved HOMS suite. Marketing registry values must never overwrite canonical name, description, capabilities, or outputs.

Persist every consumed file in `source_bindings` as `{path, sha256, role}`.

- [ ] **Step 4: Run resolver tests**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py -k 'resolver or conflicting'
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add products/product_explainer_compiler.py tests/test_product_explainer_compiler.py
git commit -m "feat: resolve product explainer truth from bound DIO sources"
```

---

### Task 3: Claim Envelope and Canonical Explainer Manifest

**Files:**
- Modify: `products/product_explainer_compiler.py`
- Modify: `tests/test_product_explainer_compiler.py`

**Interfaces:**
- Produces: `build_claim_envelope(truth: dict[str, Any]) -> dict[str, list[dict[str, Any]]]`
- Produces: `compile_product_explainer(product_id: str, *, root: Path = ROOT, output_dir: Path | None = None, market_context: dict[str, Any] | None = None) -> dict[str, Any]`
- Output contains `manifest`, `manifest_path`, `manifest_sha256`, `truth`, `semantic_readiness`, and `missing`.
- Consumers: Task 4 and graduation runner.

- [ ] **Step 1: Add failing tests for evidence refusal, source hashes, market immutability, and release authority**

```python
def build_complete_homs_fixture(tmp_path: Path) -> Path:
    _write_json(tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json", {
        "incarnations": [{
            "Incarnation": "HOMS Assess",
            "Suite": "HOMS",
            "Description": "Governed assessment production and review workflows",
            "Capabilities": ["ingest assessment intent", "generate reviewable assessment outputs"],
            "Outputs": ["assessment paper", "memorandum", "rubric"]
        }]
    })
    _write_json(tmp_path / "state/marketing_factory/CREATIVE_FAMILY_REGISTRY.json", {
        "families": [{
            "product": {"id": "HOMS_ASSESS", "name": "HOMS Assess"},
            "audience": {"pain": "Assessment production spans repetitive preparation and review steps.", "outcome": "Reviewable assessment outputs."},
            "proof_asset": "proof/homs.md"
        }]
    })
    (tmp_path / "proof").mkdir()
    (tmp_path / "proof/homs.md").write_text("HOMS controlled proof", encoding="utf-8")
    return tmp_path


def test_missing_required_truth_returns_needs_evidence(tmp_path: Path):
    _write_json(tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json", {
        "incarnations": [{"Incarnation": "HOMS Assess", "Suite": "HOMS", "Description": "", "Capabilities": [], "Outputs": []}]
    })
    result = compile_product_explainer("homs", root=tmp_path)
    assert result["semantic_readiness"] == "NEEDS_EVIDENCE"
    assert "what_it_is" in result["missing"]


def test_market_context_cannot_mutate_product_definition(tmp_path: Path):
    root = build_complete_homs_fixture(tmp_path)
    baseline = compile_product_explainer("homs", root=root)
    marketed = compile_product_explainer(
        "homs",
        root=root,
        market_context={"emphasis": ["speed"], "product_definition": "guaranteed automatic compliance"},
    )
    assert marketed["manifest"]["explanation"]["what_it_is"] == baseline["manifest"]["explanation"]["what_it_is"]
    assert marketed["manifest"]["market_context"]["emphasis"] == ["speed"]
    assert "product_definition" not in marketed["manifest"]["market_context"]


def test_release_authority_stays_human(tmp_path: Path):
    result = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    assert result["manifest"]["authority"]["human_release_required"] is True
    assert result["manifest"]["authority"]["external_publication"] == "NEEDS_YOU"
    assert result["manifest"]["authority"]["media_spend"] == "REFUSE"
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py -k 'needs_evidence or market_context or release_authority'
```

- [ ] **Step 3: Implement deterministic explanation construction**

Use these readiness fields:

```python
REQUIRED_EXPLANATION_FIELDS = (
    "what_it_is",
    "problem",
    "how_it_works",
    "why_different",
    "buyer_result",
)
```

Construct them only from bound truth:

- `what_it_is`: canonical name plus canonical description.
- `problem`: canonical product problem if present; otherwise summarize bound audience `pain` observations explicitly as observations.
- `how_it_works`: canonical capabilities/work-patterns rendered as an ordered mechanism description.
- `why_different`: only product-specific differentiators present in canonical truth plus DIO governance characteristics actually represented in source bindings.
- `buyer_result`: concrete outputs the user receives. Audience `outcome` strings remain `QUALIFIED` unless separately evidence-bound.

`build_claim_envelope` creates objects with `text`, `class`, `source_paths`, and `reason`. Canonical capability/output statements with a bound product source are `DESCRIPTIVE`; proof-backed statements are `SUPPORTED`; marketing outcomes without direct outcome proof are `QUALIFIED`; claims containing unsupported certainty such as `guarantee`, `certify`, `always`, or `eliminate` are `FORBIDDEN` unless an explicit source-bound claim record marks them supported.

When readiness is complete, write `state/product_explainers/<normalized-product-id>/PRODUCT_EXPLAINER_MANIFEST.json` using stable sorted JSON and return its SHA-256.

- [ ] **Step 4: Run the full compiler unit test file**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add products/product_explainer_compiler.py tests/test_product_explainer_compiler.py
git commit -m "feat: compile evidence-bound product explainer manifests"
```

---

### Task 4: Media Production Request v2, Scene Package, and Semantic Challenge

**Files:**
- Modify: `products/product_explainer_compiler.py`
- Modify: `tests/test_product_explainer_compiler.py`

**Interfaces:**
- Produces: `build_media_production_request(explainer_result: dict[str, Any], *, root: Path = ROOT, style_profile_id: str = "DIO_CINEMATIC_BRAND_V1") -> dict[str, Any]`
- Produces: `build_explainer_script_package(manifest: dict[str, Any]) -> dict[str, Any]`
- Produces: `semantic_challenge(manifest: dict[str, Any], script_package: dict[str, Any]) -> dict[str, Any]`
- Request `voice` is copied from the resolved style profile as `{role, profile, render_mode}`.
- Request `release` is fixed to local `ALLOW`, external `NEEDS_YOU`, spend `REFUSE`.
- Consumers: Task 6.

- [ ] **Step 1: Write failing tests**

```python
def install_test_brand_profile(root: Path) -> None:
    master = root / "media/golden_references/dio_launch_cinematic_v1/master/DIO_LAUNCH_TRAILER_MASTER_V1.mp4"
    wordmark = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-wordmark.svg"
    sigil = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-sigil.webp"
    master.parent.mkdir(parents=True, exist_ok=True)
    wordmark.parent.mkdir(parents=True, exist_ok=True)
    master.write_bytes(b"video")
    wordmark.write_text("<svg></svg>", encoding="utf-8")
    sigil.write_bytes(b"webp")
    _write_json(root / "config/media_style_profiles.json", {
        "schema": "dio.media.style_profile_registry.v1",
        "profiles": {
            "DIO_CINEMATIC_BRAND_V1": {
                "schema": "dio.media.style_profile.v1",
                "profile_id": "DIO_CINEMATIC_BRAND_V1",
                "golden_reference": {"master": str(master.relative_to(root)), "sha256": "bind-at-runtime"},
                "visual": {"palette": {"black": "#050607", "gold": "#d9b66f"}},
                "typography": {"brand_face": "Noto Serif Display", "body_face": "Noto Serif", "technical_face": "DejaVu Sans", "wordmark": str(wordmark.relative_to(root)), "sigil": str(sigil.relative_to(root)), "silent_font_fallback": False},
                "voice": {"role": "vesper_public", "profile": "vera_pocket_public", "render_mode": "presence_core_import"},
                "sound": {"sonic_identity": "DIO_SONIC_IDENTITY_V1", "music_policy": "original_local_or_rights_verified"},
                "release": {"automatic_local_render": True, "automatic_external_publication": False, "automatic_media_spend": False}
            }
        }
    })


def test_media_request_binds_explainer_style_and_voice(tmp_path: Path):
    root = build_complete_homs_fixture(tmp_path)
    install_test_brand_profile(root)
    compiled = compile_product_explainer("homs", root=root)
    request = build_media_production_request(compiled, root=root)
    assert request["schema"] == "dio.media.production_request.v2"
    assert request["explainer_manifest"]["sha256"] == compiled["manifest_sha256"]
    assert request["style_profile"]["sha256"].startswith("sha256:")
    assert request["voice"] == {
        "role": "vesper_public",
        "profile": "vera_pocket_public",
        "render_mode": "presence_core_import",
    }
    assert request["release"] == {
        "local_render": "ALLOW",
        "external_publication": "NEEDS_YOU",
        "media_spend": "REFUSE",
    }


def test_script_package_explains_before_it_sells(tmp_path: Path):
    compiled = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    script = build_explainer_script_package(compiled["manifest"])
    beats = [scene["story_beat"] for scene in script["scenes"]]
    assert beats == ["problem", "product_definition", "mechanism", "proof", "differentiation", "result", "call_to_action"]


def test_semantic_challenge_refuses_strengthened_claim(tmp_path: Path):
    compiled = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    script = build_explainer_script_package(compiled["manifest"])
    script["scenes"][2]["narration"] = "HOMS guarantees compliant assessments every time."
    report = semantic_challenge(compiled["manifest"], script)
    assert report["state"] == "REFUSE"
    assert "CLAIM_EXCEEDS_EVIDENCE" in report["codes"]
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py -k 'media_request or script_package or semantic_challenge'
```

- [ ] **Step 3: Implement request, seven-scene story grammar, and challenge**

Scene durations must sum to 55 seconds by default: `7, 7, 11, 11, 9, 7, 3`. Each scene includes `scene_id`, `story_beat`, `title`, `narration`, `screen_anchor`, `target_duration_seconds`, `claim_ids`, `source_ids`, and `asset_preference`.

Use this asset order:

```python
ASSET_PREFERENCE = [
    "real_product_output",
    "real_product_ui",
    "real_evidence_or_diagram",
    "dio_generated_explanatory_diagram",
    "generated_cinematic_metaphor",
]
```

The challenge must compare script sentences against the manifest claim envelope, reject forbidden certainty terms not present in allowed/supported claims, reject any scene with `asset_representation == "evidence"` when its asset provenance is generated, and reject CTA text that asserts unsupported price, availability, customer count, or certification.

`build_media_production_request` must copy the resolved profile voice object into `request["voice"]`; Task 6 must not infer the voice from the profile ID a second time.

- [ ] **Step 4: Run full compiler tests**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py tests/test_media_style_profiles.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add products/product_explainer_compiler.py tests/test_product_explainer_compiler.py
git commit -m "feat: build governed explainer production requests"
```

---

### Task 5: Preserve and Prove Vesper Vera / Pocket TTS as the Production Voice

**Files:**
- Modify only if local implementation is absent/incomplete: `presence_core/voice.py`
- Modify only if local profile is absent/incomplete: `config/vesper_voice_profiles.json`
- Create/modify: `tests/test_vesper_pocket_tts.py`

**Interfaces:**
- Existing `build_voice_plan(...)` must resolve `vera_pocket_public` to backend `pocket_tts` and state `ready_for_internal_render`.
- Existing `synthesize_voice(...)` must route `pocket_tts` to Pocket TTS synthesis and preserve `external_action_executed=False`, `send_authorized=False`, `identity_authority_created=False`, `translation_authority_created=False`.
- Task 6 consumes the public profile through an import-to-NicheFoundry adapter.

- [ ] **Step 1: Write tests against the required local behavior before editing production files**

```python
from pathlib import Path

from presence_core.voice import build_voice_plan, synthesize_voice

ROOT = Path(__file__).resolve().parents[1]


def test_vera_public_profile_is_internal_render_only():
    plan = build_voice_plan(
        root=ROOT,
        language="English",
        interaction={"delivery_policy": {"mode": "measured"}},
        requested_profile="vera_pocket_public",
    )
    assert plan["backend"] == "pocket_tts"
    assert plan["state"] == "ready_for_internal_render"
    assert plan["public_default_authorized"] is True
    assert plan["send_authority_created"] is False


def test_pocket_tts_receipt_creates_no_authority(monkeypatch, tmp_path: Path):
    class Response:
        content = b"RIFF" + b"0" * 64
        def raise_for_status(self):
            return None

    monkeypatch.setattr("presence_core.voice.httpx.post", lambda *args, **kwargs: Response())
    plan = {
        "state": "ready_for_internal_render",
        "backend": "pocket_tts",
        "profile_id": "vera_pocket_public",
        "voice_url": "vera",
        "language": "English",
        "delivery_mode": "measured",
    }
    receipt = synthesize_voice(text="Dio", output_path=tmp_path / "dio.wav", plan=plan)
    assert receipt["external_action_executed"] is False
    assert receipt["send_authorized"] is False
    assert receipt["identity_authority_created"] is False
    assert receipt["translation_authority_created"] is False
```

- [ ] **Step 2: Run tests**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_vesper_pocket_tts.py
```

If they PASS immediately, the local unpushed Pocket TTS patch is already sufficient: do not rewrite it. If they FAIL because the GitHub-baseline behavior is still present locally, implement the approved Pocket TTS backend/profile exactly as captured by the launch-trailer work.

- [ ] **Step 3: Verify the live local service separately**

```bash
curl -fsS http://127.0.0.1:8000/health
```

Expected: `{"status":"healthy"}` before a live graduation render. Unit tests must not require the service.

- [ ] **Step 4: Commit only actual changes plus the tests**

```bash
git add tests/test_vesper_pocket_tts.py
[ -n "$(git status --short -- presence_core/voice.py config/vesper_voice_profiles.json)" ] && \
  git add presence_core/voice.py config/vesper_voice_profiles.json || true
git commit -m "test: bind Vesper Vera voice to governed media production"
```

---

### Task 6: Make Premium Media Consume Explainer Contracts Instead of a Fixed Story

**Files:**
- Modify: `products/premium_media_federation.py`
- Modify: `products/premium_media_gauntlet.py`
- Modify: `scripts/run_premium_media_phase16_1_1.py`
- Create/modify: `tests/test_premium_media_explainer_integration.py`

**Interfaces:**
- Change: `build_premium_media(*, output_dir: Path, nichefoundry_root: Path | None = None, provider: str = "auto", script_package: dict[str, Any] | None = None, production_request: dict[str, Any] | None = None) -> dict[str, Any]`
- Change internal: `_prepare_episode(niche_root: Path, episode_dir: Path, script_package: dict[str, Any]) -> dict[str, Any]`
- Change internal: `_prepare_native_render_contract(episode_dir: Path, gamma: dict[str, Any], script_package: dict[str, Any]) -> None`
- Existing Phase 16 behavior remains available when `script_package is None`; new Product Explainer flow always supplies one.

- [ ] **Step 1: Write failing integration tests around dependency injection**

```python
from pathlib import Path

import products.premium_media_federation as federation


def test_federation_forwards_supplied_explainer_script(monkeypatch, tmp_path: Path):
    seen = {}
    script = {
        "schema": "dio.product_explainer.script_package.v1",
        "title": "HOMS",
        "scenes": [{
            "scene_id": "scene_01",
            "story_beat": "problem",
            "title": "Assessment work fragments",
            "narration": "Assessment production often spans disconnected source material and review steps.",
            "target_duration_seconds": 7,
            "claim_ids": [],
            "source_ids": []
        }]
    }

    monkeypatch.setattr(federation, "build_media_incarnation", lambda output_dir: {"output_dir": str(output_dir)})
    monkeypatch.setattr(federation, "resolve_nichefoundry_root", lambda value: tmp_path / "nf")

    def fake_run(niche_root, episode_dir, provider, script_package):
        seen["niche_script"] = script_package
        final = episode_dir / "final.mp4"
        thumb = episode_dir / "thumbnail.png"
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(b"video")
        thumb.write_bytes(b"png")
        return {
            "providers": ["imported"],
            "probe": {"streams": [{"sample_rate": "48000", "channels": 2}]},
            "sound_design": {"music_identity": "test", "rights": {"state": "self_generated_bound"}, "scenes": [{"music_cue": "bed"}]},
            "music_quality": {"hiss_detection": "PASS"},
            "gamma": {"native_engine_invoked": True},
            "native_render": {"final": str(final), "thumbnail": str(thumb), "qa": {"passed": True}},
        }

    monkeypatch.setattr(federation, "_run_nichefoundry", fake_run)

    def fake_control(*, gamma_dir, script_package, output_dir, style_profile):
        seen["document_script"] = script_package
        return {"binding_state": "CONTROL_SURFACE_BOUND"}

    monkeypatch.setattr(federation, "render_media_control_surface", fake_control)
    monkeypatch.setattr(federation, "_corpus_census", lambda niche: {"engines": [], "full_corpus_native_execution": "REFUSE"})
    monkeypatch.setattr(federation, "verify_premium_proof", lambda output_dir, proof: None)

    result = federation.build_premium_media(output_dir=tmp_path / "out", script_package=script)

    assert seen["niche_script"] is script
    assert seen["document_script"] is script
    assert result["receipt"]["external_publication"] == "REFUSE"


def test_legacy_script_remains_available():
    script = federation._script_package()
    assert script["schema"] == "nichefoundry.script_package.v1.0"
    assert script["scenes"]
```

The minimal native fake may need to create specific hash-bound files already required by `build_premium_media`. If the first RED run fails before reaching the script assertion because those files are missing, extend only the fake to create those exact files; do not weaken production integrity checks.

- [ ] **Step 2: Run and verify RED**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_premium_media_explainer_integration.py
```

- [ ] **Step 3: Thread `script_package` through the federation**

Inside `build_premium_media`:

```python
script = script_package if script_package is not None else _script_package()
niche = _run_nichefoundry(niche_root, episode, provider, script_package=script)
document_studio = render_media_control_surface(
    gamma_dir=episode / "premium_visuals",
    script_package=script,
    output_dir=premium_dir / "document_studio_media",
    style_profile="dio_professional",
)
```

Update `_prepare_episode` and `_prepare_native_render_contract` to consume the passed script instead of calling `_script_package()` internally. Do not delete the legacy `_script_package()` in this task.

- [ ] **Step 4: Add the Vesper import adapter without teaching NicheFoundry a new backend**

When `production_request["voice"]["profile"] == "vera_pocket_public"` and `production_request["voice"]["render_mode"] == "presence_core_import"`, call Presence Core once per scene narration, write each WAV beneath `episode/imports/audio/`, and write `DIO_VOICE_IMPORT_RECEIPT.json` with `{scene_id, profile_id, backend, audio_path, sha256}` rows. Then force NicheFoundry's selected provider to `imported` for that explainer episode.

Use the public `build_voice_plan` and `synthesize_voice` functions. Do not duplicate Pocket TTS HTTP logic in the premium-media federation.

- [ ] **Step 5: Distinguish original-local score from procedural fallback**

If `production_request["music"]` contains `{origin: "original_local", rights_state: "self_generated_bound", path, generator_receipt}`, expose:

```json
{
  "music_origin": "original_local",
  "music_rights_state": "self_generated_bound",
  "procedural_music_fallback": "REFUSE"
}
```

If external music is supplied, retain the existing rights-evidence requirement. Do not weaken `music_rights_evidence`, hiss detection, or loudness QA.

- [ ] **Step 6: Update gauntlet/runner arguments**

Allow the gauntlet to accept optional `script_package` and `production_request` dictionaries and pass them to `build_premium_media`. Keep all existing acceptance keys. Add:

```python
"explainer_contract_binding": "PASS",
"external_publication": "REFUSE",
```

Do not change `human_gate = NEEDS_YOU` or `media_spend = REFUSE`.

- [ ] **Step 7: Run focused plus existing Phase 16 tests**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_premium_media_explainer_integration.py \
  tests/test_premium_media_federation.py \
  tests/test_premium_media_phase16_1_1.py
```

If one historical filename differs locally, run:

```bash
find tests -maxdepth 1 -type f -iname '*premium*media*' -print
```

and include every existing Phase 16 premium-media test file returned by that command in the regression run.

- [ ] **Step 8: Commit**

```bash
git add products/premium_media_federation.py \
        products/premium_media_gauntlet.py \
        scripts/run_premium_media_phase16_1_1.py \
        tests/test_premium_media_explainer_integration.py
git commit -m "feat: feed product explainer contracts into premium media"
```

---

### Task 7: HOMS Graduation Runner and Fail-Closed Proof Receipt

**Files:**
- Create: `scripts/run_product_explainer_graduation.py`
- Modify: `tests/test_product_explainer_compiler.py`

**Interfaces:**
- Produces: `run_graduation(product_id: str, *, output_dir: Path, render: bool = False, nichefoundry_root: Path | None = None) -> dict[str, Any]`
- Produces acceptance token only when all required semantic gates pass: `DIO_PRODUCT_EXPLAINER_GRADUATION_READY`.

- [ ] **Step 1: Write the failing semantic-only graduation test**

```python
def test_graduation_without_render_proves_semantics_only(tmp_path: Path, monkeypatch):
    from scripts import run_product_explainer_graduation as graduation

    root = build_complete_homs_fixture(tmp_path / "root")
    install_test_brand_profile(root)
    monkeypatch.setattr(graduation, "ROOT", root)

    result = graduation.run_graduation(
        "homs",
        output_dir=tmp_path / "out",
        render=False,
    )

    assert result["acceptance_token"] == "DIO_PRODUCT_EXPLAINER_GRADUATION_READY"
    assert result["product_identity"] == "PASS"
    assert result["source_binding"] == "PASS"
    assert result["product_explanation"] == "PASS"
    assert result["claim_envelope"] == "PASS"
    assert result["semantic_challenge"] == "PASS"
    assert result["local_render"] == "NOT_REQUESTED"
    assert result["external_publication"] == "NEEDS_YOU"
    assert result["media_spend"] == "REFUSE"
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py -k graduation
```

- [ ] **Step 3: Implement `run_graduation` and CLI**

The runner writes:

```text
<output>/PRODUCT_EXPLAINER_MANIFEST.json
<output>/MEDIA_PRODUCTION_REQUEST.json
<output>/SCRIPT_PACKAGE.json
<output>/SEMANTIC_CHALLENGE.json
<output>/PRODUCT_EXPLAINER_GRADUATION_RECEIPT.json
```

When `--render` succeeds, also write `FINAL_MEDIA_BINDING.json` with the premium-media final path and SHA-256.

Use this receipt shape:

```python
receipt = {
    "acceptance_token": "DIO_PRODUCT_EXPLAINER_GRADUATION_READY",
    "product_identity": "PASS",
    "source_binding": "PASS",
    "product_explanation": "PASS",
    "claim_envelope": "PASS",
    "proof_binding": "PASS",
    "commercial_argument": "PASS",
    "dio_media_profile": "PASS",
    "semantic_challenge": "PASS",
    "media_render": "PASS" if render else "NOT_REQUESTED",
    "output_integrity": "PASS" if render else "NOT_REQUESTED",
    "local_render": "ALLOW" if render else "NOT_REQUESTED",
    "external_publication": "NEEDS_YOU",
    "media_spend": "REFUSE",
}
```

Do not emit the acceptance token when semantic readiness is `NEEDS_EVIDENCE` or any challenge/media gate refuses.

- [ ] **Step 4: Run compiler/graduation unit tests**

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q tests/test_product_explainer_compiler.py tests/test_media_style_profiles.py tests/test_vesper_pocket_tts.py
```

Expected: PASS.

- [ ] **Step 5: Run the real HOMS semantic graduation without media first**

```bash
rm -rf /tmp/dio-homs-explainer

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m scripts.run_product_explainer_graduation \
  --product homs \
  --output /tmp/dio-homs-explainer

cat /tmp/dio-homs-explainer/PRODUCT_EXPLAINER_GRADUATION_RECEIPT.json
```

Expected: semantic gates PASS. If HOMS returns `NEEDS_EVIDENCE`, inspect the reported missing field and repair the authoritative HOMS product/portfolio source, not the generated manifest and not the compiler with HOMS-specific marketing prose.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_product_explainer_graduation.py tests/test_product_explainer_compiler.py
git commit -m "feat: add HOMS product explainer graduation runner"
```

---

### Task 8: Full HOMS Media Graduation, Integrity Verification, and Golden Freeze

**Files:**
- No new production code unless a failing test identifies a defect.
- Generated evidence: `state/product_explainers/homs/graduation/**`

**Interfaces:**
- Consumes all prior tasks.
- Produces the first complete autonomous HOMS explainer candidate plus a hash-bound graduation receipt.

- [ ] **Step 1: Run the complete focused test suite before native rendering**

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_product_explainer_compiler.py \
  tests/test_media_style_profiles.py \
  tests/test_vesper_pocket_tts.py \
  tests/test_premium_media_explainer_integration.py
```

Expected: PASS.

- [ ] **Step 2: Verify Pocket TTS and NicheFoundry prerequisites**

```bash
curl -fsS http://127.0.0.1:8000/health

test -f /home/byron/Downloads/NicheFoundry_Phase11/package.json || \
  test -f "$HOME/NicheFoundry/package.json"

ffmpeg -version | head -1
ffprobe -version | head -1
```

- [ ] **Step 3: Run the real autonomous HOMS render**

```bash
rm -rf state/product_explainers/homs/graduation

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m scripts.run_product_explainer_graduation \
  --product homs \
  --output state/product_explainers/homs/graduation \
  --render
```

Expected terminal state:

```text
PRODUCT_IDENTITY ................. PASS
SOURCE_BINDING ................... PASS
PRODUCT_EXPLANATION .............. PASS
CLAIM_ENVELOPE ................... PASS
PROOF_BINDING .................... PASS
COMMERCIAL_ARGUMENT .............. PASS
DIO_MEDIA_PROFILE ................ PASS
SEMANTIC_CHALLENGE ............... PASS
MEDIA_RENDER ..................... PASS
OUTPUT_INTEGRITY ................. PASS
LOCAL_RENDER ..................... ALLOW
EXTERNAL_PUBLICATION ............. NEEDS_YOU
MEDIA_SPEND ...................... REFUSE
DIO_PRODUCT_EXPLAINER_GRADUATION_READY
```

- [ ] **Step 4: Tamper-test the final**

```bash
rm -rf /tmp/dio-homs-explainer-tamper
cp -a state/product_explainers/homs/graduation /tmp/dio-homs-explainer-tamper
FINAL="$(python3 - <<'PY'
import json
from pathlib import Path
binding=json.loads(Path('/tmp/dio-homs-explainer-tamper/FINAL_MEDIA_BINDING.json').read_text())
print(binding['path'])
PY
)"
printf 'TAMPER' >> "$FINAL"
```

Run the same premium proof verifier against the tampered copy and require an integrity failure. Then verify the untouched original and require PASS. Do not change the verifier to accommodate the tamper test.

- [ ] **Step 5: Human perceptual review remains explicit**

Play the generated master locally. Do not change the receipt's public release state based on automated visual/audio QA. Human review may create a separate approval receipt after inspection; until then publication remains `NEEDS_YOU`.

- [ ] **Step 6: Inspect generated sizes before any commit**

```bash
du -ah state/product_explainers/homs/graduation | sort -h | tail -30
git status --short
```

Commit source/tests separately from large rendered media. If the final MP4 is intentionally versioned, verify it is below GitHub's single-file limit before adding it. Otherwise retain the hash-bound receipt and local master path.

## Final Verification

After all eight tasks:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_product_explainer_compiler.py \
  tests/test_media_style_profiles.py \
  tests/test_vesper_pocket_tts.py \
  tests/test_premium_media_explainer_integration.py

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m scripts.run_product_explainer_graduation \
  --product homs \
  --output state/product_explainers/homs/graduation \
  --render
```

Acceptance requires all machine gates plus:

```text
LOCAL_RENDER = ALLOW
EXTERNAL_PUBLICATION = NEEDS_YOU
MEDIA_SPEND = REFUSE
```

Only after this graduation passes should a separate design/spec begin for `MediaDerivativeManifest` and the 30s/15s/channel/audience derivative compiler.
