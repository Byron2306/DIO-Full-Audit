# HOMS CAPS Ontology Closing Proof

Created: 2026-08-07

## What Changed

HOMS Exam Studio no longer has to treat one noisy CAPS PDF matrix row as the direct generation authority.

The route is now:

CAPS source documents -> document evidence -> canonical subject/phase profile -> CAPS assessment design -> render shell -> generation constraints -> validation -> educator approval.

## Canonical Ontology

- Builder: `scripts/build_caps_assessment_ontology.py`
- JSON: `deliverables/caps_assessment_ontology/caps_assessment_ontology.json`
- Report: `deliverables/caps_assessment_ontology/CAPS_ASSESSMENT_ONTOLOGY.md`
- Source matrix: `deliverables/caps_matrix_analysis/caps_matrix_analysis.json`

The ontology compresses 282 CAPS document observations into 104 canonical subject/phase profiles. Each profile carries:

- `assessment_family`
- allowed assessment modes
- default-off assessment modes
- required distribution guide
- generation constraints
- validation rules
- supporting CAPS evidence documents and signal counts

This fixes the major weakness in the raw matrix: translated versions of the same subject can now support one canonical subject profile instead of creating contradictory generator behaviour.

## Main Route Integration

- `scripts/build_caps_assessment_demos.py` now selects random proof subjects from canonical ontology profiles.
- `scripts/build_caps_assessment_demos.py` now injects the assessment-design profile into the model prompt before generation.
- `scripts/run_hymark_exam_builder.py` now resolves `assessment_ontology_profile` inside `caps_context`.
- Generation notes now treat document keyword signals as evidence, not authority.
- Source-based/essay formats are default-off unless the canonical profile and request justify them.

## Assessment Design Layer

The matrix is no longer allowed to jump straight from keyword signals to a learner paper.

- Builder: `scripts/analyze_caps_assessment_design.py`
- JSON: `deliverables/caps_assessment_design/caps_assessment_design.json`
- Report: `deliverables/caps_assessment_design/CAPS_ASSESSMENT_DESIGN.md`

This layer extracts or encodes the CAPS assessment shape:

- valid assessment forms
- annual mark weightings
- paper or task structure
- cognitive or skill distribution
- marking instruments
- render shell

Current high-confidence shells:

| Profile | Shell | Key Assessment Design |
| --- | --- | --- |
| `fet.dance_studies` | `performance_task_sheet` | SBA 25%, PAT 25%, final examinations 50%; practical performance rendered as an assessment instrument, not written answer lines |
| `intermediate.mathematics` | `question_paper` | SBA 75%, end-year exam 25%; cognitive distribution 25/45/20/10 |
| `foundation.mathematics` | `activity_sheet` | teacher-led concrete activity, observation checklist, short learner responses |
| `intermediate.coding_and_robotics` | `project_task_sheet` | design/practical deliverables, evidence log, testing record, rubric |

## Design Law Formatter

HOMS now has an executable formatting layer inspired by the NicheFoundry storyboard/visual-manifest pattern.

- Design law: `config/homs_design_law.json`
- Formatter: `scripts/apply_homs_design_law.py`
- Format references: `references/homs_assessment_examples/README.md`
- Purpose: convert a plain `assessment_pack.json` into a DBE-style formatted assessment pack with diagrams, charts, tables, visual manifest, receipt, and ZIP.

The design law controls:

- which render shell is used for the pack
- which visual families are allowed for each assessment blueprint
- which formats are default-off
- document styling
- teacher-facing visual purpose
- educator approval requirement

Current local visual types include:

- foundation number-line activity board
- intermediate design-cycle and test-log scaffold
- performance-space and rubric observation map
- generic assessment structure map fallback

## Closing Proof Run

Run folder:

`campaigns/phase3/homs/exam_builder/caps_closing_proofs/caps_closing_seed_1873619227`

Generated proof set:

| Band | Subject | Grade | Ontology Profile | Assessment Family | Status |
| --- | --- | ---: | --- | --- | --- |
| FET/Senior | Dance Studies | 10 | `fet.dance_studies` | `practical_performance_or_portfolio` | generated |
| Intermediate | Coding and Robotics | 5 | `intermediate.coding_and_robotics` | `practical_project_design_task` | generated |
| Foundation | Mathematics | 3 | `foundation.mathematics` | `foundation_activity_assessment` | generated |

Each proof folder contains:

- `ASSESSMENT_PACK.docx`
- `ASSESSMENT_PACK_FORMATTED.docx`
- `ASSESSMENT_PACK.md`
- `assessment_pack.json`
- `CAPS_ASSESSMENT_DEMO_RECEIPT.json`
- `CAPS_ASSESSMENT_DEMO_PACK.zip`
- `HOMS_VISUAL_MANIFEST.json`
- `HOMS_FORMATTER_RECEIPT.json`
- `HOMS_FORMATTED_ASSESSMENT_PACK.zip`

ZIP integrity passed for all three proof packs.

Formatted-pack ZIP integrity also passed for all three formatted packs. Learner-facing DOCX XML was checked to ensure internal labels such as `Design Law`, `Mode:`, `Assessment family:`, and `Review note:` do not appear.

After the assessment-design fix, the proof render shells are:

| Subject | Formatted Shell | Learner-Facing Headings Verified |
| --- | --- | --- |
| Dance Studies | `performance_task_sheet` | `PERFORMANCE ASSESSMENT TASK`, `ASSESSMENT INSTRUMENT` |
| Foundation Mathematics | `activity_sheet` | `LEARNER ACTIVITY`, `OBSERVATION CHECKLIST` |
| Coding and Robotics | `project_task_sheet` | `PRACTICAL ASSESSMENT TASK`, `DESIGN EVIDENCE LOG` |

## Remaining Truth

These are controlled demo packs, not classroom-authorised final assessments. The terminal gate remains educator approval.
