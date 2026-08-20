# DIO Format Core Visual Composition

## Decision

DIO does not create a second design organ.

Format Core is already the shared projection organ between canonical meaning and delivered assets. The HOMS Exam Studio visual renderer therefore becomes the reference ancestor for a new visual-composition subsystem inside Format Core.

The governing pipeline is:

```text
canonical semantic content
  + product visual intent
  + explicit visual profile
  -> dio.visual_composition.v1
  -> Format Core visual composer
  -> deterministic SVG
  -> optional PNG projection
  -> hash-linked visual receipt
  -> product renderer
```

Gamma and other generative design providers may propose art direction or candidate visual intent. They do not become the canonical renderer and they do not gain automatic publication authority.

## Why HOMS is the reference ancestor

`scripts/apply_homs_design_law.py` already proves the missing capability in production-shaped code. It constructs assessment-purpose SVGs from typed packs rather than asking a template service to invent a page. Existing visual families include calculation workspaces, source panels, case decision tables, investigation sheets, language planners, project mazes, design-cycle evidence logs, performance maps, geography maps and science data graphics.

HOMS also carries a genuine design law in `config/homs_design_law.json`: visual form follows the canonical assessment ontology, every visual has a typed purpose, age/phase changes visual density, and human release remains explicit.

The extraction keeps those principles and removes the education-only coupling.

## New reusable contract

`dio.visual_composition.v1` contains:

- `composition_id`
- `title`
- `profile_id`
- deterministic canvas dimensions and background
- ordered, uniquely identified visual components

The first component vocabulary is deliberately small:

- `text`
- `badge`
- `panel` / `rect`
- `line`
- `circle`
- `path`
- `cards`
- `process`
- `table`

This is enough to reproduce the core geometry HOMS already uses while remaining useful to Site Studio, Document Studio, Publication Studio, Finance Readiness, dashboards, campaign assets and future product surfaces.

## Visual profiles

`config/visual_profiles.json` begins with three explicit profiles:

- `dio_professional_visual`
- `caps_assessment_visual`
- `site_editorial_dark`

A profile owns palette, typography and geometry tokens. Product semantics never hard-code a provider template. This is the direct antidote to Gamma template-card drift.

## Site Studio integration

Site Studio now consumes Format Core visual composition directly through:

```text
adapters/format_core/site_visual_compositor.py
```

The live `products/site_full_grade_bridge_v3.py` route keeps Site Studio as semantic owner while moving visual projection authority to Format Core:

```text
Site Studio story / semantic law
        -> bounded art direction
        -> Format Core site visual compositor
        -> site_editorial_dark visual profile
        -> eight deterministic role-bound SVG scenes
        -> Site Studio HTML/CSS embedding
        -> visual QA + proof manifest
        -> human visual release
```

The authority contract is explicit:

- `site_semantic_authority = DIO_SITE_STUDIO`
- `geometry_authority = DIO_FORMAT_CORE`
- `text_projection_authority = DIO_FORMAT_CORE`
- `gamma_layout_authority = REFUSE`
- `gamma_text_authority = REFUSE`
- `gamma_role = OPTIONAL_IMAGE_MATERIAL_ONLY`
- `human_visual_release = NEEDS_YOU`
- `publication = REFUSE`
- `authority_created = false`

The former `adapters/document_studio/site_svg_compositor.py` remains only as legacy compatibility code while callers converge. New Site Studio full-grade receipts record `document_studio_svg_compositor = RETIRED_TO_FORMAT_CORE` rather than claiming that Document Studio still owns site geometry.

## Governance

The composer validates before rendering and fails closed on:

- unknown schema
- missing identity or profile
- invalid canvas dimensions
- duplicate component IDs
- unknown component kinds
- malformed tables
- incomplete processes or card sets

The visual receipt records composition hash, profile hash, SVG hash, rasterization status and component count. The composer creates no authority and refuses automatic publication.

## Migration sequence

1. **DONE**: land the reusable composer, profiles, tests and golden proof without changing live products.
2. **IN PROGRESS**: refactor HOMS visual primitives to call the Format Core composer while preserving the existing HOMS design law and output contract.
3. **DONE, pending runtime proof**: route Site Studio composition through `site_editorial_dark` with Format Core as the authoritative visual projection layer.
4. Promote additional product-specific visual profiles only after controlled visual proofs.
5. Remove duplicated local SVG helpers once each caller is proven on the shared path.

The acceptance law is not "the SVG rendered." The acceptance law is: the same semantic intent and visual profile produce stable composition bytes, the artifact is fit for the target surface, and no visual provider can silently rewrite product meaning or publication authority.
