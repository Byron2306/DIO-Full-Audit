from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_business_never_builds_raw_absolute_filesystem_href():
    page = text("dashboard/business.html")
    assert "'/api/business/artifact?path='" in page
    assert 'href="//home/' not in page
    assert "Browse output" in page


def test_business_has_direct_human_actions_not_only_embedded_console():
    page = text("dashboard/business.html")
    required = (
        "setPolicy(",
        "jobAction(",
        "leadAction(",
        "openLead(",
        "mailAction(",
        "Approve & SEND",
        "Issue invoice / quote",
        "Promote to job",
    )
    for marker in required:
        assert marker in page


def test_market_has_explicit_create_to_settle_workflow():
    page = text("dashboard/market.html")
    for marker in (
        "1 CREATE",
        "2 APPROVE",
        "3 CONTENT",
        "4 APPROVE",
        "5 RELEASE",
        "6 ACTIVE",
        "7 SETTLE",
        "Approve campaign",
        "Add content",
        "Release paid media",
        "Release organic",
        "Activate",
        "Record results",
        "Settle",
    ):
        assert marker in page


def test_artifact_gateway_allows_repo_and_blocks_arbitrary_absolute_paths():
    from scripts.serve_control_deck_ms10 import ROOT as SERVER_ROOT, _resolve_artifact

    assert _resolve_artifact("README.md") == (SERVER_ROOT / "README.md").resolve()
    with pytest.raises(ValueError):
        _resolve_artifact("/etc/passwd")
