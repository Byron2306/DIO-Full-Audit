# HOMS History Builder Comparison

Created: 2026-08-08

## Verdict

The latest HOMS work is strong at the CAPS shell layer: it resolves subject, grade, term, phase, assessment family, and formatting much better than the old HyMark prototype.

The source layer is the weak point. The current tight-8 deterministic route attaches source assets after the paper has already been written, so the questions are not truly grounded in the attached material. For History, the curated source bank is currently contaminated by instruction pages, question prompts, and table-of-contents style crops. Those must not be treated as paper sources.

The old HyMark History builder is stronger because it is source-first:

1. Generate or assemble Source A/B/C with provenance, content, and context.
2. Generate questions from those exact sources.
3. Generate memo points from those exact questions.
4. Render the paper with sources before questions.

That route should become the main History route again.

## Current Route Failure

Current example:

`deliverables/homs_tight8_term_source_first_packs/deterministic-history-g12-t1-20260808T101028Z/ASSESSMENT_PACK_FORMATTED.docx`

Observed source attachments:

- Source 1: `History P1 November 2024`, page 2, `text_extract`
- Source 2: `History P1 November 2024`, page 5, `photograph_or_image`
- Source 3: `History P1 November 2024`, page 4, `cartoon`

The source snippets show the problem:

- `QUESTION 2: INDEPENDENT AFRICA... QUESTION 3...`
- `Study Sources 2A, 2B, 2C and 2D and answer the questions that follow...`
- `2.3.1 Explain why you think this photograph was taken...`

These are not clean sources. They are instruction/question-page artifacts.

The generated questions are also generic:

- `Contextualise the source in relation to the historical topic.`
- `Explain the message or viewpoint of the source using evidence.`
- `Evaluate the usefulness or reliability of the source.`

Those questions are not tied to a named source, quote, author, date, cartoon detail, map feature, or historical claim.

## Old HyMark Route Strength

Old example:

`campaigns/phase3/homs/exam_builder/proof/hymark-exam-hise411-20260807T181416Z/HISE411_Exam_1stOpp_20260807T181716Z.docx`

The old route produces source cards like:

- Source A: John F. Kennedy televised address, October 22, 1962
- Source B: Herblock political cartoon description, October 26, 1962
- Source C: Robert F. Kennedy memoir excerpt, published 1969

Then it writes questions that directly reference the source cards:

- `[Source A] What specific action did President Kennedy announce...`
- `[Source B] Identify two visual elements...`
- `[Source C] Evaluate the reliability of Robert F. Kennedy's memoir...`
- `[Sources A, B, and C] Using all three sources...`

That is the pattern HOMS needs.

## Integration Decision

For History, the tight-8 route should no longer use deterministic generic History sections plus post-hoc source attachment.

New History route:

```text
CAPS grade + term context
        ↓
History topic selection
        ↓
HyMark source generation / verified source assembly
        ↓
source quality validation
        ↓
source-grounded question generation
        ↓
memo generation
        ↓
modern HOMS formatter/design law
        ↓
educator approval
```

The old-paper catalogue should inform source types and exam structure only. It should not directly supply crops unless those crops pass source QA.

## Source QA Gate Added

`scripts/attach_homs_source_assets.py` now rejects source-bank assets when they show any of these signals:

- release gate already blocked
- crop needs human review
- page-level source rather than object crop
- object/source-type mismatch
- instruction/question snippets
- mark allocation snippets
- weak or missing snippet

Dry-run result against the latest History pack:

- attached: `0`
- rejected: `6`
- gate: `blocked_no_usable_sources`

This is good. It means bad History crops now fail before they can pollute the paper.

## Rethink

The source engine should be split into two lanes:

1. **Constructed source lane**

   Use this when official extraction is weak or unavailable. It creates historically accurate, classroom-safe, review-required source cards with provenance and context. This is what the old History builder did well.

2. **Verified extracted source lane**

   Use this only when a real extraction stage has isolated the actual addendum source object, not the question prompt around it. Every extracted source needs a readability/crop/provenance gate before it can enter a learner paper.

For immediate product quality, History should use lane 1 by default and lane 2 only when a human-curated source object exists.

## Next Implementation Target

Build a `history_source_first` pack path that combines:

- current CAPS term/grade context
- old HyMark `generate_exam_sources`
- old HyMark `generate_source_questions`
- modern HOMS `assessment_pack.json`
- modern HOMS formatter

That gives us the best of both systems: current CAPS alignment plus the old source-first intelligence.
