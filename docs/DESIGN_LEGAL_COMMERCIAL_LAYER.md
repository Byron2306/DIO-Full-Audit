# DIO Design Studio + Legal Operations Commercial Layer

## Why this exists

DIO already has the organs required to create market-facing design work and bounded legal-operations/readiness work. The missing layer was commercial composition: a customer should be able to buy an understandable outcome without DIO pretending that every outcome needs a new engine.

This layer therefore adds six structural commercial compositions and **no new executors**.

## The six initial compositions

| Product | Family | Launch-price hypothesis | Primary intake |
|---|---|---:|---|
| DIO Site Studio | Design Studio | from R6,900 | Document Studio |
| DIO Launch Studio | Design Studio | from R12,900 | Document Studio |
| DIO Report & Pitch Studio | Design Studio | from R3,900 | Document Studio |
| DIO POPIA Readiness | Legal Operations | from R7,900 | Evidex |
| DIO Corporate Readiness | Legal Operations | from R4,900 | Evidex |
| DIO Contract Desk | Legal Operations | from R7,900 | Evidex |

Prices are public-launch hypotheses only. They are not willingness-to-pay evidence, revenue proof or ROI claims.

## Composition law

```text
customer outcome
    ↓
commercial composition
    ↓
existing DIO organs / proved routes
    ↓
review-ready artifacts and receipts
    ↓
human authority gates
    ↓
external effect only when separately authorised
```

The composition registry may reference an existing direct product route, existing product-class route, internal capability, semantic layer or Presence owner. It may not declare an executor.

### Design Studio

**Site Studio** composes NicheFoundry, Document Studio, LINGUA and Vesper.

**Launch Studio** composes Site Studio with NicheFoundry, Market Command, LINGUA and Vesper.

**Report & Pitch Studio** composes Document Studio, NicheFoundry and LINGUA.

The design family may create held/reviewable creative packages. Completion of design work does not create public release, deployment, publication, send or spend authority.

### Legal Operations

Legalis is the **governance owner**, not a fabricated executor.

**POPIA Readiness** composes DIO RegOps, PolicyProof, Evidex, Document Studio and LINGUA under a Legalis legal-operations boundary.

**Corporate Readiness** composes DIO RegOps, the Obligation Engine, Evidex, Document Studio and Vesper under Legalis.

**Contract Desk** composes ContractProof, the Obligation Engine, Evidex, Document Studio and Vesper under Legalis.

These products organise requirements, evidence, gaps, obligations, deadlines, draft/review artifacts and professional handoff. They do not create legal advice, a legal opinion, legal representation, filing authority, risk acceptance or compliance certification.

Where legal interpretation is required, the workflow must stop at a human/professional review gate.

## LINGUA boundary

Design and legal-operations outputs now have dedicated LINGUA artifact routes.

Design invariants include:

- source meaning survives visual rendering;
- brand rendering does not create claim authority;
- design completion does not create public release authority;
- accessibility/localisation remains reviewable.

Legal-operations invariants include:

- linguistic rendering does not create legal interpretation;
- translation or document assembly does not create filing authority;
- requirement mapping does not create legal advice;
- professional-review gates survive translation and formatting;
- jurisdiction and authority profile remain bound to the artifact.

## Maturity truth

Current state after this layer:

```text
commercial composition defined           YES
component bindings structurally checked  YES
new executor created                     NO
new execution proof created              NO
controlled customer pilot proved         NO
public launch authority created          NO
willingness to pay validated              NO
revenue proven                            NO
```

This is deliberate.

The next proof gate is one bounded controlled case per composition, using the existing organs and recording the actual route receipts. Only then may a composition be considered for controlled-pilot launch.

## Build

```bash
python3 scripts/build_design_legal_commercial_catalog.py \
  --output state/design_legal_commercial_catalog
```

Expected outputs:

- `DESIGN_LEGAL_COMMERCIAL_CATALOG.json`
- `NICHEFOUNDRY_COMPOSITION_BRIEFS.json`
- `VALIDATION_RECEIPT.json`

The NicheFoundry briefs are held by default. Publication and spend remain disabled.
