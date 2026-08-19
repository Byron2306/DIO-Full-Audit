from __future__ import annotations

import json
import os
from pathlib import Path

import dio_secrets

ROOT = Path(__file__).resolve().parents[1]


def test_secret_vault_is_gitignored_and_connections_surface_exists():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "secrets/" in ignore
    assert (ROOT / "dashboard" / "connections.html").is_file()


def test_tiktok_ads_and_organic_are_separate_secret_contracts():
    registry = json.loads((ROOT / "config" / "secret_registry.json").read_text(encoding="utf-8"))
    providers = {row["id"]: row for row in registry["providers"]}
    ads = providers["TIKTOK_ADS"]
    organic = providers["TIKTOK_ORGANIC"]
    assert ads["required"] == ["TIKTOK_ACCESS_TOKEN", "TIKTOK_ADVERTISER_ID"]
    assert "TIKTOK_APP_ID" in ads["optional"]
    assert "TIKTOK_APP_SECRET" in ads["optional"]
    assert ads["authority"] == "reporting_only"
    assert "TIKTOK_USER_ACCESS_TOKEN" in organic["optional"]
    assert "TIKTOK_OPEN_ID" in organic["optional"]
    assert organic["authority"] == "human_publish_until_content_posting_api_approved"


def test_connections_page_has_tiktok_business_and_ads_manager_links():
    page = (ROOT / "dashboard" / "connections.html").read_text(encoding="utf-8")
    server = (ROOT / "scripts" / "serve_control_deck_ms10.py").read_text(encoding="utf-8")
    for marker in (
        "https://business.tiktok.com/",
        "https://ads.tiktok.com/",
        "/api/business/secrets",
        "TIKTOK_ACCESS_TOKEN",
        "TIKTOK_ADVERTISER_ID",
    ):
        assert marker in page
    assert "Connections & Secrets" in server
    assert "TikTok Business" in server
    assert "TikTok Ads" in server


def test_secret_save_is_0600_status_never_returns_values_and_round_trip_is_exact(tmp_path, monkeypatch):
    vault = tmp_path / "secrets" / "dio.env"
    monkeypatch.setattr(dio_secrets, "SECRET_FILE", vault)
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TIKTOK_ADVERTISER_ID", raising=False)
    token = 'VERY-SECRET-"TOKEN"-WITH\\BACKSLASH-TEST-ONLY'
    result = dio_secrets.save_secret_values({
        "TIKTOK_ACCESS_TOKEN": token,
        "TIKTOK_ADVERTISER_ID": "1234567890",
    })
    assert result["mode"] == "0600"
    assert oct(vault.stat().st_mode & 0o777) == "0o600"
    assert token not in vault.read_text(encoding="utf-8")
    assert dio_secrets._parse_env(vault)["TIKTOK_ACCESS_TOKEN"] == token
    status = dio_secrets.secret_status()
    encoded = json.dumps(status)
    assert token not in encoded
    assert status["values_returned"] is False
    tiktok = next(row for row in status["providers"] if row["id"] == "TIKTOK_ADS")
    assert tiktok["state"] == "ready"
    assert tiktok["missing_required"] == []
    os.environ.pop("TIKTOK_ACCESS_TOKEN", None)
    os.environ.pop("TIKTOK_ADVERTISER_ID", None)


def test_marketing_adapter_loads_canonical_vault_before_environment_lookup():
    source = (ROOT / "adapters" / "marketing" / "base.py").read_text(encoding="utf-8")
    readiness = (ROOT / "adapters" / "marketing" / "readiness.py").read_text(encoding="utf-8")
    assert "load_secret_env(overwrite=False)" in source
    assert "load_secret_env(overwrite=False)" in readiness
