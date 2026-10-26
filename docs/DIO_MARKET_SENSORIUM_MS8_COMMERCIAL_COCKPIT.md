# DIO Market Sensorium MS-8 — Commercial Cockpit Reconstruction

## Status

IMPLEMENTED — live repository verification pending.

Target acceptance token:

`DIO_MARKET_SENSORIUM_COMMERCIAL_COCKPIT_VERIFIED`

## Objective

MS-8 reconstructs Market Sensorium state as one operator-readable, read-only epistemic surface. It does not create new market truth and it does not create execution authority.

The cockpit projects the settled state of MS-1 through MS-7 into these sections:

1. phase capability chain,
2. commercial-time observation state,
3. current ranked priority surface,
4. dynamic rank movements and causal explanations,
5. active Hivenance rival-hypothesis sets,
6. competitive offer and advertised-price observations,
7. market habitats and permission state,
8. learned discovery queries,
9. explicit authority boundary.

## Truth classes

The cockpit preserves semantic separation:

- `VERIFIED_CAPABILITY` means a system capability passed its acceptance gate.
- `ACTIVE_OBSERVATION` means a governed observation process is live but its stronger temporal gate has not necessarily matured.
- `RANKED_PRIORITY_MODEL_OUTPUT` is prioritisation only. It is not a best-target claim.
- `OBSERVED_RANK_TRANSITION` is a persisted change in the rank field with lineage.
- `UNPROVED_HYPOTHESIS` remains a research explanation, even when selected by Hivenance.
- `OBSERVED_ADVERTISED_OFFER` does not prove demand, realised price, willingness to pay, revenue or commercial success.
- `OBSERVED_MARKET_HABITAT` does not imply membership, consent, posting authority, DM authority or participant inference.
- `PROPOSED_DISCOVERY_QUERY` does not imply execution, truth, lead status or demand.
- `AUTHORITY_BOUNDARY` is displayed independently from intelligence state.

## Hard laws

The UI is downstream of the ledgers. It may not improve, reinterpret or promote their truth state.

`priority != best target`

`hypothesis != fact`

`advertised offer != demand`

`advertised price != market price`

`advertised price != realised price`

`free entry != willingness to pay`

`public visibility != consent`

`public visibility != membership`

`habitat != buyer`

`learned query != market truth`

`search hit != lead`

`silence != rejection`

`recommendation != execution authority`

## Artifacts

The builder writes:

- `state/market_sensorium/COMMERCIAL_COCKPIT.json`
- `state/market_sensorium/COMMERCIAL_COCKPIT.html`
- `state/market_sensorium/MARKET_SENSORIUM_MS8_RECEIPT.json` through the MS-8 runner.

The HTML artifact is intentionally self-contained and read-only. It can be opened locally without a service process.

## Verification gate

Strong acceptance requires:

- the persisted MS-7 verified token,
- MS-2 commercial-time state active or strongly verified,
- non-empty ranked targets,
- non-empty real rank movements,
- non-empty Hivenance hypothesis sets,
- non-empty competitive offers,
- non-empty market habitats,
- non-empty learned queries,
- at least one visible rank-transition to hypothesis-set lineage link,
- zero truth-class violations,
- both JSON and HTML operator artifacts,
- no best-target claim,
- no demand claim,
- no willingness-to-pay claim,
- no commercial-success claim,
- no customer claim,
- no authority creation,
- no external effects.

A cockpit that collapses an `UNPROVED` hypothesis into fact or converts observed offer/price/habitat evidence into commercial truth must REFUSE rather than render a misleading operator state.

## Boundary

MS-8 proves that DIO can present its commercial intelligence state coherently while preserving truth and authority boundaries. It does not prove market demand, willingness to pay, commercial success, customer acceptance or profitability.
