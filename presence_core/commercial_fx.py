from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from typing import Any
import json


FX_SCHEMA = "dio.commercial_fx.v1"


class CommercialFXError(ValueError):
    pass


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise CommercialFXError(f"invalid {label}")

    if not result.is_finite():
        raise CommercialFXError(f"invalid {label}")

    return result


def build_fx_receipt(
    *,
    quoted_amount_minor: int,
    quoted_currency: str,
    settlement_currency: str,
    rate: str | Decimal,
    rate_source: str,
    observed_at: str,
) -> dict[str, Any]:
    if not isinstance(quoted_amount_minor, int) or quoted_amount_minor < 1:
        raise CommercialFXError("quoted amount must be positive minor units")

    quoted_currency = str(quoted_currency).upper().strip()
    settlement_currency = str(settlement_currency).upper().strip()

    if len(quoted_currency) != 3 or len(settlement_currency) != 3:
        raise CommercialFXError("currency codes must be ISO-style three-letter codes")

    if quoted_currency == settlement_currency:
        raise CommercialFXError("FX requires two different currencies")

    fx_rate = _decimal(rate, "FX rate")

    if fx_rate <= 0:
        raise CommercialFXError("FX rate must be positive")

    if not str(rate_source).strip():
        raise CommercialFXError("FX rate source required")

    if not str(observed_at).strip():
        raise CommercialFXError("FX observation time required")

    quoted_major = Decimal(quoted_amount_minor) / Decimal("100")

    settlement_minor = int(
        (quoted_major * fx_rate * Decimal("100"))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )

    if settlement_minor < 1:
        raise CommercialFXError("converted settlement amount invalid")

    body = {
        "schema": FX_SCHEMA,
        "quoted_amount_minor": quoted_amount_minor,
        "quoted_currency": quoted_currency,
        "settlement_amount_minor": settlement_minor,
        "settlement_currency": settlement_currency,
        "rate": format(fx_rate, "f"),
        "rate_basis": (
            f"1 {quoted_currency} = {format(fx_rate, 'f')} "
            f"{settlement_currency}"
        ),
        "rate_source": str(rate_source).strip(),
        "observed_at": str(observed_at).strip(),
        "rounding": "ROUND_HALF_UP_TO_MINOR_UNIT",
        "authority_created": False,
        "payment_verified": False,
        "fulfilment_released": False,
    }

    canonical = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    body["receipt_sha256"] = sha256(canonical).hexdigest()

    return body
