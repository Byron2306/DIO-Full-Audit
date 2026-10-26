from __future__ import annotations

import json
from pathlib import Path

from scripts.gamma_primary_visual_bridge import _gamma_cards


def _variant(tmp_path: Path, *, request_hash: str = "REQ-1", receipt_hash: str = "REQ-1", count: int = 3) -> dict:
    cards = []
    for index in range(count):
        path = tmp_path / f"card-{index + 1}.png"
        path.write_bytes(b"png-placeholder")
        cards.append({"path": str(path)})
    receipt = tmp_path / "GAMMA_STORY_RECEIPT.json"
    receipt.write_text(
        json.dumps({"state": "ready", "request_hash": receipt_hash, "cards": cards}),
        encoding="utf-8",
    )
    return {"gamma": {"receipt": str(receipt), "request_hash": request_hash}}


def test_gamma_cards_require_explicit_operator_enable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DIO_GAMMA_VISUAL_CANDIDATE", raising=False)
    assert _gamma_cards(_variant(tmp_path), 3) == []


def test_gamma_cards_selected_when_enabled_and_bound(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DIO_GAMMA_VISUAL_CANDIDATE", "1")
    cards = _gamma_cards(_variant(tmp_path), 3)
    assert len(cards) == 3
    assert all(path.is_file() for path in cards)


def test_gamma_cards_refuse_stale_request_hash(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DIO_GAMMA_VISUAL_CANDIDATE", "true")
    assert _gamma_cards(_variant(tmp_path, request_hash="REQ-NEW", receipt_hash="REQ-OLD"), 3) == []


def test_gamma_cards_refuse_wrong_scene_count(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DIO_GAMMA_VISUAL_CANDIDATE", "yes")
    assert _gamma_cards(_variant(tmp_path, count=2), 3) == []
