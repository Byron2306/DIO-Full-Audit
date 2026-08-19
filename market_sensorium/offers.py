from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .core import MarketSensoriumStore, utc_now

REQUIRED = {"source_kind", "source_ref", "domain_id"}


def _normalise(row: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(key for key in REQUIRED if not str(row.get(key) or "").strip())
    if missing:
        raise ValueError(f"Observed offer missing required fields: {', '.join(missing)}")
    price = row.get("price_value")
    price_value = None if price in {None, ""} else float(price)
    return {
        "source_kind": str(row["source_kind"]),
        "source_ref": str(row["source_ref"]),
        "observed_at": str(row.get("observed_at") or utc_now()),
        "domain_id": str(row["domain_id"]),
        "seller": str(row.get("seller") or ""),
        "morphology": str(row.get("morphology") or ""),
        "headline": str(row.get("headline") or ""),
        "pitch_angle": str(row.get("pitch_angle") or ""),
        "audience": str(row.get("audience") or ""),
        "price_value": price_value,
        "price_currency": str(row.get("price_currency") or ""),
        "price_basis": str(row.get("price_basis") or ""),
        "payload": {
            **{k: v for k, v in row.items() if k not in {"price_value"}},
            "truth_class": "OBSERVED_ADVERTISED_OFFER_ONLY",
            "realised_price_claimed": False,
            "sales_claimed": False,
            "profitability_claimed": False,
            "market_demand_claimed": False,
            "authority_created": False,
        },
    }


def load_offer_rows(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("offers") or [payload]
        return [_normalise(dict(row)) for row in rows]
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [_normalise(dict(row)) for row in csv.DictReader(handle)]
    raise ValueError("Observed-offer import supports .json or .csv only.")


def import_offer_file(store: MarketSensoriumStore, path: Path) -> dict[str, Any]:
    rows = load_offer_rows(path)
    ids = [store.record_offer(**row) for row in rows]
    return {
        "schema": "dio.market_sensorium.offer_import_receipt.v1",
        "source_path": str(path),
        "observed_offer_count": len(ids),
        "offer_ids": ids,
        "truth_class": "OBSERVED_ADVERTISED_OFFER_ONLY",
        "realised_price_claimed": False,
        "sales_claimed": False,
        "profitability_claimed": False,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
