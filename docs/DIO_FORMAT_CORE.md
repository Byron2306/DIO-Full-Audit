# DIO Format Core

## Purpose

Format Core is the shared projection organ between canonical meaning and a delivered asset.

```text
canonical semantic content
  + approved language lane
  + style profile
  + delivery profile
  + optional client templates
  -> DOCX / PDF / PPTX / accessible HTML / VTT
  -> post-render QA
  -> hash-linked receipt
```

The formatter does not translate a finished document. Lingua translates typed semantic blocks and preserves their source hashes. Format Core then rebuilds each channel from those blocks. A changed source block invalidates the exact translated block before rendering.

## Implemented Contract

`dio.semantic_content.v1` supports:

- title and three-level heading hierarchy;
- paragraphs, references, equations, captions and annexures;
- learning objectives, teacher notes and learner instructions;
- assessment questions with marks aligned independently at the right margin;
- expected responses, bullet lists, data tables and rubrics;
- embedded figures with required captions and alternative text;
- deterministic node-and-edge diagrams;
- timed transcript blocks for VTT captions.

The shared profiles currently include DIO Professional, CAPS Educator, Institutional Academic and Minimal Print. Delivery profiles cover editable review, print, classroom, projector and mobile/LMS bundles.

Optional `format_template_paths` may provide:

```json
{
  "docx": "/controlled/templates/client.docx",
  "pptx": "/controlled/templates/client-master.pptx",
  "logo": "/controlled/templates/client-logo.png"
}
```

Template files are hashed into the render receipt. The client DOCX should be a clean template with its desired section, header and style definitions. A supplied PPTX retains its slide masters and layouts; Format Core selects its Blank layout for deterministic placement.

## Translation Authority

A target-language projection must contain:

- the same source version as the canonical object;
- one overlay for every localisable block;
- the exact source hash for each translated block;
- a human-approved lane status when `release_mode` is enabled.

Machine review candidates can be rendered for review, but they cannot be rendered in release mode. Existing Lingua controls remain responsible for terminology, numerical and protected-token checks, independent semantic critic review, reviewer dispositions, BEAST crystallisation and source-change invalidation.

## Format QA

Rendering fails closed for duplicate block IDs, unsupported block types, malformed tables, negative marks, missing media, missing captions, missing figure alternative text and incomplete or stale translation lanes.

After rendering, Format Core extracts text from DOCX, PPTX and HTML and compares it to the projected semantic strings. The PDF must also expose a non-empty text layer. The receipt records profile hashes, template hashes, source-object hash, language authority, expansion ratio, output hashes and any layout warnings.

This proves controlled semantic reconstruction. It does not claim pixel-identical recovery of arbitrary legacy formatting. A client-specific layout claim requires a supplied template and an approved rendered proof.

## Golden Proof

The controlled Grade 7 Natural Sciences bundle contains a cover, metadata, contents field, objective, explanatory text, meaningful photosynthesis diagram, equation, investigation instructions, observation table, questions, right-aligned marks, response lines, rubric, memorandum and caption track.

```text
deliverables/format_core/DIO-FORMAT-GOLDEN-001/
```

All 40 expected semantic strings are present in DOCX, PPTX and HTML. The PDF contains a valid text layer. Desktop and 390 px mobile HTML checks have no horizontal page overflow or broken images.

Rebuild it with:

```bash
./.venv/bin/python scripts/render_format_core.py \
  samples/format_core/caps_natural_sciences_g7_t1.json \
  --out deliverables/format_core \
  --style caps_educator \
  --delivery classroom_bundle
```

Document Studio now invokes this organ for both its controlled source and target-language review copy. Its earlier clean-copy, redline and bilingual-review artifacts remain intact for backward compatibility.
