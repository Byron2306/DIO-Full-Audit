# HOMS Tight 8 visual source pipeline

The Tight 8 assessment visual bank now covers English Language, Afrikaans Language, Life Orientation, Mathematics, Physical Sciences, Life Sciences, Geography and History across Grades 1–12.

## What is in the bank

- Two grade-specific, programmatically rendered stimuli for every subject/grade pair: an exact-label data graph and an original schematic diagram (a locality map for Geography). The bank has 192 such PNG/SVG pairs.
- One original teacher-authored reading passage per English and Afrikaans grade (24 additional text stimuli), plus 12 History source-analysis simulations. The History items are prominently labelled fictional and are not authentic historical documents. The reading passages are not quotations from third-party works.
- Eight Pictora-generated, subject-specific illustrations rendered locally through ComfyUI and linked to job receipts. They contain no labels or factual measurements and are explicitly marked grade-neutral.
- Every bank item records its source type, grade scope, file path, data/text origin, educator review gate and copyright status. Graph datasets are synthetic and disclosed as such. The Geography map is schematic and explicitly not to scale.

## Pipeline connection

`run_hymark_exam_builder.py` now selects grade-matched source items before authoring, passes exact graph data/text and provenance into the generation prompt, and attaches the same items to the normalized pack. Generated questions receive explicit `Source N` links when they refer to a bank visual. The Geography, science, mathematics, language and History routes then pass through the existing design-law DOCX embedding path, which gives each visual source its own page. `attach_homs_source_assets.py` uses the same grade filter: a source must declare the matching grade or be explicitly marked `grade_neutral`; unscoped subject assets are excluded. A fresh process uses `HOMS_COMPOSED_SOURCE_BANK.json` as the default bank; it composes the prior curated source bank with this visual bank.

Regenerate vector stimuli and the composed bank with:

```bash
python scripts/build_homs_tight8_pictora_source_bank.py
```

Queue the local Pictora illustrations with:

```bash
python scripts/render_homs_tight8_pictora_illustrations.py
python scripts/collect_homs_tight8_pictora_illustrations.py
```

The existing assessment build scripts then attach the new sources automatically in a fresh process. They retain educator approval and other release gates.

## Release boundary

The new material gives all 96 subject/grade combinations actual, embeddable stimuli: 236 total items, including eight grade-neutral Pictora illustrations. It is not a replacement for CAPS scope-and-sequence review or an educator's check that a particular graph, excerpt or picture supports the exact questions in a particular paper. The authored datasets are illustrative rather than measured. Pictora images require visual quality review and checkpoint/LoRA commercial-license review. Existing official-paper crops remain governed by their own provenance and release flags; unscoped source crops are deliberately not attached to grade-specific packs.

The six original English/Afrikaans Grade 10–12 excerpts are deliberately release-blocked because they are shorter than a full FET comprehension paper. HyMark should use its full-length language evidence generation for those grades; the short excerpts remain available for development/review only.
