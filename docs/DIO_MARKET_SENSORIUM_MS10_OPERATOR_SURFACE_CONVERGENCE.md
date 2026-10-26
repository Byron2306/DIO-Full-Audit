# DIO Market Sensorium MS-10 — Operator Surface Convergence

**Implementation state:** `DIO_MARKET_SENSORIUM_OPERATOR_SURFACE_CONVERGENCE_IMPLEMENTED`

**Strong acceptance token:** `DIO_MARKET_SENSORIUM_OPERATOR_SURFACE_CONVERGENCE_VERIFIED`

MS-10 closes the operator-surface lag left after MS-1 through MS-9. The Market Sensorium had become materially more capable than the interfaces used to observe and operate DIO. MS-10 converges Control Deck, Market Command and GoldenEye onto the same canonical Sensorium truth plane while preserving their existing operational roles.

## Surfaces

```text
Control Deck      http://127.0.0.1:8765/
Market Command    http://127.0.0.1:8770/
GoldenEye         http://127.0.0.1:8766/
```

All three surfaces consume:

```text
state/market_sensorium/COMMERCIAL_COCKPIT.json
state/market_sensorium/MARKET_SENSORIUM_MS9_RECEIPT.json
```

No surface is permitted to create an independent competing Market Sensorium truth engine.

## Visible Sensorium capabilities

Each converged operator entrance must visibly represent:

- phase-chain state;
- commercial time and mailbox coverage truth;
- ranked priority state without claiming a best target;
- observed rank movements and their lineage;
- Hivenance Commercial Phoenix hypotheses, still `UNPROVED`;
- competitive advertised offers and price observations without demand/WTP promotion;
- market habitats and explicit permission boundaries;
- evidence-adaptive learned discovery queries;
- MS-9 bounded autonomic-soak truth;
- the Sensorium authority boundary.

## Existing operator capability preservation

MS-10 is a convergence layer, not a rewrite of existing action authority.

Control Deck continues to subclass and expose the existing `ControlDeckHandler`, preserving its governed action APIs.

Market Command continues to subclass and expose the existing Market Command `Handler`, preserving Wave-2 campaign/content/settlement operations.

GoldenEye retires the stale service rooted at `/home/byron/DIO-Product-Factory`. Its MS-10 surface is now served from `/home/byron/DIO-Full-Audit`; portfolio state comes from the current Control Deck state API and Sensorium intelligence comes from the canonical MS-8/MS-9 artifacts.

## Truth laws

```text
priority rank        != best target
hypothesis           != fact
advertised offer     != demand
advertised price     != realised price or WTP
public habitat       != consent or posting/DM authority
learned query        != market truth or lead
NO_REPLY_OBSERVED    != rejection or follow-up authority
MS-9 soak            != long-duration endurance or commercial validation
UI projection        != execution authority
```

## Strong gate

MS-10 verifies only when:

1. MS-9 is verified;
2. all three operator surfaces exist;
3. all three are bound to the same canonical MS-8 and MS-9 artifacts;
4. all service files point to `/home/byron/DIO-Full-Audit` and no longer reference the stale product-factory repo;
5. all service bindings remain localhost-only;
6. the complete Sensorium feature set is visible;
7. Control Deck and Market Command existing action planes are preserved;
8. GoldenEye portfolio projection is current-repo bound;
9. no duplicate Sensorium truth engine is introduced;
10. no surface claims market demand, WTP, commercial success, best-target truth or new authority.

## Runner

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_ms10.py
```

Receipt:

```text
state/market_sensorium/MARKET_SENSORIUM_MS10_RECEIPT.json
```
