# Codex update boundary repairs, v1

This repair overlay is intended for the current DIO-Full-Audit working tree represented by the 2026-10-25 source-review archive. It does not revert or replace the larger Codex update.

## Repairs

- Correct Sophia's DOI regex so source URLs are parsed as DOI identifiers rather than literal backslash sequences.
- Require Sophia's reasoning endpoint to be a loopback HTTP URL before any request is sent.
- Restrict the sovereign runtime's Ollama URL to loopback and explicitly listed local-container aliases (`ollama`, `seraph-ollama`, and `host.docker.internal`). Arbitrary remote hosts and HTTPS endpoints are refused.
- Extend an already-imported `backend.services` package with the canonical Sophia services directory without replacing the pre-existing package object.
- Make the startup guard verify the filesystem UUID of the configured state and telemetry paths, not just the UUID mounted at `/data`.
- Add a separate `dio-vesper-public-api.service` on loopback port 8772 for the exact-origin, allowlisted `/api/vesper/web/*` protocol. The existing local/operator web-chat service on port 8770 remains separate.
- Render IncidentReadinessProof cards with the locally generated DIO house-style gradient until a product-specific, rights-verified asset pack is available, rather than reusing HOMS Command Hall artwork.
- Update/add regression tests for these boundaries and correct two stale test assumptions exposed during the targeted run.

## Test evidence

The targeted suite passed **103 tests** in the source-review environment. The HOMS local-provider suite was not included in that pass because the isolated environment lacks the `bson` dependency (`ModuleNotFoundError: bson`); that is an environment dependency gap, not a failure in these repair paths.

`systemd-analyze verify` parsed the new unit but could not verify the configured interpreter path because `/home/byron/DIO-Full-Audit/.venv/bin/python` does not exist in the isolated review container. Verify the actual path on the Lenovo before installing the unit.

## Deployment boundary

The public API unit is added but is **not enabled automatically**. Before enabling it, configure the approved reverse proxy or tunnel to forward the website's API origin to `127.0.0.1:8772`. The unit is loopback-only and does not itself expose a public listener. Do not point the website at port 8772 until the actual ingress mapping is confirmed.

The local endpoint allowlist is a configuration boundary, not independent network attestation. In particular, Docker aliases are trusted as local deployment names and still depend on the host's Docker/network configuration.

External send, publication, and customer release authority remain unchanged.
