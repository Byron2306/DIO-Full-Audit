import json
from pathlib import Path

import pytest

from market_command.agency import list_agency_outreach, prepare_agency_rfq
from market_command.core import MarketStore


CONFIG = {
    "default_experiment_window_days": 14,
    "max_experiment_budget_minor": 0,
    "promotion_min_qualified_leads": 5,
    "promotion_min_paid_orders": 2,
    "promotion_min_roas": 1.5,
    "kill_min_spend_minor": 50000,
    "revise_min_clicks": 50,
}


def make_root(tmp_path: Path, registry: dict) -> tuple[Path, MarketStore]:
    root = tmp_path / "dio"
    (root / "config").mkdir(parents=True)
    (root / "config" / "agency_partner_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (root / "config" / "marketing_channels.json").write_text('{"channels": []}', encoding="utf-8")
    (root / "config" / "sa_media_marketplace.json").write_text('{"vendors": []}', encoding="utf-8")
    (root / "config" / "market_command.json").write_text("{}", encoding="utf-8")
    store = MarketStore(root / "state" / "market_command" / "market.sqlite", root / "telemetry" / "events.jsonl", CONFIG)
    return root, store


def campaign(store: MarketStore) -> dict:
    return store.create_campaign({
        "product_line_id": "HOMS_ASSESS",
        "name": "HOMS controlled pilot",
        "audience": "South African secondary schools",
        "channel_id": "SA_MEDIA_BUY",
        "objective": "qualified pilot conversation",
    })


def test_verified_email_agency_creates_governed_rfq_and_mail_intent(tmp_path: Path):
    registry = {"partners": [{
        "id": "TEST_AGENCY",
        "name": "Test Agency",
        "status": "public_route_verified",
        "inquiry": {"mode": "email", "email": "hello@example.test", "url": "https://example.test/contact", "permission": "single_rfq_only"},
    }]}
    root, store = make_root(tmp_path, registry)
    item = prepare_agency_rfq(root, store, campaign(store)["campaign_id"], "TEST_AGENCY", "measurable education pilot", "test operator", True)
    assert item["state"] == "mail_intent_ready"
    assert item["mail_intent_id"].startswith("MAIL-")
    intent = json.loads((root / "state" / "mail_intents" / f"{item['mail_intent_id']}.json").read_text())
    assert intent["approval"]["state"] == "pending"
    assert intent["send_state"] == "draft"
    assert Path(intent["attachments"][0]).name == "MEDIA_BUY_BRIEF.md"
    brief = Path(item["brief_dir"]) / "MEDIA_BUY_BRIEF.md"
    assert "not** a booking or spend authorization" in brief.read_text()
    assert len(list_agency_outreach(root)) == 1


def test_research_only_agency_is_blocked(tmp_path: Path):
    root, store = make_root(tmp_path, {"partners": [{
        "id": "UNQUALIFIED",
        "name": "Unqualified",
        "status": "directory_verified_research_only",
        "inquiry": {"mode": "research", "permission": "none_recorded"},
    }]})
    with pytest.raises(ValueError, match="research-only"):
        prepare_agency_rfq(root, store, campaign(store)["campaign_id"], "UNQUALIFIED", "", "test", True)


def test_quote_spend_and_provider_report_are_separate_gates(tmp_path: Path):
    root, store = make_root(tmp_path, {"partners": []})
    current = campaign(store)
    buy = store.create_media_buy({
        "vendor_id": "TEST_AGENCY",
        "product_line_id": current["product_line_id"],
        "campaign_id": current["campaign_id"],
        "placement": "paid social pilot",
    })
    quote = store.record_media_quote(buy["media_buy_id"], 25000, "quote-email-001", 25000)
    assert quote["state"] == "quote_received"
    with pytest.raises(ValueError, match="held"):
        store.approve_media_buy(buy["media_buy_id"], True)
    store.set_policy("agency_spend", "release")
    approved = store.approve_media_buy(buy["media_buy_id"], True)
    assert approved["approval_state"] == "approved"
    result = store.record_media_result(buy["media_buy_id"], "provider-report-001", {"impressions": 1000, "clicks": 17, "spend_minor": 24000})
    assert result["media_buy"]["state"] == "reported"
    assert store.aggregate_metrics(current["campaign_id"])["clicks"] == 17
