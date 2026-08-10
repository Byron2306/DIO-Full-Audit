# HOMS C8 Assessment Convergence

## Purpose

C8 turns the existing HOMS/HyMark assets into two conservative commercial entrypoints:

1. **Marking Relief** uses Byron's Smart Assessor as the long-form semantic marking engine, then projects its results into Grant's Local HOMS moderation and learning layer.
2. **Exam Studio** keeps the existing rich HyMark exam builder, but places a phase/term/CAPS/cognitive scope gate in front of commercial generation.

Neither original engine is replaced. C8 is the convergence boundary.

## Marking Relief

Canonical route:

```text
submission + rubric + optional memo/gradebook
  -> Smart Assessor
       -> criterion scores
       -> substantive criterion comments
       -> exact quoted submission evidence
       -> anchored annotations
       -> overall feedback / strengths / improvements
  -> C8 quality contract
       -> quote-grounding check
       -> score reconciliation
       -> annotation completeness
       -> group-ID validation against supplied gradebook
       -> buyer-facing bundle completeness
  -> Local HOMS projection
       -> cohort moderation
       -> outlier/review flags
       -> recurring difficulty/common-error learning
  -> lecturer review pack
  -> HUMAN EDUCATOR APPROVAL
```

### Required bundle

A submission is not `completed_review_ready` unless the Smart Assessor result passes the C8 quality contract. The commercial pack includes:

- criterion-specific comments;
- exact quoted evidence grounded in the submitted text;
- anchored annotations;
- annotated DOCX/PDF when the original format supports it;
- filled rubric feedback document;
- feedback text and criterion-feedback Markdown;
- marks CSV;
- compiled gradebook;
- validated group-member map;
- cohort moderation report;
- Local-HOMS learning insights;
- text-similarity review candidates;
- lecturer review summary; and
- C8 receipt and bundle manifest.

The similarity report is **not a plagiarism finding**. It only identifies pairs that warrant human inspection.

### Long-form coverage

The current Smart Assessor implementation internally caps its submission prompt. C8 therefore detects long input and passes an opening/middle/conclusion evidence window rather than silently dropping the end of the essay. The receipt records whether this happened and the estimated character coverage.

This improves coverage but does not pretend sampling equals a full-token read. A future Smart Assessor revision can replace this compatibility measure with native full-document/chunk synthesis without changing the C8 bundle contract.

### Live proof command

Prepare a real input folder:

```text
homs-longform-proof/
  rubric.json
  memo.md                 # optional
  gradebook.csv           # strongly recommended
  uploads/
    12345678.docx
```

Then on Valinor:

```bash
cd ~/DIO-Full-Audit
git switch dio-c8-homs-assessment-convergence

python scripts/run_homs_hymark_batch.py \
  --input ~/homs-longform-proof \
  --out ~/KnowEdge_Microsoft_Mirror/HOMS/done \
  --provider nim \
  --quality-retries 1
```

A clean commercial proof must finish as:

```text
completed_review_ready
```

and the generated job must contain at least:

```text
annotated/*_ANNOTATED.docx
rubric_feedback/*_RUBRIC_FEEDBACK.docx
feedback/*_CRITERION_FEEDBACK.md
gradebook_marked.csv
GROUP_MEMBER_MAP.json
MODERATION_REPORT.json
LEARNING_INSIGHTS.json
SIMILARITY_REVIEW.json
BUNDLE_MANIFEST.json
HOMS_C8_RECEIPT.json
HOMS_C8_REVIEW_PACK.zip
```

If criterion feedback or quoted evidence is missing, the job is deliberately returned as `completed_blocked_incomplete_feedback`.

## Exam Studio

The existing `run_hymark_exam_builder.py` remains the assessment-generation engine. C8 adds the commercial front door:

```text
scripts/run_homs_exam_studio_c8.py
```

The gate must establish:

- grade 1-12;
- phase;
- exact selected CAPS document;
- source SHA-256;
- term 1-4, or explicit Grade 12 `final_exam` mode;
- grade/term content signals from that CAPS source;
- grade-level Bloom targets;
- reading and writing load;
- question-style contract;
- ZPD/scaffolding expectation;
- memo style;
- cognitive-distribution source; and
- human review checks.

If grade/term content cannot be established from the selected CAPS document, C8 blocks before provider generation.

### Phase behaviour

The existing `config/homs_grade_ladder.json` remains authoritative for HOMS grade-development guardrails:

- Grades 1-3: Foundation Phase
- Grades 4-6: Intermediate Phase
- Grades 7-9: Senior Phase
- Grades 10-12: FET

The gate therefore does not create a smaller Grade 12 paper for younger learners. It carries the grade profile's allowed question styles, cognitive targets, reading/writing load and scaffolding into the generation instruction.

### Cognitive complexity

When the selected CAPS assessment-design profile contains an extracted `cognitive_distribution`, C8 uses it and records that source.

When no exact percentage is extracted, C8 uses a HOMS grade-level cognitive guardrail and explicitly marks it as **not an official CAPS percentage**. This prevents internal design heuristics from being marketed as DBE requirements.

### Example commands

Foundation Phase:

```bash
python scripts/run_homs_exam_studio_c8.py \
  --subject-profile mathematics \
  --grade 2 \
  --term 2
```

Intermediate Phase:

```bash
python scripts/run_homs_exam_studio_c8.py \
  --subject-profile natural_sciences \
  --grade 6 \
  --term 3
```

Senior Phase:

```bash
python scripts/run_homs_exam_studio_c8.py \
  --subject-profile history \
  --grade 9 \
  --term 2
```

FET final examination mode:

```bash
python scripts/run_homs_exam_studio_c8.py \
  --subject-profile history \
  --grade 12 \
  --term final_exam
```

Every C8 Exam Studio run writes `HOMS_EXAM_SCOPE_CONTRACT.json` and `HOMS_EXAM_STUDIO_C8_RECEIPT.json` beside the underlying builder outputs.

## Commercial site

`sites/homs/index.html` now visibly shows the C8 Marking Relief annotated-output shape and advertises Exam Studio as a Grades 1-12, phase/term/CAPS-aware service. The proof is labelled as a controlled demonstration rather than a client case.

## Authority boundary

C8 never turns machine scoring into final assessment authority. All marking, moderation, academic-integrity signals, memoranda, assessment papers and learner-facing artifacts remain subject to educator / subject-expert review and institutional rules.
