# HyMark Exam Builder Route

HyMark has a second commercial capability separate from batch marking:

```text
Exam paper setup + memorandum generation
```

This is a different market from HOMS Marking Relief.

## Product

HyMark Exam Studio turns an exam brief into:

- 1st opportunity exam paper
- 1st opportunity memorandum / marking guide
- 2nd opportunity exam paper
- 2nd opportunity memorandum / marking guide

The proven History structure supports:

- two source-based History questions
- methodology / lesson-planning question
- essay question
- essay assessment matrix
- mark calculation tables

Subject expansion now uses the same HyMark route, but with a CAPS assessment-design shell when the subject is not History. Seed profiles live in:

- `config/homs_subject_profiles/history.json`
- `config/homs_subject_profiles/life_sciences.json`
- `config/homs_subject_profiles/business_studies.json`

History remains the validated first route. Non-History school subjects now use the `caps_shell` backend inside `scripts/run_hymark_exam_builder.py`, not the separate CAPS demo builder.

Grade expansion is also profile-driven. The Grade 1-12 ladder lives in:

- `config/homs_grade_ladder.json`

The route records grade phase, learner level, Bloom targets, ZPD level, question style, reading load, writing load, and review checks.

CAPS is the curriculum authority and assessment-shape layer for school-level routes:

- `corpora/caps/caps_corpus_manifest.json`
- `deliverables/caps_matrix_analysis/caps_matrix_analysis.json`
- `deliverables/caps_assessment_ontology/caps_assessment_ontology.json`
- `deliverables/caps_assessment_design/caps_assessment_design.json`
- `docs/CAPS_CORPUS_ROUTE.md`

The current script records grade and subject profiles, resolves the matching CAPS PDF(s), extracts a compact curriculum excerpt, attaches the CAPS matrix row, attaches the canonical ontology profile, attaches the CAPS assessment-design profile, injects those controls into generation prompts, validates mark reconciliation, and records source IDs/hashes/blueprint/render-shell signals in the request and receipt.

Resolver command:

```bash
python3 scripts/resolve_caps_source.py \
  --subject business_studies \
  --grade 12 \
  --preferred-language English \
  --extract-top
```

The integrated Exam Builder route uses the same CAPS manifest by default:

```bash
/home/byron/Downloads/NoEdge-Multi-Hymark-main/homs_production/venv/bin/python \
  scripts/run_hymark_exam_builder.py \
  --provider nim \
  --secret-file /home/byron/EdgeK-BEAST/.beast/provider_secrets.env \
  --subject-profile business_studies \
  --grade 12 \
  --preferred-language English \
  --request path/to/business_studies_exam_request.json
```

## Buyer

Primary buyers:

- lecturers preparing test or exam papers
- school History teachers under assessment deadline pressure
- education departments that need moderated paper drafts
- tutors or programme coordinators creating controlled practice exams

## Command Proof

Run the no-UI proof route:

```bash
/home/byron/Downloads/NoEdge-Multi-Hymark-main/homs_production/venv/bin/python \
  scripts/run_hymark_exam_builder.py \
  --provider nim \
  --secret-file /home/byron/EdgeK-BEAST/.beast/provider_secrets.env \
  --subject-profile history \
  --grade 12
```

Default demo brief:

- Module: `HISE411 - HISTORY SNR & FET 4A`
- Source topics:
  - `The Cuban Missile Crisis (1962)`
  - `The Division of Germany (1945-1949)`
- Methodology topic: `The Berlin Airlift`
- Essay topic: `The role of media in shaping public opinion during the Vietnam War`
- Total: `125 marks`

Run a controlled non-History profile with a matching request JSON:

```bash
/home/byron/Downloads/NoEdge-Multi-Hymark-main/homs_production/venv/bin/python \
  scripts/run_hymark_exam_builder.py \
  --provider nim \
  --secret-file /home/byron/EdgeK-BEAST/.beast/provider_secrets.env \
  --subject-profile life_sciences \
  --grade 10 \
  --request path/to/life_sciences_exam_request.json
```

Run a dynamic subject-aware CAPS route even when no subject JSON exists:

```bash
/home/byron/Downloads/NoEdge-Multi-Hymark-main/homs_production/venv/bin/python \
  scripts/run_hymark_exam_builder.py \
  --provider nim \
  --secret-file /home/byron/EdgeK-BEAST/.beast/provider_secrets.env \
  --subject-profile dance_studies \
  --grade 10 \
  --preferred-language English \
  --out campaigns/phase3/homs/exam_builder/subject_aware_proof
```

## Outputs

The proof route writes to:

`campaigns/phase3/homs/exam_builder/proof/<job_id>/`

Each job contains:

- `exam_builder_request.json`
- `exam_set.json`
- `HYMARK_EXAM_REVIEW_SUMMARY.md`
- `HYMARK_EXAM_BUILDER_RECEIPT.json`
- `HYMARK_EXAM_BUILDER_PACK.zip`
- CAPS source context inside the request and receipt
- `generation_backend`: `hymark_history` for the proven History route or `caps_shell` for non-History CAPS assessment-design routes
- CAPS matrix blueprint and format signals
- first opportunity exam DOCX
- first opportunity memo DOCX
- second opportunity exam DOCX
- second opportunity memo DOCX
- non-History route only: opportunity folders containing `assessment_pack.json`, `HYMARK_ASSESSMENT_VALIDATION.md`, `ASSESSMENT_PACK_FORMATTED.docx`, visual manifest, and formatted ZIP

## Subject-Aware Shells

The `caps_shell` backend chooses the render shell from `deliverables/caps_assessment_design/caps_assessment_design.json`:

- `performance_task_sheet` for practical/performance subjects such as Dance Studies
- `project_task_sheet` for design/project subjects
- `activity_sheet` for Foundation Phase activity assessments
- `question_paper` for formal written tests/exams
- `structured_case_paper`, `investigation_task_sheet`, and source-response shells where the CAPS profile supports them

The validation layer rejects unreconciled marks, missing sections/rubrics, internal uncertainty phrases, and practical-performance packs that drift back into written-paper or essay language.

## Review Boundary

This product creates professional drafts, not final authorized assessment instruments.

Human expert review is required before use:

- verify source authenticity
- check mark allocation
- check institutional format
- moderate difficulty
- align with module outcomes
- confirm subject-profile controls were followed
- confirm grade-profile controls were followed
