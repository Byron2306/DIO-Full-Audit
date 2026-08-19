from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_campaign_media_v3.py"


def test_v3_media_script_bootstraps_repo_root_for_direct_execution() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ROOT = Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(ROOT))" in source
    assert "from scripts import build_campaign_media as legacy" in source
