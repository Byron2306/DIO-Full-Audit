from __future__ import annotations

import json
import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_command.events import emit_event


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def token(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6).upper()}"


def jd(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


INTELLIGENCE_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS external_campaign_links (
  link_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  external_account_id TEXT,
  external_campaign_id TEXT NOT NULL,
  external_adgroup_id TEXT,
  external_ad_id TEXT,
  state TEXT NOT NULL DEFAULT 'bound',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_external_campaign_link_unique
ON external_campaign_links(channel_id, external_campaign_id, campaign_id);

CREATE TABLE IF NOT EXISTS channel_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  campaign_id TEXT,
  external_campaign_id TEXT,
  window_start TEXT,
  window_end TEXT,
  recorded_at TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'ZAR',
  impressions INTEGER NOT NULL DEFAULT 0,
  reach INTEGER NOT NULL DEFAULT 0,
  views INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0,
  conversions REAL NOT NULL DEFAULT 0,
  spend_minor INTEGER NOT NULL DEFAULT 0,
  conversion_value_minor INTEGER NOT NULL DEFAULT 0,
  source_mode TEXT NOT NULL,
  evidence_grade TEXT NOT NULL,
  raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_channel_snapshots_campaign ON channel_snapshots(campaign_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_channel_snapshots_channel ON channel_snapshots(channel_id, recorded_at);

CREATE TABLE IF NOT EXISTS attribution_events (
  attribution_id TEXT PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  campaign_id TEXT,
  channel_id TEXT,
  content_id TEXT,
  lead_id TEXT,
  order_id TEXT,
  payment_id TEXT,
  job_id TEXT,
  event_type TEXT NOT NULL,
  value_minor INTEGER NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'ZAR',
  evidence_ref TEXT,
  source TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attribution_campaign ON attribution_events(campaign_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_attribution_channel ON attribution_events(channel_id, occurred_at);

CREATE TABLE IF NOT EXISTS professional_role_bindings (
  binding_id TEXT PRIMARY KEY,
  prospect_id TEXT,
  organisation TEXT NOT NULL,
  product_line_id TEXT NOT NULL,
  buyer_unit TEXT,
  role_title TEXT NOT NULL,
  person_name TEXT,
  profile_url TEXT,
  location TEXT,
  source TEXT NOT NULL,
  source_ref TEXT,
  verified_at TEXT,
  confidence TEXT NOT NULL DEFAULT 'unverified',
  outreach_permission TEXT NOT NULL DEFAULT 'not_recorded',
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_role_binding_org ON professional_role_bindings(organisation, product_line_id);

CREATE TABLE IF NOT EXISTS channel_health (
  channel_id TEXT PRIMARY KEY,
  checked_at TEXT NOT NULL,
  state TEXT NOT NULL,
  read_authority TEXT NOT NULL,
  write_authority TEXT NOT NULL,
  detail TEXT,
  metadata_json TEXT NOT NULL
);
"""


@dataclass
class IntelligenceStore:
    db_path: Path
    event_log: Path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.executescript(INTELLIGENCE_SQL)
        snapshot_columns = {row["name"] for row in con.execute("PRAGMA table_info(channel_snapshots)")}
        if "views" not in snapshot_columns:
            con.execute("ALTER TABLE channel_snapshots ADD COLUMN views INTEGER NOT NULL DEFAULT 0")
        con.commit()
        return con

    def bind_external_campaign(self, spec: dict[str, Any]) -> dict[str, Any]:
        for key in ("campaign_id", "channel_id", "external_campaign_id"):
            if not str(spec.get(key) or "").strip():
                raise ValueError(f"Missing external link field: {key}")
        now = utc_now()
        with self.connect() as con:
            existing = con.execute(
                "SELECT link_id FROM external_campaign_links WHERE channel_id=? AND external_campaign_id=? AND campaign_id=?",
                (spec["channel_id"], str(spec["external_campaign_id"]), spec["campaign_id"]),
            ).fetchone()
            link_id = existing["link_id"] if existing else (spec.get("link_id") or token("XLINK"))
            con.execute(
                """INSERT INTO external_campaign_links(
                    link_id,campaign_id,channel_id,external_account_id,external_campaign_id,
                    external_adgroup_id,external_ad_id,state,created_at,updated_at,metadata_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(link_id) DO UPDATE SET
                    external_account_id=excluded.external_account_id,external_adgroup_id=excluded.external_adgroup_id,
                    external_ad_id=excluded.external_ad_id,state='bound',updated_at=excluded.updated_at,
                    metadata_json=excluded.metadata_json""",
                (
                    link_id, spec["campaign_id"], spec["channel_id"], spec.get("external_account_id"),
                    spec["external_campaign_id"], spec.get("external_adgroup_id"), spec.get("external_ad_id"),
                    "bound", now, now, jd(spec.get("metadata") or {}),
                ),
            )
            con.execute(
                "UPDATE channel_snapshots SET campaign_id=? WHERE channel_id=? AND external_campaign_id=?",
                (spec["campaign_id"], spec["channel_id"], str(spec["external_campaign_id"])),
            )
            con.commit()
        emit_event(self.event_log, "market.external_campaign_bound", "info", "campaign", spec["campaign_id"], {
            "channel_id": spec["channel_id"], "external_campaign_id": spec["external_campaign_id"], "link_id": link_id,
        }, spec["campaign_id"])
        return self.get_external_link(link_id)

    def get_external_link(self, link_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM external_campaign_links WHERE link_id=?", (link_id,)).fetchone()
        if not row:
            raise ValueError("External campaign link not found")
        d = dict(row)
        d["metadata"] = json.loads(d.pop("metadata_json"))
        return d

    def list_external_links(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM external_campaign_links ORDER BY created_at DESC").fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["metadata"] = json.loads(d.pop("metadata_json"))
            out.append(d)
        return out

    def record_snapshot(self, snap: dict[str, Any]) -> dict[str, Any]:
        channel_id = str(snap.get("channel_id") or "").strip()
        if not channel_id:
            raise ValueError("channel_id is required")
        source_mode = str(snap.get("source_mode") or "manual_import")
        identity = "|".join(str(value or "") for value in (channel_id, snap.get("external_campaign_id"), snap.get("window_start"), snap.get("window_end"), source_mode))
        snapshot_id = snap.get("snapshot_id")
        if not snapshot_id:
            with self.connect() as con:
                existing = con.execute(
                    """SELECT snapshot_id FROM channel_snapshots
                       WHERE channel_id=? AND COALESCE(external_campaign_id,'')=? AND COALESCE(window_start,'')=?
                         AND COALESCE(window_end,'')=? AND source_mode=? ORDER BY recorded_at DESC LIMIT 1""",
                    (channel_id, str(snap.get("external_campaign_id") or ""), str(snap.get("window_start") or ""), str(snap.get("window_end") or ""), source_mode),
                ).fetchone()
            snapshot_id = existing["snapshot_id"] if existing else "SNAP-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
        ints = {}
        for key in ("impressions", "reach", "views", "clicks", "spend_minor", "conversion_value_minor"):
            try:
                ints[key] = max(0, int(float(snap.get(key) or 0)))
            except (TypeError, ValueError):
                raise ValueError(f"Invalid numeric field: {key}")
        try:
            conversions = max(0.0, float(snap.get("conversions") or 0))
        except (TypeError, ValueError):
            raise ValueError("Invalid numeric field: conversions")
        evidence_grade = str(snap.get("evidence_grade") or ("platform_api" if source_mode == "api" else "operator_import"))
        recorded = snap.get("recorded_at") or utc_now()
        with self.connect() as con:
            con.execute(
                """INSERT INTO channel_snapshots(snapshot_id,channel_id,campaign_id,external_campaign_id,window_start,window_end,
                recorded_at,currency,impressions,reach,views,clicks,conversions,spend_minor,conversion_value_minor,source_mode,evidence_grade,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    campaign_id=excluded.campaign_id,recorded_at=excluded.recorded_at,currency=excluded.currency,
                    impressions=excluded.impressions,reach=excluded.reach,views=excluded.views,clicks=excluded.clicks,
                    conversions=excluded.conversions,spend_minor=excluded.spend_minor,
                    conversion_value_minor=excluded.conversion_value_minor,evidence_grade=excluded.evidence_grade,
                    raw_json=excluded.raw_json""",
                (
                    snapshot_id, channel_id, snap.get("campaign_id"), snap.get("external_campaign_id"), snap.get("window_start"),
                    snap.get("window_end"), recorded, snap.get("currency") or "ZAR", ints["impressions"], ints["reach"], ints["views"],
                    ints["clicks"], conversions, ints["spend_minor"], ints["conversion_value_minor"], source_mode,
                    evidence_grade, jd(snap.get("raw") if "raw" in snap else snap),
                ),
            )
            con.commit()
        emit_event(self.event_log, "market.channel_snapshot_recorded", "info", "channel", channel_id, {
            "snapshot_id": snapshot_id, "campaign_id": snap.get("campaign_id"), "spend_minor": ints["spend_minor"],
            "impressions": ints["impressions"], "views": ints["views"], "clicks": ints["clicks"], "evidence_grade": evidence_grade,
        }, snap.get("campaign_id"))
        return self.get_snapshot(snapshot_id)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM channel_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if not row:
            raise ValueError("Channel snapshot not found")
        d = dict(row)
        d["raw"] = json.loads(d.pop("raw_json"))
        return d

    def record_attribution(self, spec: dict[str, Any]) -> dict[str, Any]:
        event_type = str(spec.get("event_type") or "").strip()
        if not event_type:
            raise ValueError("event_type is required")
        if not any(spec.get(k) for k in ("campaign_id", "lead_id", "order_id", "payment_id", "job_id", "content_id")):
            raise ValueError("Attribution requires at least one causal entity reference")
        aid = spec.get("attribution_id") or token("ATTR")
        now = utc_now()
        value = max(0, int(spec.get("value_minor") or 0))
        with self.connect() as con:
            con.execute(
                """INSERT INTO attribution_events(attribution_id,occurred_at,recorded_at,campaign_id,channel_id,content_id,lead_id,
                order_id,payment_id,job_id,event_type,value_minor,currency,evidence_ref,source,metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    aid, spec.get("occurred_at") or now, now, spec.get("campaign_id"), spec.get("channel_id"), spec.get("content_id"),
                    spec.get("lead_id"), spec.get("order_id"), spec.get("payment_id"), spec.get("job_id"), event_type, value,
                    spec.get("currency") or "ZAR", spec.get("evidence_ref"), spec.get("source") or "operator", jd(spec.get("metadata") or {}),
                ),
            )
            con.commit()
        emit_event(self.event_log, "market.attribution_recorded", "info", "attribution", aid, {
            "event_type": event_type, "campaign_id": spec.get("campaign_id"), "channel_id": spec.get("channel_id"), "value_minor": value,
        }, spec.get("campaign_id"))
        return self.get_attribution(aid)

    def get_attribution(self, attribution_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM attribution_events WHERE attribution_id=?", (attribution_id,)).fetchone()
        if not row:
            raise ValueError("Attribution event not found")
        d = dict(row)
        d["metadata"] = json.loads(d.pop("metadata_json"))
        return d

    def bind_role(self, spec: dict[str, Any]) -> dict[str, Any]:
        for key in ("organisation", "product_line_id", "role_title", "source"):
            if not str(spec.get(key) or "").strip():
                raise ValueError(f"Missing professional-role field: {key}")
        permission = str(spec.get("outreach_permission") or "not_recorded")
        if permission not in {"not_recorded", "consented", "existing_customer", "withheld", "do_not_contact"}:
            raise ValueError("Unsupported outreach_permission")
        bid = spec.get("binding_id") or token("ROLE")
        now = utc_now()
        with self.connect() as con:
            con.execute(
                """INSERT INTO professional_role_bindings(binding_id,prospect_id,organisation,product_line_id,buyer_unit,role_title,person_name,
                profile_url,location,source,source_ref,verified_at,confidence,outreach_permission,notes,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    bid, spec.get("prospect_id"), spec["organisation"], spec["product_line_id"], spec.get("buyer_unit"), spec["role_title"],
                    spec.get("person_name"), spec.get("profile_url"), spec.get("location"), spec["source"], spec.get("source_ref"),
                    spec.get("verified_at"), spec.get("confidence") or "unverified", permission, spec.get("notes"), now, now,
                ),
            )
            con.commit()
        emit_event(self.event_log, "market.professional_role_bound", "info", "professional_role", bid, {
            "organisation": spec["organisation"], "product_line_id": spec["product_line_id"], "role_title": spec["role_title"],
            "confidence": spec.get("confidence") or "unverified", "outreach_permission": permission,
        })
        return self.get_role(bid)

    def get_role(self, binding_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM professional_role_bindings WHERE binding_id=?", (binding_id,)).fetchone()
        if not row:
            raise ValueError("Professional role binding not found")
        return dict(row)

    def set_channel_health(self, channel_id: str, state: str, read_authority: str, detail: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        write_authority = "blocked_by_design"
        with self.connect() as con:
            con.execute(
                """INSERT INTO channel_health(channel_id,checked_at,state,read_authority,write_authority,detail,metadata_json)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(channel_id) DO UPDATE SET checked_at=excluded.checked_at,state=excluded.state,
                read_authority=excluded.read_authority,write_authority=excluded.write_authority,detail=excluded.detail,metadata_json=excluded.metadata_json""",
                (channel_id, utc_now(), state, read_authority, write_authority, detail, jd(metadata or {})),
            )
            con.commit()
        return self.get_channel_health(channel_id)

    def get_channel_health(self, channel_id: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM channel_health WHERE channel_id=?", (channel_id,)).fetchone()
        if not row:
            return {"channel_id": channel_id, "state": "unknown", "read_authority": "unknown", "write_authority": "blocked_by_design", "detail": "Not checked"}
        d = dict(row)
        d["metadata"] = json.loads(d.pop("metadata_json"))
        return d

    def _rows(self, query: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(query, args).fetchall()
        return [dict(r) for r in rows]

    def attribution_summary(self) -> dict[str, Any]:
        rows = self._rows("""SELECT channel_id,event_type,COUNT(*) AS n,COALESCE(SUM(value_minor),0) AS value_minor
                             FROM attribution_events GROUP BY channel_id,event_type ORDER BY channel_id,event_type""")
        by_channel: dict[str, dict[str, Any]] = {}
        for r in rows:
            channel = r["channel_id"] or "UNATTRIBUTED"
            bucket = by_channel.setdefault(channel, {"events": 0, "revenue_minor": 0, "paid_orders": 0, "qualified_leads": 0})
            bucket["events"] += int(r["n"] or 0)
            if r["event_type"] in {"payment.succeeded", "paid_order"}:
                bucket["paid_orders"] += int(r["n"] or 0)
                bucket["revenue_minor"] += int(r["value_minor"] or 0)
            elif r["event_type"] in {"lead.qualified", "qualified_lead"}:
                bucket["qualified_leads"] += int(r["n"] or 0)
        return {"by_channel": by_channel, "raw": rows}

    def portfolio_scoreboard(self) -> list[dict[str, Any]]:
        rows = self._rows("""SELECT channel_id,
            COALESCE(SUM(impressions),0) impressions, COALESCE(SUM(views),0) views, COALESCE(SUM(clicks),0) clicks,
            COALESCE(SUM(spend_minor),0) spend_minor, COALESCE(SUM(conversion_value_minor),0) platform_value_minor,
            COUNT(*) snapshots
            FROM channel_snapshots GROUP BY channel_id ORDER BY spend_minor DESC""")
        attr = self.attribution_summary()["by_channel"]
        out = []
        for row in rows:
            a = attr.get(row["channel_id"], {})
            spend = int(row["spend_minor"] or 0)
            revenue = int(a.get("revenue_minor") or 0)
            qualified = int(a.get("qualified_leads") or 0)
            paid = int(a.get("paid_orders") or 0)
            clicks = int(row["clicks"] or 0)
            impressions = int(row["impressions"] or 0)
            out.append({
                **row,
                "qualified_leads": qualified,
                "paid_orders": paid,
                "verified_revenue_minor": revenue,
                "ctr": round(clicks / impressions * 100, 2) if impressions else None,
                "verified_roas": round(revenue / spend, 2) if spend else None,
                "cost_per_qualified_lead_minor": round(spend / qualified) if qualified else None,
                "cac_minor": round(spend / paid) if paid else None,
            })
        # include channels that have attribution but no platform snapshots
        seen = {r["channel_id"] for r in out}
        for channel, a in attr.items():
            if channel in seen:
                continue
            out.append({
                "channel_id": channel, "impressions": 0, "views": 0, "clicks": 0, "spend_minor": 0, "platform_value_minor": 0,
                "snapshots": 0, "qualified_leads": int(a.get("qualified_leads") or 0), "paid_orders": int(a.get("paid_orders") or 0),
                "verified_revenue_minor": int(a.get("revenue_minor") or 0), "ctr": None, "verified_roas": None,
                "cost_per_qualified_lead_minor": None, "cac_minor": None,
            })
        return sorted(out, key=lambda r: (int(r.get("verified_revenue_minor") or 0), int(r.get("qualified_leads") or 0)), reverse=True)

    def state(self) -> dict[str, Any]:
        roles = self._rows("SELECT * FROM professional_role_bindings ORDER BY created_at DESC LIMIT 200")
        links = self.list_external_links()
        snapshots = self._rows("SELECT * FROM channel_snapshots ORDER BY recorded_at DESC LIMIT 100")
        health = self._rows("SELECT * FROM channel_health ORDER BY channel_id")
        attribution = self._rows("SELECT * FROM attribution_events ORDER BY occurred_at DESC LIMIT 100")
        for row in snapshots:
            row.pop("raw_json", None)
        for row in health:
            raw = row.pop("metadata_json", "{}")
            row["metadata"] = json.loads(raw)
        for row in attribution:
            raw = row.pop("metadata_json", "{}")
            row["metadata"] = json.loads(raw)
        return {
            "schema": "dio.market_intelligence.state.v2",
            "generated_at": utc_now(),
            "external_links": links,
            "snapshots": snapshots,
            "attribution": attribution,
            "professional_roles": roles,
            "channel_health": health,
            "scoreboard": self.portfolio_scoreboard(),
            "attribution_summary": self.attribution_summary(),
        }
