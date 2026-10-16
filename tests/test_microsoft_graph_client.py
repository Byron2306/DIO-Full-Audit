from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from adapters.microsoft_graph.client import GraphClient


def test_graph_request_uses_acquired_bearer_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = GraphClient(
        {
            "client_id": "test-client-id",
            "token_cache_path": str(tmp_path / "token-cache.json"),
        }
    )
    monkeypatch.setattr(graph, "acquire_token", lambda interactive=False: "test-access-token")
    captured: dict = {}

    def fake_request(method: str, url: str, *, headers: dict, timeout: int) -> SimpleNamespace:
        captured.update(method=method, url=url, headers=headers, timeout=timeout)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr("adapters.microsoft_graph.client.requests.request", fake_request)

    graph.request("GET", "/me")

    assert captured["method"] == "GET"
    assert captured["url"] == "https://graph.microsoft.com/v1.0/me"
    assert captured["headers"]["Authorization"] == "Bearer test-access-token"
