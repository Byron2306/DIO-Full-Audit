from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRESENCE_SERVER_PATH = ROOT / "backend" / "services" / "presence_server.py"


def test_presence_legacy_triune_fallback_is_explicitly_opt_in():
    content = PRESENCE_SERVER_PATH.read_text()

    assert 'FEATURE_LEGACY_PRESENCE_TRIUNE_FALLBACK = _env_flag("SOPHIA_ENABLE_LEGACY_PRESENCE_TRIUNE_FALLBACK", False)' in content
    assert 'if FEATURE_LEGACY_PRESENCE_TRIUNE_FALLBACK:' in content
    assert 'return _bounded_triune_compatibility_response(' in content
    assert 'Presence legacy Triune fallback explicitly enabled for compatibility mode' in content


def test_presence_legacy_triune_contract_is_marked_non_canonical():
    content = PRESENCE_SERVER_PATH.read_text()

    assert "Legacy compatibility-only Triune evaluation for Presence." in content
    assert "This is not a canonical governance authority path and must remain opt-in." in content
