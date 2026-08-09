# HOMS Grade Stratification

Date: 2026-08-07

HOMS needs two independent controls:

- Subject profile: what discipline is being assessed.
- Grade profile: what developmental and cognitive level is appropriate.

The grade ladder lives at `config/homs_grade_ladder.json`.

The school curriculum authority corpus lives at `corpora/caps/`.

## Grade Ladder

| Grade | Phase | Bloom Range | Assessment Shape |
| --- | --- | --- | --- |
| 1 | Foundation | remember, understand | picture prompts, oral prompts, matching, short word responses |
| 2 | Foundation | remember, understand, apply | picture prompts, sentence starters, short answers |
| 3 | Foundation | remember, understand, apply | short answers, sequencing, picture interpretation |
| 4 | Intermediate | remember, understand, apply | simple source use, short explanations, basic tables |
| 5 | Intermediate | remember, understand, apply, analyze | compare two items, explain cause, interpret simple graph |
| 6 | Intermediate | remember, understand, apply, analyze | structured responses, data/source interpretation, paragraphs |
| 7 | Senior | remember, understand, apply, analyze | source analysis, case/data response, paragraph answers |
| 8 | Senior | understand, apply, analyze, evaluate | multi-step source analysis, scenario application, short essays |
| 9 | Senior | understand, apply, analyze, evaluate | integrated source analysis, case evaluation, extended paragraph |
| 10 | FET | understand, apply, analyze, evaluate | source sets, data responses, structured essays, case analysis |
| 11 | FET | apply, analyze, evaluate, create | complex source sets, argument essays, methodology/investigation |
| 12 | FET Exit | apply, analyze, evaluate, create | exam source sets, synthesis, high-stakes equivalent opportunities |

## Sophia Bridge

Sophia's pedagogy stack already exposes the useful controls:

- Bloom target
- ZPD level
- scaffold intensity
- learner level
- assessment cycle
- examiner/source-librarian/methodologist/integrity-auditor offices

For HOMS, those controls become explicit exam constraints:

- Grade 1-3: close scaffold, low reading load, concrete prompts.
- Grade 4-6: guided scaffold, growing subject vocabulary, simple evidence use.
- Grade 7-9: moderate scaffold, source/case/data interpretation, justified reasoning.
- Grade 10-12: light scaffold to expert challenge, complex evidence, synthesis, moderation readiness.

## CAPS Bridge

Grade stratification must be anchored to CAPS before school-level generation.

The resolver should combine:

- grade profile
- subject profile
- CAPS manifest row
- CAPS matrix row
- extracted CAPS chunks
- human review boundary

The receipt for every school-level assessment should name the CAPS PDF path, source URL, phase, document hash, assessment blueprint, format signals, and extracted curriculum chunks used.

## Product Stratification

This turns HOMS into multiple education products:

- Primary School Assessment Builder: Grades 1-6.
- Senior Phase Assessment Builder: Grades 7-9.
- FET Exam Studio: Grades 10-12.
- University Exam Studio: module-level exams and memoranda.
- Marking Relief Pack: any grade, if a rubric/memo and learner work are supplied.

## Next Proofs

Do not claim full multi-grade readiness until each lane has one controlled artifact:

- Grade 3 Foundation sample.
- Grade 6 Intermediate sample.
- Grade 9 Senior sample.
- Grade 12 FET sample.
- One university History sample, already proven.

Each proof should include:

- input brief
- generated paper/task
- memo/rubric
- human review checklist
- grade-profile receipt
- subject-profile receipt
