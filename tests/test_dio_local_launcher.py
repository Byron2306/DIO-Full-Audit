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
