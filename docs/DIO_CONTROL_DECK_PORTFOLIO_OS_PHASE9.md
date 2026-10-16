# DIO Phase 9 — GoldenEye Control Deck Portfolio OS

Phase 9 turns the recovered GoldenEye interface into the operator-facing projection of the canonical product factory.

GoldenEye is not a new runtime, registry, authority plane or product. It reads canonical Phase 0–8 state and produces one deterministic portfolio snapshot across the six Atlas suites and the currently proven reference incarnations.

## Recovered GoldenEye lineage

The newer UI was found on `dio-c7-goldeneye-control-deck` at commit `b500c0a57e3ecb19f5cab187c2cafeb6e73f9081`. That branch is intentionally not merged wholesale because it diverged before the canonical Phase 0–8 product-factory spine.

Phase 9 selectively preserves its strongest contracts:

- operator-first `Needs Me` presentation;
- `MEMORY ≠ PERMISSION`;
- truthful absence instead of inferred success;
- advanced organ machinery remains secondary;
- localhost-only operation.

## Canonical projection

`products/control_deck.py` reads:

- the six-suite registry;
- the canonical maturity vocabulary;
- canonical product manifests;
- Product Compiler output;
- the consolidated Phase 8 META runtime receipt.

It emits `dio.control_deck.portfolio_snapshot.v1`, containing:

- suite registration coverage;
- product maturity and operational flags;
- compiler, composition and runtime fingerprints;
- META execution order;
- explicit human-attention items;
- commercial and authority truth boundaries.

## Constitutional boundary

The Control Deck is a projection plane only.

It cannot:

- create human authority or a capability lease;
- create or invoke a product executor;
- change a product's maturity;
- infer customer validation, revenue proof or product-market fit;
- authorize external release;
- create external effects.

Every Phase 9 `Needs Me` record describes the permitted human action but cannot perform that action.

## GoldenEye surface

The browser surface is `dashboard/goldeneye-portfolio.html`. It consumes the Phase 9 portfolio at `GET /api/control-deck/portfolio` and the separate commercial projection at `GET /api/commercial-truth`. The dedicated server rejects POST and non-localhost binding.

Generate both read-only projections from one matching Phase 9 snapshot:

```bash
python scripts/refresh_goldeneye_projections.py
```

The persistent user service is `deploy/systemd/dio-goldeneye-portfolio.service`. Install and start it with:

```bash
systemctl --user link "$PWD/deploy/systemd/dio-goldeneye-portfolio.service"
systemctl --user daemon-reload
systemctl --user enable --now dio-goldeneye-portfolio.service
```

It serves only on `127.0.0.1:8766`; open `http://127.0.0.1:8766/`. Refresh both snapshots after changing their source registries; the running service reads the refreshed files on the next request.

## Acceptance

```bash
python -m pytest -q tests/test_control_deck_phase9.py
python scripts/run_control_deck_phase9.py --output /tmp/dio-phase9-control-deck
```

The phase is accepted only when the final token is:

```text
DIO_CONTROL_DECK_PORTFOLIO_OS_READY
```
