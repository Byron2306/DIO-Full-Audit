# HOMS Selling Kit

Updated: 2026-08-07

## Positioning

HOMS has two academic ops offers:

```text
1. HOMS Marking Relief Pack
2. HyMark Exam Studio
```

HOMS Marking Relief Pack turns a batch, rubric, memo, and marksheet into structured marking support.

HyMark Exam Studio turns an exam brief into a first opportunity paper, second opportunity paper, and memoranda.

Neither is sold as replacing the educator. They are sold as assessment workload relief while keeping the academic in control.

## Primary Buyer

Start with people who already feel assessment workload pain:

- Lecturers with marking backlogs.
- Teachers during assessment crunch.
- Tutors and markers working from rubrics.
- Academic departments coordinating first-pass marking.
- Course administrators who need marksheet collation.
- Lecturers setting exam papers under deadline pressure.
- History teachers who need paper drafts, source questions, and memoranda.
- Programme coordinators creating controlled practice assessments.

## Offer 1

### Marking Relief Pilot

```text
Send one fake, redacted, or non-sensitive batch with rubric/memo.
Get back a HOMS marking request pack for draft feedback, rubric mapping, marks CSV support, and lecturer review.
```

Suggested pilot price:

```text
R350-R750 for a tiny fake batch
R950-R1,800 for a normal pilot batch
R2,500-R6,500 for urgent or messy deadline rescue
```

## Offer 2

### Exam Paper + Memo Pilot

```text
Send the module, topics, exam structure, and any institutional rules.
Get back a first opportunity exam paper, second opportunity exam paper, and memoranda for human review.
```

Suggested pilot price:

```text
R750-R1,500 for one small test / practice paper
R1,800-R3,500 for a full exam paper with memo
R3,500-R7,500 for first + second opportunity papers with memoranda and review checklist
```

## Proof Assets

Landing page:

```text
sites/homs/index.html
```

Preview MP4:

```text
/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-homs-marking-relief-pack-send-the-batch-rubric-memo-and-marksheet-get-structured-marking-s-aec7fc9b/free_preview.mp4
```

Visual receipt:

```text
/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-homs-marking-relief-pack-send-the-batch-rubric-memo-and-marksheet-get-structured-marking-s-aec7fc9b/HOMS_VISUAL_ASSET_RECEIPT.json
```

Commercial ops receipt:

```text
campaigns/phase3/homs/commercial_ops/HOMS_COMMERCIAL_OPS_RECEIPT.json
```

HyMark exam builder route:

```text
docs/HYMARK_EXAM_BUILDER_ROUTE.md
```

## Outlook-First CTA

Subject marker:

```text
HOMS MARKING RELIEF REQUEST
```

Use this in direct messages and posts:

```text
Reply with: HOMS MARKING RELIEF REQUEST
```

## Outreach Copy

```text
Hi [Name],

I am testing a small marking relief workflow for lecturers, teachers, and markers.

The idea is simple: send one fake, redacted, or non-sensitive batch with the rubric/memo and marksheet, and I return a structured marking support pack.

It can prepare draft feedback, rubric mapping, marks CSV support, and a lecturer review summary.

It does not replace your judgement. Educator approval stays final.

Would you be open to testing it on a tiny fake or non-sensitive batch?
```

## Exam Studio Outreach Copy

```text
Hi [Name],

I am testing a small exam setup workflow for History lecturers and teachers.

You send the module details, topics, paper structure, and any institutional rules.

I return a review-ready exam pack: first opportunity paper, second opportunity paper, and memoranda.

It is not final without your academic review. The value is that the structure, source questions, essay matrix, and marking guide are already drafted.

Would you be open to testing it on a non-sensitive practice paper brief?
```

## Fulfilment Loop

```text
lead replies
-> Outlook bot triages the reply
-> AutoRelease routes it as HOMS
-> HOMS adapter prepares marking request pack
-> operator checks rubric/memo/batch readiness
-> collect fake/redacted/non-sensitive sample
-> run deeper HOMS backend only after scope is clear
-> educator reviews before any final marks or feedback
```

## Exam Studio Fulfilment Loop

```text
lead replies
-> Outlook bot triages as exam setup
-> collect module, outcomes, topics, paper structure, constraints
-> run HyMark Exam Builder
-> package first paper, second paper, and memoranda
-> human academic reviews source authenticity, level, marks, and policy fit
-> deliver review pack
```

## Verified Dry Run

Verified on 2026-08-07:

```text
campaigns/phase3/homs/commercial_ops/outlook_first/dummy_outlook_homs_intake.json
-> KnowEdge Outlook Triage 2.0.0
-> campaigns/phase3/homs/commercial_ops/outlook_first/outlook_bot_output/triage_summary.csv
-> runs/homs_outlook_bot_csv_dry_run
-> deliverables/homs_outlook_bot_csv_dry_run/homs/homs-09d7b6a2e7463661bc81
```

Result:

```text
1 Outlook-style lead processed by the Outlook bot
triage_summary.csv routed to HOMS
route confidence 0.95
HOMS marking request pack generated
```

## Boundary

```text
HOMS prepares marking support.
Educator approval remains required for final marks and feedback.
Use fake, redacted, or non-sensitive pilots first.

HyMark Exam Studio prepares assessment drafts.
Human subject expert review remains required before any paper is used with learners or students.
```
