# HOMS Core Subjects Readiness

Status: the core route layer is now ready for:

- English Language / English HL / English FAL
- Afrikaans Language
- Economics
- Geography
- History
- Life Orientation
- Life Sciences
- Mathematics
- Physical Sciences

## What Ready Means

Ready means the system has:

- a hand-authored HOMS subject profile
- a CAPS assessment-design family
- a render route
- subject-specific risk checks
- memo expectations
- source/visual expectations

For Economics, English, Geography, History, Life Sciences, Mathematics and Physical Sciences, the source bank now contains extracted official-paper page exemplars that can be attached and embedded into HOMS assessment packs.

For Afrikaans and Life Orientation, the CAPS route and subject profile are present, but official-paper/source exemplars still need to be added to the source bank. Life Orientation can still produce supervised school-based tasks because its assessment route is practical/portfolio/rubric-driven rather than a normal external exam-paper route.

## Source Embedding Proof

The source pipeline now has a reusable attachment step:

`official-paper source bank -> source_assets in assessment_pack.json -> DOCX source section -> manifest/receipt/zip audit trail -> PDF visual check`

The first proof run was Physical Sciences Grade 12. It attached and embedded:

- data table
- diagram/model
- graph/chart

The DOCX package contains the embedded media, the review zip includes the source images under `source_material/`, and the PDF visual check confirms the source pages render with visible content.

The core FET smoke lane has also passed for 7 generated packs:

- Physical Sciences
- Life Sciences
- Geography
- History
- Economics
- Mathematics
- English Language

Validation checks confirm each generated pack has embedded media, review-zip source material, and successful PDF export. This proves the route mechanics.

The source bank now has a curated derivative layer:

`raw official-paper page exemplar -> Pillow margin trim -> pdftotext-bbox snippet anchor -> preferred source candidate -> blocked release gate`

This improves the visual quality of source embedding by using closer object-candidate crops where the PDF snippet can be anchored. It still does not make the pack client-ready by itself.

Current source-quality caveats:

- Life Sciences is missing a trustworthy `graph_or_chart` exemplar in the local source bank; the previous candidate was an instruction-page false positive and is now rejected.
- Geography passes route validation, but several source pages are flagged as multi-source or classifier/object-id mismatches; these need object-level cropping/readability review before client delivery.
- English, History, Mathematics and Physical Sciences have smaller source flags that are acceptable for smoke proof but still require educator/source review.
- Release status is intentionally blocked while any embedded source has a blocked release gate. Passing smoke validation means the machine works; it does not mean the product is ready to sell.

## The Skull Problem

The Life Sciences skull asset exposed the real issue: generated visuals are not automatically authoritative source material.

The fix is now encoded in the manifest policy:

- generated diagrams are allowed as schematics
- anatomy/science diagrams must be marked as schematic unless sourced or curated
- educator verification remains mandatory
- high-touch assets should preferably come from extracted official-paper exemplars or curated subject templates

The current Life Sciences hominin diagram is acceptable only as a simplified comparison schematic. It should not be treated as a biologically authoritative skull illustration.

The practical implication: for Life Sciences human evolution, the route should prefer curated/source-verified diagrams over generated anatomy. The generated skull-style diagram can support a draft or teacher review pack, but it should not be the authoritative assessment source by itself.

## Next Build Priority

The fastest sensible pilots are:

1. Physical Sciences: data + diagram + graph route, closest cousin to the Life Sciences win.
2. Geography: source-heavy route; must use the source bank, especially maps, synoptic maps, graphs and photographs.
3. History: source-based route; must use source extracts/photographs/cartoons and keep essay requirements subject-aware.
4. Economics: case/source route; use graphs, cartoons, tables and text extracts.
5. Mathematics: calculation/problem route, but needs stronger graph/geometry diagram templates.
6. English: language-integrated shell is available; use official text/visual exemplars.
7. Afrikaans: route is ready, but source exemplars need to be catalogued.
8. Life Orientation: portfolio/performance route is ready, but must stay educator-supervised and sensitive.
