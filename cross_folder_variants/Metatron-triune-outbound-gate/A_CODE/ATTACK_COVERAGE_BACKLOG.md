ATT&CK Coverage Backlog — New Features Summary (generated 2026-03-10)

Overview
- Consolidated ATT&CK scanning across modules and unified agent; unioned coverage estimate: 180 unique ATT&CK IDs (prior analysis).
- Implemented integrations and ingestion pipelines to capture telemetry and indicators from OSINT/host/network collectors and emulators.

New Features Implemented
- Integrations Manager
  - Persistent `integrations_jobs` in MongoDB for durable job history and artifacts.
  - API endpoints: `/integrations/amass/run`, `/integrations/velociraptor/run`, `/integrations/purplesharp/run`, `/integrations/ingest/*`, `/integrations/jobs` and artifact endpoints.
  - Internal machine-to-machine auth via `X-Internal-Token` / `INTEGRATION_API_KEY`.
- Celery Worker & Tasks
  - `celery_app.py` + `tasks/integrations_tasks.py` with hardened `run_velociraptor_task` (retries/backoff/soft-time-limit).
  - Yara scanning integrated into Velociraptor collection flows (prefer `yara-python`, CLI fallback).
  - Celery tasks post indicators to the canonical `threat_intel.ingest_indicators(...)` ingestion path.
- Parsers & Runners
  - Amass, Arkime, BloodHound parsers added (host/domain/graph extractions).
  - Velociraptor collection runner and indicator extractor.
  - PurpleSharp runner scaffolds (WinRM runner `run_purplesharp.py`) plus parser to translate emulation output into indicators.
- Honeypot / Canary Ingestion
  - `routers/honeypots.py` for canary alerts; writes `honeypot_alerts` and generates system alerts.
- Frontend (React)
  - `ThreatIntelPage.jsx` and `JobCard.jsx`: job listing, artifact download, integration controls (Amass/Velociraptor/PurpleSharp), polling for job status.
  - UX polish: job start state (`jobStarting`) wired to disable start buttons and show loader text; polling tuned to 5s.
- Unified Agent Helpers
  - `unified_agent/integrations_client.py` helpers to start collectors and perform direct ingest.
- Tests & Deployment
  - Unit tests for honeypot and Yara flows added.
  - `docker-compose.celery.yml` and `celery-worker.service` examples for supervision.

Immediate ATT&CK Impact (per-feature)
- OSINT / Amass ingestion: improves coverage of Enterprise/Reconnaissance techniques (TA0043) — sub-techniques: Domain Discovery, External Remote Services discovery.
- Velociraptor host collections + Yara: enhances detection for Persistence (TA0003), Defense Evasion (TA0005), Discovery (TA0007), Credential Access (TA0006) where host artifacts or yara signatures map to file/registry/behavioral indicators.
- PurpleSharp emulation: increases coverage for Privilege Escalation (TA0004) and Lateral Movement (TA0008) telemetry by exercising attack chains and surfacing observable artifacts.
- Arkime / BloodHound ingestion: expands visibility for Lateral Movement and Discovery (domain graphing, AD relationships).
- Honeypots/canaries: strengthens Early Warning (Collection) for Initial Access (TA0001) and Credential Access attempts.

Prioritized Gaps & Recommendations
1. Endpoint Telemetry Coverage (High)
   - Missing: Universal Sysmon/EDR schema normalization for all hosts. Recommendation: standardize host event mapping and add parsers for common schemas to increase fidelity of Velociraptor/host logs.
2. Process/Network Correlation (High)
   - Missing: cross-source correlation rules linking Velociraptor host events with Arkime network sessions. Recommendation: add correlation rules in `threat_intel` to join by PID/connection hashes.
3. ATT&CK Mapping Coverage (Medium)
   - Missing: systematic mapping from parsed indicators/artifacts to ATT&CK technique IDs. Recommendation: maintain a mapping table and annotate `ingest_indicators` outputs with technique IDs and confidence scores.
4. PurpleSharp Real Execution & Safeguards (Medium)
   - Current: scaffolds + WinRM runner. Recommendation: finalize safe execution harness (sandboxed hosts), ensure logging, and run limited emulations using least-privilege credentials.
5. CI / E2E Testing (Medium)
   - Missing: CI that runs integration tests with ephemeral MongoDB + Redis. Recommendation: add GitHub Actions job that runs docker-compose.celery.yml for tests.
6. Secrets & Rotation (High)
   - `INTEGRATION_API_KEY` must be rotated and stored in a secret store. Recommendation: integrate Key Vault / HashiCorp vault for production secrets and ensure worker/service envs pull securely.

Next Actions (suggested immediate priorities)
- Finish frontend UX verification and unit tests run (you asked to run frontend; see PowerShell note below).
- Implement ATT&CK mapping annotations inside `threat_intel.ingest_indicators`.
- Add normalization layer for host telemetry (Sysmon/OSQuery/Velociraptor) and unit tests.
- Add CI job to run unit tests with ephemeral MongoDB+Redis.
- Harden secrets and rotate `INTEGRATION_API_KEY` (deploy secret manager).

Notes on running the frontend locally
- The React dev server was started but blocked by PowerShell execution policy (yarn.ps1 script not allowed). To fix on Windows, run PowerShell as Administrator and execute:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

- After that, in the workspace root run:

```bash
cd frontend
yarn install
yarn start
```

This will bring up the dev server on the default port (usually 3000). Ensure `REACT_APP_BACKEND_URL` is set if your backend runs on a non-default host/port.

---

Generated by the integration work; if you'd like, I can: run the unit tests, add CI workflow, or create the ATT&CK mapping table scaffold in the codebase next.