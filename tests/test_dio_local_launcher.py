from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMD = ROOT / "deploy" / "systemd"


def _launcher():
    return importlib.import_module("dio_launcher")


def _script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(f"dio_test_{name.replace('.', '_')}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ready_state() -> dict:
    return {
        "surfaces": [
            {"id": "goldeneye", "ready": True},
            {"id": "control-deck", "ready": True},
            {"id": "market-command", "ready": True},
            {"id": "production-studio", "ready": True},
        ],
        "portfolio": {"verified": True},
        "ready": True,
    }


def test_dio_apps_target_groups_launcher_and_three_surface_services():
    target = (SYSTEMD / "dio-apps.target").read_text(encoding="utf-8")
    wanted = (
        "Wants=dio-launcher.service dio-control-deck.service "
        "dio-goldeneye.service dio-market-command.service"
    )
    after = (
        "After=dio-launcher.service dio-control-deck.service "
        "dio-goldeneye.service dio-market-command.service"
    )
    assert wanted in target
    assert after in target


def test_dio_surface_services_are_local_and_distinct():
    expected = {
        "dio-control-deck.service": ("serve_business_workbench.py", "--port 8765"),
        "dio-goldeneye.service": ("serve_goldeneye_ms10.py", "--port 8766"),
        "dio-market-command.service": ("serve_market_command_ms10.py", "--port 8770"),
        "dio-launcher.service": ("serve_dio_launcher.py", "--port 8764"),
    }
    for name, markers in expected.items():
        unit = (SYSTEMD / name).read_text(encoding="utf-8")
        assert "--host 127.0.0.1" in unit
        assert markers[0] in unit
        assert markers[1] in unit
        assert "PYTHONNOUSERSITE=1" in unit
        assert "PartOf=dio-apps.target" in unit


def test_surface_catalog_exposes_four_apps_on_three_services():
    rows = _launcher().surface_catalog()
    assert [row["id"] for row in rows] == [
        "goldeneye",
        "control-deck",
        "market-command",
        "production-studio",
    ]
    assert rows[0]["url"] == "http://127.0.0.1:8766/"
    assert rows[1]["url"] == "http://127.0.0.1:8765/"
    assert rows[2]["url"] == "http://127.0.0.1:8770/"
    assert rows[3]["url"] == "http://127.0.0.1:8765/dashboard/production.html"
    assert rows[1]["service"] == rows[3]["service"] == "dio-control-deck.service"


def test_portfolio_truth_requires_exact_verified_components_and_row_count():
    truth = _launcher().portfolio_truth
    verified = {
        "base_canonical_incarnation_count": 53,
        "canon_extension_count": 15,
        "canonical_incarnation_count": 68,
        "extension_summary_state": "VERIFIED",
        "incarnations": [{}] * 68,
    }
    assert truth(verified)["verified"] is True

    missing = {
        "base_canonical_incarnation_count": 53,
        "canon_extension_count": 0,
        "canonical_incarnation_count": 53,
        "extension_summary_state": "MISSING",
        "incarnations": [{}] * 53,
    }
    assert truth(missing)["verified"] is False

    wrong_rows = dict(verified)
    wrong_rows["incarnations"] = [{}] * 67
    assert truth(wrong_rows)["verified"] is False


def test_launcher_state_reuses_shared_business_probe(monkeypatch):
    launcher = _launcher()
    calls: list[str] = []

    def fake_probe(url: str, timeout: float = 1.0):
        calls.append(url)
        if ":8765/" in url:
            if url.endswith("/api/business/portfolio"):
                return {
                    "ready": True,
                    "status": 200,
                    "payload": {
                        "base_canonical_incarnation_count": 53,
                        "canon_extension_count": 15,
                        "canonical_incarnation_count": 68,
                        "extension_summary_state": "VERIFIED",
                        "incarnations": [{}] * 68,
                    },
                }
            return {"ready": True, "status": 200, "payload": {"status": "ok"}}
        return {"ready": False, "error": "unavailable"}

    monkeypatch.setattr(launcher, "probe_url", fake_probe)
    state = launcher.launcher_state()
    by_id = {row["id"]: row for row in state["surfaces"]}

    assert by_id["control-deck"]["ready"] is True
    assert by_id["production-studio"]["ready"] is True
    assert by_id["goldeneye"]["ready"] is False
    assert by_id["market-command"]["ready"] is False
    assert state["portfolio"]["verified"] is True
    assert state["ready"] is False
    assert calls.count("http://127.0.0.1:8765/api/business/health") == 1


def test_launcher_server_is_read_only_localhost_only_and_names_four_apps():
    server = (ROOT / "scripts" / "serve_dio_launcher.py").read_text(encoding="utf-8")
    page = (ROOT / "dashboard" / "dio-launcher.html").read_text(encoding="utf-8")

    assert "/api/launcher/state" in server
    assert "launcher_state" in server
    assert "127.0.0.1" in server and "localhost" in server and "::1" in server
    assert "def do_POST" in server and "405" in server
    for name in ("GoldenEye", "Control Deck", "Market Command", "Production Studio"):
        assert name in page
    assert "53 + 15 = 68" in page
    assert "/api/launcher/state" in page
    assert "Start service" not in page
    assert "Restart service" not in page


def test_launch_command_starts_target_then_opens_verified_launcher(monkeypatch):
    launch = _script("launch_dio_apps.py")
    starts: list[list[str]] = []
    opened: list[str] = []

    def fake_run(command, check):
        starts.append(list(command))
        return None

    monkeypatch.setattr(launch.subprocess, "run", fake_run)
    monkeypatch.setattr(launch, "fetch_launcher_state", lambda: _ready_state())
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: opened.append(url) or True)

    assert launch.launch_apps(timeout_seconds=1.0, open_browser=True) == 0
    assert starts == [["systemctl", "--user", "start", "dio-apps.target"]]
    assert opened == ["http://127.0.0.1:8764/"]


def test_launch_command_times_out_without_opening_browser(monkeypatch, capsys):
    launch = _script("launch_dio_apps.py")
    unavailable = {
        "surfaces": [
            {"id": "goldeneye", "name": "GoldenEye", "ready": False},
            {"id": "control-deck", "name": "Control Deck", "ready": True},
            {"id": "market-command", "name": "Market Command", "ready": True},
            {"id": "production-studio", "name": "Production Studio", "ready": True},
        ],
        "portfolio": {"verified": False, "summary": "53 + 0 = 53"},
        "ready": False,
    }
    opened: list[str] = []

    monkeypatch.setattr(launch.subprocess, "run", lambda command, check: None)
    monkeypatch.setattr(launch, "fetch_launcher_state", lambda: unavailable)
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: opened.append(url) or True)

    assert launch.launch_apps(timeout_seconds=0.0, open_browser=True) == 2
    assert opened == []
    output = capsys.readouterr().out
    assert "GoldenEye" in output
    assert "53 + 0 = 53" in output


def test_desktop_entry_and_installer_are_user_local_and_bounded(tmp_path):
    desktop = (ROOT / "deploy" / "desktop" / "dio-apps.desktop").read_text(encoding="utf-8")
    installer_text = (ROOT / "scripts" / "install_dio_launcher.py").read_text(encoding="utf-8")

    assert "Type=Application" in desktop
    assert "Name=DIO" in desktop
    assert "Terminal=false" in desktop
    assert "scripts/launch_dio_apps.py" in desktop
    assert "Categories=Development;Office;" in desktop
    assert "dio-apps.target" in installer_text
    assert ".config/systemd/user" in installer_text
    assert ".local/share/applications" in installer_text

    installer = _script("install_dio_launcher.py")
    installed = installer.install(destination_home=tmp_path, invoke_systemd=False)
    expected = {
        tmp_path / ".config/systemd/user/dio-launcher.service",
        tmp_path / ".config/systemd/user/dio-control-deck.service",
        tmp_path / ".config/systemd/user/dio-goldeneye.service",
        tmp_path / ".config/systemd/user/dio-market-command.service",
        tmp_path / ".config/systemd/user/dio-apps.target",
        tmp_path / ".local/share/applications/dio-apps.desktop",
    }
    assert set(installed) == expected
    assert all(path.is_file() for path in expected)
