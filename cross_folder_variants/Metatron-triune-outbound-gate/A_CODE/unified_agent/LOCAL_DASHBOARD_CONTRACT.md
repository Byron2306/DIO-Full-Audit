# Local Dashboard Ownership Contract

## Goal
Guarantee that localhost:5000 always serves the substantive, fully featured local dashboard.

## Canonical Ownership
- localhost:5000: owned by unified_agent/ui/web/app.py (Flask dashboard).
- localhost:5050: reserved for unified_agent/core/agent.py built-in LocalWebUIServer fallback.

## Startup Contract
1. Start the canonical local dashboard on port 5000:
   - python unified_agent/ui/web/app.py --host 0.0.0.0 --port 5000
2. If running the monolithic agent process, do not let it claim 5000.
   - Default now uses 5050 for built-in UI.
   - Optional explicit: python unified_agent/core/agent.py --ui-port 5050
3. In operator workflows and links, treat 5000 as source of truth.

## Operational Guarantees
- No port collision between Flask dashboard and built-in lightweight UI by default.
- Full local dashboard feature surface remains on 5000.
- Legacy built-in UI remains available for diagnostics on 5050.

## Phase-2 Refactor Plan
1. Replace WebAgentBridge desktop-core dependency with direct monolithic UnifiedAgent integration.
2. Expose a shared status/command facade used by both 5000 UI and backend heartbeat paths.
3. Add contract tests that validate parity for monitors, commands, and dashboard payload fields.
