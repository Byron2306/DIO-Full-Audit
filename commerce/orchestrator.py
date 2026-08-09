from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from commerce.triune import STAGE_ORDER, assess_transaction
from scripts.manage_mail_intent import emit_event, write_json
from scripts.manage_product_workflow import bootstrap_job
from scripts.route_intake import build_job, load_routes, normalize_record, route_record, write_job


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_SENDERS = (
    "paypal.com",
    "microsoft.com",
    "accountprotection.microsoft.com",
    "emailnotifications.microsoft.com",
    "notify.cloudflare.com",
    "google.com",
    "youtube.com",
)


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def _body_text(ingress: dict[str, Any]) -> str:
    body = ingress.get("body") or {}
    value = str(body.get("content") or ingress.get("body_preview") or "")
    return re.sub(r"<[^>]+>", " ", value).replace("&nbsp;", " ").strip()


def _system_sender(address: str) -> bool:
    domain = str(address or "").lower().rsplit("@", 1)[-1]
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in SYSTEM_SENDERS)


class CommercialStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS transactions (
              transaction_id TEXT PRIMARY KEY,
              lead_id TEXT,
              conversation_id TEXT,
              product TEXT,
              stage TEXT NOT NULL,
              state_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_lead
              ON transactions(lead_id) WHERE lead_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_transactions_stage ON transactions(stage);
            CREATE TABLE IF NOT EXISTS decisions (
              decision_id TEXT PRIMARY KEY,
              transaction_id TEXT NOT NULL,
              verdict TEXT NOT NULL,
              decision_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(transaction_id) REFERENCES transactions(transaction_id)
            );
            CREATE INDEX IF NOT EXISTS idx_decisions_transaction
              ON decisions(transaction_id, created_at DESC);
            """
        )
        self.connection.commit()

    @staticmethod
    def operational_fingerprint(transaction: dict[str, Any], decision: dict[str, Any]) -> str:
        payload = {
            "stage": transaction.get("stage"),
            "lineage": transaction.get("lineage"),
            "intake_messages": (transaction.get("intake") or {}).get("message_ids"),
            "attachments": [item.get("sha256") or item.get("provider_attachment_id") for item in (transaction.get("intake") or {}).get("attachments") or []],
            "payment": transaction.get("payment"),
            "review_approved": transaction.get("review_approved"),
            "verdict": decision.get("verdict"),
            "selected_action": ((decision.get("michael") or {}).get("selected_action") or {}).get("action"),
            "loki": [(item.get("code"), item.get("severity")) for item in (decision.get("loki") or {}).get("challenges") or []],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()

    def upsert(self, transaction: dict[str, Any], decision: dict[str, Any]) -> bool:
        now = timestamp()
        existing = self.get(transaction["transaction_id"])
        before = self.operational_fingerprint(existing, existing.get("triune") or {}) if existing else None
        after = self.operational_fingerprint(transaction, decision)
        changed = before != after
        self.connection.execute(
            """INSERT INTO transactions
               (transaction_id, lead_id, conversation_id, product, stage, state_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(transaction_id) DO UPDATE SET
                 lead_id=excluded.lead_id,
                 conversation_id=excluded.conversation_id,
                 product=excluded.product,
                 stage=excluded.stage,
                 state_json=excluded.state_json,
                 updated_at=excluded.updated_at""",
            (
                transaction["transaction_id"],
                (transaction.get("lineage") or {}).get("lead_id"),
                (transaction.get("lineage") or {}).get("conversation_id"),
                transaction.get("product"),
                transaction["stage"],
                json.dumps(transaction, sort_keys=True, ensure_ascii=True),
                transaction.get("created_at") or now,
                now,
            ),
        )
        if changed:
            decision_raw = json.dumps(decision, sort_keys=True, ensure_ascii=True)
            decision_id = stable_id("DEC", transaction["transaction_id"], after)
            self.connection.execute(
                "INSERT OR IGNORE INTO decisions (decision_id, transaction_id, verdict, decision_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (decision_id, transaction["transaction_id"], decision["verdict"], decision_raw, now),
            )
        self.connection.commit()
        return changed

    def list_transactions(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT state_json FROM transactions ORDER BY updated_at DESC").fetchall()
        return [json.loads(row["state_json"]) for row in rows]

    def get(self, transaction_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT state_json FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
        return json.loads(row["state_json"]) if row else None


class CommercialOrchestrator:
    def __init__(self, root: Path = ROOT):
        self.root = root.resolve()
        self.state_root = self.root / "state"
        self.event_log = self.root / "telemetry" / "dio_events.jsonl"
        self.transaction_root = self.state_root / "transactions"
        self.store = CommercialStore(self.state_root / "commerce" / "dio_commerce.sqlite")

    def _files(self, relative: str) -> list[Path]:
        path = self.root / relative
        return sorted(path.glob("*.json")) if path.exists() else []

    def _leads(self) -> list[dict[str, Any]]:
        return [load_json(path) for path in self._files("state/leads")]

    def _mail(self) -> list[dict[str, Any]]:
        return [load_json(path) for path in self._files("state/mail_ingress")]

    def _create_mail_lead(self, ingress: dict[str, Any], product: str) -> dict[str, Any]:
        received = _parse_datetime(ingress.get("received_at") or ingress.get("captured_at"))
        day = received.strftime("%Y%m%d") if received else datetime.now(timezone.utc).strftime("%Y%m%d")
        lead_id = f"{product.upper()}-{day}-{stable_id('', ingress.get('provider_message_id') or ingress.get('mail_ingress_id')).replace('-', '')[:10]}"
        sender = ingress.get("sender") or {}
        path = self.state_root / "leads" / f"{lead_id}.json"
        if path.exists():
            return load_json(path)
        lead = {
            "schema": "dio.lead.v1",
            "lead_id": lead_id,
            "product": product,
            "offer": "mailbox_request_unscoped",
            "contact": {
                "name": sender.get("name"),
                "email": sender.get("address"),
                "organisation": None,
            },
            "request": {
                "subject": ingress.get("subject") or "(no subject)",
                "mail_ingress_id": ingress.get("mail_ingress_id"),
                "scope": "Direct mailbox request awaiting human qualification and scope confirmation.",
            },
            "consents": {
                "email_received": True,
                "processing_authority_confirmed": False,
            },
            "attribution": {"source": "outlook_direct", "medium": "email"},
            "state": "new",
            "qualification": {"state": "pending", "decided_at": None, "decided_by": None},
            "conversation_id": ingress.get("conversation_id"),
            "acknowledgement": {"mail_intent_id": None, "state": "not_prepared"},
            "created_at": ingress.get("received_at") or timestamp(),
            "updated_at": timestamp(),
            "source_mail_ingress_id": ingress.get("mail_ingress_id"),
        }
        write_json(path, lead)
        emit_event(self.event_log, "lead.created_from_mail", "action", "lead", lead_id, {
            "product": product,
            "mail_ingress_id": ingress.get("mail_ingress_id"),
            "qualification": "pending",
        }, ingress.get("conversation_id"))
        return lead

    def _mail_intents(self) -> list[dict[str, Any]]:
        return [load_json(path) for path in self._files("state/mail_intents")]

    def _orders(self) -> list[dict[str, Any]]:
        paths = sorted((self.state_root / "commerce").glob("**/orders/*.json"))
        return [dict(load_json(path), _path=str(path)) for path in paths]

    def _product_jobs(self) -> list[dict[str, Any]]:
        paths = sorted((self.state_root / "product_jobs").glob("*/JOB.json"))
        return [dict(load_json(path), _path=str(path)) for path in paths]

    def _special_jobs(self) -> list[dict[str, Any]]:
        rows = []
        for product, folder in (("sophia", "sophia_jobs"), ("vamp", "vamp_jobs")):
            for path in sorted((self.state_root / folder).glob("*/JOB.json")):
                rows.append(dict(load_json(path), product=product, _path=str(path)))
        return rows

    @staticmethod
    def _lead_indexes(leads: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        by_id = {str(lead.get("lead_id")): lead for lead in leads if lead.get("lead_id")}
        by_conversation = {str(lead.get("conversation_id")): lead for lead in leads if lead.get("conversation_id")}
        by_email = {
            str((lead.get("contact") or {}).get("email") or "").lower(): lead
            for lead in leads
            if (lead.get("contact") or {}).get("email")
        }
        return by_id, by_conversation, by_email

    def _stage_mail_job(self, ingress: dict[str, Any], lead: dict[str, Any] | None, product: str, confidence: float) -> dict[str, Any] | None:
        text = _body_text(ingress)
        attachments = ingress.get("attachments") or []
        if not text and not attachments:
            return None
        record = normalize_record({
            "message_id": ingress.get("provider_message_id") or ingress.get("mail_ingress_id"),
            "thread_ref": ingress.get("conversation_id"),
            "subject": ingress.get("subject"),
            "sender": (ingress.get("sender") or {}).get("address"),
            "body": text,
            "attachment_names": ", ".join(str(item.get("name") or "") for item in attachments),
            "source_path": str(self.state_root / "mail_ingress" / f"{ingress['mail_ingress_id']}.json"),
            "risk": "sensitive" if attachments else "moderate",
        })
        route = {"product": product, "confidence": confidence, "reason": "Bound through the canonical commercial transaction and Outlook conversation."}
        job = build_job(record, route, redact=True)
        job["source"].update({
            "lead_id": (lead or {}).get("lead_id"),
            "mail_ingress_id": ingress.get("mail_ingress_id"),
            "conversation_id": ingress.get("conversation_id"),
        })
        job["billing"].update({"payment_status": "pending"})
        run_root = self.root / "runs" / f"mailbox-auto-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        job_path = run_root / product / f"{job['job_id']}.json"
        created = not job_path.exists()
        if created:
            job_path = write_job(job, run_root)
            summary_path = run_root / "run_summary.json"
            summary = load_json(summary_path) if summary_path.exists() else {"created_at": timestamp(), "input": "microsoft_graph", "count": 0, "jobs": []}
            if not any(item.get("job_id") == job["job_id"] for item in summary["jobs"]):
                summary["jobs"].append({"job_id": job["job_id"], "product": product, "path": str(job_path)})
                summary["count"] = len(summary["jobs"])
                write_json(summary_path, summary)
            if product in {"homs", "evidex"}:
                bootstrap_job(job_path, self.state_root / "product_jobs", self.root / "runs")
            emit_event(self.event_log, "job.staged_from_mail", "action", "product_job", job["job_id"], {
                "product": product,
                "lead_id": (lead or {}).get("lead_id"),
                "mail_ingress_id": ingress.get("mail_ingress_id"),
            }, (lead or {}).get("lead_id") or ingress.get("conversation_id"))
        return {"job_id": job["job_id"], "path": str(job_path), "created": created}

    def triage_mail(self, *, stage_jobs: bool = True) -> dict[str, Any]:
        leads = self._leads()
        by_id, by_conversation, by_email = self._lead_indexes(leads)
        counts = {"system_ignored": 0, "bound": 0, "staged": 0, "needs_review": 0}
        for path in self._files("state/mail_ingress"):
            ingress = load_json(path)
            sender = str((ingress.get("sender") or {}).get("address") or "").lower()
            if _system_sender(sender):
                state, lead, reason = "system_ignored", None, "Known provider or platform notification sender."
                counts["system_ignored"] += 1
            else:
                lead = (
                    by_id.get(str(ingress.get("lead_id") or ""))
                    or by_conversation.get(str(ingress.get("conversation_id") or ""))
                    or by_email.get(sender)
                )
                if lead:
                    state, reason = "bound_to_transaction", "Matched canonical lead identity, conversation, or sender address."
                    ingress["lead_id"] = lead.get("lead_id")
                    counts["bound"] += 1
                else:
                    normalized = normalize_record({
                        "message_id": ingress.get("provider_message_id"),
                        "subject": ingress.get("subject"),
                        "sender": sender,
                        "body": _body_text(ingress),
                        "attachment_names": ", ".join(str(item.get("name") or "") for item in ingress.get("attachments") or []),
                    })
                    routed = route_record(normalized, load_routes(self.root / "config" / "routes.json"))
                    product, confidence = str(routed["product"]), float(routed["confidence"])
                    if product != "unknown" and confidence >= 0.65:
                        lead = self._create_mail_lead(ingress, product)
                        ingress["lead_id"] = lead["lead_id"]
                        state = "bound_to_transaction"
                        reason = "Confident product route created an unqualified direct-mail lead bound to this conversation."
                        counts["bound"] += 1
                    else:
                        state, reason = "needs_operator_triage", "No authoritative lead, conversation binding, or confident product route was found."
                        counts["needs_review"] += 1
            ingress["routing_state"] = state
            ingress["triage"] = {"state": state, "reason": reason, "assessed_at": timestamp(), "authority": "dio_triune_internal"}
            if state != "system_ignored" and (_body_text(ingress) or ingress.get("attachments")):
                if lead:
                    product, confidence = str(lead.get("product") or "unknown"), 0.95
                else:
                    normalized = normalize_record({
                        "message_id": ingress.get("provider_message_id"),
                        "subject": ingress.get("subject"),
                        "sender": sender,
                        "body": _body_text(ingress),
                        "attachment_names": ", ".join(str(item.get("name") or "") for item in ingress.get("attachments") or []),
                    })
                    routed = route_record(normalized, load_routes(self.root / "config" / "routes.json"))
                    product, confidence = str(routed["product"]), float(routed["confidence"])
                ingress["triage"].update({"product": product, "confidence": confidence})
                if stage_jobs and product != "unknown" and confidence >= 0.65:
                    staged = self._stage_mail_job(ingress, lead, product, confidence)
                    if staged:
                        ingress["triage"]["staged_job"] = staged
                        counts["staged"] += int(staged["created"])
            write_json(path, ingress)
        return counts

    @staticmethod
    def _stage(
        lead: dict[str, Any] | None,
        intents: list[dict[str, Any]],
        jobs: list[dict[str, Any]],
        orders: list[dict[str, Any]],
    ) -> tuple[str, float]:
        if lead and lead.get("state") == "closed":
            return "closed", 1.0
        qualification = str(((lead or {}).get("qualification") or {}).get("state") or (lead or {}).get("state") or "")
        if qualification == "rejected":
            return "blocked", 1.0
        delivery_intents = [item for item in intents if item.get("purpose") == "delivery"]
        if any(item.get("send_state") == "sent" for item in delivery_intents):
            return "delivered", 1.0
        if lead and qualification not in {"qualified", ""}:
            acknowledgement = (lead.get("acknowledgement") or {}).get("state")
            if acknowledgement in {"draft_ready", "outlook_draft_ready"}:
                return "acknowledgement_ready", 0.9
            return "qualification_pending", 0.9
        if delivery_intents:
            return "delivery_ready", 0.95
        if any((job.get("approval") or job.get("output_review") or {}).get("state") == "approved" for job in jobs):
            return "delivery_ready", 0.9
        if any((job.get("review") or job.get("snapshot") or job.get("output_review") or {}).get("state") in {"ready_for_human_review", "pending"} for job in jobs):
            return "review_required", 0.85
        if any((job.get("processing") or {}).get("state") not in {None, "not_started"} or str(job.get("state") or "") in {"processing", "review_ready", "snapshot_ready"} for job in jobs):
            return "processing", 0.85
        payment_states = {str(order.get("payment_state") or order.get("state") or "") for order in orders}
        if "paid" in payment_states:
            return "paid", 1.0
        if orders:
            return "payment_pending", 0.95
        if jobs:
            return "intake_ready", 0.85
        if qualification == "qualified":
            return "qualified", 1.0
        ack = (lead or {}).get("acknowledgement") or {}
        if ack.get("state") == "sent":
            return "qualification_pending", 0.9
        if ack.get("mail_intent_id"):
            return "acknowledgement_ready", 0.9
        return "observed", 0.7

    def _transaction_for_lead(
        self,
        lead: dict[str, Any],
        mail: list[dict[str, Any]],
        intents: list[dict[str, Any]],
        jobs: list[dict[str, Any]],
        orders: list[dict[str, Any]],
    ) -> dict[str, Any]:
        lead_id = str(lead["lead_id"])
        conversation_id = lead.get("conversation_id")
        lead_mail = [item for item in mail if item.get("lead_id") == lead_id or (conversation_id and item.get("conversation_id") == conversation_id)]
        lead_intents = [item for item in intents if item.get("lead_id") == lead_id or (conversation_id and item.get("conversation_id") == conversation_id)]
        job_ids = {
            str(((item.get("triage") or {}).get("staged_job") or {}).get("job_id"))
            for item in lead_mail
            if ((item.get("triage") or {}).get("staged_job") or {}).get("job_id")
        }
        lead_jobs = [
            item for item in jobs
            if item.get("job_id") in job_ids
            or (item.get("source") or {}).get("lead_id") == lead_id
            or str((item.get("request") or {}).get("lead_id") or "") == lead_id
        ]
        lead_order_ids = {str((item.get("payment") or {}).get("order_id")) for item in lead_jobs if (item.get("payment") or {}).get("order_id")}
        lead_orders = [
            item for item in orders
            if item.get("order_id") in lead_order_ids
            or str((item.get("metadata") or {}).get("lead_id") or "") == lead_id
            or str((item.get("metadata") or {}).get("job_id") or "") in job_ids
        ]
        stage, confidence = self._stage(lead, lead_intents, lead_jobs, lead_orders)
        attachment_rows = [attachment for item in lead_mail for attachment in (item.get("attachments") or [])]
        event_times = [lead.get("created_at"), lead.get("updated_at")]
        event_times += [item.get("received_at") or item.get("captured_at") for item in lead_mail]
        event_times += [item.get("created_at") or item.get("updated_at") for item in lead_intents]
        job_id = next((item.get("job_id") for item in lead_jobs if item.get("job_id")), None)
        order_id = next((item.get("order_id") for item in lead_orders if item.get("order_id")), None)
        payment_state = next((item.get("payment_state") or item.get("state") for item in lead_orders), "not_started")
        review_approved = any((item.get("approval") or item.get("output_review") or {}).get("state") == "approved" for item in lead_jobs)
        return {
            "schema": "dio.commercial_transaction.v1",
            "transaction_id": stable_id("TXN", lead_id),
            "created_at": lead.get("created_at") or timestamp(),
            "updated_at": timestamp(),
            "product": lead.get("product"),
            "offer": lead.get("offer"),
            "stage": stage,
            "customer": {"name": (lead.get("contact") or {}).get("name"), "email": (lead.get("contact") or {}).get("email"), "organisation": (lead.get("contact") or {}).get("organisation")},
            "lineage": {
                "campaign_id": (lead.get("attribution") or {}).get("campaign_id"),
                "lead_id": lead_id,
                "conversation_id": conversation_id,
                "job_id": job_id,
                "order_id": order_id,
                "mail_intent_ids": [item.get("mail_intent_id") for item in lead_intents],
            },
            "consents": lead.get("consents") or {},
            "attribution": lead.get("attribution") or {},
            "intake": {
                "message_ids": [item.get("mail_ingress_id") for item in lead_mail],
                "attachments": attachment_rows,
                "attachments_untrusted": any(item.get("trust_state") not in {"trusted", "approved"} for item in attachment_rows),
                "meaningful_input": bool((lead.get("request") or {}) or any(_body_text(item) for item in lead_mail) or attachment_rows),
                "sender_mismatch": any(
                    str((item.get("sender") or {}).get("address") or "").lower()
                    not in {"", str((lead.get("contact") or {}).get("email") or "").lower()}
                    for item in lead_mail
                ),
            },
            "payment": {"state": payment_state},
            "review_approved": review_approved,
            "signals": {"stage_confidence": confidence, "duplicate_messages": 0},
            "source_paths": {
                "lead": str(self.state_root / "leads" / f"{lead_id}.json"),
                "jobs": [item.get("_path") for item in lead_jobs],
                "orders": [item.get("_path") for item in lead_orders],
            },
            "event_times": [item for item in event_times if item],
        }

    def run(self, *, stage_jobs: bool = True) -> dict[str, Any]:
        triage = self.triage_mail(stage_jobs=stage_jobs)
        leads = self._leads()
        mail = self._mail()
        intents = self._mail_intents()
        jobs = self._product_jobs() + self._special_jobs()
        orders = self._orders()
        results = []
        self.transaction_root.mkdir(parents=True, exist_ok=True)
        for lead in leads:
            transaction = self._transaction_for_lead(lead, mail, intents, jobs, orders)
            decision = assess_transaction(transaction)
            transaction["triune"] = decision
            transaction["next_actions"] = (decision.get("michael") or {}).get("ranked_actions") or []
            tx_dir = self.transaction_root / transaction["transaction_id"]
            write_json(tx_dir / "TRANSACTION.json", transaction)
            write_json(tx_dir / "TRIUNE_DECISION.json", decision)
            changed = self.store.upsert(transaction, decision)
            if changed:
                emit_event(self.event_log, "commercial.triune_assessed", "action" if decision["verdict"] != "ALLOW" else "info", "commercial_transaction", transaction["transaction_id"], {
                    "stage": transaction["stage"],
                    "verdict": decision["verdict"],
                    "selected_action": ((decision.get("michael") or {}).get("selected_action") or {}).get("action"),
                    "loki_challenges": len((decision.get("loki") or {}).get("challenges") or []),
                    "harmonic_mode": (decision.get("harmonic") or {}).get("mode_recommendation"),
                }, (transaction.get("lineage") or {}).get("lead_id"))
            results.append(transaction)
        receipt = {
            "schema": "dio.commercial_orchestration_receipt.v1",
            "created_at": timestamp(),
            "triage": triage,
            "transactions": len(results),
            "stages": {stage: sum(1 for item in results if item["stage"] == stage) for stage in STAGE_ORDER},
            "decisions": {verdict: sum(1 for item in results if (item.get("triune") or {}).get("verdict") == verdict) for verdict in ("ALLOW", "ALLOW_WITH_OBLIGATIONS", "BLOCK")},
        }
        write_json(self.state_root / "commerce" / "ORCHESTRATION_RECEIPT.json", receipt)
        return receipt
