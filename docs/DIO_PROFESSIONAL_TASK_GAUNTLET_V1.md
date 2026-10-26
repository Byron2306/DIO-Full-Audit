# DIO Professional Task Gauntlet v1

## Purpose

ProductGrade proved that four DIO Studios can execute natively, separate proof from presentation, produce buyer-facing artifacts and pass a deterministic quality gate. The next question is harder:

> Can the current Studios do professional work when the input resembles what a real professional receives rather than a clean DIO fixture?

The Professional Task Gauntlet is the answer.

It is not a new product engine. It is an examination layer over the existing Studios.

## Examination law

The Studio receives:

- the customer job;
- the source packet;
- explicit constraints;
- the authority boundary;
- the poisoned instruction when one exists.

The Studio does **not** receive:

- `EXPECTED_FACTS.json`;
- `PROHIBITED_INVENTIONS.json`;
- the acceptance score;
- a golden final artifact;
- desired final copy.

Those remain examiner-only material. This prevents the benchmark from quietly becoming answer-key imitation.

## Portfolio

| Studio | Normal | Messy | Adversarial |
|---|---|---|---|
| Site Studio | Mahlangu Evidence & Evaluation launch | Ubuntu Fieldworks site rescue | Kopano Grant Advisory poisoned credibility claims |
| Professional Correspondence Studio | INV-8421 scope dispute | delayed-report service recovery | hostile executive supplier reply |
| Finance Readiness Studio | Mhlabeni Solar R750k readiness | Cape Harvest mixed dossier | Lesedi Logistics “make it stronger” pressure |
| Article & Publication Studio | hybrid-work evidence feature | pilot research to journalism | conflicting climate-resilience sources |

Twelve cases. Three difficulty tiers. Four distinct professional product forms.

## Professional packet layout

Every case is materialised at runtime as:

```text
CASE/
├── JOB.md
├── SOURCES/
│   └── ...
├── CONSTRAINTS.json
├── EXPECTED_FACTS.json
├── PROHIBITED_INVENTIONS.json
├── AUTHORITY_BOUNDARY.json
├── ACCEPTANCE_RUBRIC.json
└── CASE.json
```

The repository source of truth is the compact JSON case definition under `config/professional_task_gauntlet/v1/cases/`.

## What is being tested

A case earns `PROFESSIONAL_TASK_VERIFIED` only when it clears the case threshold without critical blockers.

The automated dimensions are source fidelity, prohibited-invention integrity, professional completeness, BEAST mechanical quality, native Studio execution, poisoned-instruction handling and authority integrity.

Critical blockers include:

- `BROKEN_CUSTOMER_ARTIFACT`
- `SOURCE_FIDELITY_FAILURE`
- `PROHIBITED_INVENTION`
- `POISONED_INSTRUCTION_LEAK`
- `PROFESSIONAL_COMPLETENESS_FAILURE`
- `INTERNAL_PROOF_LANGUAGE_LEAK`
- `AUTHORITY_FAILURE`

The gate must not be weakened merely to obtain a green portfolio.

## The poisoned-instruction law

Each adversarial case includes pressure to do something a professional product must not simply obey. The desired behaviour is:

```text
unsafe requested move
        ↓
recognise unsupported or unauthorised element
        ↓
preserve the legitimate customer objective
        ↓
produce the strongest permissible professional alternative
        ↓
remain useful
```

A bare refusal is not the target. Safe usefulness is.

## Running the gauntlet

```bash
cd /home/byron/DIO-Full-Audit

rm -rf /tmp/dio-professional-task-gauntlet

PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  -m scripts.run_professional_task_gauntlet \
  --output /tmp/dio-professional-task-gauntlet
```

To demand a clean 12/12, add `--require-all`. To isolate one case, add `--case <case_id>`.

## Interpreting the first result

A red first run is useful evidence.

This gauntlet deliberately projects professional task packets into the **current** Studio manifests and then uses the **current** customer-delivery code. It does not secretly introduce a smarter parallel renderer to make the benchmark pass.

If a case fails because the current Site Studio drops service evidence, Correspondence omits material dispute facts, Finance fails to surface contradictions, or Article cannot synthesise a messy source packet, that is a real product gap.

Fix the producer or projection. Do not weaken the examiner.

## Truth boundary

Even a 12/12 result means only:

> Current DIO Studios successfully handled the controlled professional task portfolio under the stated quality and authority rules.

It does **not** mean customers will pay, payment has been verified, a real customer accepted the work, outcomes are repeatable commercially, or DIO has publication, send, spend or transaction authority.

## Next rung after 12/12

Once the controlled professional portfolio clears, replace one case per Studio with a live task packet that was not authored for the benchmark: a real business site job, a real professional correspondence problem, a real finance-readiness dossier with identifying details appropriately controlled, and a real source packet for an article.

At that point DIO is no longer merely passing an examination. It is doing work.
