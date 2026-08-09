# HOMS Next Layers: Email, Subject Intelligence, Memory, Marketing

Date: 2026-08-07

## Immediate Decision

Do not create another Google Form yet.

For the next proof, use an email-first HOMS transaction loop:

1. Prospect emails a request or replies to an advert.
2. Triage classifies the request as `homs_marking_relief` or `hymark_exam_studio`.
3. A human quote/invoice/pay-link state is recorded.
4. Files arrive by attachment, Drive link, OneDrive mirror, or existing upload folder.
5. The correct HOMS strand runs.
6. Human review approves or requests revisions.
7. Delivery and closeout receipt are sent.

The payment layer should be tested as a state transition first, not as another intake surface. A pay link can sit in the email thread, and the suite records `invoice_sent`, `payment_pending`, `payment_confirmed`, `delivered`, and `closed`. Only add a new form when repeated real prospects need structured self-service intake.

## Why This Matters

The suite already proved both HOMS strands locally:

- HOMS Marking Relief produced marks, feedback, a gradebook, lecturer review summary, and review zip.
- HyMark Exam Studio produced first-opportunity and second-opportunity History exams with memoranda.

The next risk is not whether generation can happen. The next risk is whether the business loop can close without friction.

## Subject Expansion Layer

HyMark Exam Studio is currently History-shaped. To expand it, use Sophia and Mandos as a subject intelligence layer.

Sophia contributes:

- Academic retrieval from approved scholarly and educational sources.
- CAPS retrieval from the local DBE curriculum corpus.
- Source-support mapping: claim to source, provenance, contradiction, partial support, and unsupported claims.
- Pedagogical office selection: examiner, source librarian, methodologist, novice scaffold, expert challenge, integrity auditor.
- Rubric evaluation focused on evidence grounding, authorship preservation, pedagogical substance, and source limits.

Mandos contributes:

- A bounded memory ledger of repeated gaps, failures, approvals, and corrections.
- A way to remember which subject prompts, rubrics, source patterns, and exam templates are recoverable or should be rejected.
- A persistent reviewer history per subject/profile without pretending the model has durable wisdom by itself.

## Subject Profile Contract

Each subject should be represented as a small `subject_profile.json` file. The Exam Studio should consume the profile before generating papers or memos.

Required fields:

- `subject_id`
- `display_name`
- `default_level`
- `assessment_modes`
- `source_types`
- `question_families`
- `cognitive_targets`
- `rubric_dimensions`
- `memo_expectations`
- `retrieval_queries`
- `human_review_checks`
- `blocked_claims_or_modes`

The point is to stop hardcoding History assumptions into the exam builder. History can still be the best first product, but the engine should know when it is building a source analysis paper, a case-study paper, a calculation paper, a diagram paper, or a conceptual essay paper.

## Grade Stratification Layer

Subject is not enough. HOMS also needs grade/developmental stratification from Grade 1 through Grade 12.

The grade ladder now lives at:

- `config/homs_grade_ladder.json`

It records:

- grade
- phase
- learner level
- Bloom targets
- ZPD level
- reading load
- writing load
- expected question style
- memo style
- human review checks

Preview artifact:

- `deliverables/homs_grade_matrix_preview/HOMS_GRADE_MATRIX_PREVIEW.md`

This lets the operator inspect each seeded subject across Grade 1-12 before running provider-backed generation.

## CAPS Curriculum Authority

CAPS is now the source-of-truth layer for school-level Exam Studio work.

Local corpus:

- `corpora/caps/`
- `corpora/caps/caps_corpus_manifest.json`
- `docs/CAPS_CORPUS_ROUTE.md`

Current status:

- 282 official DBE CAPS/support PDFs downloaded.
- 0 failed downloads.
- Phase split: Foundation R-3, Intermediate 4-6, Senior 7-9, FET 10-12, and policy/support.
- CAPS matrix analysis completed for all 282 PDFs with recommended assessment blueprints.

The Exam Studio should resolve grade + subject + language/phase to one or more CAPS PDFs before generating school-level tasks, papers, rubrics, or memoranda.

## Seed Profiles

Seeded profile files:

- `config/homs_subject_profiles/history.json`
- `config/homs_subject_profiles/life_sciences.json`
- `config/homs_subject_profiles/business_studies.json`

History remains the proven route. Life Sciences tests diagram/source interpretation and terminology. Business Studies tests case-study reasoning and applied memo rules.

## Marketing Intelligence Layer

The old Hivenance Phoenix stack should not be reused as trading machinery here. Its useful pattern is:

observe -> hypothesise -> test -> settle -> score -> promote or retire

For the business suite, that becomes:

1. Observe market signals:
   - email replies
   - ad clicks
   - booked calls
   - upload starts
   - paid jobs
   - revision requests
   - delivery time
   - effective hourly return
2. Register hypotheses before testing:
   - "History lecturers respond better to marking-relief pain ads than exam-builder ads."
   - "Exam Studio converts better when sold as first/second-opportunity paper production."
   - "Proof screenshots outperform abstract automation claims."
3. Run campaign slices:
   - one audience
   - one offer
   - one CTA
   - one channel
4. Settle outcomes:
   - reply rate
   - qualified-lead rate
   - intake completion
   - paid conversion
   - manual minutes per job
   - revenue per job
5. Promote repeatable winners:
   - keep ads that convert
   - retire angles that produce curiosity but no files/payment
   - refine subject profiles based on actual reviewer corrections

NicheFoundry already has the right public YouTube discovery and owned analytics connectors. Use those for market evidence only, not factual evidence inside academic outputs.

## Build Order

1. Keep HOMS email-only for the next transaction proof.
2. Add payment as a business state in the email loop, not a new form.
3. Wire Exam Studio to load both a subject profile and a grade profile.
4. Run History through the profile path to avoid breaking the proven route.
5. Use the CAPS resolver already wired into Exam Studio: grade + subject + language/phase -> CAPS PDF candidates.
6. Record CAPS source IDs, hashes, extracted excerpts, matrix blueprint, and format signals in Exam Studio receipts.
7. Run one controlled provider-backed proof for Grade 3, Grade 6, Grade 9, and Grade 12.
8. Run one Life Sciences and one Business Studies controlled demo.
9. Add Mandos-style correction memory: CAPS source, profile, grade, issue, reviewer action, accepted fix.
10. Add Hivenance-style campaign hypothesis records.
11. Feed NicheFoundry/YouTube trend observations into campaign hypotheses.

## Product Position

This is no longer just "AI marking" or "AI exam generation."

The stronger product is:

HOMS is a controlled academic production desk. It receives messy education work, routes it into the right strand and grade level, generates review-ready outputs, remembers corrections, and learns which offers actually sell.
