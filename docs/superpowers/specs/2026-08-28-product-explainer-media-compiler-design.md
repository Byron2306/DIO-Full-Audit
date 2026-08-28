# DIO Product Explainer Media Compiler Design

Date: 2026-08-28
Status: DESIGN FROZEN PENDING IMPLEMENTATION PLAN
Branch: agent/dio-public-launch-rail

## 1. Purpose

DIO needs a reusable production-media capability that can take a known DIO product and autonomously produce a truthful, persuasive local product explainer without requiring the operator to manually enter the audience, pain points, hook, product description, brand style, voice, or media grammar.

The system must explain the product first and sell it second. The canonical explainer becomes the semantic parent for later audience-specific and channel-specific derivatives.

The flagship DIO launch trailer, DIO_LAUNCH_TRAILER_MASTER_V1, is the first golden calibration reference for the media style profile. It teaches production grammar rather than becoming a scene-by-scene template.

## 2. Authority Boundary

The autonomous production boundary is:

- Local semantic compilation: ALLOW when source truth is sufficient.
- Local media generation and rendering: ALLOW when machine-checkable gates pass.
- Automatic external publication: REFUSE.
- Human publication decision: NEEDS_YOU.
- Automatic media spend: REFUSE.

Learning and market observations may influence emphasis, sequencing, channel fit, and creative hypotheses. They may not silently mutate canonical product truth, evidence, claim boundaries, or publication authority.

## 3. Core Architecture

```text
PRODUCT REGISTRY / PRODUCT MANIFEST / ATLAS
        +
DIO LINGUA APPROVED MEANING
        +
COMMERCIAL TRUTH
        +
EVIDENCE / CLAIM BOUNDARIES
        +
CURRENT PRODUCT ASSETS
        ↓
PRODUCT EXPLAINER COMPILER
        ↓
ProductExplainerManifest
        ↓
MEDIA STYLE PROFILE RESOLVER
        ↓
MediaProductionRequest v2
        ↓
PRODUCTION MEDIA / NICHEFOUNDRY / DOCUMENT STUDIO
        ↓
SERAPH / SOPHIA / SEMANTIC + MEDIA QA
        ↓
LOCAL CANONICAL PRODUCT EXPLAINER MASTER
        ↓
DERIVATIVE COMPILER
        ↓
AUDIENCE / CHANNEL / DURATION VARIANTS
        ↓
HUMAN RELEASE GATE
        ↓
OPTIONAL PUBLICATION
```

The existing Phase 16 premium-media federation remains the production backend. This project teaches that backend what to make from DIO product truth rather than replacing the existing render, audio, rights, integrity, and human-gate machinery.

## 4. Truth Hierarchy

The system must keep source authority explicit:

```text
Product Registry / canonical product manifest
    = what the product is

Evidence / Commercial Truth
    = what may truthfully be claimed

DIO Lingua
    = how approved meaning is expressed clearly and consistently

Market Sensorium / marketing intelligence
    = which truthful benefits to emphasize for a given audience

Media Style Profile
    = how the production looks, sounds, moves, and closes

Production Media
    = how the artifact is manufactured
```

Market learning is a lens, never the author of product reality.

### 4.1 Product source resolution

The compiler must not search arbitrary JSON files and choose whichever one resembles a product record. Product identity is resolved by an explicit source resolver with deterministic precedence.

Resolution order:

1. a registered canonical product manifest or portfolio record explicitly marked authoritative for the requested product;
2. the current self-hydrated portfolio runtime only when it carries a source/hash binding to the canonical portfolio source from which it was derived;
3. product-specific registries may contribute capabilities, proof, outputs, and assets, but may not silently override canonical identity.

Every resolved identity source must return at least `path`, `schema`, `sha256`, `source_type`, and the normalized `product_id`.

If two candidates at the same authority level disagree on identity or core product definition, the compiler must emit `PRODUCT_IDENTITY_AMBIGUOUS` and refuse compilation. If a runtime record has lost its canonical source/hash binding, it is not authoritative and must not be silently trusted.

This design deliberately does not hard-code one current filesystem path for ATLAS or the portfolio runtime. The implementation plan must bind the resolver to the current canonical adapters/files present in the working tree, while preserving this precedence and ambiguity behavior.

## 5. Canonical Contracts

### 5.1 ProductExplainerManifest

Schema identifier: `dio.product_explainer.v1`

This is the semantic master for a product explainer. It contains meaning, evidence lineage, claims, and the canonical story structure. It must not contain renderer-specific implementation detail.

Minimum fields:

```json
{
  "schema": "dio.product_explainer.v1",
  "product_id": "homs",
  "source_binding": {
    "product_manifest": "...",
    "product_manifest_sha256": "...",
    "lingua_snapshot": "...",
    "commercial_truth_snapshot": "...",
    "evidence_snapshot": "..."
  },
  "explanation": {
    "what_it_is": "...",
    "problem": "...",
    "how_it_works": "...",
    "why_different": "...",
    "buyer_result": "..."
  },
  "outputs": [],
  "proof_points": [],
  "claims": {
    "allowed": [],
    "qualified": [],
    "forbidden": []
  },
  "canonical_story": [
    "problem",
    "product_definition",
    "mechanism",
    "proof",
    "differentiation",
    "result",
    "call_to_action"
  ],
  "target_seconds": 55,
  "authority": {
    "semantic_truth_source": "product_registry",
    "market_may_change_product_truth": false,
    "human_release_required": true
  }
}
```

If the system cannot establish required product truth or proof, the compiler must fail closed with `EXPLAINER_SEMANTIC_READINESS = NEEDS_EVIDENCE` and identify the missing requirement. It must not manufacture a persuasive sentence to conceal an evidence gap.

### 5.2 MediaStyleProfile

Schema identifier: `dio.media.style_profile.v1`

The first profile is `DIO_CINEMATIC_BRAND_V1`.

It binds:

- golden reference master and hash;
- DIO palette;
- approved visual grammar;
- prohibited visual clichés;
- typography family names, canonical wordmark, and canonical sigil;
- Vesper public voice role and approved Pocket TTS Vera profile;
- DIO sonic identity;
- original-local or rights-verified music policy;
- motion and transition grammar;
- end-card grammar;
- automatic local render and human publication boundary.

The golden launch trailer teaches style grammar, not literal scene reuse.

### 5.3 MediaProductionRequest v2

Schema identifier: `dio.media.production_request.v2`

This replaces the current thin campaign handoff as the canonical semantic-to-production request while preserving compatibility with current product, audience, proof-asset, output, and release concepts.

Minimum fields:

```json
{
  "schema": "dio.media.production_request.v2",
  "request_id": "...",
  "product_id": "homs",
  "explainer_manifest": {
    "path": "...",
    "sha256": "..."
  },
  "style_profile": {
    "id": "DIO_CINEMATIC_BRAND_V1",
    "sha256": "..."
  },
  "production": {
    "kind": "canonical_product_explainer",
    "target_seconds": 55,
    "aspect_ratio": "16:9",
    "resolution": "1920x1080",
    "voice_required": true,
    "captions": true
  },
  "assets": {
    "proof_assets": [],
    "product_screens": [],
    "generated_visuals": []
  },
  "release": {
    "local_render": "ALLOW",
    "external_publication": "NEEDS_YOU",
    "media_spend": "REFUSE"
  }
}
```

The request must be auto-hydrated. The operator must not be required to re-enter product facts DIO already knows.

### 5.4 MediaDerivativeManifest

Schema identifier: `dio.media.derivative.v1`

A derivative may only be compiled after a canonical explainer exists. It may change emphasis, sequencing, duration, CTA, channel framing, and audience relevance. It may not alter the canonical product definition, claim boundaries, or evidence lineage.

Minimum invariants:

```json
{
  "immutable": {
    "product_definition": true,
    "claim_boundaries": true,
    "evidence_lineage": true
  }
}
```

## 6. Autonomous Compiler Algorithm

The compiler has nine stages.

### Stage 1: Resolve Product

Input may be as small as a product identifier, for example `homs`.

The compiler resolves that identifier to a canonical DIO product record through the source resolver defined in section 4.1. If identity cannot be established or is ambiguous, compilation refuses.

### Stage 2: Hydrate Truth

The compiler builds transient internal state from authoritative DIO sources. Expected categories include:

- identity;
- product purpose;
- capabilities;
- required inputs;
- operating mechanism;
- outputs;
- current product proof;
- limitations;
- commercial state;
- approved terminology;
- current maturity/readiness;
- real screenshots and output assets;
- known audiences.

Source hashes must be retained. Stale semantic material must not be silently preferred over newer bound product truth.

### Stage 3: Build Claim Envelope

Candidate commercial statements are classified into at least:

- SUPPORTED;
- QUALIFIED;
- DESCRIPTIVE;
- UNPROVED;
- FORBIDDEN.

The sales argument may be persuasive only inside this envelope.

### Stage 4: Crystallize Explanation

Before sales language is produced, the compiler must answer:

1. What is the product?
2. What problem exists without it?
3. How does it work?
4. Why is this approach different?
5. What does the user receive or achieve?

If a required answer cannot be supported, semantic readiness becomes `NEEDS_EVIDENCE`.

### Stage 5: Build Sales Argument

The canonical master follows an explainer-first sales grammar:

```text
PROBLEM
→ PRODUCT DEFINITION
→ MECHANISM
→ REAL PROOF / OUTPUT
→ DIFFERENTIATION
→ USER RESULT
→ NEXT ACTION
```

Persuasion should result from comprehension and proof, not unsupported urgency, generic hype, or repeated hooks.

### Stage 6: Design Story and Scenes

Default target is approximately 45 to 60 seconds. A 55-second initial target is preferred.

Typical timing:

```text
00-07  problem
07-14  product definition
14-25  mechanism
25-36  real product/output/evidence
36-45  differentiation
45-52  user result
52-55  CTA / brand
```

Timing is adaptive. Semantic importance, proof density, and product complexity determine allocation.

Each scene has independent narration and on-screen semantic anchor. On-screen text should sharpen or diagram meaning rather than merely duplicate narration.

### Stage 7: Resolve Media

Asset preference order is mandatory:

1. real product output;
2. real product UI or screenshot;
3. real evidence or diagram;
4. DIO-generated explanatory diagram;
5. generated cinematic metaphor.

Generated imagery must never be presented as a real customer result, real product screenshot, or observed evidence when it is not.

### Stage 8: Render and Challenge

Before existing media QA, the explainer receives semantic adversarial QA.

Checks include:

- every material claim binds to suitable evidence or qualification;
- qualified claims were not strengthened during rewriting;
- market intelligence did not alter product truth;
- generated illustration is not represented as evidence;
- CTA does not imply unsupported availability, pricing, readiness, or customer validation;
- current product limitations remain intact;
- no automatic perceptual or publication authority is created.

Failures should trigger targeted semantic repair when possible rather than whole-project regeneration.

Existing premium-media verification remains responsible for narration provider quality, music-rights evidence, audio mix, 48 kHz stereo, loudness, native visual execution, final-video binding, canonical-output integrity, tamper detection, human visual release, and publication/spend boundaries.

### Stage 9: Freeze Canonical Explainer

A passing local master receives a stable identity such as:

`HOMS_PRODUCT_EXPLAINER_MASTER_V1`

The freeze receipt must bind:

- video hash;
- explainer-manifest hash;
- style-profile hash;
- source-product hashes;
- claim ledger;
- asset provenance;
- voice receipt;
- music/rights receipt;
- render receipt;
- semantic QA receipt;
- authority state.

Release remains `NEEDS_YOU` until explicit human authorization.

## 7. DIO Cinematic Brand Profile

`DIO_CINEMATIC_BRAND_V1` captures the learned production grammar from the approved launch trailer.

### Visual grammar

- black glass, obsidian metal, graphite;
- restrained warm gold representing active information, verified flow, authority, or release;
- monumental technological scale;
- reflective dark surfaces and controlled haze;
- deliberate symmetry and geometry;
- boundaries, chambers, routes, and gates used to communicate governance;
- real product evidence preferred over abstract imagery.

### Visual prohibitions

- generic blue AI glow;
- humanoid robots;
- glowing brains;
- Matrix-style code rain;
- decorative HUD overload;
- indiscriminate gold decoration;
- fake product interfaces;
- generated scenes presented as proof.

### Typography

- brand display: Noto Serif Display;
- body serif: Noto Serif;
- technical diagrams: clean sans-serif / DejaVu Sans class;
- canonical DIO wordmark and sigil are referenced as assets, not re-created from typed text.

### Voice

- public narrator role: Vesper;
- approved provider/profile: Pocket TTS Vera through `vera_pocket_public`;
- style: measured, composed, authoritative, restrained;
- pronunciation for the brand name must use the approved natural `Dio` form.

### Sound

- canonical sonic identity: `DIO_SONIC_IDENTITY_V1`;
- ambience: dark evolving cybernetic field, no mandatory beat;
- no generic corporate music;
- no unverified commercial music;
- generated local score is preferred when suitable;
- external music is allowed only with rights evidence.

### Motion and transitions

- restrained cinematic pushes and reveals;
- hard cut may communicate authority boundaries;
- gold aperture/bloom may communicate verified release;
- fades through black may separate conceptual states;
- no transition-pack spectacle for its own sake.

### End card

The canonical end card uses the real DIO sigil, real DIO wordmark, `WORKFLOWS`, product-appropriate CTA/tagline, and approved DIO URL. Duplicate branding layers and rasterized fake wordmarks are forbidden.

## 8. Repo Components

### New files

```text
products/product_explainer_compiler.py
config/media_style_profiles.json
schemas/product_explainer_manifest.schema.json
schemas/media_production_request_v2.schema.json
tests/test_product_explainer_compiler.py
tests/test_media_style_profiles.py
scripts/run_product_explainer_graduation.py
```

A derivative compiler is deliberately deferred until the canonical explainer graduation proof passes.

### Existing files to modify

```text
products/premium_media_federation.py
products/premium_media_gauntlet.py
scripts/run_premium_media_phase16_1_1.py
```

Changes must preserve the existing premium-media responsibilities and remove the requirement that the federation construct one fixed incident-readiness script internally.

### Existing authorities and systems to preserve

- Product Registry / product manifests / ATLAS authority over product identity;
- DIO Lingua meaning and source-hash authority;
- Commercial Truth boundaries;
- current NicheFoundry native renderer;
- Document Studio non-destructive media-control boundary;
- Seraph challenge role;
- Sophia semantic/review role where applicable;
- existing evidence/provenance receipts;
- human external-publication authority.

## 9. Failure States

The compiler must fail closed with explicit typed states rather than collapsing every failure into an exception or generic REFUSE.

Required semantic failure categories include:

- `PRODUCT_IDENTITY_UNRESOLVED`;
- `PRODUCT_IDENTITY_AMBIGUOUS`;
- `PRODUCT_TRUTH_INCOMPLETE`;
- `SOURCE_BINDING_STALE`;
- `EXPLAINER_SEMANTIC_READINESS_NEEDS_EVIDENCE`;
- `CLAIM_EXCEEDS_EVIDENCE`;
- `PROOF_ASSET_MISSING`;
- `STYLE_PROFILE_INVALID`;
- `STYLE_ASSET_MISSING`;
- `VOICE_PROFILE_UNAVAILABLE`;
- `MUSIC_RIGHTS_UNVERIFIED` when external music is supplied;
- `SEMANTIC_CHALLENGE_REFUSE`;
- `MEDIA_QA_REFUSE`;
- `HUMAN_RELEASE_NEEDS_YOU`.

Machine-repairable failures may be retried only inside their authority. No retry may invent evidence, broaden a claim, approve perception, publish, or spend money.

## 10. Testing Strategy

Implementation is test-first.

### Product Explainer Compiler tests

At minimum:

1. Given HOMS and no operator creative brief, the compiler produces a complete `ProductExplainerManifest` from bound DIO sources.
2. Missing canonical product identity refuses.
3. Conflicting identity sources at the same authority level produce `PRODUCT_IDENTITY_AMBIGUOUS`.
4. Missing required product truth produces `NEEDS_EVIDENCE` rather than invented copy.
5. Source hashes are persisted.
6. A changed bound source invalidates stale explainer reuse.
7. Market input may alter emphasis metadata but cannot mutate canonical product definition or claim envelope.
8. Unsupported benefit claims are not promoted to allowed claims.
9. Real proof assets outrank generated cinematic assets.
10. External publication remains `NEEDS_YOU`.
11. Media spend remains `REFUSE`.

### Media Style Profile tests

At minimum:

1. `DIO_CINEMATIC_BRAND_V1` validates.
2. Required wordmark, sigil, voice role, sonic identity, and palette fields are present.
3. Missing required brand asset fails closed.
4. Silent font fallback is not permitted by the profile.
5. External publication cannot be enabled by the style profile.

### Premium Media integration tests

At minimum:

1. Federation accepts a compiled explainer request rather than relying on the hard-coded incident-readiness script.
2. Existing audio, rights, native-render, integrity, tamper, visual-release, publication, and spend gates remain intact.
3. Final media receipt binds explainer-manifest and style-profile hashes.
4. Semantic QA failure prevents a passing local master.
5. Passing machine gates produce a local master while external publication remains `NEEDS_YOU`.

## 11. First Graduation Proof

HOMS is the reference graduation product because it has real product material, launch-asset machinery, and knowledge-bank assets already present in DIO.

The first proof target is conceptually:

```bash
./dio media explain homs
```

The initial implementation may use `scripts/run_product_explainer_graduation.py` before the top-level `dio` command is wired.

Success should produce a receipt equivalent to:

```text
PRODUCT_IDENTITY ................. PASS
SOURCE_BINDING ................... PASS
PRODUCT_EXPLANATION .............. PASS
CLAIM_ENVELOPE ................... PASS
PROOF_BINDING .................... PASS
COMMERCIAL_ARGUMENT .............. PASS
DIO_MEDIA_PROFILE ................ PASS
VESPER_VOICE ..................... PASS
MEDIA_RENDER ..................... PASS
SEMANTIC_CHALLENGE ............... PASS
OUTPUT_INTEGRITY ................. PASS

HOMS_PRODUCT_EXPLAINER_MASTER_V1.mp4

LOCAL_RENDER ..................... ALLOW
EXTERNAL_PUBLICATION ............. NEEDS_YOU
MEDIA_SPEND ...................... REFUSE
```

The first acceptance criterion is not that HOMS merely produces a video. The acceptance criterion is that DIO produces a truthful, persuasive, source-bound explainer without an operator-supplied creative brief and preserves its existing authority boundaries.

## 12. Deferred Scope

The following are intentionally deferred until the HOMS canonical explainer graduation passes:

- 30-second and 15-second derivative compilation;
- vertical-reel auto-derivation;
- LinkedIn-specific variants;
- buyer-specific narrative variants;
- automatic A/B creative generation;
- Market Sensorium feedback-driven creative adaptation;
- automated campaign publication;
- automated media buying or spend;
- portfolio-wide bulk explainer generation.

This keeps Round 2 focused on establishing the semantic parent object and reusable production profile before multiplying outputs.

## 13. Non-Negotiable Invariants

1. Explain the product before selling it.
2. Product truth outranks market preference.
3. Evidence constrains claims.
4. Market learning may change emphasis, not truth.
5. Real product evidence outranks generated metaphor.
6. The golden trailer teaches grammar, not scene cloning.
7. Local production may be autonomous.
8. Public release remains human-authorized.
9. No media spend is autonomously authorized.
10. Every frozen explainer carries source, claim, asset, style, audio, render, and authority lineage.
