# HOMS Learning Studio Golden Proof

## Product

HOMS Learning Studio turns one defined curriculum topic into a connected learning sequence:

```text
CAPS source
-> concept guide
-> worked examples and visuals
-> practical or topic-appropriate activity
-> scaffolded worksheet
-> mini-assessment
-> memoranda
-> optional captioned video lesson
-> educator approval
```

The learner is the end user. The initial buyer is a school, tutor, parent, subject department, extra-class provider or education publisher. Marketing is directed to adults and institutions, never directly to minors.

## Golden Review Candidate

- Subject: Physical Sciences
- Grade: 10
- Term: 3
- Topic: Motion in One Dimension
- Curriculum source: local South African CAPS Physical Sciences source
- Worksheet: 40 marks
- Mini-assessment: 30 marks
- Video: 2:06, 1920x1080, captioned, Edge narration
- Music: Warm Sunset by MusicLFiles, CC BY 4.0, attribution and rights receipt included

Proof folder:

`deliverables/homs_learning_studio/grade_10_physical_sciences_term_3_motion`

Local review route:

`http://127.0.0.1:8765/sites/homs/learning-studio/`

The campaign route preserves incoming attribution, selects the Learning Studio proof, and preselects the `learning_companion` intake offer.

The release ZIP contains editable DOCX files, PDFs, visual assets, the video lesson, captions, curriculum evidence, validation, rights provenance and operator receipts.

## Passed Gates

- CAPS term and topic evidence found locally
- One curriculum spine shared across guide, practice and assessment
- Worksheet and assessment mark totals validated
- Memoranda present
- Meaningful diagrams embedded
- Printable practical graph grid present
- PDF pages visually audited
- Full-HD video contains H.264 video and stereo AAC audio
- Educational static render mode preserves graph labels
- Captions and music attribution included
- Public HOMS intake supports `learning_companion`
- Website proof video and learner-guide preview linked
- DIO campaign retains registry lineage and exposes the golden proof update

## Remaining Gate

This is not yet an externally approved or commercially proven product. A Physical Sciences subject expert must recalculate answers, review CAPS pacing, inspect the practical, approve narration and confirm classroom suitability. The first paid pilot must record manual time, revisions, delivery, revenue and effective hourly return.

## Rebuild

```bash
./.venv/bin/python scripts/build_homs_learning_pack.py
./.venv/bin/python scripts/build_free_media_preview.py \
  --episode /home/byron/Downloads/NicheFoundry_Phase11/episodes/homs-learning-grade10-motion-one-dimension \
  --provider auto --reuse-audio --motion-mode static_educational \
  --transition 0.55 --width 1920 --height 1080 --crf 22 \
  --output HOMS_G10_T3_MOTION_VIDEO_LESSON.mp4 \
  --receipt HOMS_LEARNING_VIDEO_RECEIPT.json
./.venv/bin/python scripts/finalize_homs_learning_video.py
```
