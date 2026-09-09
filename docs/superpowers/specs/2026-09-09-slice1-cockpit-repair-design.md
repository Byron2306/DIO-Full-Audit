# Slice 1 Cockpit Repair Design

## Goal

Make the existing 68-product cloud cockpit truthful and usable before investor/commercial integration: repair artifact navigation, expose hydration failures, surface Atlas and the preserved prospect/company registry, and make Production Studio report real runtime readiness and production errors.

## Boundaries

- Preserve the verified 53 + 15 = 68 portfolio truth. Do not mutate the historical 53-row anchor.
- Preserve existing Atlas, prospect outreach and Wave 4 registry state. Do not create a replacement lead registry.
- No autonomous outreach, publication, spend, customer delivery or other external action is added.
- Keep all cockpit services localhost-only.
- Old-Debian/Arda recovery is explicitly deferred as `LEGACY_HOST_AUDIT_PENDING`; no missing privileged artifact is invented.
- Slice 1 does not merge the investor-market or Vesper-commercial branches.

## Findings driving the repair

1. `MS10ControlDeckHandler` already provides a governed `/api/business/artifact?path=...` gateway with approved-root containment.
2. The advanced Control Deck still constructs links with a stale `href()` helper that produces `file://` URLs or `../` paths, which is incompatible with the localhost HTTP cockpit and explains artifact/evidence 404s.
3. Advanced Control Deck refresh currently swallows `/api/control/state` fetch failures, allowing stale or blank UI to masquerade as live truth.
4. Production Studio correctly calls the live multichannel/NicheFoundry factory, but runtime provisioning is incomplete: ffmpeg/ffprobe are present while Node/npm and edge-tts are absent on the current Droplet. Gamma is an optional, operator-enabled visual candidate with a local-compositor fallback.
5. Atlas and prospect registry data are present in the deployed tree. The historical prospect registry includes hundreds of buyer targets/opportunities and explicit outreach gates.

## Design

### Artifact navigation

All internal file/folder links in the HTTP cockpit route through `/api/business/artifact`. HTTP(S) external links remain external. The artifact gateway continues to enforce approved-root containment and returns explicit `artifact_missing`/`artifact_path_blocked` errors.

### Hydration truth

The advanced cockpit gets a visible runtime-status banner. A failed state fetch is rendered as `LIVE_STATE_UNAVAILABLE`; stale baked-in state is labelled fallback rather than silently appearing current.

### Production runtime readiness

`/api/business/production/state` exposes a `runtime_readiness` object containing booleans/states only, never secret values. It reports ffmpeg, ffprobe, Node, npm, edge-tts Python package/CLI, Gamma optional-candidate state, local-compositor fallback, and legacy-host audit state. The Production Studio renders this readiness before the operator starts media work.

Production actions continue returning bounded server errors. The UI must display the exact error message in the result panel as well as a toast so a failed Create Marketing Pack action cannot look like a no-op.

### Atlas and prospect/company registry

Add a read-only `/api/business/atlas` projection derived from current Atlas assets plus the existing `build_dashboard_state().prospect_registry`. It exposes counts, top operator targets and source lineage, while retaining electronic-sales/outreach gates. The Business page surfaces a compact Atlas card/panel linking to this projection and the existing Prospects tab.

### Legacy-host boundary

Expose `legacy_host_audit: LEGACY_HOST_AUDIT_PENDING`. This is not an error state for cloud-safe Slice 1 and does not imply the old Debian filesystem has been audited.

## Acceptance criteria

- Internal artifact links no longer generate `file://` or unsupported relative paths.
- Artifact traversal outside approved roots remains blocked.
- Advanced cockpit visibly distinguishes live state from fallback/unavailable state.
- Production Studio displays runtime readiness and visible action failure output.
- Atlas + existing prospect/company registry are visible from BUSINESS without creating a second registry.
- 68-product portfolio truth remains unchanged.
- No external authority is created.
- Existing localhost service boundaries remain unchanged.
