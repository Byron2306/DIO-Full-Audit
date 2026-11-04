# HOMS Exam Studio → Learning Studio → Assess

## Shared curriculum contract

Exam Studio writes `HOMS_CURRICULUM_SPINE.json` using schema
`dio.homs.curriculum_spine.v1`. It carries subject, grade, term, curriculum-source
hash, selected topics, requested and grade-level Bloom targets, question families,
item-level marks and memo points, evidence cards, visual references, and hashes for
the generated paper, memo, and structured assessment pack.

The spine is a draft handoff. It does not approve curriculum alignment, create
assessment authority, or permit classroom release. A qualified educator remains
responsible for subject accuracy, source rights, answers, accessibility, language,
and final release.

## Exam Studio

Submit the HOMS exam intake with the subject, grade, term, topics, assessment form,
mark total, duration, Bloom focus, question forms, and evidence/visual preferences.
The builder uses the subject and grade profiles to constrain the generated forms.
Unsupported requested source forms are recorded for review; the builder must not
claim an unused source or visual was included.

For non-History CAPS subjects, the subject-aware assessment route is retained even
when a CAPS source is unavailable. In that case the generated spine exposes the
missing source evidence for educator review. Invalid or incomplete subject packs
are blocked after one repair attempt; no generic paper is substituted.

## Learning Studio

When `include_learning_studio` is enabled, Exam Studio builds a linked companion
from the same spine without making provider calls. The bundle contains a learner
revision route, an educator lesson and marking map, the exact first-opportunity
paper and memo, verified generated visuals, PDFs where the local converter is
available, and a video storyboard draft. The storyboard is a production brief,
not a finished video; it is explicitly gated for subject-expert approval.

The standalone generator can also be run from a matching spine:

```bash
python3 scripts/build_homs_learning_studio_from_spine.py \
  --curriculum-spine path/to/HOMS_CURRICULUM_SPINE.json \
  --out path/to/learning-studio-output
```

The older Grade 10 Physical Sciences Motion pack remains available for its existing
golden video, captions, music rights and attribution bundle. It is intentionally
kept distinct from the generic spine generator: that video is only attached to a
matching Motion request, never presented as subject-neutral content.

## HOMS Assess intake

For spine-based assessment projection, include the manifest-bound
`HOMS_CURRICULUM_SPINE.json` and the exact first-opportunity paper and memo in
`SOURCES/hymark_input/uploads/`. The projection verifies their hashes against the
spine before it derives marking criteria from the item memo points. A missing memo
point, mismatched file, unbound spine, or missing paper/memo blocks the projection.
The resulting rubric is a marking aid; it does not replace an educator's judgment.

## Review checklist

- Confirm the source is the correct subject, grade, phase and term; inspect its
  recorded hash and source rights.
- Check that question forms match the subject and assessment purpose.
- Recalculate marks, validate each answer and memo point, and inspect the actual
  mark-weighted Bloom distribution.
- Check every cited source, excerpt, image, map, graph and diagram for accuracy,
  provenance, rights, legibility and accessibility.
- Confirm the learner bundle excludes educator-only memo content from learner
  exercises and that any storyboard receives a separate expert review.
- Approve language, inclusion, classroom fit and final release explicitly.
