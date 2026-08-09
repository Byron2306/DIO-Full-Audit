from backend.services.runtime_environment import current_environment, is_lab_like, is_production_like


def test_current_environment_prefers_environment_over_arda_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "Production")
    monkeypatch.setenv("ARDA_ENV", "lab")

    assert current_environment() == "production"


def test_current_environment_falls_back_to_arda_env(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ARDA_ENV", "Demo")

    assert current_environment() == "demo"
    assert is_lab_like() is True


def test_production_like_detects_prod_and_strict(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("SERAPH_STRICT_SECURITY", raising=False)
    monkeypatch.delenv("MCP_STRICT_SECURITY", raising=False)
    assert is_production_like() is True

    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("SERAPH_STRICT_SECURITY", "true")
    assert is_production_like() is True


def test_lab_like_is_false_for_non_lab_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("ARDA_ENV", raising=False)

    assert is_lab_like() is False
