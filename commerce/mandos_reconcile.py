from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mandos import MandosLedger, commercial_outcome, source_state


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _time(value: Any) -> str:
    parsed = _parse_time(value)
    return parsed.replace(microsecond=0).isoformat() if parsed else datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _strategy(transaction: dict[str, Any], intent: dict[str, Any] | None = None) -> dict[str, Any]:
    intent = intent or {}
    binding = intent.get("semantic_binding") or {}
    attribution = transaction.get("attribution") or {}
    return {
        "product": transaction.get("product"),
        "offer": transaction.get("offer"),
        "communicative_act": intent.get("communicative_act") or binding.get("communicative_act"),
        "channel": "email" if intent else attribution.get("medium"),
        "audience": attribution.get("audience") or attribution.get("segment"),
        "tactic_id": binding.get("tactic_id"),
        "proof_family": binding.get("proof_family"),
    }


def _lineage(transaction: dict[str, Any], intent: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(transaction.get("lineage") or {})
    intent = intent or {}
    binding = intent.get("semantic_binding") or {}
    judgement = intent.get("semantic_judgement") or {}
    return {
        "transaction_id": transaction.get("transaction_id"),
        "campaign_id": base.get("campaign_id") or intent.get("campaign_id"),
        "lead_id": base.get("lead_id") or intent.get("lead_id"),
        "conversation_id": base.get("conversation_id") or intent.get("conversation_id"),
        "job_id": base.get("job_id") or intent.get("job_id"),
        "order_id": base.get("order_id") or intent.get("order_id"),
        "mail_intent_id": intent.get("mail_intent_id"),
        "semantic_object_id": binding.get("semantic_object_id"),
        "semantic_judgement_id": judgement.get("judgement_id"),
    }


def _state_rows(root: Path, paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        if path.is_file():
            rows.append(source_state(path, root))
    return rows


def _load_intents(root: Path, transaction: dict[str, Any]) -> list[tuple[dict[str, Any], Path]]:
    rows = []
    for intent_id in (transaction.get("lineage") or {}).get("mail_intent_ids") or []:
        if not intent_id:
            continue
        path = root / "state" / "mail_intents" / f"{intent_id}.json"
        if path.is_file():
            rows.append((_read(path), path))
    return rows


def _load_ingress(root: Path, transaction: dict[str, Any]) -> list[tuple[dict[str, Any], Path]]:
    rows = []
    for ingress_id in (transaction.get("intake") or {}).get("message_ids") or []:
        if not ingress_id:
            continue
        path = root / "state" / "mail_ingress" / f"{ingress_id}.json"
        if path.is_file():
            rows.append((_read(path), path))
    return rows


def _nearest_prior_sent(
    ingress: dict[str, Any],
    intents: list[tuple[dict[str, Any], Path]],
) -> tuple[dict[str, Any], Path] | None:
    received = _parse_time(ingress.get("received_at") or ingress.get("captured_at"))
    if received is None:
        return None
    candidates = []
    for intent, path in intents:
        if intent.get("send_state") != "sent":
            continue
        sent = _parse_time(intent.get("sent_at") or intent.get("updated_at"))
        if sent and sent < received:
            candidates.append((sent, intent, path))
    if not candidates:
        return None
    _, intent, path = max(candidates, key=lambda row: row[0])
    return intent, path


def reconcile_transaction(root: Path, transaction: dict[str, Any], ledger: MandosLedger | None = None) -> dict[str, Any]:
    root = root.resolve()
    ledger = ledger or MandosLedger(root)
    created: list[str] = []
    reused: list[str] = []
    intent_rows = _load_intents(root, transaction)
    ingress_rows = _load_ingress(root, transaction)
    lead_id = str((transaction.get("lineage") or {}).get("lead_id") or "")
    lead_path = root / "state" / "leads" / f"{lead_id}.json" if lead_id else None

    def remember(outcome: dict[str, Any]) -> None:
        stored, was_created = ledger.record(outcome)
        (created if was_created else reused).append(stored["outcome_id"])

    for intent, intent_path in intent_rows:
        if intent.get("send_state") != "sent":
            continue
        remember(commercial_outcome(
            outcome_type="delivery_sent" if intent.get("purpose") == "delivery" else "outbound_sent",
            lineage=_lineage(transaction, intent),
            source_refs=[f"mail_intent:{intent.get('mail_intent_id')}"],
            source_classes=["outbound_mail_receipt"],
            occurred_at=_time(intent.get("sent_at") or intent.get("updated_at")),
            polarity="neutral",
            strategy=_strategy(transaction, intent),
            detail={"purpose": intent.get("purpose"), "send_state": "sent"},
            source_states=_state_rows(root, [intent_path]),
        ))

    for ingress, ingress_path in ingress_rows:
        prior = _nearest_prior_sent(ingress, intent_rows)
        if prior is None:
            continue
        prior_intent, prior_path = prior
        refs = [
            f"mail_ingress:{ingress.get('mail_ingress_id')}",
            f"mail_intent:{prior_intent.get('mail_intent_id')}",
        ]
        classes = ["outlook_ingress", "outbound_mail_receipt"]
        remember(commercial_outcome(
            outcome_type="reply_received",
            lineage=_lineage(transaction, prior_intent),
            source_refs=refs,
            source_classes=classes,
            occurred_at=_time(ingress.get("received_at") or ingress.get("captured_at")),
            polarity="positive",
            strategy=_strategy(transaction, prior_intent),
            detail={
                "mail_ingress_id": ingress.get("mail_ingress_id"),
                "in_reply_to_mail_intent_id": prior_intent.get("mail_intent_id"),
            },
            source_states=_state_rows(root, [ingress_path, prior_path]),
        ))
        if prior_intent.get("purpose") == "delivery":
            remember(commercial_outcome(
                outcome_type="delivery_acknowledged",
                lineage=_lineage(transaction, prior_intent),
                source_refs=refs,
                source_classes=["customer_acknowledgement", "outbound_mail_receipt"],
                occurred_at=_time(ingress.get("received_at") or ingress.get("captured_at")),
                polarity="positive",
                strategy=_strategy(transaction, prior_intent),
                detail={"mail_ingress_id": ingress.get("mail_ingress_id")},
                source_states=_state_rows(root, [ingress_path, prior_path]),
            ))

    if lead_path and lead_path.is_file():
        lead = _read(lead_path)
        qualification = lead.get("qualification") or {}
        qstate = str(qualification.get("state") or "")
        if qstate in {"qualified", "rejected"} and qualification.get("decided_at"):
            latest_intent = None
            sent = [row for row in intent_rows if row[0].get("send_state") == "sent"]
            if sent:
                latest_intent = max(sent, key=lambda row: _parse_time(row[0].get("sent_at") or row[0].get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc))[0]
            remember(commercial_outcome(
                outcome_type="qualification_changed",
                lineage=_lineage(transaction, latest_intent),
                source_refs=[f"lead:{lead_id}"],
                source_classes=["operator_qualification"],
                occurred_at=_time(qualification.get("decided_at")),
                polarity="positive" if qstate == "qualified" else "negative",
                evidence_state="operator_confirmed",
                strategy=_strategy(transaction, latest_intent),
                detail={"qualification_state": qstate, "decided_by": qualification.get("decided_by")},
                source_states=_state_rows(root, [lead_path]),
            ))

    order_paths = []
    for value in (transaction.get("source_paths") or {}).get("orders") or []:
        if value:
            order_paths.append(Path(value))
    if not order_paths and (transaction.get("lineage") or {}).get("order_id"):
        order_id = str((transaction.get("lineage") or {}).get("order_id"))
        for base in (root / "state" / "commerce" / "orders", root / "state" / "commerce" / "live" / "orders"):
            candidate = base / f"{order_id}.json"
            if candidate.is_file():
                order_paths.append(candidate)

    for order_path in order_paths:
        if not order_path.is_file():
            continue
        order = _read(order_path)
        order_id = str(order.get("order_id") or (transaction.get("lineage") or {}).get("order_id") or "")
        payment_state = str(order.get("payment_state") or order.get("state") or "").lower()
        provider_event_id = str(order.get("provider_event_id") or "")
        payment_event_path = None
        payment_event = None
        if provider_event_id:
            matches = list((root / "state" / "commerce" / "payment_events").glob(f"*-{provider_event_id}.json"))
            if matches:
                payment_event_path = matches[0]
                payment_event = _read(payment_event_path)
        payload = (payment_event or {}).get("payload") or {}
        occurred_at = payload.get("create_time") or (payment_event or {}).get("received_at") or order.get("updated_at") or transaction.get("updated_at")
        latest_intent = None
        sent = [row for row in intent_rows if row[0].get("send_state") == "sent"]
        if sent:
            latest_intent = max(sent, key=lambda row: _parse_time(row[0].get("sent_at") or row[0].get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc))[0]
        lineage = _lineage(transaction, latest_intent)
        lineage["order_id"] = order_id
        if payment_state == "paid":
            remember(commercial_outcome(
                outcome_type="paid_order",
                lineage=lineage,
                source_refs=[f"order:{order_id}", *([f"payment_event:{provider_event_id}"] if provider_event_id else [])],
                source_classes=["payment_order_state", *(["provider_payment_event"] if payment_event else [])],
                occurred_at=_time(occurred_at),
                polarity="positive",
                strategy=_strategy(transaction, latest_intent),
                economics={
                    "currency": order.get("currency") or payload.get("currency") or "ZAR",
                    "revenue_minor": int(order.get("amount_minor") or payload.get("amount_minor") or 0),
                },
                detail={"provider": order.get("provider"), "payment_state": payment_state},
                source_states=_state_rows(root, [order_path, *([payment_event_path] if payment_event_path else [])]),
            ))
        elif payment_state in {"failed", "declined", "cancelled", "canceled"}:
            remember(commercial_outcome(
                outcome_type="payment_failed",
                lineage=lineage,
                source_refs=[f"order:{order_id}"],
                source_classes=["payment_order_state"],
                occurred_at=_time(occurred_at),
                polarity="negative",
                strategy=_strategy(transaction, latest_intent),
                detail={"provider": order.get("provider"), "payment_state": payment_state},
                source_states=_state_rows(root, [order_path]),
            ))

    if transaction.get("stage") == "closed":
        tx_path = root / "state" / "transactions" / str(transaction["transaction_id"]) / "TRANSACTION.json"
        remember(commercial_outcome(
            outcome_type="transaction_closed",
            lineage=_lineage(transaction),
            source_refs=[f"transaction:{transaction['transaction_id']}"],
            source_classes=["commercial_transaction_state"],
            occurred_at=_time(transaction.get("updated_at")),
            polarity="neutral",
            strategy=_strategy(transaction),
            detail={"stage": "closed"},
            source_states=_state_rows(root, [tx_path]),
        ))

    return {
        "transaction_id": transaction.get("transaction_id"),
        "created": created,
        "reused": reused,
    }


def reconcile_market_measurements(root: Path, ledger: MandosLedger | None = None) -> dict[str, Any]:
    root = root.resolve()
    ledger = ledger or MandosLedger(root)
    db_path = root / "state" / "market_command" / "market_command.sqlite"
    if not db_path.is_file():
        return {"created": [], "reused": [], "measurements": 0}
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT m.*, c.product_line_id, c.offer_id, c.audience, c.channel_id
               FROM measurements m JOIN campaigns c ON c.campaign_id=m.campaign_id
               ORDER BY m.recorded_at, m.measurement_id"""
        ).fetchall()
    except sqlite3.Error:
        con.close()
        return {"created": [], "reused": [], "measurements": 0}
    created: list[str] = []
    reused: list[str] = []
    for row in rows:
        item = dict(row)
        paid = int(item.get("paid_orders") or 0)
        qualified = int(item.get("qualified_leads") or 0)
        spend = int(item.get("spend_minor") or 0)
        polarity = "positive" if paid > 0 else "negative" if spend > 0 and qualified == 0 else "neutral"
        outcome = commercial_outcome(
            outcome_type="campaign_measurement",
            lineage={"campaign_id": item["campaign_id"]},
            source_refs=[f"market_measurement:{item['measurement_id']}"],
            source_classes=["market_measurement"],
            occurred_at=_time(item.get("recorded_at")),
            polarity=polarity,
            strategy={
                "product": item.get("product_line_id"),
                "offer": item.get("offer_id"),
                "communicative_act": "proof_led_campaign_content",
                "channel": item.get("channel_id"),
                "audience": item.get("audience"),
            },
            economics={
                "currency": "ZAR",
                "revenue_minor": int(item.get("revenue_minor") or 0),
                "cost_minor": spend,
                "manual_minutes": float(item.get("manual_minutes") or 0.0),
            },
            detail={
                key: item.get(key)
                for key in ("impressions", "reach", "clicks", "enquiries", "qualified_leads", "orders", "paid_orders")
            },
            source_states=[source_state(db_path, root)],
        )
        stored, was_created = ledger.record(outcome)
        (created if was_created else reused).append(stored["outcome_id"])
    con.close()
    return {"created": created, "reused": reused, "measurements": len(rows)}


def reconcile_all(root: Path) -> dict[str, Any]:
    root = root.resolve()
    ledger = MandosLedger(root)
    transactions = []
    for path in sorted((root / "state" / "transactions").glob("*/TRANSACTION.json")):
        transaction = _read(path)
        transactions.append(reconcile_transaction(root, transaction, ledger))
    market = reconcile_market_measurements(root, ledger)
    patterns = ledger.refresh_patterns()
    journal = ledger.verify_journal()
    receipt = {
        "schema": "dio.mandos_reconciliation_receipt.v1",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "transactions": transactions,
        "market_measurements": market,
        "pattern_count": len(patterns),
        "journal": journal,
        "authority": {
            "automatic_strategy_promotion": False,
            "automatic_execution_authority": False,
        },
    }
    output = root / "state" / "mandos" / "RECONCILIATION_RECEIPT.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
