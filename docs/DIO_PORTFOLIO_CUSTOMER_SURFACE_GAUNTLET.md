# DIO Portfolio Customer Surface Gauntlet

The Portfolio Customer Surface Gauntlet asks a deliberately different question from pipeline, ProductGrade and commercial validation:

> Did the real governed product route emit a substantial artifact that an intended buyer can inspect as the product's customer-facing output?

It does **not** create substitute mini-products, fabricate a product surface beside an organ, claim willingness to pay, or grant publication/release authority.

## Execution law

```text
existing governed product route
        ↓
actual execution outputs
        ↓
customer-surface inspector
        ↓
strongest buyer-facing candidates
        ↓
blind buyer review portal
        ↓
ENGINEERING_READY_NEEDS_BUYER_REVIEW / REFUSE
```

Canonical incarnations use the existing Vesper-first normal/messy/adversarial executor. Site Studio uses the actual Format Core customer-pack production build. The other newer Studios use their existing ProductGrade customer artifacts.

## Waves

- `alpha`: seven representative canonical incarnations plus Site Studio.
- `canonical53`: every canonical ATLAS incarnation.
- `full57`: all 53 canonical incarnations plus Site Studio, Professional Correspondence Studio, Finance Readiness Studio and Article & Publication Studio.

The contract lives in `config/portfolio_customer_surface_gauntlet.json`.

## Surface gate

The automated gate deliberately rejects obvious internal machinery such as receipts, manifests, requests, bindings, trace files, QA/log/error artifacts and JSON-only plumbing. It requires a nontrivial supported buyer-readable artifact and ranks candidates by customer format, product-family preference, content size and terminal-artifact affinity.

This is stronger than the old `human_artifact_gate`, but it remains weaker than a human buyer-quality verdict. A file can be substantial and professionally formatted while still being wrong, unhelpful or commercially weak.

## Blind buyer review

Every automatically eligible product is placed into `CUSTOMER_SURFACE_BUYER_REVIEW_QUEUE.json` with review dimensions such as:

- correctness and trust;
- buyer-job fidelity;
- edit burden;
- professional presentation;
- would use / buy;
- production blocker.

`CUSTOMER_SURFACE_REVIEW_PORTAL.html` presents copies of the strongest selected artifacts for visual review. Multi-file products such as Site Studio remain authoritative in their original customer package; the portal must not be treated as a substitute product build.

## Acceptance boundary

Only a `full57` run in which every selected surface reaches engineering readiness can emit:

`DIO_PORTFOLIO_CUSTOMER_SURFACES_READY_NEEDS_YOU`

Even then:

- `customer_grade_claimed = false`
- `commercial_validation = UNPROVED`
- `verified_payment = false`
- `human_visual_or_artifact_release = NEEDS_YOU`
- `automatic_publication = REFUSE`

The acceptance token means the portfolio is ready for blind customer-surface review. It does not mean customers have accepted, bought or paid for the products.

## Commands

Focused test:

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  -m pytest -q tests/test_portfolio_customer_surface_gauntlet.py
```

Alpha:

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  scripts/run_portfolio_customer_surface_gauntlet.py \
  --wave alpha
```

Full 57:

```bash
PYTHONNOUSERSITE=1 /home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  scripts/run_portfolio_customer_surface_gauntlet.py \
  --wave full57 \
  --online
```

Use `--strict` only when a non-zero exit is desired for any selected surface that is not engineering-ready. Without `--strict`, the harness completes the measurement, emits the refusal matrix and still builds the buyer-review portal.

Existing canonical and ProductGrade runs can be reused with `--reuse-canonical-root` and `--reuse-product-grade-root`.
