# HOMS FET Paper Audit

- Created: 2026-08-08T07:42:28+00:00
- Overall status: `failed`
- Papers audited: 9

## Verdict

The current tight-8 outputs are route smoke packs, not final FET learner papers. Render validation passed, but learner-facing educational validity fails across the set because smoke-test and product-review language leaked into the papers.

## Summary

| Subject | Audit | Marks | Shell | Questions | Sources | Top Failures |
|---|---|---:|---|---:|---:|---|
| Afrikaans | `fatal` | 31 | `language_integrated_task` | 7 | 4 | `pipeline_review_rubric`, `source_release_blocked`, `source_curation_flags` |
| Economics | `fatal` | 31 | `structured_case_paper` | 7 | 4 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |
| English Language | `fatal` | 31 | `language_integrated_task` | 7 | 4 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |
| Geography | `fatal` | 31 | `source_response_paper` | 7 | 4 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |
| History | `fatal` | 31 | `source_essay_paper` | 7 | 4 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |
| Life Orientation | `fatal` | 23 | `performance_task_sheet` | 5 | 2 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |
| Life Sciences | `fatal` | 27 | `investigation_task_sheet` | 6 | 3 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |
| Mathematics | `fatal` | 27 | `question_paper` | 6 | 3 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |
| Physical Sciences | `fatal` | 27 | `investigation_task_sheet` | 6 | 3 | `smoke_test_language`, `product_qa_question`, `source_exemplar_meta`, `pipeline_review_rubric`, `non_learner_method_review_section` |

## Per-Paper Findings

### Afrikaans
- Folder: `deliverables/homs_core_subject_smoke_packs/afrikaans_language_g12_source_smoke`
- Expected shape: subject-specific final paper shape
- Actual title: Afrikaans Graad 12 Bron-Ingebedde Roetetoets
- Blueprint/shell: `language_integrated_assessment` / `language_integrated_task`
- Marks/duration/questions: 31 / 45 minutes / 7
- Visual assets: Text Response And Language Planner
- Source types: {'text_extract': 1, 'cartoon': 1, 'graph_or_chart': 1, 'photograph_or_image': 1}
- Findings:
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `critical` `source_release_blocked`: 4 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

### Economics
- Folder: `deliverables/homs_core_subject_smoke_packs/economics_g12_source_smoke`
- Expected shape: Economics paper: concepts, data/graphs, case material, short/structured and longer analytical responses
- Actual title: Economics Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `case_study_structured_questions` / `structured_case_paper`
- Marks/duration/questions: 31 / 45 minutes / 7
- Visual assets: Case Facts And Decision Table
- Source types: {'text_extract': 1, 'graph_or_chart': 1, 'data_table': 1, 'cartoon': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: Economics Grade 12 Source-Embedded Smoke Test
  - `major` `not_full_fet_paper_scale`: Pack has 31 marks; expected final-paper scale is around 150 marks for this subject route.
  - `critical` `source_release_blocked`: 4 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

### English Language
- Folder: `deliverables/homs_core_subject_smoke_packs/english_language_g12_source_smoke`
- Expected shape: language paper: reading/viewing, language structures, writing/presenting; no product QA questions
- Actual title: English Language Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `language_integrated_assessment` / `language_integrated_task`
- Marks/duration/questions: 31 / 45 minutes / 7
- Visual assets: Text Response And Language Planner
- Source types: {'text_extract': 1, 'cartoon': 1, 'data_table': 1, 'photograph_or_image': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: English Language Grade 12 Source-Embedded Smoke Test
  - `critical` `source_release_blocked`: 4 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

### Geography
- Folder: `deliverables/homs_core_subject_smoke_packs/geography_g12_source_smoke`
- Expected shape: Geography paper: mapwork/source skills, climate/geomorphology/settlement/economic geography and data interpretation
- Actual title: Geography Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `source_based_plus_extended_response` / `source_response_paper`
- Marks/duration/questions: 31 / 45 minutes / 7
- Visual assets: Source Panel And Evidence Table
- Source types: {'map_extract': 1, 'synoptic_weather_map': 1, 'graph_or_chart': 1, 'photograph_or_image': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: Geography Grade 12 Source-Embedded Smoke Test
  - `major` `not_full_fet_paper_scale`: Pack has 31 marks; expected final-paper scale is around 150 marks for this subject route.
  - `critical` `source_release_blocked`: 4 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

### History
- Folder: `deliverables/homs_core_subject_smoke_packs/history_g12_source_smoke`
- Expected shape: History paper: source-based analysis, reliability/usefulness/comparison and essay/paragraph argument
- Actual title: History Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `source_based_plus_essay` / `source_essay_paper`
- Marks/duration/questions: 31 / 45 minutes / 7
- Visual assets: Source Panel And Evidence Table
- Source types: {'text_extract': 1, 'photograph_or_image': 1, 'cartoon': 1, 'data_table': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: History Grade 12 Source-Embedded Smoke Test
  - `major` `not_full_fet_paper_scale`: Pack has 31 marks; expected final-paper scale is around 150 marks for this subject route.
  - `critical` `source_release_blocked`: 4 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

### Life Orientation
- Folder: `deliverables/homs_core_subject_smoke_packs/life_orientation_g12_source_smoke`
- Expected shape: LO CAT/question paper: Section A/B compulsory, Section C choice, scenario extracts, full-sentence paragraph responses
- Actual title: Life Orientation Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `practical_performance_or_portfolio` / `performance_task_sheet`
- Marks/duration/questions: 23 / 45 minutes / 5
- Visual assets: Performance Floor Plan And Sequence Map, Teacher Observation Instrument
- Source types: {'text_extract': 1, 'data_table': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: Life Orientation Grade 12 Source-Embedded Smoke Test
  - `major` `not_full_fet_paper_scale`: Pack has 23 marks; expected final-paper scale is around 100 marks for this subject route.
  - `fatal` `wrong_subject_visual_shell`: Subject uses inappropriate visual/shell token: performance floor
  - `fatal` `wrong_subject_visual_shell`: Subject uses inappropriate visual/shell token: teacher observation
  - `fatal` `lo_wrong_render_shell`: FET LO CAT should render as a structured question paper, not a performance task sheet.
  - `critical` `source_release_blocked`: 2 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.
  - `major` `lo_false_data_table_candidate`: LO paragraph mentioning data analytics was classified as a data_table source.

### Life Sciences
- Folder: `deliverables/homs_core_subject_smoke_packs/life_sciences_g12_source_smoke`
- Expected shape: Life Sciences paper: biological concepts, diagrams, data/graphs, investigations and content-specific questions
- Actual title: Life Sciences Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `data_diagram_practical_investigation` / `investigation_task_sheet`
- Marks/duration/questions: 27 / 45 minutes / 6
- Visual assets: Investigation Data And Method Sheet
- Source types: {'data_table': 1, 'diagram_or_model': 1, 'graph_or_chart': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: Life Sciences Grade 12 Source-Embedded Smoke Test
  - `major` `not_full_fet_paper_scale`: Pack has 27 marks; expected final-paper scale is around 150 marks for this subject route.
  - `critical` `source_release_blocked`: 3 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

### Mathematics
- Folder: `deliverables/homs_core_subject_smoke_packs/mathematics_g12_source_smoke`
- Expected shape: calculation/problem paper with values, diagrams, graphs and worked memo; no source-curation meta
- Actual title: Mathematics Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `calculation_problem_solving` / `question_paper`
- Marks/duration/questions: 27 / 45 minutes / 6
- Visual assets: Working Grid And Method Marks
- Source types: {'diagram_or_model': 1, 'graph_or_chart': 1, 'data_table': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: Mathematics Grade 12 Source-Embedded Smoke Test
  - `major` `not_full_fet_paper_scale`: Pack has 27 marks; expected final-paper scale is around 150 marks for this subject route.
  - `critical` `source_release_blocked`: 3 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

### Physical Sciences
- Folder: `deliverables/homs_core_subject_smoke_packs/physical_sciences_g12_source_smoke`
- Expected shape: Physical Sciences paper: equations/calculations, experiments, graphs/tables, units and scientific reasoning
- Actual title: Physical Sciences Grade 12 Source-Embedded Smoke Test
- Blueprint/shell: `data_diagram_practical_investigation` / `investigation_task_sheet`
- Marks/duration/questions: 27 / 45 minutes / 6
- Visual assets: Investigation Data And Method Sheet
- Source types: {'data_table': 1, 'diagram_or_model': 1, 'graph_or_chart': 1}
- Findings:
  - `fatal` `smoke_test_language`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `product_qa_question`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `source_exemplar_meta`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `pipeline_review_rubric`: Learner-facing paper contains smoke-test/product-QA language.
  - `fatal` `non_learner_method_review_section`: Pack includes a review section aimed at product/educator QA rather than learners.
  - `fatal` `smoke_title`: Assessment title is not a final classroom paper title: Physical Sciences Grade 12 Source-Embedded Smoke Test
  - `major` `not_full_fet_paper_scale`: Pack has 27 marks; expected final-paper scale is around 150 marks for this subject route.
  - `critical` `source_release_blocked`: 3 embedded source(s) remain blocked for human source review.
  - `major` `source_curation_flags`: One or more source assets are still page-level, mismatched, or require object-level review.

## Required Repair

1. Split route smoke tests from learner-facing exam generation. Smoke packs must never be presented as final papers.
2. Remove `Method And Review`, source-catalogue meta questions, and release/copyright/product-QA questions from learner papers.
3. Build subject-specific FET paper shells from actual DBE paper structures before regenerating.
4. Fix Life Orientation as a CAT-style structured response paper, not a performance task.
5. Clear or replace all blocked source assets with human-reviewed object crops before client delivery.
