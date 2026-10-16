from __future__ import annotations

from pathlib import Path

from scripts.run_hivenance_market_agents import (
    BUNDLED_HIVENANCE_ROOT,
    resolve_hivenance_root,
)


def test_hivenance_runner_falls_back_to_bundled_runtime_when_configured_path_is_missing(
    tmp_path: Path,
) -> None:
    assert resolve_hivenance_root(tmp_path) == BUNDLED_HIVENANCE_ROOT


def test_hivenance_runner_prefers_configured_runtime_when_available(
    tmp_path: Path,
) -> None:
    module = tmp_path / "agents" / "market_intelligence.py"
    module.parent.mkdir(parents=True)
    module.write_text("def assess_market_campaign(context): return context\n", encoding="utf-8")

    assert resolve_hivenance_root(tmp_path) == tmp_path
