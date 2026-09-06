from __future__ import annotations
import hashlib, json, os, re, secrets, sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def now() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=True)+"\n",encoding="utf-8"); tmp.replace(path)
def read_json(path: Path) -> dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))
def safe(v: str) -> str: return re.sub(r"[^A-Za-z0-9._-]+","_",v)[:120] or "unknown"

def identity_hash(channel: str, external_user_id: str) -> str:
    salt=os.getenv("DIO_PRESENCE_IDENTITY_SALT") or "DIO-PRESENCE-DEVELOPMENT-ONLY-CHANGE-ME"
    return hashlib.sha256(f"{salt}:{channel}:{external_user_id}".encode()).hexdigest()
def conversation_id(channel: str, external_user_id: str) -> str: return "CONV-"+identity_hash(channel,external_user_id)[:20].upper()

def conversation_path(root: Path, conv_id: str) -> Path: return root/"conversations"/f"{safe(conv_id)}.json"
def load_or_create_conversation(root: Path, envelope: dict[str,Any], role: str) -> dict[str,Any]:
    channel=str(envelope["channel"]); uid=str(envelope["external_user_id"]); cid=conversation_id(channel,uid); path=conversation_path(root,cid)
    if path.exists(): conv=read_json(path)
    else:
        conv={"schema":"dio.presence_conversation.v1","conversation_id":cid,"channel":channel,"external_user_ref_hash":identity_hash(channel,uid),"role":role,"display_name":envelope.get("display_name"),"created_at":now(),"updated_at":now(),"message_count":0,"last_intent":None,"last_product":None,"attribution":{"campaign_hint":None}}
    hint=((envelope.get("metadata") or {}).get("telegram_start_payload"))
    if hint and not (conv.get("attribution") or {}).get("campaign_hint"): conv.setdefault("attribution",{})["campaign_hint"]=hint
    conv["updated_at"]=now(); conv["message_count"]=int(conv.get("message_count",0))+1; write_json(path,conv); return conv

def update_conversation(root: Path, conv: dict[str,Any], intent: str, product: str|None) -> None:
    conv["last_intent"]=intent; conv["last_product"]=product; conv["updated_at"]=now(); write_json(conversation_path(root,conv["conversation_id"]),conv)

def create_needs_you(root: Path, *, reason: str, conversation_id: str, product: str|None, summary: str, priority: str="normal") -> dict[str,Any]:
    item_id="NY-"+secrets.token_hex(6).upper(); item={"schema":"dio.presence_needs_you.v1","needs_you_id":item_id,"state":"open","reason":reason,"priority":priority,"conversation_id":conversation_id,"product":product,"summary":summary[:1000],"created_at":now(),"resolved_at":None}
    write_json(root/"needs_you"/f"{item_id}.json",item); return item

def create_intake(root: Path, conv: dict[str,Any], product: str, summary: str, source_message_id: str|None=None, attachment_ids: list[str]|None=None) -> dict[str,Any]:
    intake_id="PRES-"+secrets.token_hex(7).upper(); intake={"schema":"dio.presence_intake.v2","intake_id":intake_id,"conversation_id":conv["conversation_id"],"channel":conv["channel"],"product":product,"summary":summary[:4000],"source_message_id":source_message_id,"campaign_hint":(conv.get("attribution") or {}).get("campaign_hint"),"attachment_ids":list(attachment_ids or []),"state":"pending_operator_review","created_at":now(),"authority":{"automatic_fulfilment":False,"operator_review_required":True}}
    write_json(root/"intakes"/f"{intake_id}.json",intake); return intake

def list_needs_you(root: Path, limit: int=20) -> list[dict[str,Any]]:
    items=[]
    for p in sorted((root/"needs_you").glob("*.json"), key=lambda p:p.stat().st_mtime, reverse=True) if (root/"needs_you").exists() else []:
        try:
            item=read_json(p)
            if item.get("state")=="open": items.append(item)
        except Exception: pass
        if len(items)>=limit: break
    return items

def count_json_dirs(path: Path) -> int:
    return sum(1 for p in path.glob("*/JOB.json")) if path.exists() else 0

def _iter_json_files(path: Path, pattern: str = "*.json") -> list[Path]:
    if not path.exists():
        return []
    return sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

def _nested(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def _job_state(job: dict[str, Any]) -> str:
    for keys in (
        ("state",),
        ("delivery", "state"),
        ("notification", "state"),
        ("processing", "state"),
        ("review", "state"),
        ("snapshot", "state"),
    ):
        value = _nested(job, *keys)
        if value:
            return str(value)
    return "unknown"

def _job_product(root_name: str, job: dict[str, Any]) -> str:
    if job.get("product"):
        return str(job["product"])
    if str(job.get("product_code", "")).startswith("SOPHIA"):
        return "sophia"
    if str(job.get("product_code", "")).startswith("VAMP"):
        return "vamp"
    return root_name.replace("_jobs", "")

def _summarise_jobs(dio_root: Path) -> dict[str, Any]:
    roots = ["product_jobs", "sophia_jobs", "vamp_jobs", "document_studio_jobs"]
    by_product: Counter[str] = Counter()
    by_state: Counter[str] = Counter()
    awaiting_review: list[dict[str, Any]] = []
    delivery_ready: list[dict[str, Any]] = []
    total = 0
    for root_name in roots:
        for path in _iter_json_files(dio_root / "state" / root_name, "*/JOB.json"):
            try:
                job = read_json(path)
            except Exception:
                continue
            product = _job_product(root_name, job)
            state = _job_state(job)
            total += 1
            by_product[product] += 1
            by_state[state] += 1
            review_state = str(_nested(job, "output_review", "state", default="") or _nested(job, "review", "state", default="") or _nested(job, "snapshot", "state", default=""))
            approval_state = str(_nested(job, "approval", "state", default="") or _nested(job, "output_review", "state", default=""))
            delivery_state = str(_nested(job, "delivery", "state", default="") or _nested(job, "notification", "state", default=""))
            record = {
                "job_id": str(job.get("job_id") or path.parent.name),
                "product": product,
                "state": state,
                "path": str(path.relative_to(dio_root)) if path.is_relative_to(dio_root) else str(path),
            }
            if review_state in {"ready_for_human_review", "review_ready", "pending_operator_review"} and approval_state not in {"approved", "not_required"}:
                awaiting_review.append(record)
            if delivery_state in {"draft_ready", "delivery_draft_ready"} and _nested(job, "delivery", "released", default=False) is not True:
                delivery_ready.append(record | {"mail_intent_id": _nested(job, "delivery", "mail_intent_id", default=_nested(job, "notification", "mail_intent_id"))})
    return {
        "total": total,
        "by_product": dict(sorted(by_product.items())),
        "by_state": dict(sorted(by_state.items())),
        "awaiting_review": awaiting_review[:10],
        "delivery_ready": delivery_ready[:10],
    }

def _summarise_mail(dio_root: Path) -> dict[str, Any]:
    pending: list[dict[str, Any]] = []
    by_state: Counter[str] = Counter()
    by_purpose: Counter[str] = Counter()
    for path in _iter_json_files(dio_root / "state" / "mail_intents"):
        try:
            mail = read_json(path)
        except Exception:
            continue
        state = str(mail.get("send_state") or "unknown")
        purpose = str(mail.get("purpose") or "unknown")
        by_state[state] += 1
        by_purpose[purpose] += 1
        approval_state = str(_nested(mail, "approval", "state", default=""))
        if state not in {"sent", "rejected"}:
            pending.append({
                "mail_intent_id": str(mail.get("mail_intent_id") or path.stem),
                "purpose": purpose,
                "recipient": str(mail.get("recipient") or ""),
                "subject": str(mail.get("subject") or "")[:160],
                "send_state": state,
                "approval_state": approval_state,
                "risk": str(mail.get("risk") or "unknown"),
                "path": str(path.relative_to(dio_root)) if path.is_relative_to(dio_root) else str(path),
            })
    approval_required = [x for x in pending if x.get("approval_state") not in {"approved", "consumed"}]
    return {
        "total": sum(by_state.values()),
        "pending": len(pending),
        "approval_required": len(approval_required),
        "by_state": dict(sorted(by_state.items())),
        "by_purpose": dict(by_purpose.most_common(8)),
        "top_pending": pending[:8],
    }

def _summarise_commerce(dio_root: Path) -> dict[str, Any]:
    order_paths = _iter_json_files(dio_root / "state" / "commerce" / "orders") + _iter_json_files(dio_root / "state" / "commerce" / "live" / "orders")
    seen: set[str] = set()
    orders: list[dict[str, Any]] = []
    by_state: Counter[str] = Counter()
    by_currency: Counter[str] = Counter()
    paid = live_paid = paid_unreleased = 0
    for path in order_paths:
        try:
            order = read_json(path)
        except Exception:
            continue
        oid = str(order.get("order_id") or path.stem)
        if oid in seen:
            continue
        seen.add(oid)
        state = str(order.get("payment_state") or "unknown")
        currency = str(order.get("currency") or "unknown")
        is_live = "/live/" in str(path)
        released = bool(order.get("fulfilment_released"))
        amount = int(order.get("amount_minor") or 0)
        by_state[state] += 1
        by_currency[currency] += amount
        if state in {"paid", "succeeded"}:
            paid += 1
            if is_live:
                live_paid += 1
            if not released:
                paid_unreleased += 1
        orders.append({
            "order_id": oid,
            "payment_state": state,
            "provider": str(order.get("provider") or ""),
            "amount_minor": amount,
            "currency": currency,
            "live": is_live,
            "fulfilment_released": released,
            "path": str(path.relative_to(dio_root)) if path.is_relative_to(dio_root) else str(path),
        })
    return {
        "orders": len(orders),
        "paid": paid,
        "live_paid": live_paid,
        "paid_unreleased": paid_unreleased,
        "by_state": dict(sorted(by_state.items())),
        "amount_minor_by_currency": dict(sorted(by_currency.items())),
        "top_paid_unreleased": [o for o in orders if o["payment_state"] in {"paid", "succeeded"} and not o["fulfilment_released"]][:8],
    }

def _market_scalar(cur: sqlite3.Cursor, sql: str) -> int:
    try:
        value = cur.execute(sql).fetchone()[0]
        return int(value or 0)
    except Exception:
        return 0

def _summarise_market(dio_root: Path) -> dict[str, Any]:
    db = dio_root / "state" / "market_command" / "market_command.sqlite"
    if not db.exists():
        return {"available": False, "campaigns": 0, "active": 0, "awaiting_approval": 0, "content_awaiting_approval": 0, "metrics": {}}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        metrics_row = cur.execute(
            "select coalesce(sum(impressions),0), coalesce(sum(clicks),0), coalesce(sum(enquiries),0), "
            "coalesce(sum(qualified_leads),0), coalesce(sum(orders),0), coalesce(sum(paid_orders),0), "
            "coalesce(sum(spend_minor),0), coalesce(sum(revenue_minor),0) from measurements"
        ).fetchone() or (0, 0, 0, 0, 0, 0, 0, 0)
        top = [
            {
                "campaign_id": row[0],
                "product_line_id": row[1],
                "name": row[2],
                "channel_id": row[3],
                "state": row[4],
                "approval_state": row[5],
                "publication_state": row[6],
            }
            for row in cur.execute(
                "select campaign_id, product_line_id, name, channel_id, state, approval_state, publication_state "
                "from campaigns order by updated_at desc limit 8"
            ).fetchall()
        ]
        return {
            "available": True,
            "campaigns": _market_scalar(cur, "select count(*) from campaigns"),
            "active": _market_scalar(cur, "select count(*) from campaigns where state in ('active','approved')"),
            "released": _market_scalar(cur, "select count(*) from campaigns where publication_state='released'"),
            "awaiting_approval": _market_scalar(cur, "select count(*) from campaigns where approval_state not in ('approved','rejected')"),
            "content_awaiting_approval": _market_scalar(cur, "select count(*) from content_items where approval_state not in ('approved','rejected')"),
            "metrics": {
                "impressions": int(metrics_row[0] or 0),
                "clicks": int(metrics_row[1] or 0),
                "enquiries": int(metrics_row[2] or 0),
                "qualified_leads": int(metrics_row[3] or 0),
                "orders": int(metrics_row[4] or 0),
                "paid_orders": int(metrics_row[5] or 0),
                "spend_minor": int(metrics_row[6] or 0),
                "revenue_minor": int(metrics_row[7] or 0),
            },
            "top_campaigns": top,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc), "campaigns": 0, "active": 0, "awaiting_approval": 0, "content_awaiting_approval": 0, "metrics": {}}
    finally:
        conn.close()

def _count_state_files(path: Path) -> int:
    return len(_iter_json_files(path))

def operator_summary(dio_root: Path, presence_root: Path) -> dict[str,Any]:
    jobs = _summarise_jobs(dio_root)
    mail = _summarise_mail(dio_root)
    commerce = _summarise_commerce(dio_root)
    market = _summarise_market(dio_root)
    needs = list_needs_you(presence_root, 100)
    top_actions: list[dict[str, Any]] = []
    for item in needs[:5]:
        top_actions.append({"kind": "needs_you", "entity_id": item.get("needs_you_id"), "summary": item.get("summary", "")[:180]})
    for item in jobs["delivery_ready"][:5]:
        top_actions.append({"kind": "delivery_ready", "entity_id": item.get("job_id"), "summary": f"{item.get('product')} delivery draft ready"})
    for item in commerce["top_paid_unreleased"][:5]:
        top_actions.append({"kind": "paid_unreleased", "entity_id": item.get("order_id"), "summary": f"{item.get('provider')} payment verified; fulfilment still locked"})
    for item in mail["top_pending"][:5]:
        top_actions.append({"kind": "mail_pending", "entity_id": item.get("mail_intent_id"), "summary": f"{item.get('purpose')} to {item.get('recipient')}"})
    return {
        "schema": "dio.presence.operator_brief.v1",
        "generated_at": now(),
        "jobs": jobs,
        "mail": mail,
        "commerce": commerce,
        "market": market,
        "leads": {"total": _count_state_files(dio_root / "state" / "leads")},
        "incidents": {"open_or_recorded": _count_state_files(dio_root / "state" / "incidents")},
        "needs_you": {"open": len(needs), "top": needs[:8]},
        "top_actions": top_actions[:12],
        "authority": {
            "read_only": True,
            "can_send_mail": False,
            "can_release_fulfilment": False,
            "can_publish_marketing": False,
            "can_spend_money": False,
            "can_process_attachments": False,
        },
        "legacy_counts": {
            "product_jobs": count_json_dirs(dio_root / "state" / "product_jobs"),
            "sophia_jobs": count_json_dirs(dio_root / "state" / "sophia_jobs"),
            "vamp_jobs": count_json_dirs(dio_root / "state" / "vamp_jobs"),
            "pending_mail": mail["pending"],
            "verified_paid_orders": commerce["paid"],
            "needs_you": len(needs),
        },
    }


def conversation_state_path(root: Path, conv_id: str) -> Path:
    return root / "conversation_state" / f"{safe(conv_id)}.json"


def conversation_turns_path(root: Path, conv_id: str) -> Path:
    return root / "conversation_turns" / f"{safe(conv_id)}.json"


def load_conversation_state(root: Path, conversation_id: str) -> dict[str, Any]:
    path = conversation_state_path(root, conversation_id)
    if path.is_file():
        return read_json(path)
    return {
        "schema": "dio.vesper.conversation_state.v1",
        "conversation_id": conversation_id,
        "turn_count": 0,
        "current_need": None,
        "current_topic": None,
        "candidate_products": [],
        "selected_product": None,
        "last_user_act": None,
        "last_vesper_act": None,
        "open_question": None,
        "known_constraints": [],
        "action_proposal": None,
        "last_route_intent": None,
        "updated_at": now(),
    }


def save_conversation_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    if state.get("schema") != "dio.vesper.conversation_state.v1":
        raise ValueError("unsupported Vesper conversation state schema")
    conversation_id = str(state.get("conversation_id") or "").strip()
    if not conversation_id:
        raise ValueError("conversation_id is required")
    forbidden = {"authority", "authorized", "spend_authorized", "fulfilment_released"}
    if forbidden.intersection(state):
        raise ValueError("conversation state cannot contain authority fields")
    state["updated_at"] = now()
    write_json(conversation_state_path(root, conversation_id), state)
    return state


def append_conversation_turn(
    root: Path,
    conversation_id: str,
    *,
    role: str,
    text: str,
    act: str | None = None,
    product: str | None = None,
    max_turns: int = 6,
) -> list[dict[str, Any]]:
    path = conversation_turns_path(root, conversation_id)
    rows = read_json(path).get("turns", []) if path.is_file() else []
    rows.append({
        "role": role,
        "text": str(text)[:4000],
        "act": act,
        "product": product,
        "observed_at": now(),
    })
    rows = rows[-max(1, int(max_turns)):]
    write_json(path, {
        "schema": "dio.vesper.recent_turns.v1",
        "conversation_id": conversation_id,
        "turns": rows,
    })
    return rows


def load_recent_conversation_turns(root: Path, conversation_id: str) -> list[dict[str, Any]]:
    path = conversation_turns_path(root, conversation_id)
    return list((read_json(path).get("turns") or [])) if path.is_file() else []
