from __future__ import annotations

import html
import json
import os
import secrets
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _money(minor: int, currency: str) -> str:
    return f"{currency} {minor / 100:,.2f}"


def _invoice_html(invoice: dict[str, Any]) -> str:
    e = lambda value: html.escape(str(value or ""), quote=True)
    seller = invoice["seller"]
    customer = invoice["customer"]
    line_rows = "".join(
        f"<tr><td>{e(item['description'])}</td><td>{item['quantity']}</td><td>{e(_money(item['unit_amount_minor'], invoice['currency']))}</td><td>{e(_money(item['subtotal_minor'], invoice['currency']))}</td></tr>"
        for item in invoice["line_items"]
    )
    tax_label = e(invoice["tax"].get("label") or "Tax")
    state_label = "INVOICE" if invoice["state"] == "issued" else "DRAFT INVOICE"
    checkout = invoice["payment"].get("checkout_url")
    checkout_html = f'<p><a class="pay" href="{e(checkout)}">Open secure checkout</a></p>' if checkout else ""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(invoice['invoice_id'])}</title>
<style>body{{margin:0;background:#eef1f3;color:#172027;font:14px/1.45 Arial,sans-serif}}.page{{width:min(900px,calc(100% - 30px));margin:30px auto;background:#fff;padding:46px;box-shadow:0 12px 42px #0002}}header{{display:flex;justify-content:space-between;gap:30px;border-bottom:3px solid #172027;padding-bottom:20px}}h1{{margin:0;font:700 34px Georgia,serif}}.muted{{color:#687780}}.meta{{text-align:right}}.cols{{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin:28px 0}}h2{{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:#687780}}table{{border-collapse:collapse;width:100%}}th,td{{padding:11px 9px;border-bottom:1px solid #dfe4e7;text-align:left}}th{{font-size:10px;text-transform:uppercase;color:#687780}}.totals{{margin:20px 0 0 auto;width:min(360px,100%)}}.totals div{{display:flex;justify-content:space-between;padding:7px 0}}.totals .grand{{border-top:2px solid #172027;font-size:18px;font-weight:800;margin-top:5px;padding-top:12px}}.pay{{display:inline-block;background:#172027;color:#fff;padding:10px 15px;text-decoration:none;border-radius:5px}}.footer{{margin-top:38px;padding-top:18px;border-top:1px solid #dfe4e7;color:#687780;font-size:11px}}.print{{position:fixed;right:20px;top:20px;padding:9px 13px}}@media print{{body{{background:#fff}}.page{{box-shadow:none;width:auto;margin:0;padding:20px}}.print{{display:none}}}}</style></head>
<body><button class="print" onclick="window.print()">Print / Save PDF</button><main class="page"><header><div><div class="muted">{e(state_label)}</div><h1>DIO Workflows</h1><div class="muted">Professional governed workflow services</div></div><div class="meta"><b>{e(invoice['invoice_id'])}</b><br>Created: {e(invoice['created_date'])}<br>Due: {e(invoice['due_date'])}<br>Status: {e(invoice['state'].upper())}</div></header>
<section class="cols"><div><h2>From</h2><b>{e(seller['display_name'])}</b><br>{e(seller['email'])}<br>{e(seller['country'])}</div><div><h2>Bill to</h2><b>{e(customer['name'])}</b><br>{e(customer.get('organisation'))}<br>{e(customer.get('email'))}<br>{e(customer.get('address'))}</div></section>
<table><thead><tr><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead><tbody>{line_rows}</tbody></table>
<div class="totals"><div><span>Subtotal</span><b>{e(_money(invoice['subtotal_minor'], invoice['currency']))}</b></div><div><span>{tax_label}</span><b>{e(_money(invoice['tax']['amount_minor'], invoice['currency']))}</b></div><div class="grand"><span>Total</span><span>{e(_money(invoice['total_minor'], invoice['currency']))}</span></div></div>
<section><h2>Payment</h2><p>Reference: <b>{e(invoice['payment'].get('order_id') or invoice['invoice_id'])}</b></p>{checkout_html}<p>{e(invoice.get('notes'))}</p></section>
<div class="footer">DIO Workflows is represented here as the trading brand recorded in DIO. Tax is included only when explicitly configured on this invoice. This document does not itself assert VAT registration or any unrecorded legal status.</div></main></body></html>"""


def create_invoice(root: Path, spec: dict[str, Any], *, issue: bool, operator: str) -> dict[str, Any]:
    required = ("customer_name", "description", "amount_minor", "currency", "due_date")
    missing = [field for field in required if not str(spec.get(field) or "").strip()]
    if missing:
        raise ValueError("Missing invoice fields: " + ", ".join(missing))
    amount_minor = int(spec.get("amount_minor") or 0)
    tax_minor = int(spec.get("tax_minor") or 0)
    quantity = int(spec.get("quantity") or 1)
    if amount_minor <= 0 or tax_minor < 0 or quantity <= 0:
        raise ValueError("Invoice amount and quantity must be positive; tax may be zero or positive")
    try:
        date.fromisoformat(str(spec["due_date"]))
    except ValueError as exc:
        raise ValueError("Invoice due_date must be YYYY-MM-DD") from exc
    invoice_id = str(spec.get("invoice_id") or f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}")
    if not invoice_id.startswith("INV-") or not all(ch.isalnum() or ch == "-" for ch in invoice_id):
        raise ValueError("Invalid invoice id")
    directory = root / "state" / "invoices" / invoice_id
    if directory.exists():
        raise ValueError("Invoice already exists")
    subtotal_minor = amount_minor * quantity
    invoice = {
        "schema": "dio.invoice.v1",
        "invoice_id": invoice_id,
        "state": "issued" if issue else "draft",
        "created_at": utc_now(),
        "created_date": datetime.now(timezone.utc).date().isoformat(),
        "issued_at": utc_now() if issue else None,
        "due_date": str(spec["due_date"]),
        "currency": str(spec.get("currency") or "ZAR").upper(),
        "seller": {
            "display_name": str(spec.get("seller_name") or "DIO Workflows"),
            "email": str(spec.get("seller_email") or "dio_workflows@outlook.com"),
            "country": str(spec.get("seller_country") or "South Africa"),
            "legal_status": "trading_brand",
        },
        "customer": {
            "name": str(spec["customer_name"]).strip(),
            "email": str(spec.get("customer_email") or "").strip(),
            "organisation": str(spec.get("customer_organisation") or "").strip(),
            "address": str(spec.get("customer_address") or "").strip(),
        },
        "line_items": [{
            "description": str(spec["description"]).strip(),
            "quantity": quantity,
            "unit_amount_minor": amount_minor,
            "subtotal_minor": subtotal_minor,
        }],
        "subtotal_minor": subtotal_minor,
        "tax": {
            "label": str(spec.get("tax_label") or "Tax not applied"),
            "amount_minor": tax_minor,
            "registration_claimed": False,
        },
        "total_minor": subtotal_minor + tax_minor,
        "payment": {
            "order_id": str(spec.get("order_id") or "").strip() or None,
            "checkout_url": str(spec.get("checkout_url") or "").strip() or None,
        },
        "lineage": {
            "lead_id": str(spec.get("lead_id") or "").strip() or None,
            "job_id": str(spec.get("job_id") or "").strip() or None,
            "order_id": str(spec.get("order_id") or "").strip() or None,
        },
        "notes": str(spec.get("notes") or "").strip(),
        "authority": {
            "operator": operator,
            "issued": issue,
            "authority_created": False,
        },
    }
    directory.mkdir(parents=True, exist_ok=False)
    invoice["json_path"] = str(directory / "INVOICE.json")
    invoice["document_path"] = str(directory / "INVOICE.html")
    _write_json(directory / "INVOICE.json", invoice)
    (directory / "INVOICE.html").write_text(_invoice_html(invoice), encoding="utf-8")
    return invoice


def load_invoice(root: Path, invoice_id: str) -> dict[str, Any]:
    if not invoice_id.startswith("INV-") or not all(ch.isalnum() or ch == "-" for ch in invoice_id):
        raise ValueError("Invalid invoice id")
    path = root / "state" / "invoices" / invoice_id / "INVOICE.json"
    if not path.is_file():
        raise ValueError("Invoice not found")
    return json.loads(path.read_text(encoding="utf-8"))


def list_invoices(root: Path) -> list[dict[str, Any]]:
    invoice_root = root / "state" / "invoices"
    if not invoice_root.exists():
        return []
    rows = []
    for path in sorted(invoice_root.glob("INV-*/INVOICE.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return rows
