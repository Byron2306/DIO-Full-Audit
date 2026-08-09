# Metatron Full Architecture Map (March 6, 2026)

## 1) System Topology at a Glance

- Primary stack: `frontend` (React) + `backend` (FastAPI) + `mongodb`.
- Security/ops stack: `elasticsearch`, `kibana`, `wireguard`, optional `ollama`, `trivy`, `falco`, `suricata`, `cuckoo`.
- Entry channels:
- Web UI routes from `frontend/src/App.js` (47 route entries, including redirects).
- REST API under `/api/*` and `/api/v1/*`.
- WebSockets under `/ws/*`.
- Endpoint-agent control plane under `/api/unified/*` and `/api/swarm/*`.

## 2) Frontend Architecture (Local and Remote Use)

Core frontend shell:
- Router and protected layout: `frontend/src/App.js`, `frontend/src/components/Layout`.
- Auth/session context: `frontend/src/context/AuthContext.jsx`.

Operational page groups:
- SOC and incident ops: dashboard, threats, alerts, hunting, correlation, timeline, audit, reports.
- Response and containment: quarantine, threat response, SOAR, ransomware, honey tokens, deception.
- Endpoint and swarm ops: unified agent, command center, cli sessions, network topology.
- Platform security: zero trust, cspm, attack paths, kernel sensors, secure boot, identity.
- Advanced services: AI threats, advanced services, VNS alerts, browser extension, kibana.

Frontend implementation model:
- Local: browser to `http://localhost:3000` with backend fallback or configured API base.
- Remote: browser to reverse-proxied `https://<domain>` via Nginx with backend routed through `/api`.

## 3) Backend Architecture (Current Router Mesh)

FastAPI entrypoint:
- `backend/server.py`.
- Router registration uses `/api` plus selected routers with native `/api/v1` prefixes.

Major API domains:
- Core platform: auth, users, dashboard, settings, websocket, reports.
- Security analytics: threats, alerts, threat intel, hunting, correlation, timeline, audit.
- Response plane: response, quarantine, SOAR, ransomware, honeypots, honey tokens, deception.
- Endpoint plane: agents, agent commands, swarm, unified agent.
- Enterprise plane: enterprise, zero trust, multi-tenant, extension.
- Advanced plane: advanced, AI analysis, AI threats, ML prediction, sandbox, EDR, containers, VPN, CSPM.
- Tier-1 security routers: attack paths, secure boot, kernel sensors, identity.

Real-time plane:
- `/ws/threats` and `/ws/agent/{agent_id}`.

## 4) Security/Service Layer

Key service families:
- Control and governance: `policy_engine`, `token_broker`, `tool_gateway`, `identity`.
- AI/security reasoning: `aatl`, `aatr`, `cognition_engine`, `ai_reasoning`, `cce_worker`.
- Threat data and memory: `mcp_server`, `vector_memory`, `vns`, `vns_alerts`, `telemetry_chain`.
- Deployment and operations: `agent_deployment`, `network_discovery`, `siem`.

Core engine modules:
- `threat_response`, `threat_correlation`, `threat_timeline`, `threat_intel`.
- `ransomware_protection`, `quarantine`, `container_security`, `browser_isolation`, `zero_trust`.
- `identity_protection`, `ml_threat_prediction`, `sandbox_analysis`, `quantum_security`, `deception_engine`.

## 5) Endpoint and Agent Implementations

Unified agent stack:
- Main endpoint agent: `unified_agent/core/agent.py`.
- Local control and UI: `unified_agent/server_api.py`, `unified_agent/ui/web/app.py`, `unified_agent/ui/desktop/main.py`.
- Deployment helpers and diagnostics: `unified_agent/auto_deployment.py`, tests/utilities in `unified_agent/`.

Agent install paths:
- Backend-served installers/downloads via `backend/routers/unified_agent.py` and swarm routes.
- Scripted local installers in `scripts/`.

Implementation model:
- Local: endpoint agent + local UI/service for host-level visibility and control.
- Remote: endpoint heartbeat/events to backend control plane, command dispatch from backend to agents.

## 6) Data and Storage Architecture

Primary data store:
- MongoDB (`seraph_ai_defense`) for platform state, telemetry, commands, and control-plane records.

Observability and SIEM:
- Elasticsearch + Kibana local stack.
- Optional external SIEM forwarding via `services/siem.py`.

EDM-specific data path:
- Dataset metadata/versioning and rollout state persisted by unified-agent router.
- Agent EDM hits ingested centrally for analytics and readiness evaluation.

## 7) Local vs Remote Implementation Split

Local/on-host implementations:
- Endpoint monitors and remediation primitives in unified agent.
- Desktop/local web control surfaces for agent utilities.
- Dockerized local stack for full platform bring-up.

Remote/distributed implementations:
- Central API control plane and SOC UI.
- Remote agent deployment over SSH/WinRM.
- Optional external integrations (SIEM APIs, threat feeds, communication channels).
- Reverse proxy/TLS ingress for internet-facing operation.

## 8) End-to-End Runtime Flows

Primary SOC flow:
1. Agent/events/sensors feed backend APIs and websockets.
2. Backend correlates and enriches alerts/threats.
3. Frontend renders situational and investigative views.
4. Analyst executes response/SOAR/deployment commands.
5. Backend dispatches and tracks command/deployment outcomes.

EDM flow:
1. Dataset version published in backend source-of-truth.
2. Staged rollout to target cohorts (5/25/100) with readiness checks.
3. Agents perform EDM matching and emit hit telemetry.
4. Backend evaluates anomaly thresholds and can auto-rollback.

## 9) Current Architectural Risk Focus

- Contract governance and schema invariants across fast-moving routes.
- Hardening consistency across all legacy and secondary entry paths.
- Durability guarantees for governance-critical state under restart/scale.
- Assurance depth (security regression and denial-path coverage).
