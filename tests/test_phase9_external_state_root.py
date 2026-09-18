from __future__ import annotations

import importlib
from pathlib import Path

from presence_core.config import load_config


def test_presence_config_can_bind_external_state_root(monkeypatch, tmp_path: Path):
    state = tmp_path / "durable"
    monkeypatch.setenv("DIO_STATE_ROOT", str(state))
    cfg = load_config()
    assert Path(cfg["state_root"]) == state.resolve() / "presence"


def test_presence_config_defaults_to_repo_local_state(monkeypatch):
    monkeypatch.delenv("DIO_STATE_ROOT", raising=False)
    cfg = load_config()
    assert cfg["state_root"] == "state/presence"


def test_phase9_pollers_honor_external_state_root(monkeypatch, tmp_path: Path):
    state = tmp_path / "durable"
    monkeypatch.setenv("DIO_STATE_ROOT", str(state))

    import scripts.poll_vesper_telegram as telegram
    import scripts.sync_outlook_mail as outlook
    import scripts.reconcile_paypal_local as paypal

    telegram = importlib.reload(telegram)
    outlook = importlib.reload(outlook)
    paypal = importlib.reload(paypal)

    assert telegram.STATE_BASE == state
    assert outlook.DEFAULT_DELTA_STATE == state / "microsoft_graph" / "mail_delta.json"
    assert outlook.DEFAULT_INGRESS_DIR == state / "mail_ingress"
    assert paypal.DEFAULT_ORDER_DIR == state / "commerce" / "orders"
    assert paypal.DEFAULT_RECEIPT_DIR == state / "commerce" / "payment_events"
