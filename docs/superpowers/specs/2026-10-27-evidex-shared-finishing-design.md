# Evidex Shared Finishing Design

## Purpose

Evidex remains responsible for evidence ingestion, claim state, source custody, and the human review gate. DIO's shared product systems finish the generated pack without changing those decisions:

- Format Core renders a consistent customer review surface from Evidex's sealed review data.
- Production Studio packages that surface with the evidence pack and records the delivery boundary.
- NicheFoundry is available for approved brand and media material, but is not invoked for an evidence pack that has no approved brand material request.

## Required behavior

1. The finishing step consumes the generated pack directory, `SOURCE_REVIEW.json`, and the original intake.
2. The customer review surface repeats the pack's review state, human gate, and claim states. It must never promote an unverified claim.
3. Format Core renders the review surface with `dio_professional`, `editable_review`, English, and review mode. Its QA receipt must pass.
4. Production Studio writes one normalized finishing receipt that identifies every generated artifact by relative path, hash, and size.
5. The normalized receipt records external delivery, publication, spend, and authority as refused or false.
6. NicheFoundry is recorded as available for an approved brand request and unexecuted when no such request exists.
7. The existing evidence-pack ZIP is rebuilt atomically after finishing so the added artifacts and receipt are inside the archive.
8. A failed shared finishing step makes the outer Evidex job fail. The original custody files remain inspectable on disk.

## Boundaries

The embedded Evidex engine remains independently runnable. Shared finishing lives in DIO's product layer and is invoked by `scripts/run_evidex_jobs.py` after the engine succeeds. The first slice adds a review surface and receipt; it does not replace the existing executive summary, narrative, invoice, or evidence workbook.

NicheFoundry must not add decorative imagery or marketing claims to an audit pack by default. A later approved brand-material request can use the existing governed material registry and Format Core visual compositor.

