# Local Machine Validation Guide (Canonical UI on Port 5000)

This validates the merged architecture where all local dashboard functionality is served on port 5000.

## 1) Setup

```bash
cd /path/to/Metatron
python -m venv .venv
source .venv/bin/activate
pip install -r unified_agent/requirements.txt

# Optional: profile-driven local installer
# core (default): agent + dashboard
python scripts/install.py --auto --profile core

# security stack: includes best-effort trivy/falco/suricata setup
python scripts/install.py --auto --profile security-stack

# forensics: includes volatility3 Python package
python scripts/install.py --auto --profile forensics

# full: security stack + forensics
python scripts/install.py --auto --profile full
```

## 2) Start Canonical Dashboard

```bash
bash unified_agent/run_local_dashboard.sh
```

Expected:
- Dashboard UI available on `http://localhost:5000`
- API status endpoint returns JSON: `http://localhost:5000/api/status`
- External access diagnostics endpoint is available: `http://localhost:5000/api/external-access/status`

## 3) Run Contract Tests

```bash
python -m pytest -q unified_agent/tests/test_monitor_scan_regression.py unified_agent/tests/test_canonical_ui_contract.py
```

Expected:
- Both tests pass.
- `test_monitor_scan_regression` confirms monitor scan safety.
- `test_canonical_ui_contract` confirms port-5000 parity routes and tooling health payloads.

## 4) Validate Legacy 5050 Parity Routes on Port 5000

```bash
curl -s http://localhost:5000/api/dashboard | jq '.available'
curl -s http://localhost:5000/api/data | jq '.available'
curl -s http://localhost:5000/api/yara | jq '.available'
```

Expected:
- `api/data` mirrors `api/dashboard`
- YARA status endpoint is available (if YARA dependency present)

## 5) Validate WireGuard

```bash
curl -s http://localhost:5000/api/vpn/status | jq
curl -s -X POST http://localhost:5000/api/vpn/start | jq
curl -s -X POST http://localhost:5000/api/vpn/stop | jq
```

Notes:
- Interface resolution prefers `metatron-vpn` then `wg0`.
- On Windows, service names are tried for both interface names.

## 6) Validate Trivy/Falco/Suricata/Volatility Readiness

```bash
curl -s http://localhost:5000/api/security/tooling | jq
curl -s http://localhost:5000/api/tooling/health | jq
```

Expected:
- `tools` includes `trivy`, `falco`, `suricata`, `volatility`, `wireguard`
- `ready` is true only if required capabilities are detected
- `issues` enumerates what is still missing when not ready

## 7) Validate External Reachability (Codespaces/Remote)

```bash
curl -s http://localhost:5000/api/external-access/status | jq
```

Expected:
- `checks.local_listener.ok` is true
- `checks.local_status_http.ok` is true
- When running in Codespaces, `forwarded_base_url` is populated
- If browser access fails, `issues` and `recommendations` provide actionable forwarding guidance

## 8) Optional: Start Agent with Lightweight Built-In UI on 5050

```bash
python unified_agent/core/agent.py --ui-port 5050
```

This is fallback-only. Canonical operational UI remains port 5000.
