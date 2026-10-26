#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.public_intake_local import materialize_public_intakes
from scripts.manage_mail_intent import DEFAULT_EVENT_LOG


MAX_PUBLIC_INTAKE_BYTES = 32_768
PUBLIC_PRODUCTS = {
    "evidex",
    "homs",
    "sophia",
    "vamp",
    "document_studio",
}
DB_PATH = ROOT / "state" / "public_edge" / "public_intake.sqlite"

app = FastAPI(
    title="DIO Phase 9 Local Public Edge",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _clean_text(
    value: Any,
    maximum: int,
    *,
    required: bool = False,
) -> str | None:
    text = str(value or "").strip()
    if required and not text:
        return None
    if len(text) > maximum:
        return None
    if any(ord(ch) < 32 and ord(ch) not in {9, 10, 13} for ch in text):
        return None
    return text


def _clean_record(value: Any, maximum_bytes: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return {}
    encoded = _canonical(value).encode("utf-8")
    if len(encoded) > maximum_bytes:
        return None
    return value


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS intake_receipts(
             request_fingerprint TEXT PRIMARY KEY,
             lead_id TEXT NOT NULL,
             response_json TEXT NOT NULL,
             created_at TEXT NOT NULL
           )"""
    )
    connection.commit()
    return connection


def _cors_headers(request: Request) -> dict[str, str]:
    allowed = os.getenv("DIO_PUBLIC_SITE_ORIGIN", "").strip().rstrip("/")
    origin = str(request.headers.get("origin") or "").strip().rstrip("/")
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if allowed and origin == allowed:
        headers.update(
            {
                "Access-Control-Allow-Origin": allowed,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "content-type",
                "Vary": "Origin",
            }
        )
    return headers


def _lead_id(product: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return (
        f"{product.upper()}-{day}-"
        + secrets.token_hex(5).upper()
    )


def _materialize(
    *,
    lead_id: str,
    envelope: dict[str, Any],
    received_at: str,
) -> None:
    created = materialize_public_intakes(
        [
            {
                "id": f"local-intake:{lead_id}",
                "source": "public_intake",
                "event_type": "public.intake.received",
                "received_at": received_at,
                "payload": {
                    "lead_id": lead_id,
                    "envelope": envelope,
                },
            }
        ],
        ROOT / "state" / "leads",
        ROOT / "state" / "mail_intents",
        DEFAULT_EVENT_LOG,
    )
    if created != 1:
        raise RuntimeError("local public intake did not materialize exactly one lead")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": "dio.phase9.local_public_edge_health.v1",
        "cloudflare_used": False,
        "durable_state": "local_sqlite_and_files",
        "automatic_processing": False,
        "payment_authority": False,
        "release_authority": False,
    }


@app.options("/api/public/intake")
async def intake_options(request: Request) -> JSONResponse:
    headers = _cors_headers(request)
    if "Access-Control-Allow-Origin" not in headers:
        raise HTTPException(403, "origin_not_allowed")
    return JSONResponse({}, status_code=204, headers=headers)


@app.post("/api/public/intake")
async def public_intake(request: Request) -> JSONResponse:
    headers = _cors_headers(request)
    allowed = os.getenv("DIO_PUBLIC_SITE_ORIGIN", "").strip().rstrip("/")
    origin = str(request.headers.get("origin") or "").strip().rstrip("/")
    if allowed and origin != allowed:
        raise HTTPException(403, "origin_not_allowed")

    declared = int(request.headers.get("content-length") or 0)
    if declared > MAX_PUBLIC_INTAKE_BYTES:
        raise HTTPException(413, "payload_too_large")
    body = await request.body()
    if len(body) > MAX_PUBLIC_INTAKE_BYTES:
        raise HTTPException(413, "payload_too_large")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "invalid_json") from exc

    if payload.get("website_honeypot"):
        return JSONResponse(
            {
                "schema": "dio.public_intake_receipt.v1",
                "state": "received",
            },
            status_code=202,
            headers=headers,
        )
    if payload.get("schema") != "dio.public_intake.v1":
        raise HTTPException(400, "invalid_intake_schema")

    product = (_clean_text(payload.get("product"), 32, required=True) or "").lower()
    offer = _clean_text(payload.get("offer"), 80, required=True)
    contact = _clean_record(payload.get("contact"), 2_048)
    intake_request = _clean_record(payload.get("request"), 16_384)
    consents = _clean_record(payload.get("consents"), 4_096)
    attribution = _clean_record(payload.get("attribution"), 4_096)
    if product not in PUBLIC_PRODUCTS:
        raise HTTPException(400, "invalid_product")
    if not offer or contact is None or intake_request is None or consents is None or attribution is None:
        raise HTTPException(400, "invalid_intake_fields")

    email = (_clean_text(contact.get("email"), 254, required=True) or "").lower()
    name = _clean_text(contact.get("name"), 160, required=True)
    organisation = _clean_text(contact.get("organisation"), 240) or ""
    if (
        not email
        or not name
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
    ):
        raise HTTPException(400, "invalid_contact")

    fingerprint_basis = {
        "product": product,
        "offer": offer,
        "email": email,
        "request": intake_request,
    }
    fingerprint = hashlib.sha256(
        _canonical(fingerprint_basis).encode("utf-8")
    ).hexdigest()

    with _connect() as connection:
        existing = connection.execute(
            "SELECT lead_id,response_json FROM intake_receipts WHERE request_fingerprint=?",
            (fingerprint,),
        ).fetchone()
        if existing is not None:
            response = json.loads(existing["response_json"])
            response["duplicate"] = True
            return JSONResponse(response, headers=headers)

    lead_id = _lead_id(product)
    received_at = _now()
    envelope = {
        "schema": "dio.public_intake.v1",
        "product": product,
        "offer": offer,
        "contact": {
            "name": name,
            "email": email,
            "organisation": organisation or None,
        },
        "request": intake_request,
        "consents": consents,
        "attribution": attribution,
        "submitted_at": _clean_text(payload.get("submitted_at"), 64) or received_at,
    }
    _materialize(
        lead_id=lead_id,
        envelope=envelope,
        received_at=received_at,
    )
    response = {
        "schema": "dio.public_intake_receipt.v1",
        "lead_id": lead_id,
        "state": "received",
        "reply_channel": "outlook",
        "message": "Your request is in the DIO review queue.",
        "cloudflare_used": False,
        "automatic_processing": False,
    }
    with _connect() as connection:
        connection.execute(
            """INSERT INTO intake_receipts(
                 request_fingerprint,lead_id,response_json,created_at
               ) VALUES(?,?,?,?)""",
            (
                fingerprint,
                lead_id,
                json.dumps(response, sort_keys=True, separators=(",", ":")),
                received_at,
            ),
        )
        connection.commit()
    return JSONResponse(response, status_code=201, headers=headers)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serve DIO public intake locally behind Caddy or a self-owned relay."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and os.getenv(
        "DIO_PHASE9_ALLOW_NONLOCAL_PUBLIC_EDGE"
    ) != "1":
        raise SystemExit(
            "Non-local public edge bind refused. Put Caddy/reverse proxy in front."
        )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
