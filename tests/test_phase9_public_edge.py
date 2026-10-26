from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import scripts.serve_public_edge_local as edge


def _payload() -> dict:
    return {
        "schema": "dio.public_intake.v1",
        "website_honeypot": "",
        "product": "sophia",
        "offer": "section_review",
        "contact": {
            "name": "Test Customer",
            "email": "customer@example.org",
            "organisation": "Example",
        },
        "request": {
            "outcome": "Review one controlled section",
        },
        "consents": {
            "contact": True,
        },
        "attribution": {
            "source": "phase9-test",
        },
    }


def test_local_public_intake_is_durable_and_idempotent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(edge, "DB_PATH", tmp_path / "public-intake.sqlite")
    monkeypatch.setenv("DIO_PUBLIC_SITE_ORIGIN", "https://site.example")
    materialized = []

    def fake_materialize(**kwargs):
        materialized.append(kwargs)
        return None

    monkeypatch.setattr(edge, "_materialize", fake_materialize)
    client = TestClient(edge.app)
    headers = {"Origin": "https://site.example"}

    first = client.post("/api/public/intake", json=_payload(), headers=headers)
    assert first.status_code == 201
    body = first.json()
    assert body["state"] == "received"
    assert body["cloudflare_used"] is False
    assert body["automatic_processing"] is False
    assert len(materialized) == 1

    second = client.post("/api/public/intake", json=_payload(), headers=headers)
    assert second.status_code == 200
    assert second.json()["lead_id"] == body["lead_id"]
    assert second.json()["duplicate"] is True
    assert len(materialized) == 1


def test_local_public_intake_refuses_wrong_origin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(edge, "DB_PATH", tmp_path / "public-intake.sqlite")
    monkeypatch.setenv("DIO_PUBLIC_SITE_ORIGIN", "https://site.example")
    client = TestClient(edge.app)
    response = client.post(
        "/api/public/intake",
        json=_payload(),
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403


def test_static_public_intake_has_no_hardcoded_cloudflare_endpoint() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "sites"
        / "assets"
        / "dio-public-intake.js"
    ).read_text(encoding="utf-8")
    assert "workers.dev" not in source
    assert "DIO_PUBLIC_INTAKE_ENDPOINT" in source
    assert "public_intake_api_not_configured" in source
