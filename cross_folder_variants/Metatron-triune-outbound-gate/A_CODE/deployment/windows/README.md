# Seraph Windows Lab (Download → Run)

This folder is a **Windows-friendly** way to run the Seraph UI/API locally (via Docker Desktop) and execute **Windows Atomic Red Team** tests on your laptop, while attaching **SOAR response evidence** and optional **osquery telemetry** back into Seraph.

Use only on systems you own or are explicitly authorized to test. Run atomics in an isolated lab whenever possible.

## 1) Start Seraph on Windows (Docker Desktop)

Prereqs:
- Windows 10/11
- Docker Desktop (WSL2 backend) + “File sharing” enabled for this repo folder

From the repo root:

```powershell
docker compose -f deployment/windows/docker-compose.windows.stack.yml up -d --build
```

Then open:
- UI: `http://localhost:3000`
- API: `http://localhost:8001/api/health`

Create your first admin account in the UI (first registration becomes admin).

## 2) Install Windows Atomics (on the laptop)

Run:

```powershell
powershell -ExecutionPolicy Bypass -File deployment/windows/Setup-AtomicRedTeam.ps1
```

This installs:
- Atomic YAMLs under `C:\AtomicRedTeam\atomics`
- Invoke-AtomicRedTeam under `C:\AtomicRedTeam\invoke-atomicredteam`

## 3) Run Atomics + attach SOAR evidence

1) Get an auth token:

```powershell
powershell -ExecutionPolicy Bypass -File deployment/windows/Get-SeraphToken.ps1 -BackendUrl http://localhost:8001
```

2) Run one or more techniques (example):

```powershell
$env:SERAPH_TOKEN = Get-Content .seraph-token.txt
powershell -ExecutionPolicy Bypass -File deployment/windows/Run-WindowsAtomicsAndSoar.ps1 `
  -BackendUrl http://localhost:8001 `
  -Techniques T1059.001,T1105 `
  -OutputDir .\\artifacts\\windows-atomics `
  -IUnderstandThisRunsAdversarySimulation
```

What you get:
- Per-technique `run_*.json` files under `OutputDir`
- SOAR execution records (S5 evidence linkage) archived inside the backend container under:
  `/var/lib/seraph-ai/artifacts/soar_executions_archive.json`

## 4) Optional: osquery telemetry into Seraph

If you want Seraph’s `/api/osquery/results` to show **real laptop telemetry**, you can:

1) Install + configure osquery on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File deployment/windows/Setup-Osquery.ps1
```

2) Push recent results into Seraph:

```powershell
powershell -ExecutionPolicy Bypass -File deployment/windows/Push-OsqueryResults.ps1 -BackendUrl http://localhost:8001
```

Notes:
- `Push-OsqueryResults.ps1` uses the backend’s integration token header (`x-internal-token`). Set it in your environment:
  `setx INTEGRATION_API_KEY "dev-integration-key-change-me"`
- You can change the token in `deployment/windows/docker-compose.windows.stack.yml` via `INTEGRATION_API_KEY=...`.

