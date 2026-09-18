from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests


PAYPAL_TWO_DECIMAL_CURRENCIES = {
    "AUD", "BRL", "CAD", "CNY", "CZK", "DKK", "EUR", "HKD", "HUF",
    "ILS", "JPY", "MYR", "MXN", "TWD", "NZD", "NOK", "PHP", "PLN",
    "GBP", "SGD", "SEK", "CHF", "THB", "USD",
}

ORDER_SCHEMA = "dio.local_commerce_order_state.v2"
PAYMENT_RECEIPT_SCHEMA = "dio.local_paypal_payment_receipt.v1"


class PayPalLocalError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    os.replace(temp, path)


def _safe(value: str) -> str:
    text = str(value or "").strip()
    if (
        len(text) < 3
        or len(text) > 128
        or not all(ch.isalnum() or ch in "._:-" for ch in text)
    ):
        raise ValueError("invalid local commerce identifier")
    return text


def amount_value(amount_minor: int, currency: str) -> str:
    currency = str(currency or "").upper()
    if currency not in PAYPAL_TWO_DECIMAL_CURRENCIES:
        raise PayPalLocalError(
            f"PayPal local checkout does not support configured currency {currency}"
        )
    try:
        amount = int(amount_minor)
    except (TypeError, ValueError) as exc:
        raise PayPalLocalError("payment amount must be integer minor units") from exc
    if amount < 1:
        raise PayPalLocalError("payment amount must be positive")
    return f"{Decimal(amount) / Decimal(100):.2f}"


def value_minor(value: str, currency: str) -> int:
    if str(currency or "").upper() not in PAYPAL_TWO_DECIMAL_CURRENCIES:
        raise PayPalLocalError("unsupported PayPal currency")
    try:
        amount = Decimal(str(value)) * Decimal(100)
    except InvalidOperation as exc:
        raise PayPalLocalError("invalid PayPal amount") from exc
    if amount != amount.to_integral_value() or amount < 0:
        raise PayPalLocalError("invalid PayPal amount")
    return int(amount)


@dataclass
class PayPalLocalClient:
    client_id: str
    client_secret: str
    environment: str = "sandbox"
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "PayPalLocalClient":
        client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
        client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
        environment = os.getenv("PAYPAL_ENV", "sandbox").strip().lower()
        if not client_id or not client_secret:
            raise PayPalLocalError(
                "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are required locally"
            )
        if environment not in {"sandbox", "live"}:
            raise PayPalLocalError("PAYPAL_ENV must be sandbox or live")
        return cls(client_id, client_secret, environment)

    @property
    def base_url(self) -> str:
        return (
            "https://api-m.paypal.com"
            if self.environment == "live"
            else "https://api-m.sandbox.paypal.com"
        )

    def _access_token(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        response = requests.post(
            self.base_url + "/v1/oauth2/token",
            headers={
                "Authorization": "Basic " + base64.b64encode(raw).decode("ascii"),
                "Accept": "application/json",
            },
            data={"grant_type": "client_credentials"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise PayPalLocalError(
                f"PayPal token request failed ({response.status_code})"
            )
        token = str(response.json().get("access_token") or "")
        if not token:
            raise PayPalLocalError("PayPal token response omitted access_token")
        return token

    def _json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        response = requests.request(
            method,
            self.base_url + path,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise PayPalLocalError(
                f"PayPal {method} {path} failed ({response.status_code}): {detail}"
            )
        return response.json() if response.content else {}

    def create_order(
        self,
        *,
        order_id: str,
        amount_minor: int,
        currency: str,
        return_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        value = amount_value(amount_minor, currency)
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "invoice_id": order_id,
                    "custom_id": order_id,
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": value,
                    },
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "user_action": "PAY_NOW",
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    }
                }
            },
        }
        provider = self._json(
            "POST",
            "/v2/checkout/orders",
            payload=payload,
            request_id=(
                "dio-create-"
                + hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:48]
            ),
        )
        links = provider.get("links") or []
        approval = next(
            (
                str(row.get("href"))
                for row in links
                if row.get("rel") in {"payer-action", "approve"} and row.get("href")
            ),
            "",
        )
        if not provider.get("id") or not approval:
            raise PayPalLocalError("PayPal order omitted provider ID or approval URL")
        return {
            "provider_order_id": str(provider["id"]),
            "provider_status": str(provider.get("status") or ""),
            "approval_url": approval,
        }

    def get_order(self, provider_order_id: str) -> dict[str, Any]:
        return self._json(
            "GET",
            f"/v2/checkout/orders/{provider_order_id}",
        )

    def capture_order(self, provider_order_id: str) -> dict[str, Any]:
        return self._json(
            "POST",
            f"/v2/checkout/orders/{provider_order_id}/capture",
            payload={},
            request_id=f"dio-capture-{provider_order_id}",
        )

    def get_capture(self, capture_id: str) -> dict[str, Any]:
        return self._json(
            "GET",
            f"/v2/payments/captures/{capture_id}",
        )


class LocalCommerceStore:
    def __init__(
        self,
        order_dir: Path,
        receipt_dir: Path,
    ):
        self.order_dir = Path(order_dir)
        self.receipt_dir = Path(receipt_dir)

    def order_path(self, order_id: str) -> Path:
        return self.order_dir / f"{_safe(order_id)}.json"

    def register(
        self,
        *,
        order_id: str,
        product_code: str,
        amount_minor: int,
        currency: str,
        lineage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = self.order_path(order_id)
        if path.exists():
            raise FileExistsError(f"local DIO order already exists: {order_id}")
        order = {
            "schema": ORDER_SCHEMA,
            "order_id": _safe(order_id),
            "product_code": str(product_code or "").strip().upper(),
            "amount_minor": int(amount_minor),
            "currency": str(currency or "").strip().upper(),
            "payment_state": "awaiting_checkout",
            "provider": "paypal",
            "provider_order_id": None,
            "provider_capture_id": None,
            "approval_url": None,
            "provider_status": None,
            "lineage": dict(lineage or {}),
            "fulfilment_released": False,
            "authority_created": False,
            "external_send_authority": False,
            "created_at": _now(),
            "updated_at": _now(),
        }
        if not order["product_code"] or order["amount_minor"] < 1:
            raise ValueError("product_code and positive amount_minor are required")
        amount_value(order["amount_minor"], order["currency"])
        _atomic_json(path, order)
        return order

    def load(self, order_id: str) -> dict[str, Any]:
        path = self.order_path(order_id)
        if not path.is_file():
            raise FileNotFoundError(f"local DIO order not found: {order_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, order: dict[str, Any]) -> dict[str, Any]:
        order = dict(order)
        order["updated_at"] = _now()
        _atomic_json(self.order_path(str(order["order_id"])), order)
        return order

    def pending(self) -> list[dict[str, Any]]:
        if not self.order_dir.is_dir():
            return []
        rows = []
        for path in sorted(self.order_dir.glob("*.json")):
            try:
                order = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if (
                order.get("provider") == "paypal"
                and order.get("payment_state")
                not in {"paid", "refunded", "reversed", "cancelled"}
            ):
                rows.append(order)
        return rows

    def receipt(
        self,
        order: dict[str, Any],
        *,
        provider_order: dict[str, Any],
        capture: dict[str, Any],
    ) -> dict[str, Any]:
        provider_order_id = str(provider_order.get("id") or "")
        capture_id = str(capture.get("id") or "")
        basis = {
            "schema": PAYMENT_RECEIPT_SCHEMA,
            "order_id": order["order_id"],
            "provider": "paypal",
            "provider_order_id": provider_order_id,
            "provider_capture_id": capture_id,
            "amount_minor": order["amount_minor"],
            "currency": order["currency"],
            "provider_order_status": provider_order.get("status"),
            "provider_capture_status": capture.get("status"),
            "verified_at": _now(),
            "external_funds_moved": True,
            "fulfilment_released": False,
            "authority_created": False,
        }
        basis["receipt_sha256"] = hashlib.sha256(
            json.dumps(
                basis,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        path = self.receipt_dir / f"{basis['receipt_sha256']}.json"
        _atomic_json(path, basis)
        return basis


def _purchase_unit(order: dict[str, Any]) -> dict[str, Any]:
    units = order.get("purchase_units") or []
    if len(units) != 1 or not isinstance(units[0], dict):
        raise PayPalLocalError("PayPal order must contain exactly one purchase unit")
    return units[0]


def verify_provider_order(
    local: dict[str, Any],
    provider: dict[str, Any],
) -> None:
    unit = _purchase_unit(provider)
    if str(unit.get("custom_id") or "") != str(local["order_id"]):
        raise PayPalLocalError("PayPal custom_id does not match DIO order")
    if str(unit.get("invoice_id") or "") != str(local["order_id"]):
        raise PayPalLocalError("PayPal invoice_id does not match DIO order")
    amount = unit.get("amount") or {}
    if str(amount.get("currency_code") or "").upper() != str(local["currency"]):
        raise PayPalLocalError("PayPal currency does not match DIO order")
    if value_minor(str(amount.get("value") or ""), str(local["currency"])) != int(
        local["amount_minor"]
    ):
        raise PayPalLocalError("PayPal amount does not match DIO order")


def completed_capture(provider_order: dict[str, Any]) -> dict[str, Any] | None:
    captures = (
        ((_purchase_unit(provider_order).get("payments") or {}).get("captures"))
        or []
    )
    for capture in captures:
        if str(capture.get("status") or "").upper() == "COMPLETED":
            return dict(capture)
    return None


def verify_capture(
    local: dict[str, Any],
    capture: dict[str, Any],
) -> None:
    if str(capture.get("status") or "").upper() != "COMPLETED":
        raise PayPalLocalError("PayPal capture is not COMPLETED")
    amount = capture.get("amount") or {}
    if str(amount.get("currency_code") or "").upper() != str(local["currency"]):
        raise PayPalLocalError("PayPal capture currency mismatch")
    if value_minor(str(amount.get("value") or ""), str(local["currency"])) != int(
        local["amount_minor"]
    ):
        raise PayPalLocalError("PayPal capture amount mismatch")


def reconcile_local_paypal_order(
    store: LocalCommerceStore,
    client: PayPalLocalClient,
    order_id: str,
    *,
    capture_approved: bool = False,
) -> dict[str, Any]:
    """Reconcile one DIO order from PayPal provider truth by outbound polling.

    Browser return URLs are never settlement evidence. A payment becomes paid
    only after DIO independently reads a completed provider capture with exact
    invoice/custom identity, amount and currency.
    """

    local = store.load(order_id)
    provider_order_id = str(local.get("provider_order_id") or "").strip()
    if not provider_order_id:
        raise PayPalLocalError("DIO order has no provider_order_id to reconcile")

    provider_order = client.get_order(provider_order_id)
    verify_provider_order(local, provider_order)
    provider_status = str(provider_order.get("status") or "").upper()

    capture = completed_capture(provider_order)
    capture_attempted = False

    if (
        capture is None
        and provider_status == "APPROVED"
        and capture_approved
    ):
        provider_order = client.capture_order(provider_order_id)
        capture_attempted = True
        verify_provider_order(local, provider_order)
        provider_status = str(provider_order.get("status") or "").upper()
        capture = completed_capture(provider_order)

    local["provider_status"] = provider_status
    local["cloudflare_used"] = False
    local["webhook_required_for_reconciliation"] = False
    local["browser_return_authority"] = False
    local["authority_created"] = False
    local["external_send_authority"] = False

    receipt = None

    if capture is not None:
        capture_id = str(capture.get("id") or "")
        if not capture_id:
            raise PayPalLocalError("completed PayPal capture omitted capture id")
        capture_detail = client.get_capture(capture_id)
        capture_status = str(capture_detail.get("status") or "").upper()
        local["provider_capture_id"] = capture_id
        local["provider_capture_status"] = capture_status

        if capture_status == "COMPLETED":
            verify_capture(local, capture_detail)
            already_paid = (
                local.get("payment_state") == "paid"
                and str(local.get("provider_capture_id") or "") == capture_id
                and bool(local.get("payment_receipt_sha256"))
            )
            local["payment_state"] = "paid"
            local["external_funds_moved"] = True
            local["fulfilment_released"] = False
            if not already_paid:
                receipt = store.receipt(
                    local,
                    provider_order=provider_order,
                    capture=capture_detail,
                )
                local["payment_receipt_sha256"] = receipt["receipt_sha256"]

        elif capture_status in {"REFUNDED"}:
            local["payment_state"] = "refunded"
            local["external_funds_moved"] = False
            local["fulfilment_released"] = False

        elif capture_status in {"PARTIALLY_REFUNDED"}:
            local["payment_state"] = "held"
            local["external_funds_moved"] = True
            local["fulfilment_released"] = False

        else:
            local["payment_state"] = "held"
            local["external_funds_moved"] = False
            local["fulfilment_released"] = False

    elif provider_status == "APPROVED":
        local["payment_state"] = "approved_awaiting_capture"
        local["external_funds_moved"] = False
    elif provider_status in {"CREATED", "PAYER_ACTION_REQUIRED", "SAVED"}:
        local["payment_state"] = "awaiting_payment"
        local["external_funds_moved"] = False
    elif provider_status in {"VOIDED"}:
        local["payment_state"] = "cancelled"
        local["external_funds_moved"] = False
    else:
        local["payment_state"] = "held"
        local["external_funds_moved"] = False

    store.save(local)

    return {
        "schema": "dio.local_paypal_reconciliation.v1",
        "order_id": local["order_id"],
        "provider_order_id": provider_order_id,
        "provider_status": provider_status,
        "provider_capture_id": local.get("provider_capture_id"),
        "provider_capture_status": local.get("provider_capture_status"),
        "payment_state": local["payment_state"],
        "capture_attempted": capture_attempted,
        "capture_requires_explicit_flag": not capture_approved,
        "payment_receipt_sha256": local.get("payment_receipt_sha256"),
        "external_funds_moved": bool(local.get("external_funds_moved")),
        "fulfilment_released": False,
        "browser_return_authority": False,
        "cloudflare_used": False,
        "webhook_required": False,
        "authority_created": False,
    }
