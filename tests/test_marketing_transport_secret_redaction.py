from adapters.marketing.base import redact_url_secrets


def test_redact_url_secrets_removes_sensitive_query_values():
    url = (
        "https://example.com/path?"
        "access_token=meta-secret&"
        "key=youtube-secret&"
        "client_secret=oauth-secret&"
        "safe=value"
    )

    result = redact_url_secrets(url)

    assert "meta-secret" not in result
    assert "youtube-secret" not in result
    assert "oauth-secret" not in result
    assert "safe=value" in result
    assert result.count("%3CREDACTED%3E") == 3


def test_redact_url_secrets_preserves_non_sensitive_url_components():
    url = "https://example.com/path?fields=id%2Cname&page=2"

    result = redact_url_secrets(url)

    assert result.startswith("https://example.com/path?")
    assert "fields=id%2Cname" in result
    assert "page=2" in result
