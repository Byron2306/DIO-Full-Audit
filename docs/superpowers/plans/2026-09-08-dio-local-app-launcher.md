# DIO Local App Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide one Debian launcher that starts, verifies, and opens GoldenEye, Control Deck, Market Command, and Production Studio while preserving their existing service boundaries.

**Architecture:** Three localhost Python servers remain independently supervised by user-level systemd. A fourth lightweight launcher server projects health and links to four surfaces; a command starts the systemd target, waits with bounded polling, verifies 53+15=68, and opens the launcher page.

**Tech Stack:** Python 3 standard library, user-level systemd, HTML/CSS/JavaScript, pytest

**Spec:** `docs/superpowers/specs/2026-09-08-dio-68-portfolio-local-launcher-design.md`

## Global Constraints

- Bind every HTTP server to `127.0.0.1`, `localhost`, or `::1` only.
- Reuse ports 8765 for Business Workbench, 8766 for GoldenEye, and 8770 for Market Command.
- Control Deck and Production Studio remain routes of the same Business Workbench process.
- Starting or opening an application creates no execution, publication, outreach, spend, payment, or release authority.
- Do not embed secrets or tokens in HTML, command lines, desktop entries, or systemd unit files.
- Portfolio readiness requires exactly 53 historical rows plus 15 verified extensions yielding 68.

---

### Task 1: Normalize the three user services and group target

**Files:**
- Create: `deploy/systemd/dio-goldeneye.service`
- Create: `deploy/systemd/dio-apps.target`
- Modify: `deploy/systemd/dio-control-deck.service`
- Modify: `deploy/systemd/dio-market-command.service`
- Create: `tests/test_dio_local_launcher.py`

**Interfaces:**
- Consumes: existing server entrypoints and repository path `/home/byron/DIO-Full-Audit`
- Produces: three services addressable by `dio-apps.target`

- [ ] **Step 1: Write failing unit-file tests**

Create:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD = ROOT / "deploy/systemd"

def test_dio_apps_target_groups_three_services():
    target = (SYSTEMD / "dio-apps.target").read_text(encoding="utf-8")
    assert "Wants=dio-control-deck.service dio-goldeneye.service dio-market-command.service" in target
    assert "After=dio-control-deck.service dio-goldeneye.service dio-market-command.service" in target

def test_dio_surface_services_are_local_and_distinct():
    expected = {
        "dio-control-deck.service": ("serve_business_workbench.py", "--port 8765"),
        "dio-goldeneye.service": ("serve_goldeneye_ms10.py", "--port 8766"),
        "dio-market-command.service": ("serve_market_command_ms10.py", "--port 8770"),
    }
    for name, markers in expected.items():
        unit = (SYSTEMD / name).read_text(encoding="utf-8")
        assert "--host 127.0.0.1" in unit
        assert markers[0] in unit
        assert markers[1] in unit
        assert "PYTHONNOUSERSITE=1" in unit
```

- [ ] **Step 2: Run tests and verify missing target/service failure**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_dio_local_launcher.py
```

Expected: FAIL because the target and GoldenEye unit do not exist.

- [ ] **Step 3: Create the GoldenEye unit**

```ini
[Unit]
Description=DIO GoldenEye MS-10
After=network.target
PartOf=dio-apps.target

[Service]
Type=simple
WorkingDirectory=/home/byron/DIO-Full-Audit
ExecStart=/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 /home/byron/DIO-Full-Audit/scripts/serve_goldeneye_ms10.py --host 127.0.0.1 --port 8766
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONNOUSERSITE=1

[Install]
WantedBy=dio-apps.target
```

- [ ] **Step 4: Create the target**

```ini
[Unit]
Description=DIO Local Applications
Wants=dio-control-deck.service dio-goldeneye.service dio-market-command.service
After=dio-control-deck.service dio-goldeneye.service dio-market-command.service

[Install]
WantedBy=default.target
```

- [ ] **Step 5: Add `PartOf=dio-apps.target` to the existing service units**

Add the directive under `[Unit]` in both existing units. Preserve their entrypoints and ports.

- [ ] **Step 6: Run tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_dio_local_launcher.py
```

Expected: PASS.

- [ ] **Step 7: Commit service topology**

```bash
git add deploy/systemd tests/test_dio_local_launcher.py
git commit -m "feat: group DIO local application services"
```

### Task 2: Add a truth-reporting launcher API

**Files:**
- Create: `dio_launcher.py`
- Modify: `tests/test_dio_local_launcher.py`

**Interfaces:**
- Produces: `surface_catalog() -> list[dict[str, str]]`
- Produces: `portfolio_truth(portfolio: dict) -> dict[str, object]`
- Produces: `probe_url(url: str, timeout: float = 1.0) -> dict[str, object]`
- Produces: `launcher_state() -> dict[str, object]`

- [ ] **Step 1: Add failing catalog and truth tests**

```python
from dio_launcher import portfolio_truth, surface_catalog

def test_surface_catalog_exposes_four_apps_on_three_services():
    rows = surface_catalog()
    assert [row["id"] for row in rows] == [
        "goldeneye", "control-deck", "market-command", "production-studio"
    ]
    assert rows[0]["url"] == "http://127.0.0.1:8766/"
    assert rows[1]["url"] == "http://127.0.0.1:8765/"
    assert rows[2]["url"] == "http://127.0.0.1:8770/"
    assert rows[3]["url"] == "http://127.0.0.1:8765/dashboard/production.html"
    assert rows[1]["service"] == rows[3]["service"] == "dio-control-deck.service"

def test_portfolio_truth_requires_exact_verified_components():
    assert portfolio_truth({
        "base_canonical_incarnation_count": 53,
        "canon_extension_count": 15,
        "canonical_incarnation_count": 68,
        "extension_summary_state": "VERIFIED",
        "incarnations": [{}] * 68,
    })["verified"] is True
    assert portfolio_truth({
        "base_canonical_incarnation_count": 53,
        "canon_extension_count": 0,
        "canonical_incarnation_count": 53,
        "extension_summary_state": "MISSING",
        "incarnations": [{}] * 53,
    })["verified"] is False
```

- [ ] **Step 2: Run tests**

Expected: FAIL because `dio_launcher` does not exist.

- [ ] **Step 3: Implement the catalog and truth predicate**

```python
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SURFACES = [
    {"id": "goldeneye", "name": "GoldenEye", "url": "http://127.0.0.1:8766/", "health_url": "http://127.0.0.1:8766/api/control/state", "service": "dio-goldeneye.service"},
    {"id": "control-deck", "name": "Control Deck", "url": "http://127.0.0.1:8765/", "health_url": "http://127.0.0.1:8765/api/business/health", "service": "dio-control-deck.service"},
    {"id": "market-command", "name": "Market Command", "url": "http://127.0.0.1:8770/", "health_url": "http://127.0.0.1:8770/api/market/health", "service": "dio-market-command.service"},
    {"id": "production-studio", "name": "Production Studio", "url": "http://127.0.0.1:8765/dashboard/production.html", "health_url": "http://127.0.0.1:8765/api/business/health", "service": "dio-control-deck.service"},
]

def surface_catalog() -> list[dict[str, str]]:
    return [dict(row) for row in SURFACES]

def portfolio_truth(portfolio: dict[str, Any]) -> dict[str, Any]:
    result = {
        "base": portfolio.get("base_canonical_incarnation_count", 0),
        "extensions": portfolio.get("canon_extension_count", 0),
        "total": portfolio.get("canonical_incarnation_count", 0),
        "extension_state": portfolio.get("extension_summary_state", "MISSING"),
        "row_count": len(portfolio.get("incarnations") or []),
    }
    result["verified"] = (
        result["base"] == 53
        and result["extensions"] == 15
        and result["total"] == 68
        and result["row_count"] == 68
        and result["extension_state"] == "VERIFIED"
    )
    return result
```

- [ ] **Step 4: Implement bounded URL probes**

Use `Request(url, headers={"Accept": "application/json"})`, `urlopen(..., timeout=timeout)`, decode JSON, and return `{"ready": True, "status": response.status, "payload": payload}`. Catch `HTTPError`, `URLError`, `TimeoutError`, `UnicodeDecodeError`, and `json.JSONDecodeError`; return `{"ready": False, "error": str(exc)}`.

`launcher_state()` must probe each distinct `health_url`, reuse shared Business Workbench results, fetch `http://127.0.0.1:8765/api/business/portfolio`, and include `portfolio_truth()`.

- [ ] **Step 5: Add a mocked partial-failure test**

Use `monkeypatch` to make `probe_url` return ready for port 8765 and unavailable for ports 8766 and 8770. Assert the launcher state preserves four rows, marks both Control Deck and Production Studio ready, and marks GoldenEye and Market Command unavailable.

- [ ] **Step 6: Run tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_dio_local_launcher.py
```

Expected: PASS.

- [ ] **Step 7: Commit launcher state**

```bash
git add dio_launcher.py tests/test_dio_local_launcher.py
git commit -m "feat: add truth-reporting DIO launcher state"
```

### Task 3: Serve the launcher UI

**Files:**
- Create: `dashboard/dio-launcher.html`
- Create: `scripts/serve_dio_launcher.py`
- Modify: `tests/test_dio_local_launcher.py`

**Interfaces:**
- Consumes: `dio_launcher.launcher_state()`
- Produces: `GET /` launcher UI, `GET /api/launcher/state` JSON, no mutation endpoints

- [ ] **Step 1: Add failing route/source tests**

Assert that the server source contains `/api/launcher/state`, imports `launcher_state`, restricts hosts to localhost, and defines no `do_POST` implementation that performs an action. Assert the HTML contains all four surface names, `53 + 15 = 68`, and fetches `/api/launcher/state`.

- [ ] **Step 2: Implement the read-only server**

Use `ThreadingHTTPServer` and `SimpleHTTPRequestHandler`. Route `/` to `dashboard/dio-launcher.html`, route `/api/launcher/state` to JSON from `launcher_state()`, set `Cache-Control: no-store`, and return 405 for POST.

CLI:

```text
--host 127.0.0.1
--port 8764
```

Reject any host outside `127.0.0.1`, `localhost`, and `::1`.

- [ ] **Step 3: Implement the launcher page**

Create four responsive cards with name, service state, health detail, and an `Open` link using the fixed catalog URLs. Show portfolio truth as separate Base, Extensions, Total, and Evidence state fields. Render verified only when the API returns `portfolio.verified === true`; otherwise show truth-blocked.

The page must not display start/restart buttons because service mutation belongs to the launch command and systemd, not the browser.

- [ ] **Step 4: Run launcher tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_dio_local_launcher.py
```

Expected: PASS.

- [ ] **Step 5: Commit the read-only launcher UI**

```bash
git add dashboard/dio-launcher.html scripts/serve_dio_launcher.py tests/test_dio_local_launcher.py
git commit -m "feat: serve local DIO application launcher"
```

### Task 4: Add the launcher service and bounded start command

**Files:**
- Create: `deploy/systemd/dio-launcher.service`
- Create: `scripts/launch_dio_apps.py`
- Modify: `deploy/systemd/dio-apps.target`
- Modify: `tests/test_dio_local_launcher.py`

**Interfaces:**
- Consumes: `systemctl --user start dio-apps.target`, launcher state API
- Produces: command exit 0 only when services and 68-product truth are ready

- [ ] **Step 1: Extend unit tests**

Require `dio-launcher.service` in the target’s `Wants` and `After`. Assert its entrypoint is `scripts/serve_dio_launcher.py --host 127.0.0.1 --port 8764`.

- [ ] **Step 2: Create the launcher unit**

Follow the established unit structure, use the current venv Python, set `PartOf=dio-apps.target`, and retain `PYTHONNOUSERSITE=1`.

- [ ] **Step 3: Implement bounded startup**

`scripts/launch_dio_apps.py` must:

1. run `systemctl --user start dio-apps.target` with `check=True`;
2. poll `http://127.0.0.1:8764/api/launcher/state` for at most 20 seconds using `time.monotonic()`;
3. succeed only when every surface is ready and `portfolio.verified` is true;
4. print the exact unavailable surfaces or portfolio component mismatch on timeout;
5. open `http://127.0.0.1:8764/` with `webbrowser.open`;
6. return 0 on success and 2 on readiness timeout.

- [ ] **Step 4: Add tests for success and timeout**

Monkeypatch `subprocess.run`, `time.monotonic`, `time.sleep`, the state fetcher, and `webbrowser.open`. Assert success opens exactly one launcher URL. Assert timeout returns 2 and never opens a browser.

- [ ] **Step 5: Run tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_dio_local_launcher.py
```

Expected: PASS without invoking real systemd or a browser.

- [ ] **Step 6: Commit startup orchestration**

```bash
git add deploy/systemd/dio-launcher.service deploy/systemd/dio-apps.target scripts/launch_dio_apps.py tests/test_dio_local_launcher.py
git commit -m "feat: launch and verify DIO local apps"
```

### Task 5: Add the Debian desktop entry and installer

**Files:**
- Create: `deploy/desktop/dio-apps.desktop`
- Create: `scripts/install_dio_launcher.py`
- Modify: `tests/test_dio_local_launcher.py`

**Interfaces:**
- Consumes: repository deploy templates
- Produces: user-local copies in `~/.config/systemd/user/` and `~/.local/share/applications/`

- [ ] **Step 1: Add failing template and installer tests**

Assert the desktop entry contains:

```ini
Type=Application
Name=DIO
Terminal=false
Exec=/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 /home/byron/DIO-Full-Audit/scripts/launch_dio_apps.py
```

Test installer with a temporary destination root and assert it copies exactly four service units, one target, and one desktop entry without invoking systemd.

- [ ] **Step 2: Create the desktop entry**

Use categories `Development;Office;` and a descriptive comment. Do not include secrets or environment values.

- [ ] **Step 3: Implement explicit installation**

`install(root: Path, config_home: Path, data_home: Path) -> list[Path]` copies known filenames only, creates destination directories, and returns installed paths. The CLI then runs:

```text
systemctl --user daemon-reload
systemctl --user enable dio-apps.target
update-desktop-database ~/.local/share/applications
```

Treat a missing `update-desktop-database` as non-fatal; propagate systemctl failure.

- [ ] **Step 4: Run tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_dio_local_launcher.py
```

Expected: PASS without writing to the real home directory.

- [ ] **Step 5: Commit desktop installation**

```bash
git add deploy/desktop/dio-apps.desktop scripts/install_dio_launcher.py tests/test_dio_local_launcher.py
git commit -m "feat: install one-click Debian DIO launcher"
```

### Task 6: Verify installation and four-surface acceptance on Debian

**Files:**
- Modify only if verification reveals a reproducible defect in files from Tasks 1–5

**Interfaces:**
- Consumes: completed portfolio plan and launcher implementation
- Produces: one-click local acceptance evidence

- [ ] **Step 1: Run all focused tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q   tests/test_canon_extension_summary_persistence.py   tests/test_portfolio_runtime_canon_extensions.py   tests/test_operator_production_studio.py   tests/test_market_command.py   tests/test_dio_local_launcher.py
```

Expected: PASS.

- [ ] **Step 2: Install user-local launcher files**

```bash
PYTHONNOUSERSITE=1 python scripts/install_dio_launcher.py
```

Expected: installed paths printed; daemon reload and target enable succeed.

- [ ] **Step 3: Launch**

```bash
PYTHONNOUSERSITE=1 python scripts/launch_dio_apps.py
```

Expected: browser opens once at `http://127.0.0.1:8764/`.

- [ ] **Step 4: Verify endpoints**

```bash
curl -fsS http://127.0.0.1:8764/api/launcher/state | python -m json.tool
curl -fsS http://127.0.0.1:8765/api/business/health | python -m json.tool
curl -fsS http://127.0.0.1:8770/api/market/health | python -m json.tool
curl -fsS http://127.0.0.1:8766/api/control/state | python -m json.tool
```

Expected: all services ready; launcher portfolio reports base 53, extensions 15, total 68, state VERIFIED.

- [ ] **Step 5: Verify the shared Production Studio route**

```bash
curl -fsSI http://127.0.0.1:8765/dashboard/production.html
```

Expected: HTTP 200 from the Business Workbench service.

- [ ] **Step 6: Verify localhost-only listeners**

```bash
ss -ltnp | grep -E ':(8764|8765|8766|8770)\b'
```

Expected: each listener bound to loopback only.

- [ ] **Step 7: Verify service state**

```bash
systemctl --user --no-pager --full status   dio-apps.target   dio-launcher.service   dio-control-deck.service   dio-goldeneye.service   dio-market-command.service
```

Expected: target and four services active.

- [ ] **Step 8: Commit any narrowly required verification fix**

If verification required a code change, first add a failing regression test, implement only that fix, rerun the focused suite, and commit the named affected files. If no change was needed, do not create an empty commit.
