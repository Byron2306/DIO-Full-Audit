from adapters.marketing import youtube_organic


def test_oauth_credentials_do_not_imply_verified_publish_transport(
    monkeypatch, tmp_path
):
    empty_env = tmp_path / ".env"
    empty_env.write_text("")

    monkeypatch.setenv("NICHEFOUNDRY_ENV_FILE", str(empty_env))

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-api-key")
    monkeypatch.setenv("YOUTUBE_CHANNEL_ID", "test-channel")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "test-client")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "test-refresh")

    status = youtube_organic.readiness()

    assert status["state"] == "ready_read_only"
    assert status["publish_credentials_configured"] is True
    assert status["publish_transport_ready"] is False
    assert status["publish_auth_state"] == "verification_required"


def test_missing_oauth_credentials_report_credentials_required(
    monkeypatch, tmp_path
):
    empty_env = tmp_path / ".env"
    empty_env.write_text("")

    monkeypatch.setenv("NICHEFOUNDRY_ENV_FILE", str(empty_env))

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-api-key")
    monkeypatch.setenv("YOUTUBE_CHANNEL_ID", "test-channel")

    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)

    status = youtube_organic.readiness()

    assert status["state"] == "ready_read_only"
    assert status["publish_credentials_configured"] is False
    assert status["publish_transport_ready"] is False
    assert status["publish_auth_state"] == "credentials_required"
