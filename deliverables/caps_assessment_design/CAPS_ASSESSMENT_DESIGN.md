# CAPS Assessment Design Profiles

Created: 2026-08-07T20:57:02+00:00

This layer converts canonical subject/phase profiles into assessment-design rules: valid assessment forms, mark weightings, render shells, and validation constraints. It sits between CAPS evidence and generation.

## Summary

- Profiles analysed: 104
- Render shells: structured_case_paper=8, language_integrated_task=46, investigation_task_sheet=10, performance_task_sheet=9, project_task_sheet=6, source_response_paper=4, question_paper=6, source_essay_paper=1, activity_sheet=14
- Confidence: medium=101, high=3

## High-Confidence Examples

### fet.dance_studies

- Subject: Dance Studies
- Shell: `performance_task_sheet`
- Forms: theory_test, practical_test, practical_exam, theory_exam, research_assignment, performance_assessment_task
- Weightings: sba=25%, performance_assessment_tasks=25%, final_examinations=50%
- Cognitive distribution: lower_order_knowledge=30%, middle_order_application=50%, higher_order_analysis_evaluation_creativity=20%

### intermediate.mathematics

- Subject: Mathematics
- Shell: `question_paper`
- Forms: test, examination, project, assignment, investigation
- Weightings: school_based_assessment=75%, end_of_year_examination=25%
- Cognitive distribution: knowledge=25%, routine_procedures=45%, complex_procedures=20%, problem_solving=10%

### foundation.mathematics

- Subject: Mathematics
- Shell: `activity_sheet`
- Forms: teacher_observation, oral_prompt, concrete_activity, short_recorded_response
- Weightings: profile-specific / educator-set
- Cognitive distribution: observable_activity=50%, oral_or_practical_response=30%, short_recorded_response=20%

### intermediate.coding_and_robotics

- Subject: Coding and Robotics
- Shell: `project_task_sheet`
- Forms: practical_task, design_project, structured_theory, oral_explanation, portfolio_evidence
- Weightings: profile-specific / educator-set
- Cognitive distribution: design_or_practical=40%, technical_knowledge=30%, diagrams_or_specifications=20%, reflection_or_safety=10%

## Gate Rule

PDF keyword evidence may suggest possible signals, but learner-facing packs must follow this assessment-design shell before rendering. Practical performance tasks are rendered as assessment instruments, not answer-line question papers.
