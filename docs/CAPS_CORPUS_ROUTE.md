# CAPS Corpus Route

Date: 2026-08-07

## Authority

Official source:

- South African Department of Basic Education CAPS page: `https://www.education.gov.za/Curriculum/CurriculumAssessmentPolicyStatements%28CAPS%29.aspx`

The DBE describes CAPS documents as the Curriculum and Assessment Policy Statements for approved school subjects in the National Curriculum Statement Grades R-12.

## Local Corpus

The CAPS corpus now lives at:

- `corpora/caps/`

Important files:

- `corpora/caps/README.md`
- `corpora/caps/caps_corpus_manifest.json`
- `corpora/caps/pdf/<phase>/...`
- `deliverables/caps_matrix_analysis/caps_matrix_analysis.json`
- `deliverables/caps_matrix_analysis/caps_matrix_analysis.csv`
- `deliverables/caps_matrix_analysis/CAPS_MATRIX_ANALYSIS.md`

Current corpus status:

- Source pages crawled: 5
- Official documents downloaded/present: 282
- Failed downloads: 0
- Total PDF payload: about 489 MB

Phase split:

- `foundation_grade_r_3`: 66
- `intermediate_grade_4_6`: 48
- `senior_grade_7_9`: 52
- `fet_grade_10_12`: 108
- `policy_and_support`: 8

## Downloader

Rebuild or refresh the corpus with:

```bash
python3 scripts/download_caps_corpus.py
```

Discovery-only mode:

```bash
python3 scripts/download_caps_corpus.py --manifest-only
```

The downloader:

- crawls the official DBE CAPS page and four phase pages
- downloads official DBE `fileticket` documents
- writes a manifest with source URLs, local paths, byte counts, hashes, phases, and statuses
- ignores malformed empty download links

## HOMS Use

CAPS becomes Exam Studio's curriculum source-of-truth layer.

The intended generation order is:

1. Choose grade profile from `config/homs_grade_ladder.json`.
2. Choose subject profile from `config/homs_subject_profiles/`.
3. Retrieve the matching CAPS document(s) from `corpora/caps/caps_corpus_manifest.json`.
4. Extract curriculum scope, assessment guidance, content topics, cognitive demands, and memo constraints.
5. Generate a task, test, exam, rubric, memo, or marking pack.
6. Record the CAPS source IDs and hashes in the receipt.
7. Require educator review before use.

## Resolver

The first CAPS resolver is available:

```text
grade + subject + language/phase -> matching CAPS PDF(s) -> extracted text chunks -> retrieval context -> generation receipt
```

Run it with:

```bash
python3 scripts/resolve_caps_source.py \
  --subject business_studies \
  --grade 12 \
  --preferred-language English \
  --extract-top \
  --out deliverables/caps_resolver/business_studies_grade12
```

Other checked examples:

```bash
python3 scripts/resolve_caps_source.py --subject life_sciences --grade 12
python3 scripts/resolve_caps_source.py --subject natural_sciences --grade 6
python3 scripts/resolve_caps_source.py --subject history --grade 12
```

Observed resolver behavior:

- Business Studies Grade 12 resolves the English CAPS first.
- Life Sciences Grade 12 resolves the English CAPS first.
- Natural Sciences Grade 6 resolves the English CAPS first.
- History Grade 12 currently resolves to `Geskiedenis (History)` from the official corpus; no English History match was found in the downloaded DBE set.

The resolver should not guess. If multiple CAPS documents match, the generation route should either use the top candidate with receipt traceability or present the candidate list for human confirmation.

## Exam Builder Integration

`scripts/run_hymark_exam_builder.py` now resolves CAPS by default.

It records:

- selected CAPS title
- phase
- local PDF path
- DBE source/final URL
- SHA-256 hash
- candidate list
- compact extracted curriculum excerpt
- selected CAPS matrix row
- recommended assessment blueprint
- assessment format signals

It also injects a compact `CAPS CONTROL` note into generation topics so the backend receives grade, phase, Bloom, question-style, memo-style, selected CAPS document, hash context, recommended blueprint, and format signals.

Important: the matrix signal columns are not hard requirements. They indicate meaningful textual evidence in the CAPS document. The `recommended_blueprint` is the safer steering field.

Current blueprint categories include:

- `language_integrated_assessment`
- `case_study_structured_questions`
- `data_diagram_practical_investigation`
- `calculation_problem_solving`
- `practical_project_design_task`
- `practical_performance_or_portfolio`
- `source_based_plus_essay`
- `source_based_plus_extended_response`
- `foundation_activity_assessment`
- `structured_test_or_task`

This is the correction to the old HyMark assumption: not every CAPS assessment is source-based, and not every subject needs an essay matrix.

Runtime note: use the HOMS production venv for full Exam Builder runs because it contains `python-docx`, `openai`, and `requests`:

```bash
/home/byron/Downloads/NoEdge-Multi-Hymark-main/homs_production/venv/bin/python \
  scripts/run_hymark_exam_builder.py ...
```

Disable this only for non-school experiments:

```bash
/home/byron/Downloads/NoEdge-Multi-Hymark-main/homs_production/venv/bin/python \
  scripts/run_hymark_exam_builder.py --skip-caps
```
