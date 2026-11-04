# HOMS Exam item-quality review

This source-bound matrix is a blank educator moderation aid. Draft labels describe the current source record; they are not verified cognitive-demand judgments. The normalized field maps UK spelling `analyse` to `analyze` and maps the observed verb label `explain` to the candidate category `understand`; this verb mapping explicitly requires educator confirmation. Other unrecognized labels are marked `REVIEW_UNCLASSIFIED` and must be classified by the educator.

For each question, read the complete examination stimulus, question, CAPS source pages, memo and allocated marks. Confirm or replace the cognitive-demand label; describe the reasoning students must show; check grade/term fit, CAPS alignment, memo coverage, mark allocation and language accessibility. Record any required revision and a disposition.

Use `APPROVE_FOR_MODERATION`, `REVISE`, or `UNRESOLVED` only after review. Add a concise rationale, reviewer identity and date.

Validate a completed copy with `python scripts/validate_homs_exam_item_quality_review.py --run-dir <grade-package-directory> --csv <completed-review.csv>`. The result may say READY_FOR_INDEPENDENT_MODERATION, but it never issues moderation or classroom-release approval.

This worksheet does not certify curriculum coverage or authorize classroom release.
