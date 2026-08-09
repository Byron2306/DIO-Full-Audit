from __future__ import annotations

import json
import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from market_command.events import emit_event


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_token(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6).upper()}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  product_line_id TEXT NOT NULL,
  offer_id TEXT,
  name TEXT NOT NULL,
  audience TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  objective TEXT NOT NULL,
  landing_page TEXT,
  proof_asset TEXT,
  creative_brief TEXT,
  budget_cap_minor INTEGER NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'ZAR',
  state TEXT NOT NULL,
  approval_state TEXT NOT NULL,
  publication_state TEXT NOT NULL,
  experiment_window_days INTEGER NOT NULL DEFAULT 14,
  utm_json TEXT NOT NULL,
  governance_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
  measurement_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaigns(campaign_id),
  recorded_at TEXT NOT NULL,
  impressions INTEGER NOT NULL DEFAULT 0,
  reach INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0,
  enquiries INTEGER NOT NULL DEFAULT 0,
  qualified_leads INTEGER NOT NULL DEFAULT 0,
  orders INTEGER NOT NULL DEFAULT 0,
  paid_orders INTEGER NOT NULL DEFAULT 0,
  spend_minor INTEGER NOT NULL DEFAULT 0,
  revenue_minor INTEGER NOT NULL DEFAULT 0,
  manual_minutes REAL NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  raw_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settlements (
  settlement_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaigns(campaign_id),
  settled_at TEXT NOT NULL,
  decision TEXT NOT NULL,
  confidence TEXT NOT NULL,
  rationale TEXT NOT NULL,
  metrics_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media_buys (
  media_buy_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  product_line_id TEXT NOT NULL,
  campaign_id TEXT,
  placement TEXT NOT NULL,
  quote_minor INTEGER NOT NULL DEFAULT 0,
  approved_cap_minor INTEGER NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'ZAR',
  state TEXT NOT NULL,
  approval_state TEXT NOT NULL,
  start_date TEXT,
  end_date TEXT,
  quote_reference TEXT,
  invoice_reference TEXT,
  creative_spec TEXT,
  result_reference TEXT,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS content_items (
  content_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaigns(campaign_id),
  created_at TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  format TEXT NOT NULL,
  hook TEXT,
  body TEXT,
  asset_path TEXT,
  state TEXT NOT NULL,
  approval_state TEXT NOT NULL,
  external_url TEXT,
  source_language TEXT NOT NULL DEFAULT 'English',
  target_language TEXT,
  semantic_object_id TEXT,
  content_hash TEXT,
  language_state TEXT NOT NULL DEFAULT 'source_ready'
);
CREATE TABLE IF NOT EXISTS market_policy (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

DEFAULT_POLICY = {
    "paid_media": "hold",
    "organic_publication": "approval_required",
    "agency_spend": "hold",
    "personalised_outreach": "hold",
    "automatic_spend": "off",
}

@dataclass
class MarketStore:
    db_path: Path
    event_log: Path
    config: dict[str, Any]

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.executescript(SCHEMA_SQL)
        content_columns = {row["name"] for row in con.execute("PRAGMA table_info(content_items)")}
        additions = {
            "source_language": "TEXT NOT NULL DEFAULT 'English'",
            "target_language": "TEXT",
            "semantic_object_id": "TEXT",
            "content_hash": "TEXT",
            "language_state": "TEXT NOT NULL DEFAULT 'source_ready'",
        }
        for column, declaration in additions.items():
            if column not in content_columns:
                con.execute(f"ALTER TABLE content_items ADD COLUMN {column} {declaration}")
        for key, value in DEFAULT_POLICY.items():
            con.execute(
                "INSERT OR IGNORE INTO market_policy(key,value,updated_at) VALUES(?,?,?)",
                (key, value, utc_now()),
            )
        con.commit()
        return con

    def _dio_root(self) -> Path | None:
        if self.db_path.parent.name == "market_command" and self.db_path.parent.parent.name == "state":
            return self.db_path.parent.parent.parent
        return None

    def _content_hash(self, item: dict[str, Any]) -> str:
        value = json_dumps({
            "hook": item.get("hook") or "",
            "body": item.get("body") or "",
            "source_language": item.get("source_language") or "English",
            "target_language": item.get("target_language") or "",
            "channel_id": item.get("channel_id") or "",
            "format": item.get("format") or "post",
        })
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _register_lingua_content(
        self,
        campaign: dict[str, Any],
        content_id: str,
        item: dict[str, Any],
    ) -> str | None:
        root = self._dio_root()
        if root is None or not (root / "config" / "lingua_product_routes.json").is_file():
            return None
        units = []
        if str(item.get("hook") or "").strip():
            units.append({"unit_id": "HOOK", "unit_type": "hook", "text": str(item["hook"]).strip()})
        if str(item.get("body") or "").strip():
            units.append({"unit_id": "BODY", "unit_type": "campaign_body", "text": str(item["body"]).strip()})
        if not units:
            return None
        from adapters.lingua.lifecycle import register_product_source

        semantic_object_id = str(item.get("semantic_object_id") or f"MARKET-{campaign['campaign_id']}-{content_id}")
        register_product_source(
            state_root=root / "state" / "lingua",
            object_id=semantic_object_id,
            source_version=str(item.get("source_version") or "1.0.0"),
            source_language=str(item.get("source_language") or "English"),
            source_rows=units,
            origin={
                "product": "market",
                "artifact_type": str(item.get("artifact_type") or "campaign_copy"),
                "artifact_id": content_id,
                "campaign_id": campaign["campaign_id"],
                "product_line_id": campaign["product_line_id"],
                "audience": campaign["audience"],
                "channel": str(item.get("channel_id") or campaign["channel_id"]).casefold(),
                "proof_asset": campaign.get("proof_asset") or "",
                "cta": item.get("cta") or "",
                "privacy_domain": "public_marketing",
            },
            domain="Professional services marketing",
        )
        return semantic_object_id

    def policy(self) -> dict[str, str]:
        with self.connect() as con:
            return {row["key"]: row["value"] for row in con.execute("SELECT * FROM market_policy")}

    def set_policy(self, key: str, value: str) -> dict[str, str]:
        allowed = {
            "paid_media": {"hold", "release"},
            "organic_publication": {"hold", "approval_required", "release"},
            "agency_spend": {"hold", "release"},
            "personalised_outreach": {"hold", "release"},
            "automatic_spend": {"off"},
        }
        if key not in allowed or value not in allowed[key]:
            raise ValueError("Unsupported Market Command policy change")
        with self.connect() as con:
            con.execute("UPDATE market_policy SET value=?, updated_at=? WHERE key=?", (value, utc_now(), key))
            con.commit()
        emit_event(self.event_log, "market.policy_changed", "action", "market_policy", "DIO-MARKET", {"key": key, "value": value})
        return self.policy()

    def create_campaign(self, spec: dict[str, Any]) -> dict[str, Any]:
        required = ["product_line_id", "name", "audience", "channel_id", "objective"]
        missing = [key for key in required if not str(spec.get(key) or "").strip()]
        if missing:
            raise ValueError(f"Missing campaign fields: {', '.join(missing)}")
        campaign_id = spec.get("campaign_id") or stable_token("MKT")
        mode = spec.get("mode") or "experiment"
        budget = int(spec.get("budget_cap_minor") or 0)
        global_cap = int(self.config.get("max_experiment_budget_minor") or 0)
        if global_cap <= 0 and budget > 0:
            raise ValueError("Paid budget is globally locked. Set max_experiment_budget_minor before creating paid campaigns.")
        if global_cap > 0 and budget > global_cap:
            raise ValueError("Campaign budget exceeds DIO Market Command experiment cap.")
        utm = {
            "utm_source": spec.get("utm_source") or spec["channel_id"].lower(),
            "utm_medium": spec.get("utm_medium") or ("paid" if budget else "organic"),
            "utm_campaign": spec.get("utm_campaign") or campaign_id.lower(),
            "utm_content": spec.get("utm_content") or "proof-led",
        }
        governance = {
            "publication_requires_approval": True,
            "personalised_outreach_allowed": bool(spec.get("personalised_outreach_allowed") is True),
            "spend_requires_release": budget > 0,
            "proof_required": True,
            "operator_created": True,
            "source_lineage": spec.get("source_lineage") or {},
            "source_gates": spec.get("source_gates") or {},
        }
        now = utc_now()
        with self.connect() as con:
            con.execute(
                """INSERT INTO campaigns(campaign_id,created_at,updated_at,product_line_id,offer_id,name,audience,channel_id,mode,objective,landing_page,proof_asset,creative_brief,budget_cap_minor,currency,state,approval_state,publication_state,experiment_window_days,utm_json,governance_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (campaign_id, now, now, spec["product_line_id"], spec.get("offer_id"), spec["name"], spec["audience"], spec["channel_id"], mode, spec["objective"], spec.get("landing_page"), spec.get("proof_asset"), spec.get("creative_brief"), budget, spec.get("currency") or "ZAR", "draft", "pending", "held", int(spec.get("experiment_window_days") or self.config.get("default_experiment_window_days",14)), json_dumps(utm), json_dumps(governance)),
            )
            con.commit()
        emit_event(self.event_log, "market.campaign_created", "info", "campaign", campaign_id, {"channel_id": spec["channel_id"], "product_line_id": spec["product_line_id"], "budget_cap_minor": budget}, campaign_id)
        return self.get_campaign(campaign_id)

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM campaigns WHERE campaign_id=?", (campaign_id,)).fetchone()
        if not row:
            raise ValueError("Campaign not found")
        data = dict(row)
        data["utm"] = json.loads(data.pop("utm_json"))
        data["governance"] = json.loads(data.pop("governance_json"))
        data["tracked_url"] = self.tracked_url(data.get("landing_page"), data["utm"])
        return data

    def tracked_url(self, landing_page: str | None, utm: dict[str, str]) -> str:
        if not landing_page:
            return ""
        parts = urlsplit(landing_page)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update(utm)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    def approve_campaign(self, campaign_id: str, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Campaign approval requires explicit operator confirmation")
        with self.connect() as con:
            row = con.execute("SELECT budget_cap_minor FROM campaigns WHERE campaign_id=?", (campaign_id,)).fetchone()
            if not row:
                raise ValueError("Campaign not found")
            policy = self.policy()
            publication = "approved" if int(row["budget_cap_minor"]) == 0 else "approved_spend_held"
            con.execute("UPDATE campaigns SET approval_state='approved', publication_state=?, state='approved', updated_at=? WHERE campaign_id=?", (publication, utc_now(), campaign_id))
            con.commit()
        emit_event(self.event_log, "market.campaign_approved", "action", "campaign", campaign_id, {"publication_state": publication}, campaign_id)
        return self.get_campaign(campaign_id)

    def activate_campaign(self, campaign_id: str, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Campaign activation requires explicit operator confirmation")
        campaign = self.get_campaign(campaign_id)
        if campaign["approval_state"] != "approved":
            raise ValueError("Campaign must be approved first")
        policy = self.policy()
        if campaign["budget_cap_minor"] > 0 and policy["paid_media"] != "release":
            raise ValueError("Paid media is held by Market Command policy")
        if campaign["budget_cap_minor"] == 0 and policy["organic_publication"] == "hold":
            raise ValueError("Organic publication is held by Market Command policy")
        if self.config.get("require_approved_content_for_activation"):
            content = self.list_content(campaign_id)
            if not content:
                raise ValueError("Campaign activation requires at least one governed content item")
            unresolved = [row["content_id"] for row in content if row["approval_state"] != "approved"]
            if unresolved:
                raise ValueError("Campaign content must be approved before activation: " + ", ".join(unresolved))
        with self.connect() as con:
            con.execute("UPDATE campaigns SET publication_state='released', state='active', updated_at=? WHERE campaign_id=?", (utc_now(), campaign_id))
            con.commit()
        emit_event(self.event_log, "market.campaign_activated", "action", "campaign", campaign_id, {"channel_id": campaign["channel_id"]}, campaign_id)
        return self.get_campaign(campaign_id)

    def add_content(self, campaign_id: str, item: dict[str, Any]) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        content_id = item.get("content_id") or stable_token("CNT")
        source_language = str(item.get("source_language") or "English")
        target_language = str(item.get("target_language") or "").strip() or None
        content_hash = self._content_hash({**item, "channel_id": item.get("channel_id") or campaign["channel_id"]})
        semantic_object_id = self._register_lingua_content(campaign, content_id, item)
        language_state = "translation_required" if target_language and target_language != source_language else "source_ready"
        with self.connect() as con:
            existing = con.execute("SELECT content_hash,approval_state FROM content_items WHERE content_id=?", (content_id,)).fetchone()
            approval_state = existing["approval_state"] if existing and existing["content_hash"] == content_hash else "pending"
            con.execute("""INSERT INTO content_items(content_id,campaign_id,created_at,channel_id,format,hook,body,asset_path,state,approval_state,external_url,source_language,target_language,semantic_object_id,content_hash,language_state)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(content_id) DO UPDATE SET
                             channel_id=excluded.channel_id,format=excluded.format,hook=excluded.hook,body=excluded.body,
                             asset_path=excluded.asset_path,state=excluded.state,approval_state=excluded.approval_state,
                             external_url=excluded.external_url,source_language=excluded.source_language,
                             target_language=excluded.target_language,semantic_object_id=excluded.semantic_object_id,
                             content_hash=excluded.content_hash,language_state=excluded.language_state""",
                        (content_id,campaign_id,utc_now(),item.get("channel_id") or campaign["channel_id"],item.get("format") or "post",item.get("hook"),item.get("body"),item.get("asset_path"),"approved" if approval_state == "approved" else "draft",approval_state,item.get("external_url"),source_language,target_language,semantic_object_id,content_hash,language_state))
            con.commit()
        emit_event(self.event_log, "market.content_prepared", "info", "content", content_id, {"campaign_id": campaign_id, "semantic_object_id": semantic_object_id, "language_state": language_state}, campaign_id)
        return self.get_content(content_id)

    def get_content(self, content_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM content_items WHERE content_id=?", (content_id,)).fetchone()
        if not row:
            raise ValueError("Content item not found")
        return dict(row)

    def list_content(self, campaign_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as con:
            if campaign_id:
                rows = con.execute("SELECT * FROM content_items WHERE campaign_id=? ORDER BY created_at", (campaign_id,)).fetchall()
            else:
                rows = con.execute("SELECT * FROM content_items ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def approve_content(self, content_id: str, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Content approval requires explicit operator confirmation")
        content = self.get_content(content_id)
        if content.get("target_language") and content["target_language"] != content["source_language"]:
            root = self._dio_root()
            object_path = root / "state" / "lingua" / "objects" / f"{content['semantic_object_id']}.json" if root else None
            semantic = json.loads(object_path.read_text(encoding="utf-8")) if object_path and object_path.is_file() else {}
            lane = (semantic.get("translations") or {}).get(content["target_language"], {})
            if lane.get("status") != "human_approved_crystallized":
                raise ValueError("Target-language content requires Lingua semantic approval before campaign approval")
        with self.connect() as con:
            con.execute("UPDATE content_items SET state='approved',approval_state='approved',language_state=? WHERE content_id=?", ("semantic_approved" if content.get("target_language") else "source_ready", content_id))
            con.commit()
        emit_event(self.event_log, "market.content_approved", "action", "content", content_id, {"campaign_id": content["campaign_id"], "semantic_object_id": content.get("semantic_object_id")}, content["campaign_id"])
        return self.get_content(content_id)

    def record_measurement(self, campaign_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        self.get_campaign(campaign_id)
        mid = stable_token("MSR")
        fields = ["impressions","reach","clicks","enquiries","qualified_leads","orders","paid_orders","spend_minor","revenue_minor"]
        clean = {key: max(0, int(metrics.get(key) or 0)) for key in fields}
        manual = max(0.0, float(metrics.get("manual_minutes") or 0))
        with self.connect() as con:
            con.execute("""INSERT INTO measurements(measurement_id,campaign_id,recorded_at,impressions,reach,clicks,enquiries,qualified_leads,orders,paid_orders,spend_minor,revenue_minor,manual_minutes,source,raw_json)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (mid,campaign_id,utc_now(),clean["impressions"],clean["reach"],clean["clicks"],clean["enquiries"],clean["qualified_leads"],clean["orders"],clean["paid_orders"],clean["spend_minor"],clean["revenue_minor"],manual,metrics.get("source") or "manual_import",json_dumps(metrics)))
            con.commit()
        emit_event(self.event_log, "market.measurement_recorded", "info", "campaign", campaign_id, {**clean, "measurement_id": mid}, campaign_id)
        return {"measurement_id": mid, "campaign_id": campaign_id, **clean, "manual_minutes": manual}

    def aggregate_metrics(self, campaign_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("""SELECT COALESCE(SUM(impressions),0) impressions,COALESCE(SUM(reach),0) reach,COALESCE(SUM(clicks),0) clicks,COALESCE(SUM(enquiries),0) enquiries,COALESCE(SUM(qualified_leads),0) qualified_leads,COALESCE(SUM(orders),0) orders,COALESCE(SUM(paid_orders),0) paid_orders,COALESCE(SUM(spend_minor),0) spend_minor,COALESCE(SUM(revenue_minor),0) revenue_minor,COALESCE(SUM(manual_minutes),0) manual_minutes FROM measurements WHERE campaign_id=?""",(campaign_id,)).fetchone()
        d = dict(row)
        d["ctr"] = round((d["clicks"] / d["impressions"] * 100), 2) if d["impressions"] else None
        d["lead_conversion"] = round((d["qualified_leads"] / d["clicks"] * 100), 2) if d["clicks"] else None
        d["roas"] = round(d["revenue_minor"] / d["spend_minor"], 2) if d["spend_minor"] else None
        d["cac_minor"] = round(d["spend_minor"] / d["paid_orders"]) if d["paid_orders"] else None
        return d

    def settle_campaign(self, campaign_id: str, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Settlement requires explicit operator confirmation")
        campaign = self.get_campaign(campaign_id)
        m = self.aggregate_metrics(campaign_id)
        min_ql = int(self.config.get("promotion_min_qualified_leads", 5))
        min_paid = int(self.config.get("promotion_min_paid_orders", 2))
        min_spend = int(self.config.get("kill_min_spend_minor", 50000))
        min_clicks = int(self.config.get("revise_min_clicks", 50))
        promote_roas = float(self.config.get("promotion_min_roas", 1.5))
        decision, confidence, rationale = "continue", "low", "Insufficient evidence. Continue the bounded experiment."
        if m["paid_orders"] >= min_paid and (m["spend_minor"] == 0 or (m["roas"] or 0) >= promote_roas):
            decision, confidence, rationale = "promote", "medium", "Repeated paid conversion evidence has crossed the promotion gate."
        elif m["qualified_leads"] >= min_ql and m["paid_orders"] == 0:
            decision, confidence, rationale = "revise", "medium", "The campaign attracts qualified interest but is not converting to paid orders. Revise offer, proof, or sales handoff."
        elif m["spend_minor"] >= min_spend and m["qualified_leads"] == 0:
            decision, confidence, rationale = "kill", "medium", "The paid test crossed its minimum spend gate without a qualified lead."
        elif m["clicks"] >= min_clicks and m["enquiries"] == 0:
            decision, confidence, rationale = "revise", "medium", "Traffic exists but the landing/offer is not producing enquiries."
        sid = stable_token("SET")
        with self.connect() as con:
            con.execute("INSERT INTO settlements(settlement_id,campaign_id,settled_at,decision,confidence,rationale,metrics_json) VALUES(?,?,?,?,?,?,?)",(sid,campaign_id,utc_now(),decision,confidence,rationale,json_dumps(m)))
            con.execute("UPDATE campaigns SET state='settled', updated_at=? WHERE campaign_id=?",(utc_now(),campaign_id))
            con.commit()
        emit_event(self.event_log, f"market.campaign_{decision}", "action" if decision in {"promote","kill","revise"} else "info", "campaign", campaign_id, {"decision": decision, "confidence": confidence, "rationale": rationale, "metrics": m}, campaign_id)
        return {"settlement_id": sid, "campaign_id": campaign_id, "decision": decision, "confidence": confidence, "rationale": rationale, "metrics": m}

    def create_media_buy(self, spec: dict[str, Any]) -> dict[str, Any]:
        required = ["vendor_id","product_line_id","placement"]
        missing=[x for x in required if not str(spec.get(x) or "").strip()]
        if missing: raise ValueError(f"Missing media-buy fields: {', '.join(missing)}")
        mid=spec.get("media_buy_id") or stable_token("BUY")
        now=utc_now()
        with self.connect() as con:
            con.execute("""INSERT INTO media_buys(media_buy_id,created_at,updated_at,vendor_id,product_line_id,campaign_id,placement,quote_minor,approved_cap_minor,currency,state,approval_state,start_date,end_date,quote_reference,invoice_reference,creative_spec,result_reference,notes)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (mid,now,now,spec["vendor_id"],spec["product_line_id"],spec.get("campaign_id"),spec["placement"],int(spec.get("quote_minor") or 0),int(spec.get("approved_cap_minor") or 0),spec.get("currency") or "ZAR","quote_received" if int(spec.get("quote_minor") or 0) else "research","pending",spec.get("start_date"),spec.get("end_date"),spec.get("quote_reference"),spec.get("invoice_reference"),spec.get("creative_spec"),spec.get("result_reference"),spec.get("notes")))
            con.commit()
        emit_event(self.event_log,"market.media_buy_created","info","media_buy",mid,{"vendor_id":spec["vendor_id"],"quote_minor":int(spec.get("quote_minor") or 0)},spec.get("campaign_id"))
        return self.get_media_buy(mid)

    def get_media_buy(self, media_buy_id:str)->dict[str,Any]:
        with self.connect() as con:
            row=con.execute("SELECT * FROM media_buys WHERE media_buy_id=?",(media_buy_id,)).fetchone()
        if not row: raise ValueError("Media buy not found")
        return dict(row)

    def approve_media_buy(self, media_buy_id:str, confirmed:bool)->dict[str,Any]:
        if not confirmed: raise ValueError("Media-buy approval requires explicit operator confirmation")
        policy=self.policy()
        if policy["agency_spend"]!="release": raise ValueError("Agency/media spend is held by Market Command policy")
        buy=self.get_media_buy(media_buy_id)
        if buy["approved_cap_minor"]<=0: raise ValueError("Set an approved spend cap before approval")
        if buy["quote_minor"]>buy["approved_cap_minor"]: raise ValueError("Quote exceeds approved spend cap")
        with self.connect() as con:
            con.execute("UPDATE media_buys SET approval_state='approved',state='approved',updated_at=? WHERE media_buy_id=?",(utc_now(),media_buy_id)); con.commit()
        emit_event(self.event_log,"market.media_buy_approved","action","media_buy",media_buy_id,{"vendor_id":buy["vendor_id"],"approved_cap_minor":buy["approved_cap_minor"]},buy.get("campaign_id"))
        return self.get_media_buy(media_buy_id)

    def record_media_quote(self, media_buy_id:str, quote_minor:int, quote_reference:str, approved_cap_minor:int=0, notes:str="")->dict[str,Any]:
        if int(quote_minor) <= 0:
            raise ValueError("Agency quote must be greater than zero")
        if not str(quote_reference or "").strip():
            raise ValueError("Agency quote requires an evidence reference")
        buy=self.get_media_buy(media_buy_id)
        if buy["approval_state"]=="approved":
            raise ValueError("An approved media buy cannot be replaced with a new quote")
        with self.connect() as con:
            con.execute("UPDATE media_buys SET quote_minor=?,approved_cap_minor=?,quote_reference=?,notes=?,state='quote_received',updated_at=? WHERE media_buy_id=?",(int(quote_minor),int(approved_cap_minor or 0),str(quote_reference),str(notes or buy.get("notes") or ""),utc_now(),media_buy_id)); con.commit()
        emit_event(self.event_log,"market.media_quote_recorded","action","media_buy",media_buy_id,{"vendor_id":buy["vendor_id"],"quote_minor":int(quote_minor),"approved_cap_minor":int(approved_cap_minor or 0),"quote_reference":str(quote_reference)},buy.get("campaign_id"))
        return self.get_media_buy(media_buy_id)

    def record_media_result(self, media_buy_id:str, result_reference:str, metrics:dict[str,Any])->dict[str,Any]:
        buy=self.get_media_buy(media_buy_id)
        if buy["approval_state"]!="approved":
            raise ValueError("Provider results may only be attached to an approved media buy")
        if not str(result_reference or "").strip():
            raise ValueError("Provider result requires an evidence reference")
        allowed={"impressions","reach","clicks","enquiries","qualified_leads","orders","paid_orders","spend_minor","revenue_minor","manual_minutes"}
        clean={key:metrics[key] for key in allowed if key in metrics}
        clean.update({"source":"agency_provider_report","evidence_reference":str(result_reference),"media_buy_id":media_buy_id})
        measurement=None
        if buy.get("campaign_id"):
            measurement=self.record_measurement(buy["campaign_id"],clean)
        with self.connect() as con:
            con.execute("UPDATE media_buys SET result_reference=?,state='reported',updated_at=? WHERE media_buy_id=?",(str(result_reference),utc_now(),media_buy_id)); con.commit()
        emit_event(self.event_log,"market.media_result_recorded","info","media_buy",media_buy_id,{"vendor_id":buy["vendor_id"],"result_reference":str(result_reference),"metrics":clean},buy.get("campaign_id"))
        return {"media_buy":self.get_media_buy(media_buy_id),"measurement":measurement}

    def list_campaigns(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows=con.execute("SELECT campaign_id FROM campaigns ORDER BY created_at DESC").fetchall()
        result=[]
        for row in rows:
            campaign=self.get_campaign(row["campaign_id"])
            campaign["metrics"]=self.aggregate_metrics(row["campaign_id"])
            with self.connect() as con:
                settlement=con.execute("SELECT decision,confidence,rationale,settled_at FROM settlements WHERE campaign_id=? ORDER BY settled_at DESC LIMIT 1",(row["campaign_id"],)).fetchone()
            campaign["settlement"]=dict(settlement) if settlement else None
            result.append(campaign)
        return result

    def list_media_buys(self)->list[dict[str,Any]]:
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM media_buys ORDER BY created_at DESC")]

    def state(self, catalogs: dict[str, Any]) -> dict[str, Any]:
        campaigns=self.list_campaigns(); buys=self.list_media_buys(); policy=self.policy(); content=self.list_content()
        totals={"spend_minor":0,"revenue_minor":0,"qualified_leads":0,"paid_orders":0}
        for c in campaigns:
            for k in totals: totals[k]+=int(c["metrics"].get(k) or 0)
        attention=[]
        for c in campaigns:
            if c["approval_state"]=="pending": attention.append({"severity":"action","kind":"campaign","entity_id":c["campaign_id"],"title":c["name"],"detail":"Campaign approval required"})
            elif c["state"]=="approved" and c["publication_state"]!="released": attention.append({"severity":"action","kind":"campaign","entity_id":c["campaign_id"],"title":c["name"],"detail":"Approved campaign is still held from publication/spend"})
            if c.get("settlement") and c["settlement"]["decision"] in {"revise","kill"}: attention.append({"severity":"action","kind":"settlement","entity_id":c["campaign_id"],"title":c["name"],"detail":f"Settlement: {c['settlement']['decision']}"})
        for item in content:
            if item["approval_state"] == "pending":
                attention.append({"severity":"action","kind":"content","entity_id":item["content_id"],"title":item["format"],"detail":f"Campaign content approval required for {item['campaign_id']}"})
        for b in buys:
            if b["approval_state"]=="pending" and b["quote_minor"]>0: attention.append({"severity":"action","kind":"media_buy","entity_id":b["media_buy_id"],"title":b["vendor_id"],"detail":"External media quote awaiting approval"})
        return {"schema":"dio.market_command.state.v2","generated_at":utc_now(),"policy":policy,"campaigns":campaigns,"content_items":content,"media_buys":buys,"attention":attention,"totals":totals,"catalogs":catalogs}
