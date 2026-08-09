# Triune Governance Integration Matrix

This matrix maps the end-to-end governance chain and the concrete backend integration hooks.

## Canonical chain

`Intent -> World Event -> Triune Assessment -> Policy Decision -> Outbound Gate Decision -> Approval -> Executor Release -> PEP Enforcement (token/policy/trust) -> Execution -> Audit + World Feedback`

## System matrix

| Layer | Canonical owner | Primary files/functions | Current state | Phase |
|---|---|---|---|---|
| Intent intake (API/WS/tasks) | Routers + workers | `backend/routers/*`, `backend/tasks/*`, `backend/websocket_service.py` | Mixed auth + mixed direct execution patterns | P2/P3 |
| World event persistence + trigger policy | `world_events` | `backend/services/world_events.py:emit_world_event` | Implemented event classes + trigger policy | Stable |
| Triune reasoning | `triune_orchestrator` | `backend/services/triune_orchestrator.py:handle_world_change` | Active; Metatron belief + Michael/Loki used for planning | Stable |
| Policy decision point (PDP) | `policy_engine` | `backend/services/policy_engine.py:evaluate/approve/deny` | Previously in-memory approval authority | **P1 active** |
| Canonical decision authority | `governance_authority` | `backend/services/governance_authority.py` | New canonical decision transition service | **P1 active** |
| Outbound gate queue | `outbound_gate` | `backend/services/outbound_gate.py:gate_action` | Central queue + decision docs for high-impact actions | Stable |
| Approval control plane | `governance router` + enterprise policy APIs | `backend/routers/governance.py`, `backend/routers/enterprise.py` | Was split updates in multiple routers | **P1 active** |
| Approved decision executor | `governance_executor` | `backend/services/governance_executor.py:process_approved_decisions` | Releases approved queue-backed decisions | P1 hardening |
| Command dispatch primitives | `governed_dispatch` | `backend/services/governed_dispatch.py` | Centralized queue writes | P2 hardening |
| Capability plane | `token_broker` | `backend/services/token_broker.py` | Exists but not fully bound to all PEP paths | P3 |
| Tool/MCP enforcement points (PEP) | `tool_gateway` + `mcp_server` | `backend/services/tool_gateway.py:execute`, `backend/services/mcp_server.py:_handle_tool_request` | High-impact runtime governance + token checks enforced; broader rollout pending | P3 |
| Audit + feedback | telemetry + world events | `backend/services/telemetry_chain.py`, `backend/services/world_events.py` | Available, not uniformly linked to decision/token IDs | P4 |

## Phase plan

### Phase 1 — Authority unification (in progress)

Goal: one canonical decision state model across triune decisions, policy approvals, and manual approval paths.

| Task | Hook | Status |
|---|---|---|
| Add canonical authority transition service | `backend/services/governance_authority.py` | Done |
| Route governance API approve/deny through canonical service | `backend/routers/governance.py` | Done |
| Route enterprise policy approve/deny through canonical service (with policy sync) | `backend/routers/enterprise.py` | Done |
| Stop manual approval from creating non-terminal custom executor status | `backend/routers/agent_commands.py` | Done |
| Persist policy decisions in DB and mirror approval-required decisions into canonical triune decisions | `backend/services/policy_engine.py` | Done |
| Restrict executor to queue-backed decisions only | `backend/services/governance_executor.py` | Done |

### Phase 2 — Chokepoint closure and dispatch consistency

Goal: remove direct/legacy release paths and enforce queue release through canonical executor.

- Enforce gating before any `enqueue_command_delivery` call site.
- Normalize command status model across swarm/unified/agent command consumers.
- Close remaining unauthenticated ingress paths (WS and ingest endpoints).

#### Early Phase 2 progress

- `agent_commands` manual approvals now route through canonical authority + governance executor release flow.
- Command polling semantics aligned to `pending -> delivered -> completed/failed` (with legacy status compatibility).
- Added machine-token enforcement on:
  - agent websocket endpoints (`server.py`, `routers/agent_commands.py`, `routers/unified_agent.py`)
  - high-risk ingest endpoints (`routers/swarm.py` CLI + USB result ingestion)
  - world-model ingestion endpoints (`routers/world_ingest.py`, `routers/loki.py`)
- Added dual-auth (machine token or write-permission user) for CLI event ingestion (`routers/cli_events.py`) and command-result reporting (`routers/agent_commands.py`).
- Added identity ingest machine-token boundary for provider event ingestion (`routers/identity.py`).
- Tightened remaining mutating control endpoints to explicit write/admin or machine-token dependencies (`enterprise`, `cspm`, `zero_trust`, `soar`, `quarantine`, `response`, `advanced`).
- Governance guardrail advisory backlog reduced to zero in current scoped routers (`backend/scripts/governance_guardrails.py` now passes).

### Phase 3 — Runtime enforcement convergence (PEP hardening)

Goal: require approved decision context + token + policy constraints at execution time.

- `tool_gateway.execute`: mandatory token validation + decision context checks.
- `mcp_server._handle_tool_request`: remove caller-trusted bypass flag semantics; verify server-side decision context.
- Bind token issuance/revocation to approved decisions only.

#### Phase 3 progress (this iteration)

- `mcp_server._handle_tool_request` now requires **server-validated** approved governance context (`decision_id`/`queue_id`) for high-impact tools; metadata-only `governance_approved` flags no longer allow execution.
- If governance context is absent/invalid for high-impact tools, requests are re-routed into `OutboundGateService` and returned as `queued_for_triune_approval`.
- High-impact MCP execution now enforces capability token validation (`token_id` + `principal_identity` + `action/target`) before handler execution.
- Execution handlers receive normalized governance/token metadata so downstream PEPs can enforce without trusting caller payload shape.
- `tool_gateway.execute` now enforces approved governance context + capability token validation for approval-required tools (and supports optional environment-wide strict rollout toggles).
- `governance_executor` now executes approved token operations (`issue_token`, `revoke_token`, `revoke_principal_tokens`) under canonical governance context instead of leaving them as non-executable gated intents.
- `token_broker` now requires approved governance context for token admin mutations by default, and records decision/queue-linked admin audit entries for issuance/revocation actions.

### Phase 4 — Audit closure

Goal: every execution is cryptographically/audit-linked to policy + decision + token.

- Persist decision-policy-token-execution linkage.
- Emit mandatory execution completion events for recompute feedback.

#### Phase 4 progress (this iteration)

- `telemetry_chain.AuditRecord` now persists explicit linkage fields: `policy_decision_id`, `governance_decision_id`, `governance_queue_id`, `token_id`, `execution_id`, and `trace_id`.
- `governance_executor` now emits mandatory `governance_execution_completed` world events for executed/skipped/failed outcomes with decision/queue/token/execution linkage in payload.
- `governance_executor` now records audit-chain entries for every terminal execution outcome (success/skip/failure), binding queue decisions to execution artifacts.
- `mcp_server` now writes execution audit-chain records with governance + token linkage for terminal MCP execution outcomes (including token-validation failures).
- Report/export pathways now emit canonical world events and tamper-audit records in key routers (`reports`, `timeline`, `cspm`).
- Vector-memory and VNS write-path endpoints in `advanced` now emit canonical world events and tamper-audit records to reduce telemetry blind spots.
- EDR telemetry collection now emits canonical `edr_telemetry_collected` world events and matching tamper-audit records.
- Swarm and unified-agent telemetry ingestion paths now emit canonical world events and write tamper-evident audit entries, closing remaining direct-ingest telemetry blind spots.
- Triune beacon cascade no longer bypasses canonical event helper; direct `world_events.insert_one` was replaced with `emit_world_event`.
- Governance executor now includes concrete domain-operation handlers for additional high-impact action types (`response_*`, `quarantine_*`, `vpn_*`, `quarantine_agent`).
- Quantum cryptography now includes end-to-end API support for Dilithium signing + verification + stored-signature verification + SHA3 hashing, all with canonical world-event and tamper-audit linkage.

### Phase 5 — Triune cognition convergence

Goal: ensure Metatron/Michael/Loki consume a unified cognitive signal plane rather than fragmented side integrations.

- Added `backend/services/cognition_fabric.py` to aggregate AATL/AATR/CCE/ML/AI-reasoning into a canonical `world_snapshot["cognition"]`.
- `triune_orchestrator` now injects cognition snapshot before Metatron/Michael/Loki execute.
- Metatron now fuses cognitive pressure/autonomy confidence into strategic pressure and policy-tier suggestion.
- Michael now augments candidate actions from cognitive recommendations and exposes `cognitive_action_alignment`.
- Loki now adds cognition-derived dissent (`cognitive_dissent`) including strategy challenge, AATR match hypotheses, and uncertainty expansion.
- Detailed capability summary published in `docs/triune_cognition_feature_summary.md`.
- Unified endpoint agent now submits local auto-remediation proposals to backend governed dispatch (`/api/unified/agents/{agent_id}/remediation/propose`) instead of relying on deprecated direct triune approval endpoint semantics.
- Unified endpoint agent heartbeat now includes structured per-monitor telemetry snapshots (all active monitor families), not only generic telemetry aggregates.
- Unified-agent ingest now projects monitor + telemetry signals into canonical `world_entities` state and emits `unified_agent_world_state_projected`/`unified_agent_monitor_telemetry_ingested` events with tamper-audit linkage; high-risk telemetry automatically triggers Triune recompute.
- `advanced` AI/VNS write paths now accept either write-permission user auth or machine-token ingest auth, enabling first-class agent side-channel ingestion without bearer-only dependence.
