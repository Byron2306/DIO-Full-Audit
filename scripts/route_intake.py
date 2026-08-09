#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "routes.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(parts: list[str]) -> str:
    joined = "\n".join(part or "" for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:20]


def redact_text(value: str) -> str:
    protected: dict[str, str] = {}

    def protect(match: re.Match[str]) -> str:
        token = f"__DATE_TOKEN_{len(protected)}__"
        protected[token] = match.group(0)
        return token

    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", value or "")
    value = re.sub(
        r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\+\d{2}:\d{2}|Z)?)?\b",
        protect,
        value,
    )
    value = re.sub(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", "[phone-or-id]", value)
    for token, original in protected.items():
        value = value.replace(token, original)
    return value


def load_routes(path: Path = ROUTES_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted(payload["routes"], key=lambda item: item.get("priority", 999))


def normalize_record(raw: dict[str, Any]) -> dict[str, str]:
    subject = str(raw.get("subject") or raw.get("Subject") or "").strip()
    sender = str(raw.get("sender") or raw.get("from") or raw.get("From") or "").strip()
    body = str(raw.get("body") or raw.get("preview") or raw.get("summary") or raw.get("Body") or "").strip()
    evidence_note_path = str(raw.get("evidence_note_path") or "").strip()
    body_from_evidence_note = False
    if not body and evidence_note_path:
        note_path = Path(evidence_note_path).expanduser()
        if note_path.exists() and note_path.is_file():
            body = note_path.read_text(encoding="utf-8", errors="replace")[:4000].strip()
            body_from_evidence_note = True
    attachments = str(raw.get("attachment_names") or raw.get("attachments") or "").strip()
    message_id = str(raw.get("message_id") or raw.get("id") or stable_id([sender, subject, body])).strip()
    thread_ref = str(raw.get("thread_ref") or message_id).strip()
    source_path = str(raw.get("source_path") or raw.get("path") or "").strip()
    risk = str(raw.get("risk") or "unknown").strip().lower()
    intent = str(raw.get("intent") or "").strip()
    urgency = str(raw.get("urgency") or "").strip()
    next_step = str(raw.get("next_step") or "").strip()
    draft_status = str(raw.get("draft_status") or "").strip()

    return {
        "message_id": message_id,
        "thread_ref": thread_ref,
        "subject": subject,
        "sender": sender,
        "body": body,
        "attachment_names": attachments,
        "source_path": source_path,
        "risk": risk if risk in {"routine", "moderate", "sensitive", "formal", "unknown"} else "unknown",
        "intent": intent,
        "urgency": urgency,
        "next_step": next_step,
        "draft_status": draft_status,
        "primary_draft_path": str(raw.get("primary_draft_path") or "").strip(),
        "safer_draft_path": str(raw.get("safer_draft_path") or "").strip(),
        "shorter_draft_path": str(raw.get("shorter_draft_path") or "").strip(),
        "evidence_note_path": evidence_note_path,
        "body_from_evidence_note": "true" if body_from_evidence_note else "false",
    }


def read_input(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items", payload if isinstance(payload, list) else [])
        return [normalize_record(item) for item in items]

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [normalize_record(row) for row in csv.DictReader(handle)]

    raise ValueError(f"Unsupported input format: {path}")


def route_record(record: dict[str, str], routes: list[dict[str, Any]]) -> dict[str, Any]:
    body_for_routing = "" if record.get("body_from_evidence_note") == "true" else record["body"]
    haystack = " ".join(
        [
            record["subject"],
            record["sender"],
            body_for_routing,
            record["attachment_names"],
            record["next_step"],
        ]
    ).lower()

    best: dict[str, Any] | None = None
    best_hits: list[str] = []
    for route in routes:
        hits = [keyword for keyword in route["keywords"] if keyword_matches(keyword, haystack)]
        if hits and (best is None or len(hits) > len(best_hits)):
            best = route
            best_hits = hits

    if not best:
        return {
            "product": "unknown",
            "confidence": 0.2,
            "reason": "No configured route keywords matched.",
        }

    confidence = min(0.95, 0.55 + (0.1 * len(best_hits)))
    return {
        "product": best["product"],
        "confidence": round(confidence, 2),
        "reason": f"Matched route keywords: {', '.join(best_hits[:8])}.",
    }


def keyword_matches(keyword: str, haystack: str) -> bool:
    keyword = keyword.lower().strip()
    if not keyword:
        return False
    escaped = re.escape(keyword).replace(r"\ ", r"\s+")
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def build_job(record: dict[str, str], route: dict[str, Any], *, redact: bool = True) -> dict[str, Any]:
    evidence_id = stable_id(
        [
            record["message_id"],
            record["subject"],
            record["sender"],
            record["body"],
            record["attachment_names"],
        ]
    )
    job_id = f"{route['product']}-{evidence_id}"

    stored_subject = redact_text(record["subject"]) if redact else record["subject"]
    stored_sender = redact_text(record["sender"]) if redact else record["sender"]
    stored_body = redact_text(record["body"][:4000]) if redact else record["body"][:4000]
    stored_attachments = redact_text(record["attachment_names"]) if redact else record["attachment_names"]

    evidence = {
        "evidence_id": evidence_id,
        "source_type": "email",
        "source_path": record["source_path"],
        "title": stored_subject or "(no subject)",
        "date_observed": utc_now(),
        "text_extract": stored_body,
        "hash": stable_id([record["body"], record["attachment_names"]]),
        "claims": [],
        "mapped_to": [],
        "confidence": route["confidence"],
        "review_status": "candidate",
    }

    return {
        "job_id": job_id,
        "created_at": utc_now(),
        "client_id": "demo-or-unassigned",
        "source": {
            "kind": "outlook_triage",
            "path": record["source_path"],
            "message_id": record["message_id"],
            "thread_ref": record["thread_ref"],
        },
        "route": route,
        "status": "needs_review" if route["product"] != "unknown" else "blocked",
        "risk": record["risk"],
        "inputs": [
            {
                "kind": "email_record",
                "subject": stored_subject,
                "sender": stored_sender,
                "attachment_names": stored_attachments,
                "intent": record["intent"],
                "urgency": record["urgency"],
                "next_step": record["next_step"],
                "draft_status": record["draft_status"],
                "primary_draft_path": record["primary_draft_path"],
                "safer_draft_path": record["safer_draft_path"],
                "shorter_draft_path": record["shorter_draft_path"],
                "evidence_note_path": record["evidence_note_path"],
            }
        ],
        "evidence": [evidence],
        "outputs": [],
        "approval": {
            "required": True,
            "state": "pending",
        },
        "billing": {
            "invoice_id": None,
            "payment_status": "not_required",
        },
    }


def write_job(job: dict[str, Any], output_root: Path) -> Path:
    product_dir = output_root / job["route"]["product"]
    product_dir.mkdir(parents=True, exist_ok=True)
    path = product_dir / f"{job['job_id']}.json"
    path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Route inbox/triage records into AutoRelease job envelopes.")
    parser.add_argument("--input", required=True, help="JSON or CSV inbox/triage export.")
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest"), help="Output run folder.")
    parser.add_argument("--no-redact", action="store_true", help="Store raw email/body values instead of redacted values.")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    out_root = Path(args.out).expanduser()
    out_root.mkdir(parents=True, exist_ok=True)

    routes = load_routes()
    records = read_input(input_path)
    jobs = []
    for record in records:
        route = route_record(record, routes)
        job = build_job(record, route, redact=not args.no_redact)
        job_path = write_job(job, out_root)
        jobs.append({"job_id": job["job_id"], "product": route["product"], "path": str(job_path)})

    summary = {
        "created_at": utc_now(),
        "input": str(input_path),
        "count": len(jobs),
        "jobs": jobs,
    }
    (out_root / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Created {len(jobs)} job(s) in {out_root}")
    for job in jobs:
        print(f"- {job['product']}: {job['job_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
