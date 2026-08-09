import json
import sqlite3

from presence_core.engine import process_envelope
from presence_core.policy import authorize
from presence_core.router import route_message
from presence_core.state import operator_summary


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_market_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        "create table campaigns (campaign_id text primary key, created_at text, updated_at text, product_line_id text, offer_id text, name text, audience text, channel_id text, mode text, objective text, landing_page text, proof_asset text, creative_brief text, budget_cap_minor integer, currency text, state text, approval_state text, publication_state text, experiment_window_days integer, utm_json text, governance_json text)"
    )
    cur.execute(
        "create table content_items (content_id text primary key, campaign_id text, created_at text, channel_id text, format text, hook text, body text, asset_path text, state text, approval_state text, external_url text, source_language text, target_language text, semantic_object_id text, content_hash text, language_state text)"
    )
    cur.execute(
        "create table measurements (measurement_id text primary key, campaign_id text, recorded_at text, impressions integer, reach integer, clicks integer, enquiries integer, qualified_leads integer, orders integer, paid_orders integer, spend_minor integer, revenue_minor integer, manual_minutes real, source text, raw_json text)"
    )
    cur.execute(
        "insert into campaigns values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("CMP-1", "now", "now", "HOMS_ASSESS", None, "HOMS proof", "teachers", "LINKEDIN_ORGANIC", "organic", "leads", None, None, None, 0, "ZAR", "active", "approved", "released", 14, "{}", "{}"),
    )
    cur.execute(
        "insert into content_items values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("CNT-1", "CMP-1", "now", "LINKEDIN_ORGANIC", "post", "hook", "body", "asset.jpg", "draft", "pending", None, "English", None, None, "abc", "source_ready"),
    )
    cur.execute(
        "insert into measurements values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("M-1", "CMP-1", "now", 100, 90, 12, 3, 2, 1, 1, 0, 4900, 15.0, "test", "{}"),
    )
    conn.commit()
    conn.close()


def test_operator_summary_reads_dio_operating_state(tmp_path):
    root = tmp_path
    presence_root = root / "state" / "presence"
    write_json(
        root / "state" / "product_jobs" / "JOB-1" / "JOB.json",
        {
            "job_id": "JOB-1",
            "product": "homs",
            "state": "active",
            "processing": {"state": "review_ready"},
            "notification": {"state": "draft_ready", "mail_intent_id": "MAIL-1"},
        },
    )
    write_json(
        root / "state" / "mail_intents" / "MAIL-1.json",
        {
            "mail_intent_id": "MAIL-1",
            "purpose": "delivery",
            "recipient": "client@example.com",
            "subject": "Your pack",
            "send_state": "draft_ready",
            "approval": {"state": "pending"},
            "risk": "moderate",
        },
    )
    write_json(
        root / "state" / "commerce" / "live" / "orders" / "ORD-1.json",
        {"order_id": "ORD-1", "payment_state": "paid", "provider": "paypal", "amount_minor": 100, "currency": "USD", "fulfilment_released": False},
    )
    write_json(presence_root / "needs_you" / "NY-1.json", {"needs_you_id": "NY-1", "state": "open", "summary": "Approve delivery"})
    write_json(root / "state" / "leads" / "LEAD-1.json", {"lead_id": "LEAD-1"})
    write_json(root / "state" / "incidents" / "INC-1.json", {"incident_id": "INC-1"})
    make_market_db(root / "state" / "market_command" / "market_command.sqlite")

    summary = operator_summary(root, presence_root)
    assert summary["schema"] == "dio.presence.operator_brief.v1"
    assert summary["jobs"]["total"] == 1
    assert summary["mail"]["pending"] == 1
    assert summary["commerce"]["live_paid"] == 1
    assert summary["commerce"]["paid_unreleased"] == 1
    assert summary["market"]["active"] == 1
    assert summary["market"]["content_awaiting_approval"] == 1
    assert summary["leads"]["total"] == 1
    assert summary["incidents"]["open_or_recorded"] == 1
    assert summary["authority"]["can_send_mail"] is False


def test_operator_can_request_focused_pa_briefs(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "telemetry").mkdir()
    (tmp_path / "config" / "routes.json").write_text('{"routes":[]}', encoding="utf-8")
    monkeypatch.setenv("DIO_OPERATOR_TELEGRAM_IDS", "777")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    cfg = {"state_root": "state/presence", "event_log": "telemetry/dio_events.jsonl", "routes_path": "config/routes.json"}
    response = process_envelope({"channel": "telegram", "external_user_id": "777", "text": "market command status", "message_type": "text", "_trusted_edge_role": "operator"}, tmp_path, cfg)
    assert response["decision"]["intent"] == "campaign_summary"
    assert "Market Command" in response["reply"]["text"]
    assert response["authority"]["executed_external_action"] is False


def test_document_studio_requests_are_captured_as_intake(tmp_path):
    routes = tmp_path / "routes.json"
    routes.write_text('{"routes":[{"product":"document_studio","keywords":["technical editing","translation","formatting"]}]}', encoding="utf-8")
    decision = route_message("I need technical editing and translation for a policy document", "public", routes)
    assert decision.intent == "intake_request"
    assert decision.product == "document_studio"


def test_public_cannot_access_focused_operator_briefs():
    assert authorize("public", "campaign_summary")[0] is False
    assert authorize("public", "revenue_summary")[0] is False
