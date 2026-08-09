# Architecture Index

This is the authoritative runtime map for the governed control plane. When multiple similarly named files exist, this document identifies which one is canonical for backend runtime authority and which ones are adapters, platform variants, or compatibility surfaces.

## Canonical Runtime Paths

### World State And Governance

- World model authority:
  `backend/services/world_model.py`
- World manifold authority:
  `backend/services/world_manifold.py`
- Governance epoch authority:
  `backend/services/governance_epoch.py`
- Decision transition authority:
  `backend/services/governance_authority.py`
- Approved-decision executor:
  `backend/services/governance_executor.py`
- High-impact outbound gate:
  `backend/services/outbound_gate.py`
- Notation/token authority:
  `backend/services/notation_token.py`

Canonical runtime path:

`intent -> world_events.emit_world_event -> triune_orchestrator.handle_world_change -> policy/governance decision -> outbound_gate.gate_action -> governance_authority.approve/deny -> governance_executor.process_approved_decisions -> audit/world feedback`

### Deception And Harmonic Control

- Deception authorization authority:
  `backend/services/deception_authority.py`
- Harmonic signal synthesis:
  `backend/services/harmonic_signal_context.py`
- Harmonic inference:
  `backend/services/harmonic_inference.py`
- Harmonic policy / obligations:
  `backend/services/harmonic_policy.py`
- Harmonic engine:
  `backend/services/harmonic_engine.py`

Canonical runtime path:

`deception_authority.create_case -> harmonic shaping / corroboration guard -> outbound_gate / governance artifacts -> governance_authority transitions -> governance_executor runtime outcome -> harmonic feedback`

### Triune Reasoning

- Triune orchestration authority:
  `backend/services/triune_orchestrator.py`
- Metatron strategic reasoning:
  `backend/triune/metatron.py`
- Michael response ranking:
  `backend/triune/michael.py`
- Loki challenge/dissent:
  `backend/triune/loki.py`

Canonical runtime path:

`world event -> bounded world snapshot -> triune_orchestrator.handle_world_change -> schema route + verdict bundle -> downstream governance / response layers`

### MCP And Tool Execution

- MCP server authority:
  `backend/services/mcp_server.py`
- Governed dispatch authority:
  `backend/services/governed_dispatch.py`
- Runtime tool execution under governance:
  `backend/services/governance_executor.py`
- Governance context contract:
  `backend/services/governance_context.py`

Canonical runtime path:

`high-impact tool intent -> outbound_gate -> governance approval -> governance_executor tool_execution -> canonical governance context enforcement -> runtime tool handler -> audit`

### Network Truth / VNS

- VNS authority:
  `backend/services/vns.py`
- VNS alerting sidecar:
  `backend/services/vns_alerts.py`

Canonical runtime path:

`network flow / DNS ingest -> vns record_* -> durable VNS persistence + reconciliation snapshot -> harmonic / governance / world feedback consumers`

## Non-Canonical But Legitimate Paths

These files are real and important, but they are not the primary backend authority path for the governed runtime:

- Windows platform manifold adapter:
  `backend/arda_windows/world_manifold.py`
  Reason: platform-normalization bridge for ARDA Windows providers, not the canonical backend governance/world-state manifold.

- Legacy or compatibility-heavy surfaces:
  `backend/services/presence_server.py` legacy fallbacks
  Reason: operational compatibility or historical surfaces, not the primary architecture to extend when hardening governance. The legacy Presence Triune path is opt-in only via `SOPHIA_ENABLE_LEGACY_PRESENCE_TRIUNE_FALLBACK`; otherwise Presence returns a bounded compatibility response instead of silently becoming a second governance authority.

## Authoring Rules

- If you are changing world-state authority, start in `backend/services/world_model.py` or `backend/services/world_manifold.py`.
- If you are changing approval state transitions, start in `backend/services/governance_authority.py`.
- If you are changing high-impact queueing, start in `backend/services/outbound_gate.py`.
- If you are changing approved execution behavior, start in `backend/services/governance_executor.py`.
- If you are changing deception eligibility, start in `backend/services/deception_authority.py`.
- If you are changing bounded triune reasoning input, start in `backend/services/triune_orchestrator.py`.
- If you are changing high-impact MCP enforcement, start in `backend/services/mcp_server.py`, `backend/services/governance_context.py`, and `backend/services/governance_executor.py`.

## Current Phase 4 Status

- Architecture index exists for the hardened control plane.
- Canonical vs platform-adapter distinction is now explicit for the manifold layer.
- Presence compatibility fallback is now explicitly quarantined from canonical Triune authority.
- Historical `server_old.py` monolith has been removed from the active backend surface.
- Duplicate conceptual ownership still exists outside these indexed subsystems and should be reduced in later Phase 4 cleanup.
