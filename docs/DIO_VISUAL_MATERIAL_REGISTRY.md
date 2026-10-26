# DIO Visual Material Registry

## Decision

Format Core must know both **how to draw** and **when not to draw**.

The existing semantic visual system remains authoritative for meaning and native diagrams. The Visual Material Registry adds governed access to other visual media without creating a new design organ or transferring authority to an asset provider.

The production pipeline is now:

```text
Site / product semantic object
  -> dio.format_core.semantic_visual.v1
  -> dio.format_core.visual_material_request.v1
  -> governed material resolver
       1. real DIO artifact when the product policy prefers it
       2. approved curated material when the policy prefers photography/illustration
       3. governed generated editorial material when allowed
       4. native semantic renderer fallback
  -> Format Core composition
  -> self-contained SVG customer asset
  -> Site/product QA
  -> human visual release
```

The ordered preferences are product/semantic-kind specific. There is no global rule that stock photography is better than native SVG. Evidence Synthesis prefers a real artifact; a human-review scene prefers approved photography; a quantitative graph remains a native renderer problem.

## Schemas

Registry:

```text
dio.format_core.visual_material_registry.v1
```

Material:

```text
dio.format_core.visual_material.v1
```

Request:

```text
dio.format_core.visual_material_request.v1
```

Resolution:

```text
dio.format_core.visual_material_resolution.v1
```

Mixed-media Site composition:

```text
dio.format_core.site_mixed_media.v1
```

## Material kinds

Current material kinds are:

- `native_renderer`
- `artifact_render`
- `curated_photo`
- `curated_illustration`
- `texture`
- `icon`
- `generated_editorial`

A material record binds semantic applicability, surface suitability, subjects, activities, mood, composition metadata, license status, approval state, payload hash and provenance.

## Approval and licensing law

External curated material may live in the registry as `NEEDS_REVIEW`, but it is not selectable until `APPROVED`.

A selected customer-facing material must satisfy all of the following:

- `commercial_use = true`
- curated external material license is `COMMERCIAL_ALLOWED` or `PUBLIC_DOMAIN`
- approval is `APPROVED` (or `SYSTEM` for native renderers)
- payload bytes match the recorded SHA-256
- payload path is repository-relative and cannot traverse outside the material root
- runtime remote asset fetching is refused
- external material never gains semantic, layout, release or publication authority

Generated editorial material must use `DIO_GENERATED`. Internal artifact renders use `INTERNAL_ORIGINAL` or `DIO_GENERATED`.

## Why assets are embedded

Approved file materials are embedded into the generated SVG as PNG/JPEG/WebP data URIs. The customer package therefore remains self-contained and does not depend on an external stock-photo CDN at runtime.

Remote `href` image loading is refused.

## Site Studio medium policy

The first Site Studio policy is keyed by **semantic visual kind**, never by scene role:

| Semantic visual kind | Preferred material order |
| --- | --- |
| `research_workbench` | curated photo -> generated editorial -> native renderer |
| `decision_landscape` | native renderer -> curated illustration |
| `evidence_network` | artifact render -> native renderer |
| `communication_outputs` | artifact render -> curated photo -> native renderer |
| `method_map` | curated photo -> generated editorial -> native renderer |
| `provenance_stack` | artifact render -> native renderer |
| `human_review_scene` | curated photo -> generated editorial -> native renderer |
| `bounded_action` | native renderer |

This creates deliberate media rhythm rather than eight photos or eight SVG diagrams.

## Importing material

Use the governed importer rather than manually editing the registry:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/import_visual_material.py \
  --file /path/to/research-review.jpg \
  --material-id CURATED-RESEARCH-REVIEW-001 \
  --kind curated_photo \
  --visual-kind research_workbench \
  --visual-kind human_review_scene \
  --subject research \
  --subject documents \
  --subject "human review" \
  --activity "reviewing documents" \
  --mood credible \
  --mood editorial \
  --surface website \
  --provider PROVIDER_NAME \
  --source-url SOURCE_URL \
  --license-status COMMERCIAL_ALLOWED \
  --orientation landscape \
  --subject-bias right \
  --negative-space left \
  --crop-safe
```

Without `--approve`, the asset is copied, hashed and catalogued as `NEEDS_REVIEW`; production continues to use the next selectable fallback.

After a human has verified the actual asset and license evidence, re-import a new approved material or use `--approve` at import time when approval is already established.

## Production proof

`FORMAT_CORE_SITE_VISUAL_COMPOSITOR_RECEIPT.json` now records:

- material request/resolution counts
- selected material IDs
- material-kind counts
- mixed-media scene count
- native material scene count
- fallback material scene count
- all-selected-materials commercial-use state
- all-selected-materials approval state
- `external_material_authority = REFUSE`
- `remote_runtime_asset_fetch = REFUSE`
- `role_material_selection = REFUSE`

These conditions are promoted into Site Studio visual QA, proof manifest and full-grade receipt.

## Boundary

The registry proves controlled provenance, approval state, commercial-use metadata, deterministic selection and self-contained projection. It does not independently prove that a third-party license statement is legally correct. License evidence must still be inspected by the operator when external material is approved.

The visual acceptance law remains human: the final composition must look like a customer-grade professional surface, not merely pass the material resolver.
