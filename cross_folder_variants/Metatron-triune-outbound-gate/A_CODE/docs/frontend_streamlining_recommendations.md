# Frontend Streamlining Recommendations (Port 3000 UI)

Scope: Main frontend on port `3000` only.  
Out of scope: Unified agent standalone dashboard on `5000` (kept as external deep-link only).

## Current State (from code audit)

- Routed pages in `frontend/src/App.js`: **59**
- Sidebar entries in `frontend/src/components/Layout.jsx`: **52**
- Navigation pattern today: flat list with many low-frequency specialist pages shown at top-level.
- Observed UX issue: high cognitive load from showing all backend capability areas as equal-priority pages.

---

## Streamlining Strategy

### 1) Move from flat navigation to **task-based domains**
Replace the current one-level menu with 6 top-level domains:

1. **Command**
2. **Intelligence**
3. **Response**
4. **Platform**
5. **Engineering**
6. **Admin**

Each domain gets a concise landing page with KPIs + top actions + links to detail views.

### 2) Treat many current pages as **drill-down tabs**, not primary routes
Several pages are valid but should not be first-class sidebar items.

### 3) Add **persona views**
- Tier 1 SOC: Command + Response
- Threat Intel/Hunt: Intelligence + Engineering
- Platform/SecOps: Platform + Admin

Use role/feature flags to show only relevant sections by default.

---

## Recommended IA (target)

## A. Command
- Dashboard
- Alerts
- Threats
- Timeline
- Command Center

## B. Intelligence
- World View (with embedded graph tab)
- Threat Intel
- Correlation
- AI Threats (AATL/AATR)
- Threat Hunting
- Attack Paths

## C. Response
- Unified Agent (main endpoint control-plane)
- EDR
- Auto Response
- SOAR
- Quarantine
- Deception
- Honey Tokens
- Ransomware

## D. Platform
- Identity
- Zero Trust
- VPN
- CSPM
- Container Security
- Browser Isolation
- Email Protection
- Email Gateway
- Mobile Security
- MDM

## E. Engineering
- Sigma
- MITRE ATT&CK
- Atomic Validation
- Zeek
- osquery/Fleet
- VNS Alerts
- ML Prediction
- Sandbox
- Advanced Services (internal tooling, MCP/vector/quantum)

## F. Admin
- Reports
- Audit Logs
- Tenants
- Settings
- Setup Guide
- Browser Extension (distribution + health)

---

## Consolidation Matrix (high-value merges)

1. **`/world` + `/world/graph`**  
   - Keep `/world` as parent page.  
   - Move graph into tab: `Overview | Graph | Events`.

2. **`/dashboard` + `/command-center` + `/alerts` + `/threats`**  
   - Keep separate backend routes, but UX as one “Command” surface with tabs + quick filters.

3. **`/ai-detection` + `/ai-threats` + `/cli-sessions`**  
   - Merge into one “AI Activity” page with tabs:
     - Live Signals
     - Session Intelligence
     - Registry/Assessments

4. **`/threat-intel` + `/correlation` + `/attack-paths`**  
   - Present as one investigation workspace:
     - Intel
     - Correlation
     - Path Analysis

5. **`/edr` + `/quarantine` + `/response` + `/soar`**  
   - Consolidate under “Response Operations” with action-centric tabs.

6. **`/email-protection` + `/email-gateway`**  
   - Merge into “Email Security” with sub-tabs for policy, gateway pipeline, quarantine.

7. **`/mobile-security` + `/mdm`**  
   - Merge into “Endpoint Mobility” workspace.

8. **`/sigma` + `/mitre-attack` + `/atomic-validation`**  
   - Merge into “Detection Engineering” with clear build/validate loop.

---

## Routes to demote from sidebar (still accessible)

Keep route, remove top-level nav entry:
- `/setup-guide`
- `/browser-extension`
- `/kibana`
- `/advanced`
- `/vns-alerts`
- `/heatmap`
- `/world/graph` (becomes world tab)

Expose via:
- “More tools” drawer
- Contextual links from domain pages

---

## Navigation/UX quick wins (lowest risk)

1. **Group sidebar sections with collapsible headings** (Command/Intelligence/Response/...).
2. **Default collapsed for Engineering/Admin**.
3. **Add global search/command palette** (`Cmd/Ctrl+K`) for page jump.
4. **Persist user “favorite pages”** and show top 5 first.
5. **Use density levels**: Summary / Analyst / Expert on data-heavy pages.
6. **Standard page frame**:
   - KPI strip
   - action bar
   - primary table/chart
   - advanced diagnostics collapsed by default

---

## Suggested phased implementation

### Phase 1 (1 sprint)
- Sidebar regroup + collapsible sections
- Demote low-frequency pages
- Merge world graph into world tabs

### Phase 2 (1–2 sprints)
- AI Activity merge (`ai-detection` + `ai-threats` + `cli-sessions`)
- Response Operations workspace (`edr` + `quarantine` + `response` + `soar`)

### Phase 3 (2 sprints)
- Investigation workspace (`threat-intel` + `correlation` + `attack-paths`)
- Detection Engineering workspace (`sigma` + `mitre` + `atomic`)

---

## Success metrics

- Reduce visible primary nav items from **52 → ~18–24**
- Reduce first-click time to core tasks (alert triage, isolate endpoint, investigate campaign)
- Increase usage concentration on top workflows
- Decrease bounce between adjacent pages (signals overlap reduction)

