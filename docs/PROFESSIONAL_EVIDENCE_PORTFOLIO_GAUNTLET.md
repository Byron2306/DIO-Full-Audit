# DIO Professional Evidence Portfolio Gauntlet

## Purpose

This gauntlet asks a harder question than the existing controlled-fixture tests:

> Can each canonical DIO incarnation begin with a plausible literal customer packet and execute its complete bounded product pipeline into the professional artifact that product actually promises?

The answer is measured across all **53 canonical incarnations**. A test fixture or pre-built downstream receipt cannot satisfy this gauntlet.

## Core law

```text
literal customer-shaped packet
        ↓
source/hash validation
        ↓
product-specific typed projection
        ↓
actual product executor / controlled processor
        ↓
professional customer artifact
        ↓
proof / processing receipts
        ↓
blind examiner loaded only after execution
        ↓
PASS_FULL_PIPELINE | FAIL_EXECUTION | BLOCKED_FULL_PIPELINE_GAP
```

`halfway_fixture_counts_as_full_pipeline = false`.

A product may legitimately be a review or assurance product. For example, CyberAssurance's bounded product is an evidence-based cyber assurance review pack. Passing the product pipeline does **not** mean DIO performed cybersecurity operations, accepted cyber risk or certified an environment as secure.

## Literal professional corpus

`products/professional_evidence_corpus.py` defines exactly one baseline professional customer case for every canonical incarnation. The cases contain realistic buyer roles, organisations, concrete requests, contradictory or incomplete evidence and explicit prohibited outcomes.

Materialized cases use this structure:

```text
<case>/
  CUSTOMER_PACKET/
    CUSTOMER_REQUEST.md
    INTAKE.json
    SOURCES/
      ... real product-shaped inputs ...
    CUSTOMER_PACKET_MANIFEST.json
  EXAMINER/
    EXPECTED_FACTS.json
    PROHIBITED_OUTCOMES.json
    RUBRIC.json
  PROJECTION/
  EXECUTION/
  BLIND_REVIEW.json
  PROFESSIONAL_EVIDENCE_RECEIPT.json
```

The customer packet is SHA-256 bound. Selected cases receive additional product-shaped files, for example learner submissions and a marking rubric, a History examination source booklet, curriculum plan tables, accreditation staff records, accessibility issue logs and dossier record indexes.

The `EXAMINER` directory is a sibling of `CUSTOMER_PACKET`. Packet loading refuses examiner paths. The executor creates its source trace before any examiner file is loaded.

## Projection is allowed, fixtures are not

A real customer does not send DIO's internal schema. Therefore the gauntlet permits typed projection from customer bytes into an engine's request schema.

Projection must satisfy all of the following:

- use only the literal customer packet;
- retain packet and file hashes;
- create no new product capability or authority;
- use canonical DIO evidence vocabulary;
- never read examiner truth;
- never substitute a golden reference case;
- remain inspectable through a projection receipt.

## Full-pipeline semantics

A pass means the product's actual promised pipeline ran. It does not require a product to perform a real-world authority action that is outside the product contract.

Examples:

- **HOMS Assess:** learner submissions + rubric → HyMark batch → educator-review marking pack.
- **HOMS Exam:** customer scope + source booklet → complete paper + memorandum + blueprint + QA → moderator gate.
- **HOMS Learning Studio:** real learning request → learner/educator pack, visuals and validation → educator gate.
- **Sophia:** manuscript → native source/review pipeline → grounded review artifacts → human academic review.
- **VAMP:** customer evidence → packet-derived SQLite evidence source → VAMP snapshot → optional profile-specific proof review.
- **Evidex:** routed customer evidence → actual Evidex runtime → evidence pack.
- **TenderProof / GrantProof / PolicyProof / PermitProof:** customer source instrument → obligation engine → evidence pack.
- **ContractProof:** customer contract evidence → canonical ContractProof executor → integrity-verified proof pack → draft-only next-step communication.
- **Accreditation / RegOps:** packet-derived criteria or prerequisites → real controlled processors → review/readiness pack.
- **DossierOps:** customer records → actual Document Studio preparation → DossierOps assembly → hash-bound dossier bundle.
- **AI trust products:** customer system evidence → current AI Trust processor → trust/authority/drift dossier.
- **Document Studio:** customer document → native edit/localisation/publish preparation → human review boundary.
- **Accessible Publish:** source document + issue log → semantic accessible-publication preparation + QA; no certification claim.
- **Market Radar:** current public signal refresh → source-bound market state; demand remains unproved.
- **Opportunity Foundry:** fresh Market Radar run + capability constraints → ranked testable hypotheses.
- **Offer Lab:** capability/buyer hypothesis → bounded pilot offer; WTP remains unproved.
- **Campaign Lab:** bounded offer → channel copy + Gamma story + local Piper narration + rights-recorded music + vertical and widescreen video; publication and spend held.
- **Vesper Desk:** inbound customer request → route/intake preservation → draft-only next step; no send.

## Status meanings

### `PASS_FULL_PIPELINE`

The literal customer packet was bound, the product-specific pipeline completed, a professional terminal artifact was created, blind source-fidelity review passed, and authority/external-effect boundaries remained clean.

### `FAIL_EXECUTION`

The product has a full route but its real execution failed. Typical examples are missing local runtimes, provider failures, invalid schemas, failed quality gates, stale dependencies or an artifact/proof failure.

This is intentionally not converted into a synthetic pass.

### `BLOCKED_FULL_PIPELINE_GAP`

No full customer route exists for the incarnation. The current implementation aims to register all 53 routes, so this state should expose a regression or newly discovered product gap rather than a planned omission.

## Portfolio acceptance

Run:

```bash
PYTHONNOUSERSITE=1 .venv/bin/python scripts/run_professional_evidence_portfolio.py \
  --output state/professional_evidence/portfolio_v1 \
  --online \
  --strict
```

`--online` is required for a genuine current Market Radar / Opportunity Foundry run and may also support external source retrieval in configured products.

The portfolio acceptance token is:

```text
DIO_PROFESSIONAL_EVIDENCE_PORTFOLIO_53_VERIFIED
```

It is emitted only when:

- all 53 canonical incarnations were selected;
- all 53 returned `PASS_FULL_PIPELINE`;
- zero execution failures remain;
- zero full-pipeline gaps remain.

The master receipt is written to:

```text
state/professional_evidence/portfolio_v1/PROFESSIONAL_EVIDENCE_PORTFOLIO_RECEIPT.json
```

## Claim boundary

A 53/53 pass would prove that the configured DIO portfolio can process these literal professional baseline customer packets through the complete bounded product pipelines under test and produce their review-ready artifacts.

It would **not** by itself prove:

- market demand;
- willingness to pay;
- customer acceptance;
- professional certification;
- legal clearance;
- regulatory approval;
- safe real-world deployment;
- external publication or delivery;
- public-launch authority;
- repeatable commercial validation.

Those remain separate evidence ladders.
