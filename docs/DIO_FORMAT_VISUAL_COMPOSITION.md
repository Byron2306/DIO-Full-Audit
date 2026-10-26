# DIO Format Core Visual Composition

## Decision

DIO does not create a second design organ.

Format Core is already the shared projection organ between canonical meaning and delivered assets. HOMS is the reference ancestor for the semantic-visual subsystem inside Format Core because HOMS proved the important design law: **draw the thing the content is about**.

The governing pipeline is now:

```text
canonical semantic content
  + product visual intent
  + explicit visual profile
        ↓
dio.format_core.semantic_visual.v1
        ↓
semantic visual kind
        ↓
Format Core semantic renderer registry
        ↓
dio.visual_composition.v1
        ↓
Format Core visual composer
        ↓
deterministic SVG
        ↓
optional PNG projection
        ↓
hash-linked visual receipt
        ↓
product renderer
```

The critical inversion is that product roles no longer select geometry. A role such as `service_2`, `proof`, `scene_4` or `question_3` is provenance and semantic context, not a template key.

Gamma and other generative design providers may propose art direction, candidate images or visual intent. They do not become the canonical renderer and they do not gain semantic, layout, text, selection, release or publication authority.

## Why HOMS is the reference ancestor

HOMS already demonstrated content-native rendering rather than generic diagram layout.

Examples in production-shaped code include:

- scientifically coherent electrical circuit schematics;
- quantitative graphs with real axes, scales, points and relationships;
- galvanic-cell apparatus diagrams;
- geography maps with grid, river, road, railway, zones, legend, scale and north arrow;
- data tables combined with charts;
- number lines and calculation workspaces;
- concept and relationship maps;
- position-time and velocity-time graphs;
- physical reference-frame illustrations;
- investigation sheets, project mazes, performance maps and design-cycle evidence logs.

Representative sources include:

- `scripts/apply_homs_design_law.py`
- `scripts/build_physical_sciences_reference_pack.py`
- `scripts/build_geography_reference_pack.py`
- `scripts/build_homs_learning_pack.py`
- `config/homs_design_law.json`

The extraction preserves the HOMS law and removes education-only coupling.

## Semantic Visual Object

The reusable contract is:

```text
dio.format_core.semantic_visual.v1
```

A semantic visual binds meaning before geometry. Core fields include:

- `visual_id`
- `surface`
- `visual_kind`
- `semantic_intent`
- `title`
- `summary`
- typed `entities`
- typed `relationships`
- optional structured `data`
- source semantic and story bindings
- governance and authority boundaries
- deterministic `semantic_visual_hash`

Every semantic visual must declare:

```text
geometry_selector = semantic_visual_kind_registry
source.role_selects_geometry = false
```

If a product tries to make a role directly own geometry, the semantic-visual gate refuses it.

## Renderer registry

`adapters/format_core/semantic_visual.py` owns the shared semantic renderer registry.

Current Site-native visual kinds are:

- `research_workbench`
- `decision_landscape`
- `evidence_network`
- `communication_outputs`
- `method_map`
- `provenance_stack`
- `human_review_scene`
- `bounded_action`

The first HOMS-native visual kinds promoted into the shared registry are:

- `quantitative_graph`
- `concept_map`
- `reference_frame`
- `circuit_schematic`
- `geographic_map`

These are semantic representations, not layout-family names. A quantitative graph means the content contains a quantitative relationship. A circuit schematic means the content contains an electrical system. A geographical map means the content contains spatial/geographical entities and relationships.

Additional products can add their own semantic compilers while feeding the same shared registry.

## Surface-specific semantic compilers

The renderer registry is universal. Meaning classification is surface-aware.

For Site Studio:

```text
adapters/format_core/site_semantic_visual.py
```

compiles Site semantic scenes into `dio.format_core.semantic_visual.v1`.

This separation is intentional:

```text
Site Studio semantics
    ↓
Site semantic visual compiler
    ↓
semantic visual object
    ↓
shared Format Core renderer registry
```

HOMS, Sophia, Evidex, Document Studio and other products may each own a semantic compiler appropriate to their domain without acquiring a private geometry engine.

## Low-level visual composition contract

`dio.visual_composition.v1` remains the deterministic low-level geometry contract. It contains:

- `composition_id`
- `title`
- `profile_id`
- deterministic canvas dimensions and background
- ordered, uniquely identified visual components

Its primitive vocabulary remains intentionally small:

- `text`
- `badge`
- `panel` / `rect`
- `line`
- `circle`
- `path`
- `cards`
- `process`
- `table`

These are implementation primitives, not creative concepts. The semantic visual layer decides whether the content is a map, graph, circuit, evidence network, human review scene or other typed visual. Only then does the renderer lower that meaning into these primitives.

That distinction prevents the failure mode where changing rectangles into circles is mistaken for visual diversity.

## Visual profiles

`config/visual_profiles.json` provides explicit profiles including:

- `dio_professional_visual`
- `caps_assessment_visual`
- `site_editorial_dark`

A profile owns palette, typography and geometry tokens. It does not choose the visual kind. Colour and typography may vary without rewriting meaning.

## Site Studio integration

Site Studio consumes Format Core semantic visual composition through:

```text
adapters/format_core/site_visual_compositor.py
```

The live `products/site_full_grade_bridge_v3.py` route keeps Site Studio as semantic owner while moving visual-semantic compilation and geometry authority to Format Core:

```text
Site Studio story / semantic law
        ↓
bounded art direction
        ↓
Site semantic visual compiler
        ↓
eight semantic visual objects
        ↓
shared Format Core semantic renderer registry
        ↓
site_editorial_dark profile
        ↓
eight deterministic SVG scenes
        ↓
Site Studio HTML/CSS embedding
        ↓
visual QA + proof manifest
        ↓
human visual release
```

The current Karoo Research Advisory proof is expected to compile into:

```text
site hook         → research_workbench
Research strategy → decision_landscape
Evidence synthesis→ evidence_network
Decision comms    → communication_outputs
method            → method_map
proof             → provenance_stack
human authority   → human_review_scene
CTA               → bounded_action
```

This mapping is a consequence of the current semantic content, not a hard-coded role table. Tests explicitly prove that the same role can resolve to different visual kinds when its meaning changes.

The authority contract remains explicit:

- `site_semantic_authority = DIO_SITE_STUDIO`
- `semantic_visual_compiler = DIO_FORMAT_CORE`
- `geometry_authority = DIO_FORMAT_CORE`
- `text_projection_authority = DIO_FORMAT_CORE`
- `role_geometry_selection = REFUSE`
- `gamma_layout_authority = REFUSE`
- `gamma_text_authority = REFUSE`
- `gamma_role = OPTIONAL_IMAGE_MATERIAL_ONLY`
- `human_visual_release = NEEDS_YOU`
- `publication = REFUSE`
- `authority_created = false`

The former `adapters/document_studio/site_svg_compositor.py` remains legacy compatibility code while callers converge. New Site Studio full-grade receipts record `document_studio_svg_compositor = RETIRED_TO_FORMAT_CORE` rather than claiming Document Studio still owns site geometry.

## Governance

The low-level composer validates before rendering and fails closed on:

- unknown schema
- missing identity or profile
- invalid canvas dimensions
- duplicate component IDs
- unknown component kinds
- malformed tables
- incomplete processes or card sets

The semantic visual layer separately fails closed on:

- unknown semantic visual schema
- unknown `visual_kind`
- missing semantic intent
- role-selected geometry
- an invalid geometry selector
- excessive collapse of a Site into too few semantic visual kinds

Site Studio also retains a linear-process budget. The current semantic site build uses zero generic `process` components because its method is rendered as a spatial method map rather than another horizontal flowchart.

Receipts record semantic visual hashes, visual-kind distribution, composition hashes, profile hashes and SVG hashes. The system creates no authority and refuses automatic publication.

## Migration sequence

1. **DONE**: reusable low-level composer, profiles, tests and golden proof.
2. **DONE**: first shared Semantic Visual Object and renderer registry.
3. **DONE, pending runtime proof**: Site Studio routed through a dedicated semantic visual compiler and shared semantic renderer registry.
4. **NEXT**: migrate HOMS visual-kind selection to emit `dio.format_core.semantic_visual.v1` while preserving existing HOMS output and assessment design law.
5. Add semantic compilers for Document Studio, Sophia, Evidex and other visual products where useful.
6. Remove duplicated local SVG/PIL helpers only after byte-level and human visual parity are proven.

The acceptance law is not "the SVG rendered" and not "the layouts look different." The acceptance law is:

> the semantic object selects an appropriate visual language, that meaning lowers deterministically into a governed artifact, the artifact is fit for the target surface, and no provider or template can silently rewrite product meaning or publication authority.
