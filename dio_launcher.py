from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PORTFOLIO_URL = "http://127.0.0.1:8767/api/business/portfolio"

_SURFACES = [
    {
        "id": "goldeneye",
        "name": "GoldenEye",
        "kicker": "Observe",
        "description": "Sensorium and control-state truth plane.",
        "url": "http://127.0.0.1:8766/",
        "health_url": "http://127.0.0.1:8766/api/control-deck/portfolio",
        "service": "dio-goldeneye.service",
    },
    {
        "id": "control-deck",
        "name": "Control Deck",
        "kicker": "Operate",
        "description": "Business workbench, portfolio truth and operator controls.",
        "url": "http://127.0.0.1:8767/",
        "health_url": "http://127.0.0.1:8767/api/business/health",
        "service": "dio-control-deck.service",
    },
    {
        "id": "market-command",
        "name": "Market Command",
        "kicker": "Sense",
        "description": "Campaign, market and channel command surface.",
        "url": "http://127.0.0.1:8771/dashboard/market.html",
        "health_url": "http://127.0.0.1:8771/api/market/health",
        "service": "dio-market-command.service",
    },
    {
        "id": "production-studio",
        "name": "Production Studio",
        "kicker": "Create",
        "description": "Governed evidence, media and product production studio.",
        "url": "http://127.0.0.1:8767/dashboard/production.html",
        "health_url": "http://127.0.0.1:8767/api/business/health",
        "service": "dio-control-deck.service",
    },
]


def surface_catalog() -> list[dict[str, str]]:
    """Return the four user-facing DIO surfaces and their supervised services."""
    return deepcopy(_SURFACES)


def portfolio_truth(portfolio: dict[str, Any]) -> dict[str, Any]:
    """Project portfolio readiness without inventing or promoting evidence."""
    base = int(portfolio.get("base_canonical_incarnation_count") or 0)
    extensions = int(portfolio.get("canon_extension_count") or 0)
    total = int(portfolio.get("canonical_incarnation_count") or 0)
    extension_state = str(portfolio.get("extension_summary_state") or "MISSING")
    rows = portfolio.get("incarnations")
    row_count = len(rows) if isinstance(rows, list) else 0
    verified = (
        base == 53
        and extensions == 15
        and total == 68
        and row_count == 68
        and extension_state == "VERIFIED"
    )
    return {
        "verified": verified,
        "base": base,
        "extensions": extensions,
        "total": total,
        "row_count": row_count,
        "extension_state": extension_state,
        "summary": f"{base} + {extensions} = {total}",
        "expected_summary": "53 + 15 = 68",
        "evidence": "VERIFIED" if verified else extension_state,
    }


def probe_url(url: str, timeout: float = 1.0) -> dict[str, Any]:
    """Probe one localhost JSON endpoint and return a bounded readiness record."""
    request = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return {"ready": False, "status": response.status, "error": "JSON object required"}
            return {"ready": 200 <= response.status < 300, "status": response.status, "payload": payload}
    except HTTPError as exc:
        return {"ready": False, "status": exc.code, "error": str(exc)}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"ready": False, "error": str(exc)}


def launcher_state() -> dict[str, Any]:
    """Read the three services once and project readiness for all four surfaces."""
    health_cache: dict[str, dict[str, Any]] = {}
    surfaces: list[dict[str, Any]] = []
    for surface in surface_catalog():
        health_url = surface["health_url"]
        if health_url not in health_cache:
            health_cache[health_url] = probe_url(health_url)
        health = health_cache[health_url]
        row: dict[str, Any] = dict(surface)
        row["ready"] = health.get("ready") is True
        if "status" in health:
            row["status"] = health["status"]
        payload = health.get("payload")
        if isinstance(payload, dict):
            row["health"] = {
                key: payload[key]
                for key in ("ok", "status", "service", "version")
                if key in payload
            }
        if health.get("error"):
            row["error"] = str(health["error"])
        surfaces.append(row)

    portfolio_probe = probe_url(PORTFOLIO_URL)
    if portfolio_probe.get("ready") is True and isinstance(portfolio_probe.get("payload"), dict):
        portfolio = portfolio_truth(portfolio_probe["payload"])
    else:
        portfolio = portfolio_truth({})
        if portfolio_probe.get("error"):
            portfolio["error"] = str(portfolio_probe["error"])
        elif "status" in portfolio_probe:
            portfolio["error"] = f"portfolio endpoint returned HTTP {portfolio_probe['status']}"

    all_surfaces_ready = all(row["ready"] is True for row in surfaces)
    catalog = canonical_catalog_state()
    return {
        "canonical_catalog": catalog,
        "schema": "dio.local_launcher.state.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "surfaces": surfaces,
        "portfolio": portfolio,
        "surfaces_ready": all_surfaces_ready,
        "ready": all_surfaces_ready and portfolio["verified"] is True,
        "authority_created": False,
        "read_only": True,
    }



def canonical_catalog_state() -> dict[str, Any]:
    """Observe canonical identities without granting product-grade authority."""
    result = probe_url(
        "http://127.0.0.1:8768/api/canonical/portfolio"
    )

    if not result.get("ready"):
        return {
            "available": False,
            "identity_count": 0,
            "runtime_count": 0,
            "product_grade_verified": False,
            "error": result.get("error", "catalog_unavailable"),
        }

    payload = result.get("payload") or {}
    products = payload.get("products", [])

    ids = [
        row.get("product_id")
        for row in products
        if isinstance(row, dict)
    ]

    valid = (
        payload.get("schema") == "dio.canonical_portfolio_operator_view.v1"
        and payload.get("canonical_identity_count") == 68
        and len(ids) == 68
        and all(isinstance(i, str) and i for i in ids)
        and len(set(ids)) == 68
        and payload.get("identity_registry_complete") is True
        and payload.get("external_release_authorized") is False
    )

    runtime = payload.get("runtime") or {}

    return {
        "available": bool(valid),
        "identity_count": 68 if valid else 0,
        "runtime_count": runtime.get("incarnation_count", 0),
        "extension_state": runtime.get(
            "extension_summary_state", "UNKNOWN"
        ),
        "product_grade_verified": False,
        "external_release_authorized": False,
        "error": None if valid else "catalog_contract_invalid",
    }
