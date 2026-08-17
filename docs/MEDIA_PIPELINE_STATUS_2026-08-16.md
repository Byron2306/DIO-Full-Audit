# DIO Media Pipeline Status - 2026-08-16

## Corrected Finding

The NicheFoundry short-form media engine is present and bridged into DIO, but the previous state model used `ready` too broadly.

The active bridge now separates four states:

- `blocked`: request, engine prerequisite or source input is missing.
- `render_ready`: inputs and local prerequisites are valid, but this run did not create a reel artifact.
- `ready`: the reel file exists **and** the native `NICHEFOUNDRY_REEL_RECEIPT.json` exists after rendering.
- `failed`: rendering failed or returned without the required artifact/receipt pair.

## Why This Matters

A planned output path is not an output.

A skipped render is not a rendered reel.

A renderer returning success without leaving inspectable artifacts is not execution proof.

The media bridge therefore records planned paths under `planned_outputs` and only records `outputs.vertical_reel` after artifact verification.

## Campaign Batch Truth

The product-class campaign batch wrapper also corrects two optimistic states from the legacy generator:

- a missing reel can no longer remain `ready` merely because a request exists;
- `youtube_candidate_ready` is set only when a concrete candidate is present in the video-candidate registry.

`--no-youtube` now bootstraps an empty registry on a clean install instead of crashing when the registry file is absent.

## Governance

Publication and spend remain held independently of render state.

A verified reel is only media execution proof. It does not imply content approval, campaign release, spend authority, private upload authority, or public YouTube release.

## Historical Run Note

Earlier receipts that used the old `ready` semantics should be treated as historical and revalidated under the corrected artifact-backed contract before they are used as evidence.

## Long-Form Boundary

Premium/long-form output remains a separate lane. A campaign-family request does not become a YouTube candidate until the episode/candidate artifacts actually exist and pass their own review gates.
